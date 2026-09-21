"""
ADX REGIME FILTER  —  utils/adx_filter.py
==========================================
Single source of truth for ADX-based market regime detection.
All 7 engines use this to enforce consistent trend-strength filtering.

Thresholds (Wilder standard, confirmed by sim analysis):
  choppy   : ADX < 20  → skip trade entirely (ranging, setups fail)
  weak     : 20 ≤ ADX < 25 → require +1 extra confluence before entry
  trending : ADX ≥ 25  → fire normally, no restriction

Fail-open rule:
  If ADX = 0 or data unavailable → allow the trade (unknown regime).
  Never block a trade due to a data fetch failure.

Usage in an engine:
    from utils.adx_filter import get_regime, adx_gate, log_adx_block

    # When ADX is already in the indicators dict:
    adx = indicators.get("adx", 0)
    regime = get_regime(adx)
    if regime == "choppy":
        log_adx_block("MyEngine", symbol, adx, regime, timeframe)
        return None
    adx_weak = (regime == "weak")

    # ... build confluences ...

    # At the confluence gate:
    min_conf = required + (1 if adx_weak else 0)
    if len(confirmations) < min_conf:
        return None

    # OR use adx_gate() for a one-liner:
    proceed, regime = adx_gate(adx, current_confluences, required_confluences)
    if not proceed:
        log_adx_block("MyEngine", symbol, adx, regime, timeframe)
        return None
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# ─── Regime thresholds ────────────────────────────────────────────────────────
ADX_CHOPPY_MAX = 20   # Below this = no trend, skip
ADX_WEAK_MAX   = 25   # 20–25 = weak trend, require +1 confluence
# ADX ≥ ADX_WEAK_MAX = confirmed trend, trade normally


def get_regime(adx: float) -> str:
    """
    Classify ADX value into a market regime string.

    Returns:
        "choppy"   — ADX < 20, ranging market, signals fail here
        "weak"     — 20 ≤ ADX < 25, trend forming, needs extra confirmation
        "trending" — ADX ≥ 25, confirmed trend, trade normally
        "unknown"  — ADX = 0 or unavailable, fail-open
    """
    if adx <= 0:
        return "unknown"
    if adx < ADX_CHOPPY_MAX:
        return "choppy"
    if adx < ADX_WEAK_MAX:
        return "weak"
    return "trending"


def adx_gate(
    adx: float,
    current_confluences: int,
    required_confluences: int,
) -> Tuple[bool, str]:
    """
    Gate function — returns (proceed: bool, regime: str).

    Logic:
      unknown  (ADX=0/unavailable) → proceed=True   [fail open]
      trending (ADX ≥ 25)          → proceed=True
      weak     (20 ≤ ADX < 25)     → proceed only if current >= required + 1
      choppy   (ADX < 20)          → proceed=False

    Args:
        adx                 : Current ADX value (float)
        current_confluences : Number of confluences the signal currently has
        required_confluences: Baseline minimum confluences the engine requires

    Returns:
        (True/False, regime_string)
    """
    regime = get_regime(adx)

    if regime in ("unknown", "trending"):
        return True, regime

    if regime == "weak":
        proceed = current_confluences >= (required_confluences + 1)
        return proceed, regime

    # choppy
    return False, regime


def log_adx_block(
    engine: str,
    symbol: str,
    adx: float,
    regime: str,
    timeframe: str = "",
) -> None:
    """
    Standardized ADX block log line.
    Consistent format across all engines — easy to grep for filter activity.

    Example output:
        [ADX BLOCK] FreeWill | BTC/USDT 4h | ADX: 14.3 | Regime: choppy
    """
    tf_part = f" {timeframe}" if timeframe else ""
    logger.info(
        f"[ADX BLOCK] {engine} | {symbol}{tf_part} | ADX: {adx:.1f} | Regime: {regime}"
    )


async def get_adx_from_market(symbol: str, timeframe: str) -> float:
    """
    Fetch ADX from market_intel for engines that don't already have
    indicator data in scope (e.g. VWAP Scalper).

    Returns 0.0 on any error — caller treats 0 as fail-open (unknown regime).
    """
    try:
        from market_intelligence import market_intel  # lazy import avoids circular
        analysis = await market_intel.get_technical_analysis(symbol, timeframe)
        indicators = analysis.get("indicators", {})
        adx = float(indicators.get("adx", 0.0) or 0.0)
        return adx
    except Exception as exc:
        logger.debug(f"[ADX] fetch failed for {symbol} {timeframe}: {exc}")
        return 0.0
