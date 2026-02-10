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


# Global instance
strategy_engine = StrategyEngine()
