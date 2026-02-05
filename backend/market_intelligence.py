"""
AEON MARKET INTELLIGENCE MODULE
Free Binance Futures API + Technical Analysis
"""

import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import ta
import logging
import asyncio

logger = logging.getLogger(__name__)

BINANCE_FUTURES_BASE = "https://fapi.binance.com"

class MarketIntelligence:
    """Free market data from Binance Futures API + Technical Analysis"""
    
    def __init__(self):
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 30  # seconds
    
    def _is_cache_valid(self, key: str) -> bool:
        if key not in self.cache_time:
            return False
        return (datetime.now() - self.cache_time[key]).total_seconds() < self.cache_duration
    
    async def _fetch(self, endpoint: str, params: dict = None) -> Any:
        """Fetch data from Binance Futures API"""
        url = f"{BINANCE_FUTURES_BASE}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Binance API error: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPEN INTEREST
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_open_interest(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get current open interest for a symbol"""
        data = await self._fetch("/fapi/v1/openInterest", {"symbol": symbol})
        if data:
            return {
                "symbol": symbol,
                "open_interest": float(data.get("openInterest", 0)),
                "time": datetime.now(timezone.utc).isoformat()
            }
        return {"error": "Failed to fetch open interest"}
    
    async def get_open_interest_history(self, symbol: str = "BTCUSDT", period: str = "1h", limit: int = 30) -> List[Dict]:
        """Get open interest history"""
        data = await self._fetch("/futures/data/openInterestHist", {
            "symbol": symbol,
            "period": period,
            "limit": limit
        })
        if data:
            return [{
                "timestamp": d.get("timestamp"),
                "open_interest": float(d.get("sumOpenInterest", 0)),
                "open_interest_value": float(d.get("sumOpenInterestValue", 0))
            } for d in data]
        return []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LONG/SHORT RATIOS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_long_short_ratio(self, symbol: str = "BTCUSDT", period: str = "1h", limit: int = 10) -> List[Dict]:
        """Get global long/short account ratio"""
        data = await self._fetch("/futures/data/globalLongShortAccountRatio", {
            "symbol": symbol,
            "period": period,
            "limit": limit
        })
        if data:
            return [{
                "timestamp": d.get("timestamp"),
                "long_short_ratio": float(d.get("longShortRatio", 0)),
                "long_account": float(d.get("longAccount", 0)),
                "short_account": float(d.get("shortAccount", 0))
            } for d in data]
        return []
    
    async def get_taker_long_short_ratio(self, symbol: str = "BTCUSDT", period: str = "1h", limit: int = 10) -> List[Dict]:
        """Get taker buy/sell ratio (actual volume flow)"""
        data = await self._fetch("/futures/data/takerlongshortRatio", {
            "symbol": symbol,
            "period": period,
            "limit": limit
        })
        if data:
            return [{
                "timestamp": d.get("timestamp"),
                "buy_sell_ratio": float(d.get("buySellRatio", 0)),
                "buy_vol": float(d.get("buyVol", 0)),
                "sell_vol": float(d.get("sellVol", 0))
            } for d in data]
        return []
    
    async def get_top_trader_long_short_ratio(self, symbol: str = "BTCUSDT", period: str = "1h", limit: int = 10) -> List[Dict]:
        """Get top trader long/short ratio (whale positioning)"""
        data = await self._fetch("/futures/data/topLongShortAccountRatio", {
            "symbol": symbol,
            "period": period,
            "limit": limit
        })
        if data:
            return [{
                "timestamp": d.get("timestamp"),
                "long_short_ratio": float(d.get("longShortRatio", 0)),
                "long_account": float(d.get("longAccount", 0)),
                "short_account": float(d.get("shortAccount", 0))
            } for d in data]
        return []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FUNDING RATE
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_funding_rate(self, symbol: str = "BTCUSDT", limit: int = 10) -> List[Dict]:
        """Get funding rate history"""
        data = await self._fetch("/fapi/v1/fundingRate", {
            "symbol": symbol,
            "limit": limit
        })
        if data:
            return [{
                "timestamp": d.get("fundingTime"),
                "funding_rate": float(d.get("fundingRate", 0)),
                "funding_rate_pct": f"{float(d.get('fundingRate', 0)) * 100:.4f}%"
            } for d in data]
        return []
    
    async def get_current_funding_rate(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get current/next funding rate"""
        data = await self._fetch("/fapi/v1/premiumIndex", {"symbol": symbol})
        if data:
            return {
                "symbol": symbol,
                "mark_price": float(data.get("markPrice", 0)),
                "index_price": float(data.get("indexPrice", 0)),
                "funding_rate": float(data.get("lastFundingRate", 0)),
                "funding_rate_pct": f"{float(data.get('lastFundingRate', 0)) * 100:.4f}%",
                "next_funding_time": data.get("nextFundingTime")
            }
        return {"error": "Failed to fetch funding rate"}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LIQUIDATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_liquidations(self, symbol: str = "BTCUSDT", limit: int = 20) -> List[Dict]:
        """Get recent liquidation orders"""
        data = await self._fetch("/fapi/v1/forceOrders", {
            "symbol": symbol,
            "limit": limit
        })
        if data:
            return [{
                "symbol": d.get("symbol"),
                "side": d.get("side"),
                "price": float(d.get("price", 0)),
                "qty": float(d.get("origQty", 0)),
                "value_usd": float(d.get("price", 0)) * float(d.get("origQty", 0)),
                "time": d.get("time")
            } for d in data]
        return []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # KLINES (CHARTS) + TECHNICAL ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_klines(self, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 100) -> pd.DataFrame:
        """Get OHLCV candlestick data"""
        data = await self._fetch("/fapi/v1/klines", {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
        if data:
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                df[col] = df[col].astype(float)
            return df
        return pd.DataFrame()
    
    async def get_technical_analysis(self, symbol: str = "BTCUSDT", interval: str = "1h") -> Dict[str, Any]:
        """Get full technical analysis with indicators"""
        df = await self.get_klines(symbol, interval, 100)
        
        if df.empty:
            return {"error": "Failed to fetch kline data"}
        
        try:
            # Current price
            current_price = df['close'].iloc[-1]
            
            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            rsi = df['rsi'].iloc[-1]
            
            # MACD
            macd_indicator = ta.trend.MACD(df['close'])
            df['macd'] = macd_indicator.macd()
            df['macd_signal'] = macd_indicator.macd_signal()
            df['macd_hist'] = macd_indicator.macd_diff()
            macd = df['macd'].iloc[-1]
            macd_signal = df['macd_signal'].iloc[-1]
            macd_hist = df['macd_hist'].iloc[-1]
            
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()
            bb_upper = df['bb_upper'].iloc[-1]
            bb_lower = df['bb_lower'].iloc[-1]
            bb_middle = df['bb_middle'].iloc[-1]
            
            # EMA
            df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
            df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
            df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
            ema_9 = df['ema_9'].iloc[-1]
            ema_21 = df['ema_21'].iloc[-1]
            ema_50 = df['ema_50'].iloc[-1]
            
            # ATR (volatility)
            df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
            atr = df['atr'].iloc[-1]
            
            # Stochastic
            stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
            df['stoch_k'] = stoch.stoch()
            df['stoch_d'] = stoch.stoch_signal()
            stoch_k = df['stoch_k'].iloc[-1]
            stoch_d = df['stoch_d'].iloc[-1]
            
            # Volume analysis
            avg_volume = df['volume'].tail(20).mean()
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Generate signals
            signals = []
            
            # RSI signals
            if rsi < 30:
                signals.append(("RSI", "OVERSOLD", "bullish"))
            elif rsi > 70:
                signals.append(("RSI", "OVERBOUGHT", "bearish"))
            elif rsi < 40:
                signals.append(("RSI", "APPROACHING OVERSOLD", "neutral_bullish"))
            elif rsi > 60:
                signals.append(("RSI", "APPROACHING OVERBOUGHT", "neutral_bearish"))
            
            # MACD signals
            if macd > macd_signal and macd_hist > 0:
                signals.append(("MACD", "BULLISH CROSSOVER", "bullish"))
            elif macd < macd_signal and macd_hist < 0:
                signals.append(("MACD", "BEARISH CROSSOVER", "bearish"))
            
            # Bollinger Band signals
            if current_price < bb_lower:
                signals.append(("BB", "BELOW LOWER BAND", "bullish"))
            elif current_price > bb_upper:
                signals.append(("BB", "ABOVE UPPER BAND", "bearish"))
            
            # EMA trend
            if ema_9 > ema_21 > ema_50:
                signals.append(("EMA", "BULLISH ALIGNMENT", "bullish"))
            elif ema_9 < ema_21 < ema_50:
                signals.append(("EMA", "BEARISH ALIGNMENT", "bearish"))
            
            # Stochastic
            if stoch_k < 20 and stoch_d < 20:
                signals.append(("STOCH", "OVERSOLD", "bullish"))
            elif stoch_k > 80 and stoch_d > 80:
                signals.append(("STOCH", "OVERBOUGHT", "bearish"))
            
            # Volume
            if volume_ratio > 1.5:
                signals.append(("VOLUME", f"HIGH ({volume_ratio:.1f}x avg)", "attention"))
            
            # Calculate overall bias
            bullish_count = sum(1 for s in signals if s[2] == "bullish")
            bearish_count = sum(1 for s in signals if s[2] == "bearish")
            
            if bullish_count > bearish_count + 1:
                overall_bias = "BULLISH"
            elif bearish_count > bullish_count + 1:
                overall_bias = "BEARISH"
            else:
                overall_bias = "NEUTRAL"
            
            return {
                "symbol": symbol,
                "interval": interval,
                "price": current_price,
                "indicators": {
                    "rsi": round(rsi, 2),
                    "macd": round(macd, 4),
                    "macd_signal": round(macd_signal, 4),
                    "macd_histogram": round(macd_hist, 4),
                    "bb_upper": round(bb_upper, 2),
                    "bb_middle": round(bb_middle, 2),
                    "bb_lower": round(bb_lower, 2),
                    "ema_9": round(ema_9, 2),
                    "ema_21": round(ema_21, 2),
                    "ema_50": round(ema_50, 2),
                    "atr": round(atr, 2),
                    "stoch_k": round(stoch_k, 2),
                    "stoch_d": round(stoch_d, 2),
                    "volume_ratio": round(volume_ratio, 2)
                },
                "signals": signals,
                "overall_bias": overall_bias,
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Technical analysis error: {e}")
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FULL MARKET SCAN
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_full_market_scan(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get comprehensive market analysis for a symbol"""
        
        # Fetch all data concurrently
        results = await asyncio.gather(
            self.get_technical_analysis(symbol, "1h"),
            self.get_current_funding_rate(symbol),
            self.get_long_short_ratio(symbol, "1h", 1),
            self.get_taker_long_short_ratio(symbol, "1h", 1),
            self.get_top_trader_long_short_ratio(symbol, "1h", 1),
            self.get_open_interest(symbol),
            return_exceptions=True
        )
        
        ta_data, funding, ls_ratio, taker_ratio, top_trader, oi = results
        
        # Handle errors gracefully
        if isinstance(ta_data, Exception) or "error" in ta_data:
            ta_data = {}
        if isinstance(funding, Exception) or "error" in str(funding):
            funding = {}
        
        # Build comprehensive report
        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": ta_data.get("price"),
            "technical": ta_data.get("indicators", {}),
            "signals": ta_data.get("signals", []),
            "overall_bias": ta_data.get("overall_bias", "UNKNOWN"),
            "funding": {
                "rate": funding.get("funding_rate_pct") if funding else None,
                "mark_price": funding.get("mark_price") if funding else None,
            },
            "positioning": {
                "long_short_ratio": ls_ratio[0].get("long_short_ratio") if ls_ratio else None,
                "longs": ls_ratio[0].get("long_account") if ls_ratio else None,
                "shorts": ls_ratio[0].get("short_account") if ls_ratio else None,
            },
            "taker_flow": {
                "buy_sell_ratio": taker_ratio[0].get("buy_sell_ratio") if taker_ratio else None,
            },
            "whale_positioning": {
                "long_short_ratio": top_trader[0].get("long_short_ratio") if top_trader else None,
            },
            "open_interest": oi.get("open_interest") if isinstance(oi, dict) else None,
        }
    
    async def get_multi_symbol_scan(self) -> Dict[str, Any]:
        """Scan multiple symbols at once"""
        results = {}
        for symbol in self.symbols:
            results[symbol] = await self.get_full_market_scan(symbol)
        return results


# Global instance
market_intel = MarketIntelligence()
