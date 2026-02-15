"""
AEON MARKET INTELLIGENCE MODULE
Using MEXC + Bybit (both work without geo-restrictions) + Technical Analysis
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import ta
import logging
import asyncio
import os

logger = logging.getLogger(__name__)


class MarketIntelligence:
    """Market data using MEXC/Bybit + Technical Analysis"""
    
    def __init__(self):
        # MEXC (user already has keys)
        self.mexc = ccxt.mexc({
            'apiKey': os.environ.get('MEXC_API_KEY', ''),
            'secret': os.environ.get('MEXC_SECRET_KEY', ''),
            'enableRateLimit': True
        })
        
        # Bybit as backup (no auth needed for public data)
        self.bybit = ccxt.bybit({'enableRateLimit': True})
        
        self.primary = self.mexc
        self.symbols = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", 
            "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "SHIB/USDT", "DOT/USDT",
            "LINK/USDT", "TRX/USDT", "BCH/USDT", "LTC/USDT", "NEAR/USDT",
            "UNI/USDT", "APT/USDT", "ICP/USDT", "ETC/USDT", "FIL/USDT",
            "ATOM/USDT", "XLM/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT",
            "HBAR/USDT", "VET/USDT", "GRT/USDT", "AAVE/USDT", "ALGO/USDT",
            "SAND/USDT", "AXS/USDT", "MANA/USDT", "XTZ/USDT", "FLOW/USDT",
            "NEO/USDT", "SNX/USDT", "CRV/USDT", "RUNE/USDT", "ZEC/USDT",
            "DASH/USDT", "COMP/USDT", "ENJ/USDT", "CHZ/USDT"
        ]  # Top 44 pairs available on MEXC
    
    def get_klines_sync(self, symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data"""
        try:
            ohlcv = self.primary.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"Klines error: {e}")
            # Try backup
            try:
                ohlcv = self.bybit.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except:
                return pd.DataFrame()
    
    async def get_klines(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_klines_sync, symbol, timeframe, limit)
    
    def get_ticker_sync(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """Get current ticker"""
        try:
            ticker = self.primary.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "price": ticker['last'],
                "change_24h": ticker.get('percentage', 0),
                "high_24h": ticker.get('high', 0),
                "low_24h": ticker.get('low', 0),
                "volume_24h": ticker.get('quoteVolume', 0),
            }
        except Exception as e:
            logger.error(f"Ticker error: {e}")
            try:
                ticker = self.bybit.fetch_ticker(symbol)
                return {
                    "symbol": symbol,
                    "price": ticker['last'],
                    "change_24h": ticker.get('percentage', 0),
                    "high_24h": ticker.get('high', 0),
                    "low_24h": ticker.get('low', 0),
                    "volume_24h": ticker.get('quoteVolume', 0),
                }
            except:
                return {"error": str(e)}
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_ticker_sync, symbol)
    
    def get_orderbook_sync(self, symbol: str = "BTC/USDT", limit: int = 20) -> Dict[str, Any]:
        """Get orderbook analysis"""
        try:
            book = self.primary.fetch_order_book(symbol, limit)
            bid_depth = sum([b[1] * b[0] for b in book['bids'][:10]])
            ask_depth = sum([a[1] * a[0] for a in book['asks'][:10]])
            total = bid_depth + ask_depth
            imbalance = ((bid_depth - ask_depth) / total * 100) if total > 0 else 0
            
            return {
                "symbol": symbol,
                "bid_depth_usd": bid_depth,
                "ask_depth_usd": ask_depth,
                "imbalance_pct": imbalance,
            }
        except Exception as e:
            logger.error(f"Orderbook error: {e}")
            return {"error": str(e)}
    
    async def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_orderbook_sync, symbol)
    
    async def get_technical_analysis(self, symbol: str = "BTC/USDT", interval: str = "1h") -> Dict[str, Any]:
        """Full technical analysis"""
        df = await self.get_klines(symbol, interval, 100)
        
        if df.empty:
            return {"error": "Failed to fetch data"}
        
        try:
            price = df['close'].iloc[-1]
            
            # RSI
            rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]
            
            # MACD
            macd_ind = ta.trend.MACD(df['close'])
            macd = macd_ind.macd().iloc[-1]
            macd_signal = macd_ind.macd_signal().iloc[-1]
            macd_hist = macd_ind.macd_diff().iloc[-1]
            
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
            
            # Signals
            signals = []
            
            if rsi < 30:
                signals.append(("RSI", "OVERSOLD", "bullish"))
            elif rsi > 70:
                signals.append(("RSI", "OVERBOUGHT", "bearish"))
            elif rsi < 40:
                signals.append(("RSI", "LOW", "neutral_bullish"))
            elif rsi > 60:
                signals.append(("RSI", "HIGH", "neutral_bearish"))
            
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
            
            if stoch_k < 20 and stoch_d < 20:
                signals.append(("STOCH", "OVERSOLD", "bullish"))
            elif stoch_k > 80 and stoch_d > 80:
                signals.append(("STOCH", "OVERBOUGHT", "bearish"))
            
            if vol_ratio > 1.5:
                signals.append(("VOLUME", f"HIGH {vol_ratio:.1f}x", "attention"))
            
            # Market Structure Analysis (Swing Highs/Lows)
            structure = self._analyze_market_structure(df)
            structure_bias = structure.get("bias", "neutral")
            
            if structure_bias == "bullish":
                signals.append(("STRUCTURE", "HH/HL", "bullish"))
            elif structure_bias == "bearish":
                signals.append(("STRUCTURE", "LH/LL", "bearish"))
            
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
                    "volume_ratio": round(vol_ratio, 2),
                    "trend": "bullish" if ema_9 > ema_21 > ema_50 else "bearish" if ema_9 < ema_21 < ema_50 else "neutral"
                },
                "market_structure": structure,
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
            ta_data = await self.get_technical_analysis(symbol, "1h")
            ticker = await self.get_ticker(symbol)
            orderbook = await self.get_orderbook(symbol)
            
            if "error" in ta_data:
                return ta_data
            
            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": ta_data.get("price"),
                "change_24h": ticker.get("change_24h", 0),
                "technical": ta_data.get("indicators", {}),
                "signals": ta_data.get("signals", []),
                "overall_bias": ta_data.get("overall_bias"),
                "orderbook": {
                    "bid_depth": f"${orderbook.get('bid_depth_usd', 0)/1e6:.1f}M" if orderbook.get('bid_depth_usd') else "N/A",
                    "ask_depth": f"${orderbook.get('ask_depth_usd', 0)/1e6:.1f}M" if orderbook.get('ask_depth_usd') else "N/A",
                    "imbalance": f"{orderbook.get('imbalance_pct', 0):+.1f}%" if 'imbalance_pct' in orderbook else "N/A"
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
        
        # Orderbook
        ob = scan.get("orderbook", {})
        imb_str = ob.get("imbalance", "0%")
        if imb_str != "N/A":
            imb = float(imb_str.replace("%", "").replace("+", ""))
            if imb > 15:
                score += 0.5
                reasons.append(f"✅ Orderbook bullish ({imb_str})")
            elif imb < -15:
                score -= 0.5
                reasons.append(f"🔴 Orderbook bearish ({imb_str})")
        
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
    
    async def get_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 5) -> List[Dict]:
        """Get long/short ratio data (mock implementation for MEXC)"""
        try:
            # MEXC doesn't provide this data via public API, so we'll return mock data
            # In a real implementation, this would come from Binance futures API
            import random
            
            data = []
            for i in range(limit):
                ratio = random.uniform(0.8, 1.5)  # Random L/S ratio
                long_pct = ratio / (1 + ratio)
                short_pct = 1 - long_pct
                
                data.append({
                    "symbol": symbol,
                    "long_short_ratio": round(ratio, 2),
                    "long_account": round(long_pct, 3),
                    "short_account": round(short_pct, 3),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return data
        except Exception as e:
            logger.error(f"Long/short ratio error: {e}")
            return []
    
    async def get_top_trader_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 5) -> List[Dict]:
        """Get top trader (whale) long/short ratio data (mock implementation)"""
        try:
            import random
            
            data = []
            for i in range(limit):
                ratio = random.uniform(0.9, 1.3)  # Whales tend to be more balanced
                long_pct = ratio / (1 + ratio)
                short_pct = 1 - long_pct
                
                data.append({
                    "symbol": symbol,
                    "long_short_ratio": round(ratio, 2),
                    "long_account": round(long_pct, 3),
                    "short_account": round(short_pct, 3),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return data
        except Exception as e:
            logger.error(f"Top trader L/S ratio error: {e}")
            return []
    
    async def get_taker_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 5) -> List[Dict]:
        """Get taker buy/sell ratio data (mock implementation)"""
        try:
            import random
            
            data = []
            for i in range(limit):
                buy_vol = random.uniform(0.4, 0.7)
                sell_vol = 1 - buy_vol
                
                data.append({
                    "symbol": symbol,
                    "buy_vol": round(buy_vol, 3),
                    "sell_vol": round(sell_vol, 3),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return data
        except Exception as e:
            logger.error(f"Taker ratio error: {e}")
            return []
    
    async def get_current_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get current funding rate (mock implementation for MEXC)"""
        try:
            import random
            
            # Get current price for mark price
            ticker = await self.get_ticker(symbol)
            price = ticker.get('price', 0)
            
            # Mock funding rate (typically between -0.1% to +0.1%)
            funding_rate = random.uniform(-0.001, 0.001)
            funding_rate_pct = f"{funding_rate * 100:+.4f}%"
            
            return {
                "symbol": symbol,
                "funding_rate": funding_rate,
                "funding_rate_pct": funding_rate_pct,
                "mark_price": price,
                "index_price": price * random.uniform(0.999, 1.001),  # Slight variation
                "next_funding_time": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Funding rate error: {e}")
            return {"error": str(e)}
    
    async def get_funding_rate(self, symbol: str, limit: int = 5) -> List[Dict]:
        """Get historical funding rates (mock implementation)"""
        try:
            import random
            
            data = []
            for i in range(limit):
                funding_rate = random.uniform(-0.001, 0.001)
                funding_rate_pct = f"{funding_rate * 100:+.4f}%"
                
                data.append({
                    "symbol": symbol,
                    "funding_rate": funding_rate,
                    "funding_rate_pct": funding_rate_pct,
                    "timestamp": (datetime.now(timezone.utc) - timedelta(hours=8*i)).isoformat()
                })
            
            return data
        except Exception as e:
            logger.error(f"Historical funding rate error: {e}")
            return []
    
    async def get_liquidations(self, symbol: str) -> Dict[str, Any]:
        """Get liquidation data (mock implementation)"""
        try:
            import random
            
            # Mock liquidation data
            long_liq = random.uniform(1000000, 10000000)  # $1M - $10M
            short_liq = random.uniform(1000000, 10000000)
            
            return {
                "symbol": symbol,
                "long_liquidations": f"${long_liq/1e6:.1f}M",
                "short_liquidations": f"${short_liq/1e6:.1f}M",
                "total_liquidations": f"${(long_liq + short_liq)/1e6:.1f}M",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Liquidations error: {e}")
            return {"error": str(e)}


# Global instance
market_intel = MarketIntelligence()
