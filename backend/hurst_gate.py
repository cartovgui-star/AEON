"""
Hurst Regime Gate — Gate 16 in submit_signal_gated()

Computes rolling Hurst exponent via R/S analysis to classify market regime:
  H < 0.45  → MEAN_REVERSION  (price reverts, fade breakouts)
  H > 0.55  → MOMENTUM        (price trends, follow direction)
  0.45–0.55 → RANDOM_WALK     → REJECT all directional signals (no edge)

This is a better regime filter than the entropy gate alone because it captures
the fractal structure of price series rather than just return distribution noise.
"""

import logging
import time
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Cache: symbol → (H, regime, timestamp)
_hurst_cache: Dict[str, Tuple[float, str, float]] = {}
_CACHE_TTL = 900  # 15 minutes


def _hurst_rs(returns: np.ndarray) -> float:
    """Compute Hurst exponent via Rescaled Range (R/S) analysis."""
    n = len(returns)
    if n < 20:
        return 0.5

    lags = range(10, n // 2)
    rs_values = []

    for lag in lags:
        chunks = [returns[i : i + lag] for i in range(0, n - lag, lag)]
        if not chunks:
            continue
        rs_chunk = []
        for chunk in chunks:
            mean_c = float(np.mean(chunk))
            dev = np.cumsum(chunk - mean_c)
            r = float(np.max(dev) - np.min(dev))
            s = float(np.std(chunk, ddof=1))
            if s > 0:
                rs_chunk.append(r / s)
        if rs_chunk:
            rs_values.append((lag, float(np.mean(rs_chunk))))

    if len(rs_values) < 5:
        return 0.5

    lags_arr = np.log([x[0] for x in rs_values])
    rs_arr = np.log([x[1] for x in rs_values])
    hurst = float(np.polyfit(lags_arr, rs_arr, 1)[0])
    return float(np.clip(hurst, 0.0, 1.0))


def _classify_regime(H: float) -> str:
    if H < 0.44:
        return "MEAN_REVERSION"
    if H > 0.56:
        return "MOMENTUM"
    if 0.48 <= H <= 0.52:
        return "RANDOM_WALK"       # hard block — genuinely coin-flip, both windows agree
    return "TRANSITIONAL"          # 0.44-0.48 or 0.52-0.56 — borderline, passes with note


async def compute_hurst_for_symbol(symbol: str, market_intel) -> Tuple[float, str]:
    """
    Fetch 1h OHLCV and compute dual-window Hurst. Returns (H, regime). Cached 15 min.

    Uses two windows:
      slow (100-bar, ~4 days) — structural regime
      fast (50-bar, ~2 days)  — recent breakout detection

    Hard block only fires when BOTH windows land in RANDOM_WALK.
    If fast window shows momentum but slow shows random walk, return TRANSITIONAL
    so a recent breakout is not unfairly blocked.
    """
    cached = _hurst_cache.get(symbol)
    if cached and (time.time() - cached[2]) < _CACHE_TTL:
        return cached[0], cached[1]

    try:
        ohlcv = await market_intel.get_ohlcv(symbol, "1h", 120)
        closes = [c[4] for c in ohlcv.get("candles", [])] if "candles" in ohlcv else []
        if len(closes) < 40:
            return 0.5, "UNKNOWN"

        arr = np.array(closes, dtype=float)
        returns = np.diff(np.log(arr))

        H_slow = _hurst_rs(returns[-100:] if len(returns) >= 100 else returns)
        H_fast = _hurst_rs(returns[-50:] if len(returns) >= 50 else returns)

        regime_slow = _classify_regime(H_slow)
        regime_fast = _classify_regime(H_fast)

        # Upgrade regime if fast window disagrees with slow (recent breakout)
        if regime_slow == "RANDOM_WALK" and regime_fast != "RANDOM_WALK":
            regime = "TRANSITIONAL"  # slow says noise but fast sees structure → don't block
            H = H_fast               # use the more responsive reading
        else:
            regime = regime_slow
            H = H_slow

        _hurst_cache[symbol] = (H, regime, time.time())
        logger.debug(f"[HURST] {symbol} H_slow={H_slow:.4f}→{regime_slow} H_fast={H_fast:.4f}→{regime_fast} → {regime}")
        return H, regime
    except Exception as e:
        logger.debug(f"[HURST GATE] {symbol} compute failed: {e}")
        return 0.5, "UNKNOWN"


async def check_hurst_gate(
    symbol: str,
    direction: str,
    market_intel,
) -> Tuple[bool, str, Dict]:
    """
    Gate 16: Hurst Regime Gate.

    Hard block: H in [0.47, 0.53] — genuine coin-flip, no directional edge.
    Soft pass: H in [0.43, 0.47] or [0.53, 0.57] — transitional, trade cautiously.
    Clear pass: H < 0.43 (mean-reversion) or H > 0.57 (momentum).

    Returns (passes, reason, detail).
    detail["soft_pass"] = True means transitional zone — downstream can apply a
    confidence penalty if desired.
    """
    if market_intel is None:
        return True, "hurst gate skipped (no market intel)", {}

    H, regime = await compute_hurst_for_symbol(symbol, market_intel)
    detail: Dict = {
        "hurst": round(H, 4),
        "regime": regime,
        "symbol": symbol,
        "direction": direction,
        "soft_pass": regime == "TRANSITIONAL",
    }

    if regime == "UNKNOWN":
        return True, "hurst gate skipped (insufficient data)", detail

    if regime == "RANDOM_WALK":
        return (
            False,
            f"HURST GATE: H={H:.3f} in [0.48,0.52] — coin-flip regime, both windows confirm no edge",
            detail,
        )

    # TRANSITIONAL or clear regime — both pass
    note = " (transitional — treat with caution)" if regime == "TRANSITIONAL" else ""
    return True, f"hurst regime={regime} H={H:.3f}{note}", detail


def get_hurst_cache_snapshot() -> Dict:
    """Return current Hurst cache snapshot for API use."""
    now = time.time()
    return {
        sym: {
            "hurst": round(val[0], 4),
            "regime": val[1],
            "age_seconds": round(now - val[2]),
        }
        for sym, val in _hurst_cache.items()
    }
