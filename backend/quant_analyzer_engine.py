"""
QUANT ANALYZER ENGINE
=====================
Senior quantitative analyst-grade multi-factor technical scoring system.
Pure analysis engine — no trading, no signals routed, no paper trades.

Covers per coin:
  1. Trend Structure    - 1H / 4H / 1D / 1W alignment
  2. Key Levels         - Support / resistance zones from swing pivots
  3. Moving Averages    - EMA 20 / 50 / 100 / 200 positioning + crossovers
  4. Momentum           - RSI (+ divergence), MACD, Stochastic RSI
  5. Volume Analysis    - OBV trend, accumulation/distribution, anomalies
  6. Chart Patterns     - Flags, wedges, triangles, H&S, cup & handle
  7. Fibonacci Levels   - Retracement + extension from last significant swing
  8. Volatility         - Bollinger Band width, ATR
  9. Trade Plan         - Entry, SL, TP1/TP2/TP3, R:R
 10. Score & Signal     - 1-10 score, Strong Buy → Strong Sell

Output: ranked report sorted by score desc, watchlist summary table.
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import ccxt

logger = logging.getLogger(__name__)

# ─────────────────────────── helpers ──────────────────────────────────────────

def _sym(raw: str) -> str:
    """Normalize to CCXT format BTC/USDT."""
    s = raw.upper().replace("-", "").replace("/", "")
    coin = s.replace("USDT", "") if s.endswith("USDT") else s
    return f"{coin}/USDT"


def _ema(series: np.ndarray, period: int) -> np.ndarray:
    k = 2 / (period + 1)
    out = np.zeros_like(series, dtype=float)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = series[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.zeros(len(close))
    avg_loss = np.zeros(len(close))
    avg_gain[period] = np.mean(gain[:period])
    avg_loss[period] = np.mean(loss[:period])
    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i - 1]) / period
    rs = np.where(avg_loss == 0, 100.0, avg_gain / avg_loss)
    rsi = 100 - (100 / (1 + rs))
    rsi[:period] = np.nan
    return rsi


def _macd(close: np.ndarray, fast=12, slow=26, signal=9):
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _stoch_rsi(close: np.ndarray, period=14, k=3, d=3) -> Tuple[np.ndarray, np.ndarray]:
    rsi = _rsi(close, period)
    stoch = np.zeros_like(rsi)
    for i in range(period, len(rsi)):
        window = rsi[i - period + 1: i + 1]
        if np.all(np.isnan(window)):
            stoch[i] = np.nan
            continue
        lo, hi = np.nanmin(window), np.nanmax(window)
        stoch[i] = 0.0 if hi == lo else (rsi[i] - lo) / (hi - lo) * 100
    k_line = np.full_like(stoch, np.nan)
    for i in range(k - 1, len(stoch)):
        w = stoch[i - k + 1: i + 1]
        if not np.any(np.isnan(w)):
            k_line[i] = np.mean(w)
    d_line = np.full_like(k_line, np.nan)
    for i in range(d - 1, len(k_line)):
        w = k_line[i - d + 1: i + 1]
        if not np.any(np.isnan(w)):
            d_line[i] = np.mean(w)
    return k_line, d_line


def _bb(close: np.ndarray, period=20, std_mult=2.0):
    mid = np.full_like(close, np.nan)
    upper = np.full_like(close, np.nan)
    lower = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        w = close[i - period + 1: i + 1]
        m = np.mean(w)
        s = np.std(w)
        mid[i] = m
        upper[i] = m + std_mult * s
        lower[i] = m - std_mult * s
    return upper, mid, lower


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period=14) -> np.ndarray:
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])))
    atr = np.zeros(len(close))
    atr[period] = np.mean(tr[:period])
    for i in range(period + 1, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i - 1]) / period
    atr[:period] = np.nan
    return atr


def _obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    obv = np.zeros(len(close))
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def _swing_highs(high: np.ndarray, lookback=5) -> List[int]:
    idx = []
    for i in range(lookback, len(high) - lookback):
        if high[i] == np.max(high[i - lookback: i + lookback + 1]):
            idx.append(i)
    return idx


def _swing_lows(low: np.ndarray, lookback=5) -> List[int]:
    idx = []
    for i in range(lookback, len(low) - lookback):
        if low[i] == np.min(low[i - lookback: i + lookback + 1]):
            idx.append(i)
    return idx


# ─────────────────────── single-coin analysis ─────────────────────────────────

class CoinAnalyzer:

    TIMEFRAMES = ["1h", "4h", "1d", "1w"]
    TF_LABELS  = {"1h": "1H", "4h": "4H", "1d": "Daily", "1w": "Weekly"}
    TF_LIMIT   = {"1h": 200, "4h": 200, "1d": 200, "1w": 104}

    def __init__(self):
        self._exchange = ccxt.okx({"enableRateLimit": True})

    # ── data ──────────────────────────────────────────────────────────────────

    def _fetch(self, symbol: str, tf: str) -> Optional[pd.DataFrame]:
        try:
            raw = self._exchange.fetch_ohlcv(_sym(symbol), tf, limit=self.TF_LIMIT[tf])
            if not raw or len(raw) < 50:
                return None
            df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
            df = df.astype({"open": float, "high": float, "low": float,
                            "close": float, "volume": float})
            return df
        except Exception as e:
            logger.warning(f"Fetch {symbol} {tf}: {e}")
            return None

    # ── trend structure ────────────────────────────────────────────────────────

    def _trend(self, df: pd.DataFrame) -> Dict:
        c  = df["close"].values
        e20  = _ema(c, 20)
        e50  = _ema(c, 50)
        e200 = _ema(c, 200)
        last = c[-1]

        price_vs_e200 = "above" if last > e200[-1] else "below"
        e20_vs_e50    = "bullish" if e20[-1] > e50[-1] else "bearish"

        # slope of last 20 bars of EMA 20 in % (10 was too noisy, one spike skewed it)
        slope = (e20[-1] - e20[-20]) / e20[-20] * 100 if len(e20) >= 20 and e20[-20] != 0 else 0

        if slope > 0.5 and e20[-1] > e50[-1]:
            direction = "BULLISH"
            strength  = "Strong" if slope > 2 else "Moderate"
        elif slope < -0.5 and e20[-1] < e50[-1]:
            direction = "BEARISH"
            strength  = "Strong" if slope < -2 else "Moderate"
        else:
            direction = "NEUTRAL"
            strength  = "Weak"

        return {
            "direction": direction,
            "strength":  strength,
            "price_vs_ema200": price_vs_e200,
            "ema20_vs_ema50":  e20_vs_e50,
            "slope_pct": round(slope, 3),
        }

    # ── key levels ────────────────────────────────────────────────────────────

    def _key_levels(self, df: pd.DataFrame, current_price: float) -> Dict:
        h, l = df["high"].values, df["low"].values
        # lookback=20 — 5-bar was too tight, missed real S/R levels
        sh_idx = _swing_highs(h, lookback=20)
        sl_idx = _swing_lows(l,  lookback=20)

        resistances = sorted(set(round(h[i], 6) for i in sh_idx), reverse=True)
        supports    = sorted(set(round(l[i], 6) for i in sl_idx))

        # nearest levels
        nearest_res = next((r for r in resistances if r > current_price), None)
        nearest_sup = next((s for s in reversed(supports) if s < current_price), None)

        # most critical = the one closest to price
        dist_r = abs(nearest_res - current_price) / current_price if nearest_res else 999
        dist_s = abs(nearest_sup - current_price) / current_price if nearest_sup else 999
        critical = nearest_res if dist_r < dist_s else nearest_sup
        critical_type = "resistance" if dist_r < dist_s else "support"

        return {
            "resistances": resistances[:5],
            "supports":    supports[-5:],
            "nearest_resistance": nearest_res,
            "nearest_support":    nearest_sup,
            "critical_level": critical,
            "critical_type": critical_type,
            "dist_to_resistance_pct": round(dist_r * 100, 2) if nearest_res else None,
            "dist_to_support_pct":    round(dist_s * 100, 2) if nearest_sup else None,
        }

    # ── moving averages ───────────────────────────────────────────────────────

    def _moving_averages(self, df: pd.DataFrame) -> Dict:
        c = df["close"].values
        last = c[-1]
        emas = {p: _ema(c, p) for p in [20, 50, 100, 200]}

        positions = {}
        for p, arr in emas.items():
            positions[f"ema{p}"] = {
                "value": round(arr[-1], 6),
                "price_vs": "above" if last > arr[-1] else "below",
                "gap_pct":  round((last - arr[-1]) / arr[-1] * 100, 2) if arr[-1] != 0 else 0.0,
            }

        # crossovers: check last 5 bars
        crossovers = []
        for fast, slow in [(20, 50), (50, 100), (50, 200), (100, 200)]:
            fa, sa = emas[fast], emas[slow]
            if fa[-2] < sa[-2] and fa[-1] > sa[-1]:
                crossovers.append({"type": "golden", "fast": fast, "slow": slow, "bars_ago": 0})
            elif fa[-2] > sa[-2] and fa[-1] < sa[-1]:
                crossovers.append({"type": "death", "fast": fast, "slow": slow, "bars_ago": 0})
            else:
                for k in range(2, 6):
                    if len(fa) > k:
                        if fa[-(k+1)] < sa[-(k+1)] and fa[-k] > sa[-k]:
                            crossovers.append({"type": "golden", "fast": fast, "slow": slow, "bars_ago": k - 1})
                            break
                        elif fa[-(k+1)] > sa[-(k+1)] and fa[-k] < sa[-k]:
                            crossovers.append({"type": "death", "fast": fast, "slow": slow, "bars_ago": k - 1})
                            break

        # stacked bull/bear
        vals = [emas[p][-1] for p in [20, 50, 100, 200]]
        stacked = "bullish" if vals == sorted(vals, reverse=True) else (
                  "bearish" if vals == sorted(vals) else "mixed")

        return {
            "positions": positions,
            "crossovers": crossovers,
            "stack": stacked,
        }

    # ── momentum ──────────────────────────────────────────────────────────────

    def _momentum(self, df: pd.DataFrame) -> Dict:
        c = df["close"].values

        # RSI
        rsi = _rsi(c, 14)
        rsi_val = float(rsi[-1]) if not np.isnan(rsi[-1]) else 50.0

        if rsi_val >= 70:
            rsi_state = "overbought"
        elif rsi_val <= 30:
            rsi_state = "oversold"
        elif rsi_val > 55:
            rsi_state = "bullish"
        elif rsi_val < 45:
            rsi_state = "bearish"
        else:
            rsi_state = "neutral"

        # RSI divergence (last 20 bars)
        rsi_div = self._detect_divergence(c[-20:], rsi[-20:])

        # MACD
        macd_l, sig_l, hist = _macd(c)
        macd_cross = "bullish" if macd_l[-1] > sig_l[-1] else "bearish"
        hist_dir = "expanding_bullish" if hist[-1] > 0 and hist[-1] > hist[-2] else (
                   "contracting_bullish" if hist[-1] > 0 else (
                   "expanding_bearish" if hist[-1] < 0 and hist[-1] < hist[-2] else
                   "contracting_bearish"))

        # Stoch RSI
        sk, sd = _stoch_rsi(c)
        sk_val = float(sk[-1]) if not np.isnan(sk[-1]) else 50.0
        sd_val = float(sd[-1]) if not np.isnan(sd[-1]) else 50.0

        if sk_val > 80:
            stoch_state = "overbought"
        elif sk_val < 20:
            stoch_state = "oversold"
        else:
            stoch_state = "neutral"
        stoch_cross = "bullish" if sk_val > sd_val else "bearish"

        return {
            "rsi": {
                "value": round(rsi_val, 1),
                "state": rsi_state,
                "divergence": rsi_div,
            },
            "macd": {
                "macd": round(float(macd_l[-1]), 6),
                "signal": round(float(sig_l[-1]), 6),
                "histogram": round(float(hist[-1]), 6),
                "cross": macd_cross,
                "histogram_dir": hist_dir,
                "interpretation": f"MACD {macd_cross} cross, histogram {hist_dir}",
            },
            "stoch_rsi": {
                "k": round(sk_val, 1),
                "d": round(sd_val, 1),
                "state": stoch_state,
                "cross": stoch_cross,
                "interpretation": f"Stoch RSI {stoch_state}, K {'>' if sk_val > sd_val else '<'} D",
            },
        }

    def _detect_divergence(self, price: np.ndarray, rsi: np.ndarray) -> str:
        """Regular divergence detection over last 40 bars (was full array — too noisy)."""
        try:
            # Use last 40 bars for meaningful divergence window
            lookback = min(40, len(price))
            p = price[-lookback:]
            r = rsi[-lookback:]

            p_hi_i = int(np.argmax(p))
            p_lo_i = int(np.argmin(p))
            r_at_hi = r[p_hi_i]
            r_at_lo = r[p_lo_i]

            # Bearish: price making higher high but RSI making lower high
            if p[-1] >= p[p_hi_i] * 0.98 and r[-1] < r_at_hi - 5 and p_hi_i < len(p) - 3:
                return "bearish divergence"
            # Bullish: price making lower low but RSI making higher low
            if p[-1] <= p[p_lo_i] * 1.02 and r[-1] > r_at_lo + 5 and p_lo_i < len(p) - 3:
                return "bullish divergence"
            return "none"
        except Exception:
            return "none"

    # ── volume ────────────────────────────────────────────────────────────────

    def _volume_analysis(self, df: pd.DataFrame) -> Dict:
        c = df["close"].values
        v = df["volume"].values

        obv = _obv(c, v)
        obv_trend = "rising" if obv[-1] > np.mean(obv[-20:]) else "falling"

        # 20-bar avg volume
        avg_vol = np.mean(v[-20:])
        last_vol = v[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        # Accumulation/Distribution index
        clv = ((c - df["low"].values) - (df["high"].values - c)) / (
               df["high"].values - df["low"].values + 1e-10)
        ad = np.cumsum(clv * v)
        ad_slope = (ad[-1] - ad[-20]) / (abs(ad[-20]) + 1e-10)  # 20-bar window (was 10, too noisy)
        ad_trend = "accumulation" if ad_slope > 0 else "distribution"

        # Volume confirmation of price trend
        price_up = c[-1] > c[-5]
        vol_up   = v[-1] > avg_vol
        if price_up and vol_up:
            confirmation = "confirmed_bullish"
        elif not price_up and vol_up:
            confirmation = "confirmed_bearish"
        elif price_up and not vol_up:
            confirmation = "weak_bullish"
        else:
            confirmation = "weak_bearish"

        anomaly = None
        if vol_ratio > 3:
            anomaly = f"Volume spike {vol_ratio:.1f}x avg — potential accumulation/distribution event"
        elif vol_ratio < 0.3:
            anomaly = "Volume dry-up — low conviction move"

        return {
            "obv_trend": obv_trend,
            "avg_volume": round(avg_vol, 2),
            "last_volume": round(last_vol, 2),
            "volume_ratio": round(vol_ratio, 2),
            "ad_trend": ad_trend,
            "confirmation": confirmation,
            "anomaly": anomaly,
            "interpretation": (
                f"OBV {obv_trend}, {ad_trend} phase. "
                f"Last bar volume {vol_ratio:.1f}x average. "
                f"Move {confirmation.replace('_', ' ')}."
            ),
        }

    # ── chart patterns ────────────────────────────────────────────────────────

    def _chart_patterns(self, df: pd.DataFrame) -> List[Dict]:
        patterns = []
        h, l, c = df["high"].values, df["low"].values, df["close"].values

        # Need enough data
        if len(c) < 40:
            return patterns

        # Bull flag: strong up move then tight consolidation
        recent_high   = np.max(h[-30:])
        recent_low    = np.min(l[-30:])
        prior_high    = np.max(h[-60:-30]) if len(h) >= 60 else None
        initial_move  = (h[-30] - l[-60]) / (l[-60] + 1e-10) if len(l) >= 60 else 0
        consol_range  = (recent_high - recent_low) / (recent_low + 1e-10)

        if initial_move > 0.08 and consol_range < 0.04:
            patterns.append({
                "name": "Bull Flag",
                "direction": "BULLISH",
                "status": "active",
                "target": round(recent_high + (h[-30] - l[-60] if len(l) >= 60 else 0), 6),
                "notes": "Tight consolidation after strong up move. Breakout targets measured move.",
            })

        # Bear flag: strong down move then tight consolidation
        down_move = (h[-60] - l[-30]) / (h[-60] + 1e-10) if len(h) >= 60 else 0
        if down_move > 0.08 and consol_range < 0.04:
            patterns.append({
                "name": "Bear Flag",
                "direction": "BEARISH",
                "status": "active",
                "target": round(recent_low - (h[-60] - l[-30] if len(h) >= 60 else 0), 6),
                "notes": "Tight consolidation after strong down move. Breakdown targets measured move.",
            })

        # Ascending triangle: flat resistance, rising lows
        sh = _swing_highs(h, lookback=5)
        sl = _swing_lows(l, lookback=5)
        if len(sh) >= 3 and len(sl) >= 3:
            tops = [h[i] for i in sh[-3:]]
            bots = [l[i] for i in sl[-3:]]
            flat_top   = (max(tops) - min(tops)) / (min(tops) + 1e-10) < 0.02
            rising_bot = bots[-1] > bots[0]
            if flat_top and rising_bot:
                patterns.append({
                    "name": "Ascending Triangle",
                    "direction": "BULLISH",
                    "status": "forming",
                    "target": round(max(tops) + (max(tops) - bots[0]), 6),
                    "notes": "Flat resistance + rising lows = bullish breakout setup.",
                })

        # Descending triangle: flat support, declining highs
        if len(sh) >= 3 and len(sl) >= 3:
            tops = [h[i] for i in sh[-3:]]
            bots = [l[i] for i in sl[-3:]]
            flat_bot    = (max(bots) - min(bots)) / (min(bots) + 1e-10) < 0.02
            falling_top = tops[-1] < tops[0]
            if flat_bot and falling_top:
                patterns.append({
                    "name": "Descending Triangle",
                    "direction": "BEARISH",
                    "status": "forming",
                    "target": round(min(bots) - (tops[0] - min(bots)), 6),
                    "notes": "Flat support + declining highs = bearish breakdown setup.",
                })

        # Double bottom (simplified)
        if len(sl) >= 2:
            b1, b2 = l[sl[-2]], l[sl[-1]]
            neckline = np.max(h[sl[-2]:sl[-1]]) if sl[-1] > sl[-2] else None
            if neckline and abs(b1 - b2) / (b1 + 1e-10) < 0.02 and c[-1] > neckline:
                patterns.append({
                    "name": "Double Bottom",
                    "direction": "BULLISH",
                    "status": "breakout",
                    "target": round(neckline + (neckline - b1), 6),
                    "notes": "Two equal lows + neckline break — bullish reversal.",
                })

        # Double top (simplified)
        if len(sh) >= 2:
            t1, t2 = h[sh[-2]], h[sh[-1]]
            neckline = np.min(l[sh[-2]:sh[-1]]) if sh[-1] > sh[-2] else None
            if neckline and abs(t1 - t2) / (t1 + 1e-10) < 0.02 and c[-1] < neckline:
                patterns.append({
                    "name": "Double Top",
                    "direction": "BEARISH",
                    "status": "breakdown",
                    "target": round(neckline - (t1 - neckline), 6),
                    "notes": "Two equal highs + neckline break — bearish reversal.",
                })

        # Rising wedge (bearish)
        if len(sh) >= 3 and len(sl) >= 3:
            tops = [h[i] for i in sh[-3:]]
            bots = [l[i] for i in sl[-3:]]
            tops_rising = tops[-1] > tops[0]
            bots_rising = bots[-1] > bots[0]
            bots_faster = (bots[-1] - bots[0]) / (bots[0] + 1e-10) > (tops[-1] - tops[0]) / (tops[0] + 1e-10)
            if tops_rising and bots_rising and bots_faster:
                patterns.append({
                    "name": "Rising Wedge",
                    "direction": "BEARISH",
                    "status": "forming",
                    "target": round(bots[0], 6),
                    "notes": "Converging rising highs & lows, support rising faster — bearish reversal signal.",
                })

        # Falling wedge (bullish)
        if len(sh) >= 3 and len(sl) >= 3:
            tops = [h[i] for i in sh[-3:]]
            bots = [l[i] for i in sl[-3:]]
            tops_falling = tops[-1] < tops[0]
            bots_falling = bots[-1] < bots[0]
            tops_faster  = (tops[0] - tops[-1]) / (tops[0] + 1e-10) > (bots[0] - bots[-1]) / (bots[0] + 1e-10)
            if tops_falling and bots_falling and tops_faster:
                patterns.append({
                    "name": "Falling Wedge",
                    "direction": "BULLISH",
                    "status": "forming",
                    "target": round(tops[0], 6),
                    "notes": "Converging falling highs & lows, resistance falling faster — bullish reversal signal.",
                })

        return patterns

    # ── fibonacci ─────────────────────────────────────────────────────────────

    def _fibonacci(self, df: pd.DataFrame) -> Dict:
        """Fibonacci retracements + extensions from last significant swing."""
        h, l, c = df["high"].values, df["low"].values, df["close"].values
        last = c[-1]

        # Find last swing high and low in last 100 bars
        window = min(100, len(h))
        hi_idx = np.argmax(h[-window:])
        lo_idx = np.argmin(l[-window:])
        swing_high = h[-window + hi_idx]
        swing_low  = l[-window + lo_idx]

        # Direction: which came last?
        direction = "up" if hi_idx > lo_idx else "down"
        diff = swing_high - swing_low

        retrace_levels  = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        extension_levels = [1.272, 1.414, 1.618, 2.0, 2.618]

        if direction == "up":
            # Price went up from lo to hi; retracements pull back from hi
            retrace = {str(r): round(swing_high - diff * r, 6) for r in retrace_levels}
            extensions = {str(e): round(swing_high + diff * (e - 1), 6) for e in extension_levels}
        else:
            retrace = {str(r): round(swing_low + diff * r, 6) for r in retrace_levels}
            extensions = {str(e): round(swing_low - diff * (e - 1), 6) for e in extension_levels}

        # Nearest retracement level
        nearest = min(retrace.items(), key=lambda x: abs(float(x[1]) - last))
        dist_pct = round((last - float(nearest[1])) / last * 100, 2) if last != 0 else 0.0

        return {
            "swing_high":  round(swing_high, 6),
            "swing_low":   round(swing_low, 6),
            "direction":   direction,
            "retracements": retrace,
            "extensions":  extensions,
            "nearest_level": nearest[0],
            "nearest_price": float(nearest[1]),
            "dist_to_nearest_pct": dist_pct,
        }

    # ── volatility ────────────────────────────────────────────────────────────

    def _volatility(self, df: pd.DataFrame) -> Dict:
        c, h, l = df["close"].values, df["high"].values, df["low"].values
        upper, mid, lower = _bb(c, 20, 2.0)
        atr = _atr(h, l, c, 14)

        bb_width = (upper[-1] - lower[-1]) / (mid[-1] + 1e-10) * 100
        # Historical BB width percentile (last 100 bars)
        widths = [(upper[i] - lower[i]) / (mid[i] + 1e-10) * 100
                  for i in range(-100, 0)
                  if not np.isnan(upper[i]) and mid[i] > 0]
        bb_pct = int(np.searchsorted(sorted(widths), bb_width) / len(widths) * 100) if widths else 50

        atr_val = float(atr[-1]) if not np.isnan(atr[-1]) else 0
        atr_pct = atr_val / c[-1] * 100 if c[-1] != 0 else 0.0

        bb_pos = (c[-1] - lower[-1]) / (upper[-1] - lower[-1] + 1e-10)

        if bb_width < np.percentile(widths, 20) if widths else True:
            regime = "coiling — potential big move incoming"
        elif bb_width > np.percentile(widths, 80) if widths else True:
            regime = "expanding — high volatility"
        else:
            regime = "normal range"

        return {
            "bb_upper": round(upper[-1], 6),
            "bb_mid":   round(mid[-1], 6),
            "bb_lower": round(lower[-1], 6),
            "bb_width_pct": round(bb_width, 2),
            "bb_width_percentile": bb_pct,
            "bb_position": round(bb_pos, 3),
            "atr": round(atr_val, 6),
            "atr_pct": round(atr_pct, 2),
            "regime": regime,
        }

    # ── trade plan ────────────────────────────────────────────────────────────

    def _trade_plan(
        self,
        current_price: float,
        trend: Dict,
        levels: Dict,
        fib: Dict,
        vol: Dict,
        score: float,
    ) -> Dict:
        direction = trend["direction"]
        atr = vol["atr"]

        if direction == "BULLISH":
            # Long plan
            entry  = current_price
            sl     = levels["nearest_support"] or (current_price - atr * 2)
            sl     = min(sl, current_price - atr * 1.5)  # at least 1.5 ATR
            risk   = entry - sl
            tp1    = entry + risk * 1.5
            tp2    = entry + risk * 2.5
            tp3    = entry + risk * 4.0
            side   = "LONG"
        elif direction == "BEARISH":
            # Short plan
            entry  = current_price
            sl     = levels["nearest_resistance"] or (current_price + atr * 2)
            sl     = max(sl, current_price + atr * 1.5)
            risk   = sl - entry
            tp1    = entry - risk * 1.5
            tp2    = entry - risk * 2.5
            tp3    = entry - risk * 4.0
            side   = "SHORT"
        else:
            return {"side": "NEUTRAL", "note": "No directional bias. Wait for trend clarity."}

        rr1 = (round((tp1 - entry) / risk, 2) if direction == "BULLISH" else round((entry - tp1) / risk, 2)) if risk > 0 else 0
        rr2 = (round((tp2 - entry) / risk, 2) if direction == "BULLISH" else round((entry - tp2) / risk, 2)) if risk > 0 else 0
        rr3 = (round((tp3 - entry) / risk, 2) if direction == "BULLISH" else round((entry - tp3) / risk, 2)) if risk > 0 else 0

        return {
            "side":  side,
            "entry": round(entry, 6),
            "stop":  round(sl, 6),
            "tp1":   round(tp1, 6),
            "tp2":   round(tp2, 6),
            "tp3":   round(tp3, 6),
            "rr1":   rr1,
            "rr2":   rr2,
            "rr3":   rr3,
            "risk_per_unit": round(risk, 6),
        }

    # ── scoring ───────────────────────────────────────────────────────────────

    def _score(
        self,
        trends: Dict,       # tf → trend dict
        ma: Dict,
        mom: Dict,
        vol_an: Dict,
        patterns: List[Dict],
        fib: Dict,
        volatility: Dict,
    ) -> Tuple[float, str]:

        pts = 0.0

        # 1. Trend alignment (max 25 pts)
        tf_directions = [v["direction"] for v in trends.values()]
        bull_count = tf_directions.count("BULLISH")
        bear_count = tf_directions.count("BEARISH")
        dominant = "BULLISH" if bull_count > bear_count else ("BEARISH" if bear_count > bull_count else "NEUTRAL")
        aligned = max(bull_count, bear_count)
        pts += aligned * 6  # 4 TFs * 6 = max 24
        # Penalty for mixed signals — 3 aligned is fine, 2/4 is weak, 1/4 is noise
        if aligned <= 2:
            pts -= 8  # conflicting timeframes penalty

        # 2. MA stack (max 10 pts)
        if ma["stack"] == "bullish" and dominant == "BULLISH":
            pts += 10
        elif ma["stack"] == "bearish" and dominant == "BEARISH":
            pts += 10
        elif ma["stack"] == "mixed":
            pts += 3

        # 3. Crossovers (max 8 pts)
        good_xo = [x for x in ma["crossovers"]
                   if (x["type"] == "golden" and dominant == "BULLISH") or
                      (x["type"] == "death"  and dominant == "BEARISH")]
        pts += min(len(good_xo) * 4, 8)

        # 4. RSI (max 10 pts)
        rsi_v = mom["rsi"]["value"]
        state = mom["rsi"]["state"]
        if dominant == "BULLISH":
            if 45 < rsi_v < 65:
                pts += 10  # healthy bull
            elif rsi_v > 65:
                pts += 5   # extended
            elif state == "bullish_divergence":
                pts += 8
        else:
            if 35 < rsi_v < 55:
                pts += 10
            elif rsi_v < 35:
                pts += 5
            elif state == "bearish_divergence":
                pts += 8

        # 5. MACD (max 8 pts)
        if (mom["macd"]["cross"] == "bullish" and dominant == "BULLISH") or \
           (mom["macd"]["cross"] == "bearish" and dominant == "BEARISH"):
            pts += 4
        if "expanding" in mom["macd"]["histogram_dir"]:
            pts += 4

        # 6. Stoch RSI (max 6 pts)
        if (mom["stoch_rsi"]["cross"] == "bullish" and dominant == "BULLISH") or \
           (mom["stoch_rsi"]["cross"] == "bearish" and dominant == "BEARISH"):
            pts += 3
        if (mom["stoch_rsi"]["state"] == "oversold" and dominant == "BULLISH") or \
           (mom["stoch_rsi"]["state"] == "overbought" and dominant == "BEARISH"):
            pts += 3

        # 7. Volume confirmation (max 8 pts)
        conf = vol_an["confirmation"]
        if (conf == "confirmed_bullish" and dominant == "BULLISH") or \
           (conf == "confirmed_bearish" and dominant == "BEARISH"):
            pts += 8
        elif "weak" in conf:
            pts += 2

        # 8. Chart patterns (max 10 pts)
        matching_patterns = [p for p in patterns
                             if (p["direction"] == "BULLISH" and dominant == "BULLISH") or
                                (p["direction"] == "BEARISH" and dominant == "BEARISH")]
        pts += min(len(matching_patterns) * 5, 10)

        # 9. Volatility regime (max 5 pts)
        if "coiling" in volatility["regime"]:
            pts += 5  # potential breakout energy

        # Max theoretical pts ≈ 90
        # Normalize to 1-10
        score = max(1.0, min(10.0, 1 + pts / 90 * 9))
        score = round(score, 1)

        # Signal is purely directional — score drives conviction, dominant drives direction
        if dominant == "NEUTRAL":
            signal = "Neutral"
        elif dominant == "BULLISH":
            if score >= 8.5:
                signal = "Strong Buy"
            elif score >= 7.0:
                signal = "Buy"
            elif score >= 5.5:
                signal = "Neutral"
            elif score >= 4.0:
                signal = "Sell"      # weak bullish = caution
            else:
                signal = "Strong Sell"
        else:  # BEARISH
            if score >= 8.5:
                signal = "Strong Sell"
            elif score >= 7.0:
                signal = "Sell"
            elif score >= 5.5:
                signal = "Neutral"
            elif score >= 4.0:
                signal = "Buy"       # weak bearish = caution
            else:
                signal = "Strong Buy"

        return score, signal

    # ── full coin analysis ────────────────────────────────────────────────────

    def analyze(self, symbol: str) -> Optional[Dict]:
        """Full analysis for a single coin. Blocking (use in executor)."""
        try:
            dfs = {}
            for tf in self.TIMEFRAMES:
                df = self._fetch(symbol, tf)
                if df is None:
                    logger.warning(f"No data for {symbol} {tf}, skipping")
                    continue
                dfs[tf] = df

            if "1h" not in dfs:
                return None

            current_price = float(dfs["1h"]["close"].values[-1])

            # Per-timeframe trend
            trends = {}
            for tf, df in dfs.items():
                trends[self.TF_LABELS[tf]] = self._trend(df)

            # Everything else uses primary TF = 4H if available else 1H
            primary_tf = "4h" if "4h" in dfs else "1h"
            primary_df = dfs[primary_tf]

            levels   = self._key_levels(primary_df, current_price)
            ma       = self._moving_averages(primary_df)
            mom      = self._momentum(primary_df)
            vol_an   = self._volume_analysis(primary_df)
            patterns = self._chart_patterns(primary_df)
            fib      = self._fibonacci(primary_df)
            volatility = self._volatility(primary_df)

            score, signal = self._score(trends, ma, mom, vol_an, patterns, fib, volatility)

            trade_plan = self._trade_plan(
                current_price, trends.get("4H") or trends.get("1H"),
                levels, fib, volatility, score
            )

            # Trend alignment summary
            tf_dirs = [f"{tf}={v['direction']}" for tf, v in trends.items()]
            aligned = len(set(v["direction"] for v in trends.values())) == 1
            alignment_note = "✅ All timeframes aligned" if aligned else "⚠️ Mixed timeframe signals"

            return {
                "symbol": _sym(symbol),
                "price": current_price,
                "score": score,
                "signal": signal,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "trend_structure": {
                    "timeframes": trends,
                    "alignment": alignment_note,
                    "tf_summary": " | ".join(tf_dirs),
                },
                "key_levels": levels,
                "moving_averages": ma,
                "momentum": mom,
                "volume": vol_an,
                "chart_patterns": patterns,
                "fibonacci": fib,
                "volatility": volatility,
                "trade_plan": trade_plan,
            }

        except Exception as e:
            logger.error(f"analyze {symbol}: {e}", exc_info=True)
            return None


# ─────────────────────── multi-coin engine ────────────────────────────────────

class QuantAnalyzerEngine:
    """
    Ranks multiple coins by setup quality.
    Pure analysis — no Telegram, no paper trades.
    """

    def __init__(self):
        self._analyzer = CoinAnalyzer()
        self.active = True

    async def analyze_coins(self, symbols: List[str]) -> Dict:
        """Analyze list of coins, return ranked results + watchlist table."""
        loop = asyncio.get_running_loop()

        async def _run(sym):
            return await loop.run_in_executor(None, self._analyzer.analyze, sym)

        results = await asyncio.gather(*[_run(s) for s in symbols], return_exceptions=True)

        reports = []
        errors  = []
        for sym, r in zip(symbols, results):
            if isinstance(r, Exception):
                errors.append({"symbol": sym, "error": str(r)})
            elif r is None:
                errors.append({"symbol": sym, "error": "No data"})
            else:
                reports.append(r)

        # Sort by score descending
        reports.sort(key=lambda x: x["score"], reverse=True)

        # Watchlist summary table
        watchlist = []
        for r in reports:
            tp = r["trade_plan"]
            watchlist.append({
                "coin":   r["symbol"],
                "signal": r["signal"],
                "score":  r["score"],
                "entry":  tp.get("entry"),
                "stop":   tp.get("stop"),
                "tp1":    tp.get("tp1"),
                "rr1":    tp.get("rr1"),
                "trend_alignment": r["trend_structure"]["alignment"],
            })

        return {
            "ranked_reports": reports,
            "watchlist_table": watchlist,
            "errors": errors,
            "total_analyzed": len(reports),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ─────────────────────── quant gatekeeper ────────────────────────────────────

class QuantGatekeeper:
    """
    System-wide pre-trade gate. Every engine signal must pass before
    submit_signal fires.

    - TTL cache (5 min) per symbol — no redundant MEXC calls for the same coin
    - Score threshold per engine risk_profile:
        conservative → 7.0
        balanced     → 6.5
        aggressive   → 6.0
    - Direction alignment: LONG requires BULLISH dominant, SHORT requires BEARISH
    - NEUTRAL dominant is always rejected (no conviction)
    - Fail-open on MEXC error or missing data — existing validator still runs
    """

    TTL_SECONDS: int = 300

    MIN_SCORE: Dict[str, float] = {
        "conservative": 7.0,
        "balanced":     6.5,
        "aggressive":   6.0,
    }

    def __init__(self):
        self._cache: Dict[str, Dict] = {}   # symbol -> {"result": Dict, "expires_at": datetime}
        self._analyzer = CoinAnalyzer()

    # ── cache helpers ─────────────────────────────────────────────────────────

    def _cached(self, symbol: str) -> Optional[Dict]:
        entry = self._cache.get(symbol)
        if entry and datetime.now(timezone.utc) < entry["expires_at"]:
            return entry["result"]
        return None

    def _store(self, symbol: str, result: Dict):
        self._cache[symbol] = {
            "result":     result,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self.TTL_SECONDS),
        }

    # ── public api ────────────────────────────────────────────────────────────

    async def check(
        self,
        symbol:       str,
        direction:    str,
        risk_profile: str = "balanced",
    ) -> Dict:
        """
        Evaluate whether a signal should be allowed through.

        Returns:
            {
                "approved":     bool,
                "score":        float | None,
                "quant_signal": str   | None,
                "dominant":     str   | None,
                "reason":       str,
                "cached":       bool,
            }
        """
        direction_upper   = direction.upper()
        required_dominant = "BULLISH" if direction_upper == "LONG" else "BEARISH"
        min_score         = self.MIN_SCORE.get(risk_profile, 6.5)

        cached    = self._cached(symbol)
        cache_hit = cached is not None

        if not cache_hit:
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(None, self._analyzer.analyze, symbol)
            except Exception as e:
                logger.warning(f"[QuantGate] Analysis error {symbol}: {e} — fail open")
                return {
                    "approved":     True,
                    "score":        None,
                    "quant_signal": None,
                    "dominant":     None,
                    "reason":       f"Analysis unavailable ({e}) — gate bypassed",
                    "cached":       False,
                }

            if result is None:
                logger.warning(f"[QuantGate] No OHLCV data for {symbol} — fail open")
                return {
                    "approved":     True,
                    "score":        None,
                    "quant_signal": None,
                    "dominant":     None,
                    "reason":       "No OHLCV data — gate bypassed",
                    "cached":       False,
                }

            self._store(symbol, result)
            cached = result

        score        = cached["score"]
        quant_signal = cached["signal"]

        tf_trends  = cached.get("trend_structure", {}).get("timeframes", {})
        directions = [v["direction"] for v in tf_trends.values()]
        bull_count = directions.count("BULLISH")
        bear_count = directions.count("BEARISH")
        dominant   = (
            "BULLISH" if bull_count > bear_count else
            ("BEARISH" if bear_count > bull_count else "NEUTRAL")
        )

        # Gate 1: Score threshold
        if score < min_score:
            return {
                "approved":     False,
                "score":        score,
                "quant_signal": quant_signal,
                "dominant":     dominant,
                "reason":       f"Score {score}/10 below {min_score} minimum ({risk_profile})",
                "cached":       cache_hit,
            }

        # Gate 2: No directional conviction
        if dominant == "NEUTRAL":
            return {
                "approved":     False,
                "score":        score,
                "quant_signal": quant_signal,
                "dominant":     dominant,
                "reason":       f"NEUTRAL across timeframes — {direction_upper} rejected",
                "cached":       cache_hit,
            }

        # Gate 3: Direction alignment
        if dominant != required_dominant:
            return {
                "approved":     False,
                "score":        score,
                "quant_signal": quant_signal,
                "dominant":     dominant,
                "reason":       f"Direction conflict: quant={dominant}, engine={direction_upper}",
                "cached":       cache_hit,
            }

        return {
            "approved":     True,
            "score":        score,
            "quant_signal": quant_signal,
            "dominant":     dominant,
            "reason":       f"Score {score}/10, {dominant} aligned with {direction_upper}",
            "cached":       cache_hit,
        }

    def invalidate(self, symbol: str):
        """Force-expire a symbol's cached analysis."""
        self._cache.pop(symbol, None)

    def cache_status(self) -> List[Dict]:
        """Return all live cache entries with remaining TTL."""
        now = datetime.now(timezone.utc)
        return [
            {
                "symbol":       sym,
                "score":        entry["result"]["score"],
                "signal":       entry["result"]["signal"],
                "expires_in_s": max(0, int((entry["expires_at"] - now).total_seconds())),
            }
            for sym, entry in self._cache.items()
            if now < entry["expires_at"]
        ]


# ─────────────────────── singletons ──────────────────────────────────────────

_engine: Optional[QuantAnalyzerEngine] = None

def get_quant_engine() -> QuantAnalyzerEngine:
    global _engine
    if _engine is None:
        _engine = QuantAnalyzerEngine()
    return _engine


_gatekeeper: Optional[QuantGatekeeper] = None

def get_quant_gatekeeper() -> QuantGatekeeper:
    global _gatekeeper
    if _gatekeeper is None:
        _gatekeeper = QuantGatekeeper()
    return _gatekeeper
