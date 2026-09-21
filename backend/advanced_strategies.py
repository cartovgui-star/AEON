"""
Advanced Trading Strategies Module
- Divergence Detection (RSI, MACD, Hidden)
- Market Structure (HH/HL/LH/LL, BOS, CHoCH)
- VWAP Calculations
- Smart Money Concepts
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import ccxt
from okx_rate_limiter import OKX_SEM

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)

# Initialize OKX
okx = ccxt.okx({'enableRateLimit': True})


class AdvancedStrategies:
    """Advanced trading strategy analysis"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60  # 1 minute cache
    
    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None
    
    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())
    
    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List:
        """Fetch OHLCV data"""
        cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            loop = asyncio.get_running_loop()
            def _fetch():
                with OKX_SEM:
                    return okx.fetch_ohlcv(symbol, timeframe, limit=limit)
            ohlcv = await loop.run_in_executor(executor, _fetch)
            self._cache_set(cache_key, ohlcv)
            return ohlcv
        except Exception as e:
            logger.error(f"OHLCV fetch error {symbol}: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DIVERGENCE DETECTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def calculate_rsi(self, closes: List[float], period: int = 14) -> List[float]:
        """Calculate RSI values"""
        if len(closes) < period + 1:
            return []
        
        rsi_values = []
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        for i in range(period - 1, len(gains)):
            avg_gain = sum(gains[i-period+1:i+1]) / period
            avg_loss = sum(losses[i-period+1:i+1]) / period
            
            if avg_loss == 0:
                rsi_values.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))
        
        return rsi_values
    
    def calculate_macd(self, closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Calculate MACD values"""
        if len(closes) < slow + signal:
            return {"macd": [], "signal": [], "histogram": []}
        
        def ema(data, period):
            ema_values = [sum(data[:period]) / period]
            multiplier = 2 / (period + 1)
            for price in data[period:]:
                ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values
        
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        
        # Align arrays
        diff = len(ema_fast) - len(ema_slow)
        macd_line = [ema_fast[i + diff] - ema_slow[i] for i in range(len(ema_slow))]
        
        signal_line = ema(macd_line, signal)
        
        # Align for histogram
        diff2 = len(macd_line) - len(signal_line)
        histogram = [macd_line[i + diff2] - signal_line[i] for i in range(len(signal_line))]
        
        return {
            "macd": macd_line[-len(histogram):],
            "signal": signal_line,
            "histogram": histogram
        }
    
    def find_peaks_troughs(self, data: List[float], lookback: int = 5) -> Tuple[List[int], List[int]]:
        """Find local peaks and troughs in data"""
        peaks = []
        troughs = []
        
        for i in range(lookback, len(data) - lookback):
            # Check if peak
            is_peak = all(data[i] > data[i-j] for j in range(1, lookback + 1)) and \
                      all(data[i] > data[i+j] for j in range(1, lookback + 1))
            if is_peak:
                peaks.append(i)
            
            # Check if trough
            is_trough = all(data[i] < data[i-j] for j in range(1, lookback + 1)) and \
                        all(data[i] < data[i+j] for j in range(1, lookback + 1))
            if is_trough:
                troughs.append(i)
        
        return peaks, troughs
    
    async def detect_divergence(self, symbol: str, timeframe: str = "1h") -> Dict:
        """
        Detect RSI and MACD divergences
        
        Regular Bullish: Price makes Lower Low, RSI makes Higher Low (reversal UP)
        Regular Bearish: Price makes Higher High, RSI makes Lower High (reversal DOWN)
        Hidden Bullish: Price makes Higher Low, RSI makes Lower Low (continuation UP)
        Hidden Bearish: Price makes Lower High, RSI makes Higher High (continuation DOWN)
        """
        ohlcv = await self.get_ohlcv(symbol, timeframe, 100)
        if len(ohlcv) < 50:
            return {"divergences": [], "error": "Insufficient data"}
        
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        
        rsi = self.calculate_rsi(closes)
        macd_data = self.calculate_macd(closes)
        
        divergences = []
        
        # Find peaks and troughs in price and RSI
        price_peaks, price_troughs = self.find_peaks_troughs(closes[-len(rsi):], 3)
        rsi_peaks, rsi_troughs = self.find_peaks_troughs(rsi, 3)
        
        # Check for Regular Bullish Divergence (price LL, RSI HL)
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
            recent_price_troughs = price_troughs[-2:]
            recent_rsi_troughs = rsi_troughs[-2:]
            
            price_values = [closes[-len(rsi):][i] for i in recent_price_troughs]
            rsi_values = [rsi[i] for i in recent_rsi_troughs]
            
            if price_values[-1] < price_values[-2] and rsi_values[-1] > rsi_values[-2]:
                divergences.append({
                    "type": "REGULAR_BULLISH",
                    "indicator": "RSI",
                    "signal": "BUY",
                    "strength": "STRONG",
                    "description": "Price Lower Low + RSI Higher Low = Reversal UP likely"
                })
        
        # Check for Regular Bearish Divergence (price HH, RSI LH)
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            recent_price_peaks = price_peaks[-2:]
            recent_rsi_peaks = rsi_peaks[-2:]
            
            price_values = [closes[-len(rsi):][i] for i in recent_price_peaks]
            rsi_values = [rsi[i] for i in recent_rsi_peaks]
            
            if price_values[-1] > price_values[-2] and rsi_values[-1] < rsi_values[-2]:
                divergences.append({
                    "type": "REGULAR_BEARISH",
                    "indicator": "RSI",
                    "signal": "SELL",
                    "strength": "STRONG",
                    "description": "Price Higher High + RSI Lower High = Reversal DOWN likely"
                })
        
        # Check for Hidden Bullish (price HL, RSI LL) - trend continuation
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
            recent_price_troughs = price_troughs[-2:]
            recent_rsi_troughs = rsi_troughs[-2:]
            
            price_values = [closes[-len(rsi):][i] for i in recent_price_troughs]
            rsi_values = [rsi[i] for i in recent_rsi_troughs]
            
            if price_values[-1] > price_values[-2] and rsi_values[-1] < rsi_values[-2]:
                divergences.append({
                    "type": "HIDDEN_BULLISH",
                    "indicator": "RSI",
                    "signal": "BUY",
                    "strength": "MODERATE",
                    "description": "Price Higher Low + RSI Lower Low = Uptrend continuation"
                })
        
        # Check for Hidden Bearish (price LH, RSI HH)
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            recent_price_peaks = price_peaks[-2:]
            recent_rsi_peaks = rsi_peaks[-2:]
            
            price_values = [closes[-len(rsi):][i] for i in recent_price_peaks]
            rsi_values = [rsi[i] for i in recent_rsi_peaks]
            
            if price_values[-1] < price_values[-2] and rsi_values[-1] > rsi_values[-2]:
                divergences.append({
                    "type": "HIDDEN_BEARISH",
                    "indicator": "RSI",
                    "signal": "SELL",
                    "strength": "MODERATE",
                    "description": "Price Lower High + RSI Higher High = Downtrend continuation"
                })
        
        # MACD Divergence check
        if len(macd_data["histogram"]) > 20:
            macd_hist = macd_data["histogram"]
            macd_peaks, macd_troughs = self.find_peaks_troughs(macd_hist, 3)
            
            # MACD Bullish Divergence
            if len(price_troughs) >= 2 and len(macd_troughs) >= 2:
                price_values = [closes[-len(macd_hist):][i] if i < len(closes[-len(macd_hist):]) else 0 for i in price_troughs[-2:]]
                macd_values = [macd_hist[i] if i < len(macd_hist) else 0 for i in macd_troughs[-2:]]
                
                if len(price_values) == 2 and len(macd_values) == 2:
                    if price_values[-1] < price_values[-2] and macd_values[-1] > macd_values[-2]:
                        divergences.append({
                            "type": "REGULAR_BULLISH",
                            "indicator": "MACD",
                            "signal": "BUY",
                            "strength": "STRONG",
                            "description": "MACD Histogram showing bullish divergence"
                        })
        
        # Current RSI and MACD values
        current_rsi = rsi[-1] if rsi else 50
        current_macd = macd_data["histogram"][-1] if macd_data["histogram"] else 0
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "divergences": divergences,
            "has_divergence": len(divergences) > 0,
            "current_rsi": round(current_rsi, 2),
            "current_macd_hist": round(current_macd, 6),
            "signal": divergences[0]["signal"] if divergences else "NONE",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MARKET STRUCTURE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def analyze_market_structure(self, symbol: str, timeframe: str = "1h") -> Dict:
        """
        Analyze market structure:
        - HH/HL = Uptrend
        - LH/LL = Downtrend
        - Mixed = Range/Consolidation
        - BOS (Break of Structure)
        - CHoCH (Change of Character)
        """
        ohlcv = await self.get_ohlcv(symbol, timeframe, 100)
        if len(ohlcv) < 30:
            return {"error": "Insufficient data"}
        
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        
        # Find swing highs and swing lows
        swing_highs = []
        swing_lows = []
        lookback = 5
        
        for i in range(lookback, len(highs) - lookback):
            # Swing high
            if all(highs[i] > highs[i-j] for j in range(1, lookback+1)) and \
               all(highs[i] > highs[i+j] for j in range(1, lookback+1)):
                swing_highs.append({"index": i, "price": highs[i]})
            
            # Swing low
            if all(lows[i] < lows[i-j] for j in range(1, lookback+1)) and \
               all(lows[i] < lows[i+j] for j in range(1, lookback+1)):
                swing_lows.append({"index": i, "price": lows[i]})
        
        # Determine trend based on swing points
        trend = "RANGING"
        structure_points = []
        
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            recent_highs = swing_highs[-3:]
            recent_lows = swing_lows[-3:]
            
            # Check for Higher Highs and Higher Lows (Uptrend)
            hh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i]["price"] > recent_highs[i-1]["price"])
            hl_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i]["price"] > recent_lows[i-1]["price"])
            
            # Check for Lower Highs and Lower Lows (Downtrend)
            lh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i]["price"] < recent_highs[i-1]["price"])
            ll_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i]["price"] < recent_lows[i-1]["price"])
            
            if hh_count >= 1 and hl_count >= 1:
                trend = "UPTREND"
                structure_points = ["HH", "HL"]
            elif lh_count >= 1 and ll_count >= 1:
                trend = "DOWNTREND"
                structure_points = ["LH", "LL"]
            else:
                trend = "RANGING"
                structure_points = ["MIXED"]
        
        # Detect Break of Structure (BOS)
        bos = None
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            last_swing_high = swing_highs[-1]["price"]
            last_swing_low = swing_lows[-1]["price"]
            current_price = closes[-1]
            
            # Bullish BOS - price breaks above recent swing high
            if current_price > last_swing_high and trend != "UPTREND":
                bos = {
                    "type": "BULLISH_BOS",
                    "level": last_swing_high,
                    "description": "Price broke above swing high - potential trend change to bullish"
                }
            
            # Bearish BOS - price breaks below recent swing low
            elif current_price < last_swing_low and trend != "DOWNTREND":
                bos = {
                    "type": "BEARISH_BOS",
                    "level": last_swing_low,
                    "description": "Price broke below swing low - potential trend change to bearish"
                }
        
        # Calculate support and resistance from structure
        support = min([s["price"] for s in swing_lows[-3:]]) if swing_lows else lows[-1]
        resistance = max([s["price"] for s in swing_highs[-3:]]) if swing_highs else highs[-1]
        
        # Range detection
        is_ranging = False
        range_size = 0
        if len(closes) > 20:
            recent_high = max(highs[-20:])
            recent_low = min(lows[-20:])
            range_size = ((recent_high - recent_low) / recent_low) * 100
            is_ranging = range_size < 5  # Less than 5% range = consolidation
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": trend,
            "structure": structure_points,
            "swing_highs": [{"price": sh["price"]} for sh in swing_highs[-3:]],
            "swing_lows": [{"price": sl["price"]} for sl in swing_lows[-3:]],
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "is_ranging": is_ranging,
            "range_pct": round(range_size, 2),
            "bos": bos,
            "current_price": closes[-1],
            "bias": "BULLISH" if trend == "UPTREND" else "BEARISH" if trend == "DOWNTREND" else "NEUTRAL",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VWAP CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def calculate_vwap(self, symbol: str, timeframe: str = "1h") -> Dict:
        """
        Calculate VWAP (Volume Weighted Average Price)
        - Price above VWAP = Bullish bias
        - Price below VWAP = Bearish bias
        - VWAP acts as dynamic support/resistance
        """
        ohlcv = await self.get_ohlcv(symbol, timeframe, 100)
        if len(ohlcv) < 20:
            return {"error": "Insufficient data"}
        
        # Calculate VWAP
        cumulative_volume = 0
        cumulative_vwap = 0
        vwap_values = []
        
        for candle in ohlcv:
            typical_price = (candle[2] + candle[3] + candle[4]) / 3  # (H+L+C)/3
            volume = candle[5]
            
            cumulative_volume += volume
            cumulative_vwap += typical_price * volume
            
            if cumulative_volume > 0:
                vwap = cumulative_vwap / cumulative_volume
                vwap_values.append(vwap)
            else:
                vwap_values.append(typical_price)
        
        current_vwap = vwap_values[-1]
        current_price = ohlcv[-1][4]
        
        # Calculate standard deviation bands
        typical_prices = [(c[2] + c[3] + c[4]) / 3 for c in ohlcv]
        variance = sum((tp - current_vwap) ** 2 for tp in typical_prices[-20:]) / 20
        std_dev = variance ** 0.5
        
        upper_band_1 = current_vwap + std_dev
        lower_band_1 = current_vwap - std_dev
        upper_band_2 = current_vwap + (2 * std_dev)
        lower_band_2 = current_vwap - (2 * std_dev)
        
        # Determine bias
        distance_pct = ((current_price - current_vwap) / current_vwap) * 100
        
        if current_price > upper_band_1:
            bias = "STRONG_BULLISH"
            signal = "Overextended above VWAP - potential pullback to VWAP"
        elif current_price > current_vwap:
            bias = "BULLISH"
            signal = "Price above VWAP - institutional buyers in control"
        elif current_price < lower_band_1:
            bias = "STRONG_BEARISH"
            signal = "Overextended below VWAP - potential bounce to VWAP"
        elif current_price < current_vwap:
            bias = "BEARISH"
            signal = "Price below VWAP - institutional sellers in control"
        else:
            bias = "NEUTRAL"
            signal = "Price at VWAP - equilibrium zone"
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "vwap": round(current_vwap, 2),
            "current_price": round(current_price, 2),
            "distance_pct": round(distance_pct, 2),
            "upper_band_1": round(upper_band_1, 2),
            "lower_band_1": round(lower_band_1, 2),
            "upper_band_2": round(upper_band_2, 2),
            "lower_band_2": round(lower_band_2, 2),
            "bias": bias,
            "signal": signal,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMPREHENSIVE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_full_analysis(self, symbol: str, timeframe: str = "1h") -> Dict:
        """Get complete advanced analysis for a symbol"""
        tasks = [
            self.detect_divergence(symbol, timeframe),
            self.analyze_market_structure(symbol, timeframe),
            self.calculate_vwap(symbol, timeframe),
        ]
        
        divergence, structure, vwap = await asyncio.gather(*tasks, return_exceptions=True)
        
        if isinstance(divergence, Exception):
            divergence = {"error": str(divergence)}
        if isinstance(structure, Exception):
            structure = {"error": str(structure)}
        if isinstance(vwap, Exception):
            vwap = {"error": str(vwap)}
        
        # Calculate overall signal
        signals = []
        if divergence.get("has_divergence"):
            signals.append(divergence.get("signal"))
        if structure.get("bias") in ["BULLISH", "BEARISH"]:
            signals.append("BUY" if structure["bias"] == "BULLISH" else "SELL")
        if vwap.get("bias") in ["BULLISH", "STRONG_BULLISH"]:
            signals.append("BUY")
        elif vwap.get("bias") in ["BEARISH", "STRONG_BEARISH"]:
            signals.append("SELL")
        
        # Determine confluence
        buy_signals = signals.count("BUY")
        sell_signals = signals.count("SELL")
        
        if buy_signals >= 2:
            overall_signal = "STRONG_BUY"
            confidence = min(90, 60 + (buy_signals * 15))
        elif sell_signals >= 2:
            overall_signal = "STRONG_SELL"
            confidence = min(90, 60 + (sell_signals * 15))
        elif buy_signals > sell_signals:
            overall_signal = "BUY"
            confidence = 55
        elif sell_signals > buy_signals:
            overall_signal = "SELL"
            confidence = 55
        else:
            overall_signal = "NEUTRAL"
            confidence = 50
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "overall_signal": overall_signal,
            "confidence": confidence,
            "divergence": divergence,
            "market_structure": structure,
            "vwap": vwap,
            "signals_breakdown": {
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "total_signals": len(signals)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
advanced_strategies = AdvancedStrategies()
