"""
AEON MARKET INTELLIGENCE MODULE
Using CCXT for multi-exchange support + Technical Analysis
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List
import ta
import logging
import asyncio

logger = logging.getLogger(__name__)


class MarketIntelligence:
    """Market data using CCXT (supports multiple exchanges) + Technical Analysis"""
    
    def __init__(self):
        # Use Binance spot (more accessible) + MEXC for derivatives data
        self.binance = ccxt.binance({'enableRateLimit': True})
        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    def get_klines_sync(self, symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data synchronously"""
        try:
            ohlcv = self.binance.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"CCXT klines error: {e}")
            return pd.DataFrame()
    
    async def get_klines(self, symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
        """Async wrapper for klines"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_klines_sync, symbol, timeframe, limit)
    
    def get_ticker_sync(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """Get current ticker data"""
        try:
            ticker = self.binance.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "price": ticker['last'],
                "change_24h": ticker['percentage'],
                "high_24h": ticker['high'],
                "low_24h": ticker['low'],
                "volume_24h": ticker['quoteVolume'],
                "bid": ticker['bid'],
                "ask": ticker['ask'],
            }
        except Exception as e:
            logger.error(f"Ticker error: {e}")
            return {"error": str(e)}
    
    async def get_ticker(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_ticker_sync, symbol)
    
    def get_orderbook_sync(self, symbol: str = "BTC/USDT", limit: int = 20) -> Dict[str, Any]:
        """Get orderbook with bid/ask analysis"""
        try:
            book = self.binance.fetch_order_book(symbol, limit)
            bid_depth = sum([b[1] * b[0] for b in book['bids'][:10]])  # USD value
            ask_depth = sum([a[1] * a[0] for a in book['asks'][:10]])
            total = bid_depth + ask_depth
            imbalance = ((bid_depth - ask_depth) / total * 100) if total > 0 else 0
            
            return {
                "symbol": symbol,
                "bid_depth_usd": bid_depth,
                "ask_depth_usd": ask_depth,
                "imbalance_pct": imbalance,
                "top_bid": book['bids'][0] if book['bids'] else None,
                "top_ask": book['asks'][0] if book['asks'] else None,
            }
        except Exception as e:
            logger.error(f"Orderbook error: {e}")
            return {"error": str(e)}
    
    async def get_orderbook(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_orderbook_sync, symbol)
    
    async def get_technical_analysis(self, symbol: str = "BTC/USDT", interval: str = "1h") -> Dict[str, Any]:
        """Full technical analysis with indicators"""
        df = await self.get_klines(symbol, interval, 100)
        
        if df.empty:
            return {"error": "Failed to fetch data"}
        
        try:
            price = df['close'].iloc[-1]
            
            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            rsi = df['rsi'].iloc[-1]
            
            # MACD
            macd_ind = ta.trend.MACD(df['close'])
            df['macd'] = macd_ind.macd()
            df['macd_signal'] = macd_ind.macd_signal()
            df['macd_hist'] = macd_ind.macd_diff()
            macd = df['macd'].iloc[-1]
            macd_signal = df['macd_signal'].iloc[-1]
            macd_hist = df['macd_hist'].iloc[-1]
            
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            bb_upper = bb.bollinger_hband().iloc[-1]
            bb_lower = bb.bollinger_lband().iloc[-1]
            bb_middle = bb.bollinger_mavg().iloc[-1]
            
            # EMAs
            ema_9 = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator().iloc[-1]
            ema_21 = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator().iloc[-1]
            ema_50 = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator().iloc[-1]
            
            # ATR
            atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range().iloc[-1]
            
            # Stochastic
            stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
            stoch_k = stoch.stoch().iloc[-1]
            stoch_d = stoch.stoch_signal().iloc[-1]
            
            # Volume
            avg_vol = df['volume'].tail(20).mean()
            curr_vol = df['volume'].iloc[-1]
            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1
            
            # Generate signals
            signals = []
            
            if rsi < 30:
                signals.append(("RSI", "OVERSOLD", "bullish"))
            elif rsi > 70:
                signals.append(("RSI", "OVERBOUGHT", "bearish"))
            
            if macd > macd_signal and macd_hist > 0:
                signals.append(("MACD", "BULLISH", "bullish"))
            elif macd < macd_signal and macd_hist < 0:
                signals.append(("MACD", "BEARISH", "bearish"))
            
            if price < bb_lower:
                signals.append(("BB", "BELOW LOWER", "bullish"))
            elif price > bb_upper:
                signals.append(("BB", "ABOVE UPPER", "bearish"))
            
            if ema_9 > ema_21 > ema_50:
                signals.append(("EMA", "BULLISH STACK", "bullish"))
            elif ema_9 < ema_21 < ema_50:
                signals.append(("EMA", "BEARISH STACK", "bearish"))
            
            if stoch_k < 20:
                signals.append(("STOCH", "OVERSOLD", "bullish"))
            elif stoch_k > 80:
                signals.append(("STOCH", "OVERBOUGHT", "bearish"))
            
            if vol_ratio > 1.5:
                signals.append(("VOLUME", f"HIGH {vol_ratio:.1f}x", "attention"))
            
            # Overall bias
            bullish = sum(1 for s in signals if s[2] == "bullish")
            bearish = sum(1 for s in signals if s[2] == "bearish")
            
            if bullish > bearish + 1:
                bias = "BULLISH"
            elif bearish > bullish + 1:
                bias = "BEARISH"
            else:
                bias = "NEUTRAL"
            
            return {
                "symbol": symbol,
                "interval": interval,
                "price": round(price, 2),
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
                    "volume_ratio": round(vol_ratio, 2)
                },
                "signals": signals,
                "overall_bias": bias,
                "bullish_signals": bullish,
                "bearish_signals": bearish,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"TA error: {e}")
            return {"error": str(e)}
    
    async def get_full_market_scan(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """Comprehensive market scan"""
        try:
            # Run all fetches
            ta_data = await self.get_technical_analysis(symbol, "1h")
            ticker = await self.get_ticker(symbol)
            orderbook = await self.get_orderbook(symbol)
            
            if "error" in ta_data:
                return ta_data
            
            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": ta_data.get("price"),
                "change_24h": ticker.get("change_24h"),
                "technical": ta_data.get("indicators", {}),
                "signals": ta_data.get("signals", []),
                "overall_bias": ta_data.get("overall_bias"),
                "orderbook": {
                    "bid_depth": f"${orderbook.get('bid_depth_usd', 0)/1e6:.1f}M",
                    "ask_depth": f"${orderbook.get('ask_depth_usd', 0)/1e6:.1f}M",
                    "imbalance": f"{orderbook.get('imbalance_pct', 0):+.1f}%"
                },
                "volume_24h": f"${ticker.get('volume_24h', 0)/1e9:.2f}B" if ticker.get('volume_24h', 0) > 1e9 else f"${ticker.get('volume_24h', 0)/1e6:.1f}M",
            }
        except Exception as e:
            logger.error(f"Full scan error: {e}")
            return {"error": str(e)}
    
    async def analyze_setup(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """Analyze trading setup with score"""
        scan = await self.get_full_market_scan(symbol)
        
        if "error" in scan:
            return scan
        
        score = 0
        reasons = []
        
        for signal in scan.get("signals", []):
            ind, cond, bias = signal
            if bias == "bullish":
                score += 1
                reasons.append(f"✅ {ind}: {cond}")
            elif bias == "bearish":
                score -= 1
                reasons.append(f"🔴 {ind}: {cond}")
        
        # Orderbook imbalance
        ob = scan.get("orderbook", {})
        imb = float(ob.get("imbalance", "0%").replace("%", "").replace("+", ""))
        if imb > 15:
            score += 0.5
            reasons.append(f"✅ Orderbook bullish imbalance ({ob['imbalance']})")
        elif imb < -15:
            score -= 0.5
            reasons.append(f"🔴 Orderbook bearish imbalance ({ob['imbalance']})")
        
        # Direction
        if score >= 2:
            direction = "LONG"
            confidence = min(85, 50 + score * 10)
        elif score <= -2:
            direction = "SHORT"
            confidence = min(85, 50 + abs(score) * 10)
        else:
            direction = "NEUTRAL"
            confidence = 40
        
        # Targets
        price = scan["price"]
        atr = scan.get("technical", {}).get("atr", price * 0.02)
        
        if direction == "LONG":
            target = price + (atr * 2)
            stop = price - (atr * 1.5)
        elif direction == "SHORT":
            target = price - (atr * 2)
            stop = price + (atr * 1.5)
        else:
            target = stop = None
        
        return {
            "symbol": symbol,
            "direction": direction,
            "confidence": round(confidence, 1),
            "score": round(score, 2),
            "price": price,
            "target": round(target, 2) if target else None,
            "stop_loss": round(stop, 2) if stop else None,
            "reasons": reasons,
            "market_data": scan,
        }


# Global instance
market_intel = MarketIntelligence()
