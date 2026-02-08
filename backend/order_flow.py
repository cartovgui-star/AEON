"""
Order Flow Analysis Module
- Cumulative Volume Delta (CVD)
- Buy/Sell Pressure
- Delta Divergence
- Absorption Detection
"""
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class OrderFlowAnalyzer:
    """
    Analyzes order flow data from Binance
    - CVD (Cumulative Volume Delta) = Buy Volume - Sell Volume
    - Positive CVD = More buying pressure
    - Negative CVD = More selling pressure
    - CVD Divergence = Price and CVD moving opposite directions (reversal signal)
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 30  # 30 second cache for real-time data
        
        # Symbol mapping for Binance Futures
        self.symbol_map = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "SOL": "SOLUSDT",
            "BNB": "BNBUSDT",
            "XRP": "XRPUSDT",
            "DOGE": "DOGEUSDT",
            "ADA": "ADAUSDT",
            "AVAX": "AVAXUSDT",
            "DOT": "DOTUSDT",
            "LINK": "LINKUSDT",
            "MATIC": "MATICUSDT",
            "SHIB": "SHIBUSDT",
            "LTC": "LTCUSDT",
            "TRX": "TRXUSDT",
            "ATOM": "ATOMUSDT",
        }
    
    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None
    
    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())
    
    def _get_binance_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format"""
        base = symbol.upper().replace("/USDT", "").replace("USDT", "")
        return self.symbol_map.get(base, f"{base}USDT")
    
    async def get_recent_trades(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """Fetch recent trades from Binance Futures"""
        cache_key = f"trades_{symbol}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            url = f"https://fapi.binance.com/fapi/v1/trades"
            params = {"symbol": binance_symbol, "limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        trades = await resp.json()
                        self._cache_set(cache_key, trades)
                        return trades
                    elif resp.status == 451:
                        # Geo-restricted, try spot
                        return await self._get_spot_trades(symbol, limit)
                    else:
                        logger.warning(f"Binance trades API returned {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    async def _get_spot_trades(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """Fallback to Binance Spot trades"""
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            url = f"https://api.binance.com/api/v3/trades"
            params = {"symbol": binance_symbol, "limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return []
        except Exception as e:
            logger.error(f"Spot trades error: {e}")
            return []
    
    async def get_aggregated_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """Fetch aggregated trades (more efficient)"""
        cache_key = f"agg_trades_{symbol}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            url = f"https://fapi.binance.com/fapi/v1/aggTrades"
            params = {"symbol": binance_symbol, "limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        trades = await resp.json()
                        self._cache_set(cache_key, trades)
                        return trades
                    elif resp.status == 451:
                        # Geo-restricted, use spot
                        url = f"https://api.binance.com/api/v3/aggTrades"
                        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                            if resp2.status == 200:
                                trades = await resp2.json()
                                self._cache_set(cache_key, trades)
                                return trades
                    return []
        except Exception as e:
            logger.error(f"Aggregated trades error: {e}")
            return []
    
    async def calculate_cvd(self, symbol: str) -> Dict:
        """
        Calculate Cumulative Volume Delta
        
        CVD = Sum of (Buy Volume - Sell Volume)
        - Buyer initiated = Trade at ask price (market buy)
        - Seller initiated = Trade at bid price (market sell)
        """
        trades = await self.get_aggregated_trades(symbol, 500)
        
        if not trades:
            return {
                "symbol": symbol,
                "cvd": 0,
                "buy_volume": 0,
                "sell_volume": 0,
                "error": "No trade data available"
            }
        
        buy_volume = 0
        sell_volume = 0
        cvd_values = []
        running_cvd = 0
        
        for trade in trades:
            qty = float(trade.get("q", 0))
            price = float(trade.get("p", 0))
            is_buyer_maker = trade.get("m", False)
            
            volume_usd = qty * price
            
            if is_buyer_maker:
                # Buyer is maker = Seller initiated (market sell)
                sell_volume += volume_usd
                running_cvd -= volume_usd
            else:
                # Seller is maker = Buyer initiated (market buy)
                buy_volume += volume_usd
                running_cvd += volume_usd
            
            cvd_values.append(running_cvd)
        
        total_volume = buy_volume + sell_volume
        buy_pct = (buy_volume / total_volume * 100) if total_volume > 0 else 50
        
        # Determine bias
        if buy_pct > 55:
            bias = "BULLISH"
            signal = "Strong buying pressure - buyers in control"
        elif buy_pct > 52:
            bias = "SLIGHT_BULLISH"
            signal = "Slight buying pressure"
        elif buy_pct < 45:
            bias = "BEARISH"
            signal = "Strong selling pressure - sellers in control"
        elif buy_pct < 48:
            bias = "SLIGHT_BEARISH"
            signal = "Slight selling pressure"
        else:
            bias = "NEUTRAL"
            signal = "Balanced order flow"
        
        # Calculate CVD trend (is it rising or falling?)
        if len(cvd_values) > 10:
            recent_cvd = cvd_values[-10:]
            cvd_change = recent_cvd[-1] - recent_cvd[0]
            cvd_trend = "RISING" if cvd_change > 0 else "FALLING"
        else:
            cvd_trend = "UNKNOWN"
        
        return {
            "symbol": symbol,
            "cvd": round(running_cvd, 2),
            "cvd_trend": cvd_trend,
            "buy_volume": round(buy_volume, 2),
            "sell_volume": round(sell_volume, 2),
            "total_volume": round(total_volume, 2),
            "buy_pct": round(buy_pct, 1),
            "sell_pct": round(100 - buy_pct, 1),
            "bias": bias,
            "signal": signal,
            "trade_count": len(trades),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def detect_cvd_divergence(self, symbol: str, price_data: List[float] = None) -> Dict:
        """
        Detect CVD Divergence
        
        Bullish Divergence: Price making lower lows, CVD making higher lows
        Bearish Divergence: Price making higher highs, CVD making lower highs
        """
        cvd_result = await self.calculate_cvd(symbol)
        
        if "error" in cvd_result:
            return {
                "symbol": symbol,
                "has_divergence": False,
                "error": cvd_result.get("error")
            }
        
        # For divergence detection, we need historical CVD
        # This is a simplified version based on current CVD trend vs price trend
        cvd_trend = cvd_result.get("cvd_trend")
        
        # Simplified divergence detection
        divergence = None
        if cvd_trend == "RISING" and cvd_result.get("bias") in ["BEARISH", "SLIGHT_BEARISH"]:
            divergence = {
                "type": "BULLISH_CVD_DIVERGENCE",
                "signal": "BUY",
                "description": "CVD rising despite selling pressure - hidden buying accumulation"
            }
        elif cvd_trend == "FALLING" and cvd_result.get("bias") in ["BULLISH", "SLIGHT_BULLISH"]:
            divergence = {
                "type": "BEARISH_CVD_DIVERGENCE",
                "signal": "SELL",
                "description": "CVD falling despite buying pressure - hidden selling distribution"
            }
        
        return {
            "symbol": symbol,
            "has_divergence": divergence is not None,
            "divergence": divergence,
            "cvd": cvd_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def detect_absorption(self, symbol: str) -> Dict:
        """
        Detect absorption (large orders being absorbed)
        
        Bullish Absorption: Large sell orders absorbed, price doesn't drop much
        Bearish Absorption: Large buy orders absorbed, price doesn't rise much
        """
        trades = await self.get_aggregated_trades(symbol, 500)
        
        if not trades or len(trades) < 100:
            return {"symbol": symbol, "error": "Insufficient trade data"}
        
        # Calculate average trade size
        trade_sizes = [float(t.get("q", 0)) * float(t.get("p", 0)) for t in trades]
        avg_size = sum(trade_sizes) / len(trade_sizes)
        large_threshold = avg_size * 5  # 5x average = large order
        
        large_buys = []
        large_sells = []
        
        for trade in trades:
            qty = float(trade.get("q", 0))
            price = float(trade.get("p", 0))
            size = qty * price
            is_buyer_maker = trade.get("m", False)
            
            if size > large_threshold:
                if is_buyer_maker:
                    large_sells.append({"size": size, "price": price})
                else:
                    large_buys.append({"size": size, "price": price})
        
        # Check for absorption
        absorption = None
        
        if large_sells and len(large_sells) > len(large_buys):
            # Large sells but price stable = bullish absorption
            first_price = float(trades[0].get("p", 0))
            last_price = float(trades[-1].get("p", 0))
            price_change = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0
            
            if price_change > -0.5:  # Price didn't drop much despite selling
                absorption = {
                    "type": "BULLISH_ABSORPTION",
                    "signal": "BUY",
                    "large_sells": len(large_sells),
                    "large_buys": len(large_buys),
                    "description": f"Large sell orders absorbed - {len(large_sells)} large sells but price stable"
                }
        
        elif large_buys and len(large_buys) > len(large_sells):
            # Large buys but price stable = bearish absorption
            first_price = float(trades[0].get("p", 0))
            last_price = float(trades[-1].get("p", 0))
            price_change = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0
            
            if price_change < 0.5:  # Price didn't rise much despite buying
                absorption = {
                    "type": "BEARISH_ABSORPTION",
                    "signal": "SELL",
                    "large_buys": len(large_buys),
                    "large_sells": len(large_sells),
                    "description": f"Large buy orders absorbed - {len(large_buys)} large buys but price stable"
                }
        
        return {
            "symbol": symbol,
            "has_absorption": absorption is not None,
            "absorption": absorption,
            "large_order_threshold": round(large_threshold, 2),
            "large_buys_count": len(large_buys),
            "large_sells_count": len(large_sells),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_full_order_flow(self, symbol: str) -> Dict:
        """Get comprehensive order flow analysis"""
        tasks = [
            self.calculate_cvd(symbol),
            self.detect_cvd_divergence(symbol),
            self.detect_absorption(symbol),
        ]
        
        cvd, divergence, absorption = await asyncio.gather(*tasks, return_exceptions=True)
        
        if isinstance(cvd, Exception):
            cvd = {"error": str(cvd)}
        if isinstance(divergence, Exception):
            divergence = {"error": str(divergence)}
        if isinstance(absorption, Exception):
            absorption = {"error": str(absorption)}
        
        # Combine signals
        signals = []
        
        if cvd.get("bias") in ["BULLISH", "STRONG_BULLISH"]:
            signals.append("BUY")
        elif cvd.get("bias") in ["BEARISH", "STRONG_BEARISH"]:
            signals.append("SELL")
        
        if divergence.get("has_divergence"):
            signals.append(divergence.get("divergence", {}).get("signal", "NONE"))
        
        if absorption.get("has_absorption"):
            signals.append(absorption.get("absorption", {}).get("signal", "NONE"))
        
        # Overall signal
        buy_count = signals.count("BUY")
        sell_count = signals.count("SELL")
        
        if buy_count > sell_count:
            overall_signal = "BUY"
            confidence = 50 + (buy_count * 15)
        elif sell_count > buy_count:
            overall_signal = "SELL"
            confidence = 50 + (sell_count * 15)
        else:
            overall_signal = "NEUTRAL"
            confidence = 50
        
        return {
            "symbol": symbol,
            "overall_signal": overall_signal,
            "confidence": min(confidence, 85),
            "cvd": cvd,
            "divergence": divergence,
            "absorption": absorption,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
order_flow = OrderFlowAnalyzer()
