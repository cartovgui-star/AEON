"""
Order Flow Analysis Module
- Cumulative Volume Delta (CVD)
- Buy/Sell Pressure
- Delta Divergence
- Absorption Detection
Uses MEXC API (no geo-restrictions)
"""
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
import ccxt

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)


class OrderFlowAnalyzer:
    """
    Analyzes order flow data from MEXC (no geo-restrictions)
    - CVD (Cumulative Volume Delta) = Buy Volume - Sell Volume
    - Positive CVD = More buying pressure
    - Negative CVD = More selling pressure
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 30  # 30 second cache
        self.okx = ccxt.okx({'enableRateLimit': True})
    
    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None
    
    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())
    
    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """Fetch recent trades from MEXC"""
        cache_key = f"trades_{symbol}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            # Format symbol for MEXC
            formatted = symbol.upper().replace("/", "") 
            if not formatted.endswith("USDT"):
                formatted += "USDT"
            full_symbol = formatted.replace("USDT", "/USDT")
            
            loop = asyncio.get_running_loop()
            trades = await loop.run_in_executor(
                executor,
                lambda: self.okx.fetch_trades(full_symbol, limit=limit)
            )
            
            self._cache_set(cache_key, trades)
            return trades
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    async def calculate_cvd(self, symbol: str) -> Dict:
        """
        Calculate Cumulative Volume Delta from MEXC trades
        
        CVD = Sum of (Buy Volume - Sell Volume)
        - 'buy' side = buyer initiated (market buy)
        - 'sell' side = seller initiated (market sell)
        """
        trades = await self.get_recent_trades(symbol, 500)
        
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
            amount = trade.get("amount", 0)
            price = trade.get("price", 0)
            side = trade.get("side", "")
            
            volume_usd = amount * price
            
            if side == "buy":
                buy_volume += volume_usd
                running_cvd += volume_usd
            else:
                sell_volume += volume_usd
                running_cvd -= volume_usd
            
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
        
        # Calculate CVD trend
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
        """
        trades = await self.get_recent_trades(symbol, 500)
        
        if not trades or len(trades) < 100:
            return {"symbol": symbol, "error": "Insufficient trade data"}
        
        # Calculate average trade size
        trade_sizes = [t.get("amount", 0) * t.get("price", 0) for t in trades]
        avg_size = sum(trade_sizes) / len(trade_sizes)
        large_threshold = avg_size * 5
        
        large_buys = []
        large_sells = []
        
        for trade in trades:
            size = trade.get("amount", 0) * trade.get("price", 0)
            side = trade.get("side", "")
            
            if size > large_threshold:
                if side == "buy":
                    large_buys.append({"size": size, "price": trade.get("price", 0)})
                else:
                    large_sells.append({"size": size, "price": trade.get("price", 0)})
        
        # Check for absorption
        absorption = None
        
        if large_sells and len(large_sells) > len(large_buys):
            first_price = trades[0].get("price", 0)
            last_price = trades[-1].get("price", 0)
            price_change = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0
            
            if price_change > -0.5:
                absorption = {
                    "type": "BULLISH_ABSORPTION",
                    "signal": "BUY",
                    "large_sells": len(large_sells),
                    "large_buys": len(large_buys),
                    "description": f"Large sell orders absorbed - {len(large_sells)} large sells but price stable"
                }
        
        elif large_buys and len(large_buys) > len(large_sells):
            first_price = trades[0].get("price", 0)
            last_price = trades[-1].get("price", 0)
            price_change = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0
            
            if price_change < 0.5:
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
