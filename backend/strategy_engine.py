"""
ADVANCED TRADING STRATEGIES MODULE v2
More sophisticated trading strategies for Aeon

Strategies:
1. Breakout Detection - Price breaking key levels
2. Support/Resistance - Dynamic S/R levels
3. MA Crossover - Golden/Death cross signals
4. Volume Spike - Unusual volume detection
5. Bollinger Squeeze - Low volatility breakout setup
6. RSI Extremes - Oversold/Overbought with confirmation
7. MACD Histogram - Momentum shifts
8. Price Action - Engulfing, Pin bars, etc.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Advanced multi-strategy trading engine"""
    
    def __init__(self):
        self.strategies = [
            "breakout",
            "support_resistance", 
            "ma_crossover",
            "volume_spike",
            "bollinger_squeeze",
            "rsi_extreme",
            "macd_histogram",
            "price_action"
        ]
    
    async def analyze_all(self, symbol: str, ohlcv: List, ticker: Dict) -> Dict:
        """Run all strategies on a symbol"""
        if not ohlcv or len(ohlcv) < 50:
            return {"error": "Insufficient data"}
        
        results = {
            "symbol": symbol,
            "price": ticker.get("price", 0),
            "strategies": {},
            "signals": [],
            "overall_bias": "NEUTRAL",
            "confidence": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Extract OHLCV data
        closes = np.array([c[4] for c in ohlcv])
        highs = np.array([c[2] for c in ohlcv])
        lows = np.array([c[3] for c in ohlcv])
        volumes = np.array([c[5] for c in ohlcv])
        opens = np.array([c[1] for c in ohlcv])
        
        # Run each strategy
        results["strategies"]["breakout"] = self._breakout_strategy(closes, highs, lows)
        results["strategies"]["support_resistance"] = self._support_resistance(closes, highs, lows)
        results["strategies"]["ma_crossover"] = self._ma_crossover(closes)
        results["strategies"]["volume_spike"] = self._volume_spike(volumes, closes)
        results["strategies"]["bollinger_squeeze"] = self._bollinger_squeeze(closes)
        results["strategies"]["rsi_extreme"] = self._rsi_extreme(closes)
        results["strategies"]["macd_histogram"] = self._macd_histogram(closes)
        results["strategies"]["price_action"] = self._price_action(opens, closes, highs, lows)
        
        # Aggregate signals
        bullish = 0
        bearish = 0
        
        for name, strat in results["strategies"].items():
            if strat.get("signal") == "LONG":
                bullish += strat.get("strength", 1)
                results["signals"].append(f"🟢 {name.upper()}: {strat.get('reason', 'Bullish')}")
            elif strat.get("signal") == "SHORT":
                bearish += strat.get("strength", 1)
                results["signals"].append(f"🔴 {name.upper()}: {strat.get('reason', 'Bearish')}")
        
        total = bullish + bearish
        if total > 0:
            if bullish > bearish:
                results["overall_bias"] = "BULLISH"
                results["confidence"] = int((bullish / total) * 100)
            elif bearish > bullish:
                results["overall_bias"] = "BEARISH"
                results["confidence"] = int((bearish / total) * 100)
        
        return results
    
    def _breakout_strategy(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Dict:
        """Detect breakouts from consolidation"""
        # Get recent range
        lookback = 20
        recent_high = np.max(highs[-lookback:-1])
        recent_low = np.min(lows[-lookback:-1])
        current = closes[-1]
        prev = closes[-2]
        
        range_size = (recent_high - recent_low) / recent_low * 100
        
        if current > recent_high and prev <= recent_high:
            return {
                "signal": "LONG",
                "strength": 2 if range_size < 5 else 1,  # Tighter range = stronger breakout
                "reason": f"Breakout above {recent_high:.2f}",
                "level": recent_high,
                "range_pct": range_size
            }
        elif current < recent_low and prev >= recent_low:
            return {
                "signal": "SHORT",
                "strength": 2 if range_size < 5 else 1,
                "reason": f"Breakdown below {recent_low:.2f}",
                "level": recent_low,
                "range_pct": range_size
            }
        
        return {"signal": "NEUTRAL", "reason": "No breakout"}
    
    def _support_resistance(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Dict:
        """Dynamic support/resistance levels"""
        # Find pivot points
        pivots_high = []
        pivots_low = []
        
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                pivots_high.append(highs[i])
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                pivots_low.append(lows[i])
        
        current = closes[-1]
        
        # Find nearest support/resistance
        resistance = min([p for p in pivots_high if p > current], default=current * 1.05)
        support = max([p for p in pivots_low if p < current], default=current * 0.95)
        
        dist_to_support = (current - support) / current * 100
        dist_to_resistance = (resistance - current) / current * 100
        
        if dist_to_support < 1:  # Very close to support
            return {
                "signal": "LONG",
                "strength": 1,
                "reason": f"Near support at ${support:.2f}",
                "support": support,
                "resistance": resistance
            }
        elif dist_to_resistance < 1:  # Very close to resistance
            return {
                "signal": "SHORT",
                "strength": 1,
                "reason": f"Near resistance at ${resistance:.2f}",
                "support": support,
                "resistance": resistance
            }
        
        return {
            "signal": "NEUTRAL",
            "support": support,
            "resistance": resistance,
            "reason": f"S: ${support:.2f} | R: ${resistance:.2f}"
        }
    
    def _ma_crossover(self, closes: np.ndarray) -> Dict:
        """Moving average crossover signals"""
        # Calculate EMAs
        ema_9 = self._ema(closes, 9)
        ema_21 = self._ema(closes, 21)
        ema_50 = self._ema(closes, 50)
        
        current_9 = ema_9[-1]
        current_21 = ema_21[-1]
        current_50 = ema_50[-1]
        prev_9 = ema_9[-2]
        prev_21 = ema_21[-2]
        
        # Golden cross (9 crosses above 21)
        if prev_9 <= prev_21 and current_9 > current_21:
            strength = 2 if current_9 > current_50 else 1
            return {
                "signal": "LONG",
                "strength": strength,
                "reason": "EMA 9/21 Golden Cross",
                "ema_9": current_9,
                "ema_21": current_21,
                "ema_50": current_50
            }
        
        # Death cross (9 crosses below 21)
        if prev_9 >= prev_21 and current_9 < current_21:
            strength = 2 if current_9 < current_50 else 1
            return {
                "signal": "SHORT",
                "strength": strength,
                "reason": "EMA 9/21 Death Cross",
                "ema_9": current_9,
                "ema_21": current_21,
                "ema_50": current_50
            }
        
        # Trend alignment
        if current_9 > current_21 > current_50:
            return {"signal": "NEUTRAL", "reason": "Bullish alignment (no cross)"}
        elif current_9 < current_21 < current_50:
            return {"signal": "NEUTRAL", "reason": "Bearish alignment (no cross)"}
        
        return {"signal": "NEUTRAL", "reason": "No MA signal"}
    
    def _volume_spike(self, volumes: np.ndarray, closes: np.ndarray) -> Dict:
        """Detect unusual volume with price direction"""
        avg_vol = np.mean(volumes[-20:-1])
        current_vol = volumes[-1]
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1
        
        price_change = (closes[-1] - closes[-2]) / closes[-2] * 100
        
        if vol_ratio > 2:  # Volume spike
            if price_change > 0.5:
                return {
                    "signal": "LONG",
                    "strength": 2 if vol_ratio > 3 else 1,
                    "reason": f"Volume spike {vol_ratio:.1f}x with +{price_change:.2f}%",
                    "volume_ratio": vol_ratio
                }
            elif price_change < -0.5:
                return {
                    "signal": "SHORT",
                    "strength": 2 if vol_ratio > 3 else 1,
                    "reason": f"Volume spike {vol_ratio:.1f}x with {price_change:.2f}%",
                    "volume_ratio": vol_ratio
                }
        
        return {"signal": "NEUTRAL", "volume_ratio": vol_ratio, "reason": "Normal volume"}
    
    def _bollinger_squeeze(self, closes: np.ndarray) -> Dict:
        """Bollinger Band squeeze detection"""
        period = 20
        std_mult = 2
        
        sma = np.mean(closes[-period:])
        std = np.std(closes[-period:])
        
        upper = sma + (std * std_mult)
        lower = sma - (std * std_mult)
        
        bandwidth = (upper - lower) / sma * 100
        
        # Check historical bandwidth for squeeze
        bandwidths = []
        for i in range(5, len(closes) - period):
            s = np.mean(closes[i:i+period])
            st = np.std(closes[i:i+period])
            bw = ((s + st*2) - (s - st*2)) / s * 100
            bandwidths.append(bw)
        
        if bandwidths:
            avg_bandwidth = np.mean(bandwidths[-20:])
            
            if bandwidth < avg_bandwidth * 0.7:  # Squeeze detected
                current = closes[-1]
                if current > sma:
                    return {
                        "signal": "LONG",
                        "strength": 1,
                        "reason": f"BB Squeeze - Price above SMA",
                        "bandwidth": bandwidth,
                        "avg_bandwidth": avg_bandwidth
                    }
                else:
                    return {
                        "signal": "SHORT",
                        "strength": 1,
                        "reason": f"BB Squeeze - Price below SMA",
                        "bandwidth": bandwidth,
                        "avg_bandwidth": avg_bandwidth
                    }
        
        return {"signal": "NEUTRAL", "bandwidth": bandwidth, "reason": "No squeeze"}
    
    def _rsi_extreme(self, closes: np.ndarray) -> Dict:
        """RSI extreme levels with confirmation"""
        rsi = self._calculate_rsi(closes, 14)
        current_rsi = rsi[-1]
        prev_rsi = rsi[-2]
        
        price_change = (closes[-1] - closes[-2]) / closes[-2] * 100
        
        if current_rsi < 30:
            if current_rsi > prev_rsi and price_change > 0:  # RSI turning up
                return {
                    "signal": "LONG",
                    "strength": 2 if current_rsi < 20 else 1,
                    "reason": f"RSI oversold ({current_rsi:.1f}) + uptick",
                    "rsi": current_rsi
                }
            return {"signal": "NEUTRAL", "rsi": current_rsi, "reason": f"RSI oversold ({current_rsi:.1f}) - waiting confirmation"}
        
        elif current_rsi > 70:
            if current_rsi < prev_rsi and price_change < 0:  # RSI turning down
                return {
                    "signal": "SHORT",
                    "strength": 2 if current_rsi > 80 else 1,
                    "reason": f"RSI overbought ({current_rsi:.1f}) + downtick",
                    "rsi": current_rsi
                }
            return {"signal": "NEUTRAL", "rsi": current_rsi, "reason": f"RSI overbought ({current_rsi:.1f}) - waiting confirmation"}
        
        return {"signal": "NEUTRAL", "rsi": current_rsi, "reason": f"RSI neutral ({current_rsi:.1f})"}
    
    def _macd_histogram(self, closes: np.ndarray) -> Dict:
        """MACD histogram momentum shift"""
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        
        macd_line = ema_12 - ema_26
        signal_line = self._ema(macd_line, 9)
        histogram = macd_line - signal_line
        
        current_hist = histogram[-1]
        prev_hist = histogram[-2]
        prev_prev_hist = histogram[-3]
        
        # Histogram turning positive
        if prev_hist <= 0 and current_hist > 0:
            return {
                "signal": "LONG",
                "strength": 1,
                "reason": "MACD histogram turned positive",
                "histogram": current_hist,
                "macd": macd_line[-1]
            }
        
        # Histogram turning negative
        if prev_hist >= 0 and current_hist < 0:
            return {
                "signal": "SHORT",
                "strength": 1,
                "reason": "MACD histogram turned negative",
                "histogram": current_hist,
                "macd": macd_line[-1]
            }
        
        # Histogram momentum increasing
        if current_hist > 0 and current_hist > prev_hist > prev_prev_hist:
            return {"signal": "NEUTRAL", "reason": "MACD bullish momentum increasing", "histogram": current_hist}
        elif current_hist < 0 and current_hist < prev_hist < prev_prev_hist:
            return {"signal": "NEUTRAL", "reason": "MACD bearish momentum increasing", "histogram": current_hist}
        
        return {"signal": "NEUTRAL", "histogram": current_hist, "reason": "No MACD signal"}
    
    def _price_action(self, opens: np.ndarray, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Dict:
        """Candlestick pattern recognition"""
        # Get last 3 candles
        o1, o2, o3 = opens[-3], opens[-2], opens[-1]
        c1, c2, c3 = closes[-3], closes[-2], closes[-1]
        h1, h2, h3 = highs[-3], highs[-2], highs[-1]
        l1, l2, l3 = lows[-3], lows[-2], lows[-1]
        
        body3 = abs(c3 - o3)
        range3 = h3 - l3
        
        # Bullish engulfing
        if c2 < o2 and c3 > o3:  # Red then green
            if c3 > o2 and o3 < c2:  # Engulfs previous
                return {
                    "signal": "LONG",
                    "strength": 2,
                    "reason": "Bullish Engulfing pattern",
                    "pattern": "bullish_engulfing"
                }
        
        # Bearish engulfing
        if c2 > o2 and c3 < o3:  # Green then red
            if c3 < o2 and o3 > c2:  # Engulfs previous
                return {
                    "signal": "SHORT",
                    "strength": 2,
                    "reason": "Bearish Engulfing pattern",
                    "pattern": "bearish_engulfing"
                }
        
        # Pin bar / hammer (bullish)
        lower_wick = min(o3, c3) - l3
        upper_wick = h3 - max(o3, c3)
        if range3 > 0 and lower_wick / range3 > 0.6 and body3 / range3 < 0.3:
            return {
                "signal": "LONG",
                "strength": 1,
                "reason": "Bullish Pin Bar / Hammer",
                "pattern": "hammer"
            }
        
        # Shooting star (bearish)
        if range3 > 0 and upper_wick / range3 > 0.6 and body3 / range3 < 0.3:
            return {
                "signal": "SHORT",
                "strength": 1,
                "reason": "Shooting Star pattern",
                "pattern": "shooting_star"
            }
        
        return {"signal": "NEUTRAL", "reason": "No pattern detected"}
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        return ema
    
    def _calculate_rsi(self, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI"""
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros(len(closes))
        avg_loss = np.zeros(len(closes))
        
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
        
        for i in range(period + 1, len(closes)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # NEW ASYNC API METHODS FOR FRONTEND
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List:
        """Fetch OHLCV data async"""
        import asyncio
        import ccxt
        from concurrent.futures import ThreadPoolExecutor
        
        mexc = ccxt.mexc()
        executor = ThreadPoolExecutor(max_workers=2)
        
        try:
            loop = asyncio.get_running_loop()
            ohlcv = await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
            return ohlcv
        except Exception as e:
            logger.error(f"OHLCV fetch error: {e}")
            return []
    
    def _calculate_atr(self, ohlcv: List, period: int = 14) -> float:
        """Calculate ATR"""
        if len(ohlcv) < period + 1:
            return 0
        
        tr_values = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        
        return sum(tr_values[-period:]) / period
    
    async def strategy_ma_crossover(self, symbol: str, timeframe: str = "1h", 
                                     fast: int = 9, slow: int = 21) -> Dict:
        """MA Crossover strategy"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, 100)
        if len(ohlcv) < slow + 5:
            return {"error": "Insufficient data", "signal": "NEUTRAL"}
        
        closes = np.array([c[4] for c in ohlcv])
        price = closes[-1]
        
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        
        signal = "NEUTRAL"
        confidence = 50
        explanation = ""
        
        # Detect crossover
        if ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1]:
            signal = "BUY"
            confidence = 75
            explanation = f"EMA{fast} crossed above EMA{slow}"
        elif ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1]:
            signal = "SELL"
            confidence = 75
            explanation = f"EMA{fast} crossed below EMA{slow}"
        elif ema_fast[-1] > ema_slow[-1]:
            signal = "BUY"
            confidence = 60
            explanation = f"Bullish trend (EMA{fast} > EMA{slow})"
        else:
            signal = "SELL"
            confidence = 60
            explanation = f"Bearish trend (EMA{fast} < EMA{slow})"
        
        atr = self._calculate_atr(ohlcv)
        entry = price
        stop = price - (atr * 1.5) if signal == "BUY" else price + (atr * 1.5)
        target = price + (atr * 3) if signal == "BUY" else price - (atr * 3)
        
        return {
            "strategy": "MA_CROSSOVER",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "confidence": confidence,
            "price": float(price),
            "entry": float(entry),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "ema_fast": round(float(ema_fast[-1]), 2),
            "ema_slow": round(float(ema_slow[-1]), 2),
            "explanation": explanation,
            "params": {"fast": fast, "slow": slow},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def strategy_rsi_momentum(self, symbol: str, timeframe: str = "1h",
                                     oversold: int = 30, overbought: int = 70) -> Dict:
        """RSI Momentum strategy"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, 100)
        if len(ohlcv) < 20:
            return {"error": "Insufficient data", "signal": "NEUTRAL"}
        
        closes = np.array([c[4] for c in ohlcv])
        price = closes[-1]
        
        rsi = self._calculate_rsi(closes)
        current_rsi = rsi[-1]
        prev_rsi = rsi[-2]
        
        signal = "NEUTRAL"
        confidence = 50
        explanation = ""
        
        if prev_rsi < oversold and current_rsi > prev_rsi:
            signal = "BUY"
            confidence = 70
            explanation = f"RSI bouncing from oversold ({prev_rsi:.0f} -> {current_rsi:.0f})"
        elif current_rsi < 20:
            signal = "BUY"
            confidence = 80
            explanation = f"RSI extremely oversold ({current_rsi:.0f})"
        elif prev_rsi > overbought and current_rsi < prev_rsi:
            signal = "SELL"
            confidence = 70
            explanation = f"RSI rejecting from overbought ({prev_rsi:.0f} -> {current_rsi:.0f})"
        elif current_rsi > 80:
            signal = "SELL"
            confidence = 80
            explanation = f"RSI extremely overbought ({current_rsi:.0f})"
        
        atr = self._calculate_atr(ohlcv)
        entry = price
        stop = price - (atr * 1.5) if signal == "BUY" else price + (atr * 1.5)
        target = price + (atr * 2.5) if signal == "BUY" else price - (atr * 2.5)
        
        return {
            "strategy": "RSI_MOMENTUM",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "confidence": min(confidence, 95),
            "price": float(price),
            "entry": float(entry),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "rsi": round(float(current_rsi), 2),
            "prev_rsi": round(float(prev_rsi), 2),
            "explanation": explanation,
            "params": {"oversold": oversold, "overbought": overbought},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def strategy_breakout(self, symbol: str, timeframe: str = "4h", lookback: int = 20) -> Dict:
        """Breakout strategy"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, lookback + 10)
        if len(ohlcv) < lookback + 5:
            return {"error": "Insufficient data", "signal": "NEUTRAL"}
        
        highs = [c[2] for c in ohlcv[-lookback-1:-1]]
        lows = [c[3] for c in ohlcv[-lookback-1:-1]]
        volumes = [c[5] for c in ohlcv[-lookback-1:-1]]
        
        resistance = max(highs)
        support = min(lows)
        avg_volume = sum(volumes) / len(volumes)
        
        current = ohlcv[-1]
        price = current[4]
        current_volume = current[5]
        volume_mult = current_volume / avg_volume if avg_volume > 0 else 1
        
        signal = "NEUTRAL"
        confidence = 50
        explanation = ""
        
        if price > resistance:
            signal = "BUY"
            confidence = 70 if volume_mult > 1.5 else 60
            explanation = f"BREAKOUT above ${resistance:,.0f}" + (f" with {volume_mult:.1f}x volume" if volume_mult > 1.5 else "")
        elif price < support:
            signal = "SELL"
            confidence = 70 if volume_mult > 1.5 else 60
            explanation = f"BREAKDOWN below ${support:,.0f}" + (f" with {volume_mult:.1f}x volume" if volume_mult > 1.5 else "")
        elif price > resistance * 0.99:
            signal = "BUY"
            confidence = 55
            explanation = f"Testing resistance ${resistance:,.0f}"
        elif price < support * 1.01:
            signal = "SELL"
            confidence = 55
            explanation = f"Testing support ${support:,.0f}"
        
        atr = self._calculate_atr(ohlcv)
        range_size = resistance - support
        entry = price
        stop = support - (atr * 0.5) if signal == "BUY" else resistance + (atr * 0.5)
        target = price + range_size if signal == "BUY" else price - range_size
        
        return {
            "strategy": "BREAKOUT",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "confidence": min(confidence, 95),
            "price": float(price),
            "entry": float(entry),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "resistance": round(resistance, 2),
            "support": round(support, 2),
            "range_pct": round(((resistance - support) / support) * 100, 2),
            "volume_mult": round(volume_mult, 2),
            "explanation": explanation,
            "params": {"lookback": lookback},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def strategy_bb_squeeze(self, symbol: str, timeframe: str = "4h") -> Dict:
        """Bollinger Band Squeeze strategy"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, 50)
        if len(ohlcv) < 30:
            return {"error": "Insufficient data", "signal": "NEUTRAL"}
        
        closes = np.array([c[4] for c in ohlcv])
        price = closes[-1]
        
        period = 20
        sma = np.mean(closes[-period:])
        std = np.std(closes[-period:])
        
        upper = sma + (2 * std)
        lower = sma - (2 * std)
        bandwidth = ((upper - lower) / sma) * 100
        
        signal = "NEUTRAL"
        confidence = 50
        explanation = ""
        
        if bandwidth < 5:
            if price > sma:
                signal = "BUY"
                confidence = 70
                explanation = f"BB squeeze (BW: {bandwidth:.1f}%) - expect upside expansion"
            else:
                signal = "SELL"
                confidence = 70
                explanation = f"BB squeeze (BW: {bandwidth:.1f}%) - expect downside expansion"
        elif price >= upper:
            signal = "SELL"
            confidence = 65
            explanation = f"Price at upper BB - overbought"
        elif price <= lower:
            signal = "BUY"
            confidence = 65
            explanation = f"Price at lower BB - oversold"
        
        atr = self._calculate_atr(ohlcv)
        entry = price
        stop = lower - (atr * 0.5) if signal == "BUY" else upper + (atr * 0.5)
        target = upper if signal == "BUY" else lower
        
        return {
            "strategy": "BB_SQUEEZE",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "confidence": min(confidence, 95),
            "price": float(price),
            "entry": float(entry),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "bb_upper": round(upper, 2),
            "bb_middle": round(float(sma), 2),
            "bb_lower": round(lower, 2),
            "bandwidth": round(bandwidth, 2),
            "explanation": explanation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def strategy_macd_reversal(self, symbol: str, timeframe: str = "4h") -> Dict:
        """MACD Histogram Reversal strategy"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, 50)
        if len(ohlcv) < 35:
            return {"error": "Insufficient data", "signal": "NEUTRAL"}
        
        closes = np.array([c[4] for c in ohlcv])
        price = closes[-1]
        
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        
        macd_line = ema_12 - ema_26
        signal_line = self._ema(macd_line, 9)
        histogram = macd_line - signal_line
        
        hist = histogram[-1]
        prev_hist = histogram[-2]
        
        signal = "NEUTRAL"
        confidence = 50
        explanation = ""
        
        if prev_hist < 0 and hist > 0:
            signal = "BUY"
            confidence = 75
            explanation = f"MACD histogram turned positive"
        elif prev_hist > 0 and hist < 0:
            signal = "SELL"
            confidence = 75
            explanation = f"MACD histogram turned negative"
        elif hist > prev_hist and hist > 0:
            signal = "BUY"
            confidence = 60
            explanation = f"MACD momentum strengthening"
        elif hist < prev_hist and hist < 0:
            signal = "SELL"
            confidence = 60
            explanation = f"MACD momentum weakening"
        
        atr = self._calculate_atr(ohlcv)
        entry = price
        stop = price - (atr * 2) if signal == "BUY" else price + (atr * 2)
        target = price + (atr * 3) if signal == "BUY" else price - (atr * 3)
        
        return {
            "strategy": "MACD_REVERSAL",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "confidence": min(confidence, 95),
            "price": float(price),
            "entry": float(entry),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "macd_line": round(float(macd_line[-1]), 6),
            "signal_line": round(float(signal_line[-1]), 6),
            "histogram": round(float(hist), 6),
            "explanation": explanation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def strategy_trend_pullback(self, symbol: str, timeframe: str = "4h") -> Dict:
        """Trend Pullback strategy"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, 60)
        if len(ohlcv) < 50:
            return {"error": "Insufficient data", "signal": "NEUTRAL"}
        
        closes = np.array([c[4] for c in ohlcv])
        price = closes[-1]
        
        ema_21 = self._ema(closes, 21)
        ema_50 = self._ema(closes, 50)
        
        current_21 = ema_21[-1]
        current_50 = ema_50[-1]
        
        uptrend = current_21 > current_50
        distance_pct = ((price - current_21) / current_21) * 100
        
        signal = "NEUTRAL"
        confidence = 50
        explanation = ""
        
        if uptrend and -2 < distance_pct < 1:
            signal = "BUY"
            confidence = 70
            explanation = f"Uptrend pullback to EMA21 (${current_21:,.0f})"
        elif not uptrend and -1 < distance_pct < 2:
            signal = "SELL"
            confidence = 70
            explanation = f"Downtrend pullback to EMA21 (${current_21:,.0f})"
        
        atr = self._calculate_atr(ohlcv)
        entry = price
        stop = current_21 - (atr * 1.5) if signal == "BUY" else current_21 + (atr * 1.5)
        target = price + (atr * 3) if signal == "BUY" else price - (atr * 3)
        
        return {
            "strategy": "TREND_PULLBACK",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "confidence": min(confidence, 95),
            "price": float(price),
            "entry": float(entry),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "ema_21": round(float(current_21), 2),
            "ema_50": round(float(current_50), 2),
            "trend": "UPTREND" if uptrend else "DOWNTREND",
            "distance_pct": round(distance_pct, 2),
            "explanation": explanation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def scan_all_strategies(self, symbol: str, timeframe: str = "4h") -> Dict:
        """Run all strategies and return combined results"""
        import asyncio
        
        tasks = [
            self.strategy_ma_crossover(symbol, timeframe),
            self.strategy_rsi_momentum(symbol, timeframe),
            self.strategy_breakout(symbol, timeframe),
            self.strategy_bb_squeeze(symbol, timeframe),
            self.strategy_macd_reversal(symbol, timeframe),
            self.strategy_trend_pullback(symbol, timeframe),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        strategies = []
        buy_count = 0
        sell_count = 0
        total_confidence = 0
        valid_count = 0
        
        for r in results:
            if isinstance(r, Exception):
                continue
            if "error" not in r:
                strategies.append(r)
                valid_count += 1
                total_confidence += r.get("confidence", 50)
                if r.get("signal") == "BUY":
                    buy_count += 1
                elif r.get("signal") == "SELL":
                    sell_count += 1
        
        if buy_count >= 3:
            overall = "STRONG_BUY"
        elif sell_count >= 3:
            overall = "STRONG_SELL"
        elif buy_count > sell_count:
            overall = "BUY"
        elif sell_count > buy_count:
            overall = "SELL"
        else:
            overall = "NEUTRAL"
        
        avg_confidence = total_confidence / valid_count if valid_count > 0 else 50
        
        best_strategy = None
        for s in sorted(strategies, key=lambda x: x.get("confidence", 0), reverse=True):
            if s.get("signal") != "NEUTRAL":
                best_strategy = s
                break
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "overall_signal": overall,
            "average_confidence": round(avg_confidence, 1),
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "neutral_signals": valid_count - buy_count - sell_count,
            "best_strategy": best_strategy,
            "strategies": strategies,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
strategy_engine = StrategyEngine()
