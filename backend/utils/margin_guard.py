"""
MARGIN GUARD  —  utils/margin_guard.py
=======================================
Hard margin cap per trade for each paper trading account.

Rules:
  STARTER ($1,500 account) → max $400 margin per trade
  PRO     ($50,000 account) → max $2,500 margin per trade

Block only — never resize, never adjust, never modify margin.
Engine logic, leverage, and position sizing are completely unchanged.
If margin is over the limit → block. Under or equal → allow.
Default to $400 if account_id is unknown.

No cap on trading frequency — unlimited trades, just capped per-trade margin.
"""

import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# MARGIN GUARD — hard limits per account
LIMITS = {
    "STARTER": 400,    # $1,500 paper account — max $400 margin per trade
    "PRO":     2500,   # $50,000 paper account — max $2,500 margin per trade
}

DEFAULT_LIMIT = 400  # fallback if account_id not in LIMITS


def check_margin(
    account_id: str,
    margin: float,
    engine_name: str,
    symbol: str,
) -> bool:
    """
    Check whether a trade's margin is within the hard cap for this account.

    Returns:
        True  → margin is within limit, trade is allowed
        False → margin exceeds limit, trade must be blocked

    Never modifies margin. Never resizes. Block or allow, nothing else.
    """
    # MARGIN GUARD — resolve limit for this account
    limit = LIMITS.get(account_id, DEFAULT_LIMIT)

    if margin > limit:
        # MARGIN GUARD — hard block, log at WARNING level for visibility
        logger.warning(
            f"[MARGIN BLOCK] {engine_name} | {symbol} | "
            f"Account: {account_id} | Margin: ${margin:,.2f} | "
            f"Limit: ${limit:,.2f} | TRADE BLOCKED"
        )
        return False  # block the trade

    return True  # allow the trade — margin is within limit


def get_limit(account_id: str) -> float:
    """Return the margin limit for a given account_id."""
    return LIMITS.get(account_id, DEFAULT_LIMIT)
