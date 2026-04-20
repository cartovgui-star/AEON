"""
AEON MARKET INTELLIGENCE MODULE
Using OKX + Technical Analysis
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import ta
import logging
import asyncio
import time
import os
import httpx

from mexc_utils import format_mexc_symbol  # normalizes any format → BTC/USDT (valid for OKX too)

logger = logging.getLogger(__name__)

_OKX_BASE = "https://www.okx.com/api/v5"


def _to_okx_ccy(symbol: str) -> str:
    """'BTC/USDT' -> 'BTC'"""
    return symbol.split("/")[0]


def _to_okx_inst(symbol: str) -> str:
    """'BTC/USDT' -> 'BTC-USDT-SWAP'"""
    base, quote = symbol.split("/")
    return f"{base}-{quote}-SWAP"


def _okx_period(period: str) -> str:
    """'1h' -> '1H', '4h' -> '4H', '1d' -> '1D'"""
    return period.upper()


class MarketIntelligence:
    """Market data using OKX + Technical Analysis"""

    def __init__(self):
        self._ticker_cache: Dict[str, tuple] = {}  # symbol -> (data, timestamp)
        self._ticker_cache_ttl = 5  # seconds
        self._deriv_cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        self._deriv_cache_ttl = 30  # seconds

        # OKX — no API key needed for public market data
        self.mexc = ccxt.okx({'enableRateLimit': True})
        self.mexc_public = ccxt.okx({'enableRateLimit': True})
        self.primary = self.mexc

        # Circuit breaker (kept for compatibility, OKX rarely fails)
        self._lsr_fail_count: int = 0
        self._lsr_disabled_until: float = 0.0  # epoch seconds

        # Symbol error cache: skip symbols that MEXC says don't exist for 24h
        # Prevents log spam for gold/silver/stock tokens LCW returns but MEXC doesn't list
        self._bad_symbols: dict = {}   # symbol -> expiry epoch
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
        import time as _time
        symbol = format_mexc_symbol(symbol)
        # Skip symbols MEXC has already rejected — re-check after 24h
        if symbol in self._bad_symbols and _time.time() < self._bad_symbols[symbol]:
            return pd.DataFrame()
        try:
            ohlcv = self.mexc_public.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            if "does not have market symbol" in str(e):
                self._bad_symbols[symbol] = _time.time() + 86400  # silence for 24h
            else:
                logger.error(f"Klines error: {e}")
            return pd.DataFrame()
    
    async def get_klines(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_klines_sync, symbol, timeframe, limit)

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 200) -> Dict:
        """Return OHLCV as candles list [[ts, o, h, l, c, v], ...] for vwap_scalper compatibility."""
        symbol = format_mexc_symbol(symbol)
        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None, lambda: self.mexc_public.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
            if not raw:
                raise ValueError("empty")
            return {"candles": raw, "symbol": symbol, "timeframe": timeframe}
        except Exception as e:
            logger.error(f"get_ohlcv error {symbol}: {e}")
            return {"error": str(e)}

    def get_ticker_sync(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """Get current ticker"""
        import time as _time
        symbol = format_mexc_symbol(symbol)
        if symbol in self._bad_symbols and _time.time() < self._bad_symbols[symbol]:
            return {"error": "symbol not on MEXC"}
        try:
            ticker = self.mexc_public.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "price": ticker['last'],
                "change_24h": ticker.get('percentage', 0),
                "high_24h": ticker.get('high', 0),
                "low_24h": ticker.get('low', 0),
                "volume_24h": ticker.get('quoteVolume', 0),
            }
        except Exception as e:
            if "does not have market symbol" in str(e):
                self._bad_symbols[symbol] = _time.time() + 86400
            else:
                logger.error(f"Ticker error: {e}")
            return {"error": str(e)}
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        now = time.time()
        cached = self._ticker_cache.get(symbol)
        if cached and (now - cached[1]) < self._ticker_cache_ttl:
            return cached[0]
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self.get_ticker_sync, symbol)
        if "error" not in result:
            self._ticker_cache[symbol] = (result, now)
        return result
    
    def get_orderbook_sync(self, symbol: str = "BTC/USDT", limit: int = 20) -> Dict[str, Any]:
        """Get orderbook analysis"""
        symbol = format_mexc_symbol(symbol)
        try:
            book = self.mexc_public.fetch_order_book(symbol, limit)
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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_orderbook_sync, symbol)
    
    async def get_technical_analysis(self, symbol: str = "BTC/USDT", interval: str = "1h") -> Dict[str, Any]:
        """Full technical analysis"""
        symbol = format_mexc_symbol(symbol)
        df = await self.get_klines(symbol, interval, 250)  # 250 candles needed for EMA 200
        
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
            ema_200 = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator().iloc[-1] if len(df) >= 200 else None
            
            # ATR
            atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range().iloc[-1]
            
            # Stochastic
            stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
            stoch_k = stoch.stoch().iloc[-1]
            stoch_d = stoch.stoch_signal().iloc[-1]
            
            # ADX
            try:
                adx_ind = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
                adx_val = adx_ind.adx().iloc[-1]
                adx_val = round(float(adx_val), 2) if adx_val == adx_val else 0.0  # nan check
            except Exception:
                adx_val = 0.0

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
                    "ema_20": round(ema_21, 2),
                    "ema_21": round(ema_21, 2),
                    "ema_50": round(ema_50, 2),
                    "ema_200": round(ema_200, 2) if ema_200 is not None else None,
                    "atr": round(atr, 2),
                    "stoch_k": round(stoch_k, 2),
                    "stoch_d": round(stoch_d, 2),
                    "volume_ratio": round(vol_ratio, 2),
                    "adx": adx_val,
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
    
    def _analyze_market_structure(self, df) -> Dict:
        """
        Analyze swing highs/lows to determine market structure.
        HH + HL = bullish (uptrend)
        LH + LL = bearish (downtrend)
        Mixed = neutral/ranging
        """
        try:
            highs = df['high'].values
            lows = df['low'].values
            n = len(highs)
            if n < 20:
                return {"bias": "neutral", "swings": []}
            
            # Find swing highs and lows using a 5-bar lookback
            swing_highs = []
            swing_lows = []
            lookback = 5
            
            for i in range(lookback, n - lookback):
                if highs[i] == max(highs[i - lookback:i + lookback + 1]):
                    swing_highs.append((i, float(highs[i])))
                if lows[i] == min(lows[i - lookback:i + lookback + 1]):
                    swing_lows.append((i, float(lows[i])))
            
            if len(swing_highs) < 2 or len(swing_lows) < 2:
                return {"bias": "neutral", "swings": [], "reason": "insufficient swings"}
            
            # Use last 3 swing highs and lows
            recent_sh = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs[-2:]
            recent_sl = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows[-2:]
            
            # Check swing high pattern
            hh_count = 0
            lh_count = 0
            for i in range(1, len(recent_sh)):
                if recent_sh[i][1] > recent_sh[i-1][1]:
                    hh_count += 1  # Higher High
                elif recent_sh[i][1] < recent_sh[i-1][1]:
                    lh_count += 1  # Lower High
            
            # Check swing low pattern
            hl_count = 0
            ll_count = 0
            for i in range(1, len(recent_sl)):
                if recent_sl[i][1] > recent_sl[i-1][1]:
                    hl_count += 1  # Higher Low
                elif recent_sl[i][1] < recent_sl[i-1][1]:
                    ll_count += 1  # Lower Low
            
            # Determine structure
            bullish_pts = hh_count + hl_count
            bearish_pts = lh_count + ll_count
            
            if bullish_pts >= 2 and bullish_pts > bearish_pts:
                bias = "bullish"
                pattern = "HH/HL"
            elif bearish_pts >= 2 and bearish_pts > bullish_pts:
                bias = "bearish"
                pattern = "LH/LL"
            else:
                bias = "neutral"
                pattern = "MIXED"
            
            return {
                "bias": bias,
                "pattern": pattern,
                "higher_highs": hh_count,
                "lower_highs": lh_count,
                "higher_lows": hl_count,
                "lower_lows": ll_count,
                "last_swing_high": recent_sh[-1][1] if recent_sh else 0,
                "last_swing_low": recent_sl[-1][1] if recent_sl else 0
            }
        except Exception as e:
            logger.error(f"Market structure error: {e}")
            return {"bias": "neutral", "error": str(e)}
    
    async def get_full_market_scan(self, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """Comprehensive market scan"""
        symbol = format_mexc_symbol(symbol)
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
                "market_structure": ta_data.get("market_structure", {}),
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
    
    def _deriv_cache_get(self, key: str):
        """Return cached value if still valid, else None."""
        entry = self._deriv_cache.get(key)
        if entry:
            value, ts = entry[0], entry[1]
            ttl = entry[2] if len(entry) > 2 else self._deriv_cache_ttl
            if (time.time() - ts) < ttl:
                return value
        return None

    def _deriv_cache_set(self, key: str, value, ttl: int = None):
        """Store value in cache. ttl overrides the class default if provided."""
        if ttl is not None:
            self._deriv_cache[key] = (value, time.time(), ttl)
        else:
            self._deriv_cache[key] = (value, time.time())

    def _mexc_futures_symbol(self, symbol: str) -> str:
        """Convert 'BTC/USDT' -> 'BTC-USDT-SWAP' for OKX futures endpoints."""
        return _to_okx_inst(symbol)

    async def get_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 5) -> List[Dict]:
        """Get long/short ratio from OKX."""
        cache_key = f"lsr:{symbol}:{period}:{limit}"
        cached = self._deriv_cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            url = f"{_OKX_BASE}/rubik/stat/contracts/long-short-account-ratio"
            params = {"ccy": _to_okx_ccy(symbol), "period": _okx_period(period), "limit": str(limit)}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
            items = body.get("data") or []
            data = []
            for item in items[:limit]:
                ts_ms, ratio_str = item[0], item[1]
                ratio = float(ratio_str)
                long_pct = round(ratio / (1 + ratio), 4)
                short_pct = round(1 - long_pct, 4)
                ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).isoformat()
                data.append({"symbol": symbol, "long_short_ratio": round(ratio, 4),
                              "long_account": long_pct, "short_account": short_pct, "timestamp": ts})
            self._deriv_cache_set(cache_key, data)
            return data
        except Exception as e:
            logger.warning(f"OKX long/short ratio error for {symbol}: {e}")
            cached_fallback = self._deriv_cache.get(cache_key)
            return cached_fallback[0] if cached_fallback else []

    async def get_top_trader_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 5) -> List[Dict]:
        """Get top-trader long/short ratio from OKX (reuses same account ratio endpoint)."""
        return await self.get_long_short_ratio(symbol, period, limit)

    async def get_taker_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 5) -> List[Dict]:
        """Get taker buy/sell volume ratio from OKX."""
        cache_key = f"taker_lsr:{symbol}:{period}:{limit}"
        cached = self._deriv_cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            url = f"{_OKX_BASE}/rubik/stat/taker-volume"
            params = {"ccy": _to_okx_ccy(symbol), "instType": "SWAP",
                      "period": _okx_period(period), "limit": str(limit)}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
            items = body.get("data") or []
            data = []
            for item in items[:limit]:
                # OKX returns [ts, sellVol, buyVol]
                ts_ms, sell_vol_s, buy_vol_s = item[0], item[1], item[2]
                buy_vol = float(buy_vol_s)
                sell_vol = float(sell_vol_s)
                total = buy_vol + sell_vol
                buy_ratio = round(buy_vol / total, 4) if total else 0.5
                sell_ratio = round(sell_vol / total, 4) if total else 0.5
                ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).isoformat()
                data.append({"symbol": symbol, "buy_vol": buy_ratio, "sell_vol": sell_ratio, "timestamp": ts})
            self._deriv_cache_set(cache_key, data)
            return data
        except Exception as e:
            logger.warning(f"OKX taker ratio error for {symbol}: {e}")
            cached_fallback = self._deriv_cache.get(cache_key)
            return cached_fallback[0] if cached_fallback else []

    async def get_current_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get current funding rate from OKX."""
        cache_key = f"cur_fr:{symbol}"
        cached = self._deriv_cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            inst_id = _to_okx_inst(symbol)
            url = f"{_OKX_BASE}/public/funding-rate"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params={"instId": inst_id})
                resp.raise_for_status()
                body = resp.json()
            data = (body.get("data") or [{}])[0]
            funding_rate = float(data.get("fundingRate", 0))
            next_ts_ms = data.get("fundingTime", 0)
            next_funding_time = (
                datetime.fromtimestamp(int(next_ts_ms) / 1000, tz=timezone.utc).isoformat()
                if next_ts_ms else (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
            )
            result = {
                "symbol": symbol,
                "funding_rate": funding_rate,
                "funding_rate_pct": f"{funding_rate * 100:+.4f}%",
                "mark_price": float(data.get("markPrice", 0)) or None,
                "index_price": float(data.get("indexPrice", 0)) or None,
                "next_funding_time": next_funding_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._deriv_cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"OKX funding rate error for {symbol}: {e}")
            cached_fallback = self._deriv_cache.get(cache_key)
            if cached_fallback:
                return cached_fallback[0]
            return {"symbol": symbol, "funding_rate": 0.0, "funding_rate_pct": "+0.0000%",
                    "mark_price": None, "index_price": None, "next_funding_time": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()}

    async def get_funding_rate(self, symbol: str, limit: int = 5) -> List[Dict]:
        """Get historical funding rates from OKX public funding-rate-history endpoint."""
        cache_key = f"hist_fr:{symbol}:{limit}"
        cached = self._deriv_cache_get(cache_key)
        if cached is not None:
            return cached

        inst_id = self._mexc_futures_symbol(symbol)
        url = f"{_OKX_BASE}/public/funding-rate-history"
        params = {"instId": inst_id, "limit": limit}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()

            items = body.get("data") or []
            data = []
            for item in items:
                funding_rate = float(item.get("fundingRate", 0))
                funding_rate_pct = f"{funding_rate * 100:+.4f}%"
                ts_ms = item.get("fundingTime", 0)
                ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).isoformat() if ts_ms else datetime.now(timezone.utc).isoformat()
                data.append({
                    "symbol": symbol,
                    "funding_rate": funding_rate,
                    "funding_rate_pct": funding_rate_pct,
                    "timestamp": ts,
                })
            self._deriv_cache_set(cache_key, data)
            return data
        except Exception as e:
            logger.warning(f"OKX historical funding rate error for {symbol}: {e}")
            cached_fallback = self._deriv_cache.get(cache_key)
            return cached_fallback[0] if cached_fallback else []

    async def get_funding_momentum(self, symbol: str) -> Dict:
        """
        Analyze funding rate TREND (velocity), not just the current level.
        Rising funding = longs piling in = potential squeeze.
        Falling from extreme = squeeze completed = reversal signal.
        Returns: signal, velocity, current, trend, squeeze_risk
        """
        try:
            rates = await self.get_funding_rate(symbol, limit=8)
            if len(rates) < 3:
                return {"signal": "NEUTRAL", "velocity": 0.0, "current": 0.0, "trend": "flat"}

            values = [r["funding_rate"] for r in rates]  # newest first
            current = values[0]
            prev = values[1]
            older = values[2]

            velocity = current - prev
            acceleration = (current - prev) - (prev - older)

            signal = "NEUTRAL"
            squeeze_risk = "LOW"

            if current > 0.001 and velocity > 0:
                signal = "BEARISH"
                if current > 0.002 and velocity > 0.0003:
                    squeeze_risk = "HIGH"
                elif current > 0.0015:
                    squeeze_risk = "MEDIUM"
            elif current < -0.0003 and velocity < 0:
                signal = "BULLISH"
                if current < -0.0008:
                    squeeze_risk = "HIGH"
                elif current < -0.0005:
                    squeeze_risk = "MEDIUM"
            elif abs(prev) > 0.002 and abs(current) < abs(prev) * 0.6:
                signal = "REVERSAL"
                squeeze_risk = "MEDIUM"

            trend = "rising" if velocity > 0.0001 else "falling" if velocity < -0.0001 else "flat"
            return {
                "signal": signal,
                "current": round(current * 100, 5),
                "prev": round(prev * 100, 5),
                "velocity": round(velocity * 100, 6),
                "acceleration": round(acceleration * 100, 7),
                "trend": trend,
                "squeeze_risk": squeeze_risk,
                "history": [round(v * 100, 5) for v in values[:5]],
            }
        except Exception as e:
            logger.warning(f"Funding momentum error for {symbol}: {e}")
            return {"signal": "NEUTRAL", "velocity": 0.0, "current": 0.0, "trend": "flat"}

    async def get_liquidations(self, symbol: str) -> Dict[str, Any]:
        """
        Estimate liquidation pressure from open-interest changes via MEXC contract API.
        Compares current OI against the previous snapshot stored in cache.
        """
        cache_key = f"liqs:{symbol}"
        cached = self._deriv_cache_get(cache_key)
        if cached is not None:
            return cached

        inst_id = self._mexc_futures_symbol(symbol)
        url = f"{_OKX_BASE}/public/open-interest"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params={"instType": "SWAP", "instId": inst_id})
                resp.raise_for_status()
                body = resp.json()

            oi_now = 0.0
            items = body.get("data") or []
            if items:
                oi_now = float(items[0].get("oiCcy", 0))

            # Use previous snapshot from deriv cache to estimate OI change
            prev_key = f"oi_prev:{symbol}"
            prev_entry = self._deriv_cache.get(prev_key)
            oi_prev = prev_entry[0] if prev_entry else oi_now
            self._deriv_cache_set(prev_key, oi_now, ttl=3600)

            oi_change = oi_now - oi_prev
            oi_change_pct = round((oi_change / oi_prev * 100) if oi_prev else 0, 4)

            ticker = await self.get_ticker(symbol)
            price = ticker.get("price", 0) or 0
            oi_change_usd = abs(oi_change) * price

            if oi_change < 0:
                long_liq_usd = oi_change_usd
                short_liq_usd = 0.0
                direction = "long_liq"
            elif oi_change > 0:
                long_liq_usd = 0.0
                short_liq_usd = oi_change_usd
                direction = "short_liq"
            else:
                long_liq_usd = short_liq_usd = 0.0
                direction = "neutral"

            total_usd = long_liq_usd + short_liq_usd
            ts_ms = (body.get("data") or {}).get("timestamp", 0)
            ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).isoformat() if ts_ms else datetime.now(timezone.utc).isoformat()

            result = {
                "symbol": symbol,
                "long_liquidations": f"${long_liq_usd/1e6:.1f}M",
                "short_liquidations": f"${short_liq_usd/1e6:.1f}M",
                "total_liquidations": f"${total_usd/1e6:.1f}M",
                "oi_change_pct": oi_change_pct,
                "oi_direction": direction,
                "timestamp": ts,
            }
            self._deriv_cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"MEXC liquidations error for {symbol}: {e}")
            cached_fallback = self._deriv_cache.get(cache_key)
            if cached_fallback:
                return cached_fallback[0]
            return {"symbol": symbol, "error": str(e)}


# Global instance
market_intel = MarketIntelligence()
