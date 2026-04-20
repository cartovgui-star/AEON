"""
MTF CONFLUENCE  —  mtf_confluence.py
=====================================
Multi-timeframe alignment scorer used as Gate 15 in submit_signal_gated().

Timeframes and weights (must sum to 1.0):
  5m  → 0.15  (noise-heavy, low weight)
  15m → 0.25
  1h  → 0.35  (primary signal timeframe)
  4h  → 0.25

Score per timeframe:
  EMA20 / EMA50 crossover on that timeframe's OHLCV:
    price > EMA20 > EMA50  →  bullish  (+1)
    price < EMA20 < EMA50  →  bearish  (-1)
    otherwise              →  neutral   (0)

Composite score = sum(weight * raw) normalized to [0, 100]
  100 = max bullish alignment
    0 = max bearish alignment
   50 = neutral/mixed

Gate threshold: score > 55 for LONG signals, score < 45 for SHORT signals.
Results are cached per symbol for 5 minutes.

Usage:
    from mtf_confluence import get_mtf_score
    result = await get_mtf_score(symbol, direction, market_intel_instance)
    if not result["passes"]:
        return REJECT
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Timeframe weights — must sum to 1.0
TF_WEIGHTS: Dict[str, float] = {
    "5m":  0.15,
    "15m": 0.25,
    "1h":  0.35,
    "4h":  0.25,
}

# Minimum score to pass (for LONG)
LONG_PASS_THRESHOLD  = 55.0
# Maximum score to pass (for SHORT — lower score = more bearish)
SHORT_PASS_THRESHOLD = 45.0

# Cache TTL in seconds (5 minutes — matches typical candle period)
CACHE_TTL = 300


# ── Module-level cache ────────────────────────────────────────────────────────
# Key: symbol → {"score": float, "breakdown": dict, "ts": monotonic_time}
_cache: Dict[str, Dict] = {}


def _ema(closes: list, period: int) -> float:
    """
    Pure-Python EMA (exponential moving average) calculation.
    Uses ccxt-style OHLCV closes list.
    Returns the most recent EMA value.
    """
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    k = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period   # SMA seed
    for price in closes[period:]:
        ema = price * k + ema * (1.0 - k)
    return ema


async def _score_timeframe(
    symbol: str,
    timeframe: str,
    market_intel,
) -> Tuple[float, str]:
    """
    Fetch OHLCV for one timeframe, compute EMA20/EMA50, return:
      (+1, "bullish")  price > EMA20 > EMA50
      (-1, "bearish")  price < EMA20 < EMA50
      ( 0, "neutral")  mixed alignment
    Returns (0, "error") on fetch failure (graceful degradation).
    """
    try:
        # Use market_intel.get_ohlcv — same pattern as vwap_scalper / other engines
        result = await market_intel.get_ohlcv(symbol, timeframe, limit=60)
        if "error" in result or not result.get("candles"):
            logger.debug(f"[MTF] {symbol} {timeframe}: no candles — neutral")
            return 0.0, "error"

        candles = result["candles"]   # [[ts, o, h, l, c, v], ...]
        closes  = [float(c[4]) for c in candles]   # index 4 = close

        if len(closes) < 52:   # need at least 52 closes for EMA50
            logger.debug(f"[MTF] {symbol} {timeframe}: only {len(closes)} candles — neutral")
            return 0.0, "insufficient_data"

        price  = closes[-1]
        ema20  = _ema(closes, 20)
        ema50  = _ema(closes, 50)

        if price > ema20 > ema50:
            return 1.0, "bullish"
        elif price < ema20 < ema50:
            return -1.0, "bearish"
        else:
            return 0.0, "neutral"

    except Exception as e:
        logger.warning(f"[MTF] {symbol} {timeframe} error: {e}")
        return 0.0, "error"


async def get_mtf_score(
    symbol:      str,
    direction:   str,
    market_intel,
) -> Dict:
    """
    Compute multi-timeframe confluence score for (symbol, direction).

    Returns:
        {
            "score":          float,    # 0–100 (50 = neutral)
            "passes":         bool,     # True if score clears gate threshold
            "direction":      str,
            "breakdown": {
                "5m":   "+1/0/-1" label,
                "15m":  label,
                "1h":   label,
                "4h":   label,
            },
            "threshold_used": float,
            "reason":         str,      # human-readable verdict
        }
    """
    dir_lower = direction.lower()

    # ── Cache check (5 minute TTL) ────────────────────────────────────────────
    cached = _cache.get(symbol)
    if cached and (time.monotonic() - cached["ts"]) < CACHE_TTL:
        score     = cached["score"]
        breakdown = cached["breakdown"]
        logger.debug(f"[MTF] {symbol} using cached score={score:.0f}")
    else:
        # ── Fetch all 4 timeframes concurrently ───────────────────────────────
        tasks = {
            tf: _score_timeframe(symbol, tf, market_intel)
            for tf in TF_WEIGHTS
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        tf_scores: Dict[str, Tuple[float, str]] = {}
        for tf, res in zip(tasks.keys(), results):
            if isinstance(res, Exception):
                tf_scores[tf] = (0.0, "error")
            else:
                tf_scores[tf] = res

        # ── Weighted composite: raw ∈ [−1, +1], map to [0, 100] ──────────────
        weighted_sum = sum(
            TF_WEIGHTS[tf] * tf_scores[tf][0]
            for tf in TF_WEIGHTS
        )
        # weighted_sum ∈ [−1, +1] → score ∈ [0, 100]
        score = round((weighted_sum + 1.0) / 2.0 * 100.0, 1)

        breakdown = {tf: tf_scores[tf][1] for tf in TF_WEIGHTS}

        # ── Store in cache ────────────────────────────────────────────────────
        _cache[symbol] = {"score": score, "breakdown": breakdown, "ts": time.monotonic()}

    # ── Gate decision ─────────────────────────────────────────────────────────
    if dir_lower == "long":
        threshold = LONG_PASS_THRESHOLD
        passes    = score > threshold
    elif dir_lower == "short":
        threshold = SHORT_PASS_THRESHOLD
        passes    = score < threshold
    else:
        # Unknown direction — pass through
        threshold = 50.0
        passes    = True

    # Human-readable log line
    bd_str = " ".join(
        f"{tf}:{breakdown.get(tf, '?')[0].upper()}"
        for tf in ["5m", "15m", "1h", "4h"]
    )
    verdict = "PASS" if passes else "BLOCK"
    reason  = (
        f"MTF CONFLUENCE: {symbol} {direction.upper()} score={score:.0f} "
        f"({bd_str}) threshold={'>' if dir_lower=='long' else '<'}{threshold:.0f} → {verdict}"
    )
    logger.info(reason)

    return {
        "score":          score,
        "passes":         passes,
        "direction":      direction,
        "breakdown":      breakdown,
        "threshold_used": threshold,
        "reason":         reason,
    }


def clear_cache(symbol: Optional[str] = None):
    """Clear the MTF cache for one symbol or all symbols."""
    if symbol:
        _cache.pop(symbol, None)
    else:
        _cache.clear()
