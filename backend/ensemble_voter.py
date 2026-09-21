"""
Ensemble Voter — Cross-engine signal agreement tracker.

When multiple engines fire the same symbol+direction within a rolling 10-minute
window, that represents a higher-confidence event that gets flagged for elevated
priority and larger position sizing multiplier.

Threshold: CONSENSUS_THRESHOLD engines in CONSENSUS_WINDOW_SECONDS → elevated=True
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

CONSENSUS_WINDOW_SECONDS = 600   # 10-minute rolling window
CONSENSUS_THRESHOLD = 3          # engines required for elevated consensus
ELEVATED_SIZE_BONUS = 0.25       # +25% position multiplier on consensus


@dataclass
class _Vote:
    engine: str
    symbol: str
    direction: str
    confidence: float
    timestamp: float = field(default_factory=time.time)


# (symbol, direction) → list of active votes
_votes: Dict[Tuple[str, str], List[_Vote]] = defaultdict(list)
_lock = asyncio.Lock()


def _prune(key: Tuple[str, str], now: float) -> List[_Vote]:
    active = [v for v in _votes[key] if now - v.timestamp < CONSENSUS_WINDOW_SECONDS]
    _votes[key] = active
    return active


async def record_vote(engine: str, symbol: str, direction: str, confidence: float) -> None:
    """Record a directional vote from an engine. Replaces any prior vote from same engine."""
    async with _lock:
        key = (symbol, direction.lower())
        now = time.time()
        active = _prune(key, now)
        # One vote per engine per window
        _votes[key] = [v for v in active if v.engine != engine]
        _votes[key].append(_Vote(engine=engine, symbol=symbol, direction=direction.lower(), confidence=confidence))


async def get_consensus(symbol: str, direction: str) -> Dict:
    """Return consensus state for a specific symbol+direction."""
    async with _lock:
        key = (symbol, direction.lower())
        active = _prune(key, time.time())

    engines = [v.engine for v in active]
    count = len(engines)
    avg_conf = round(sum(v.confidence for v in active) / count, 1) if active else 0.0
    elevated = count >= CONSENSUS_THRESHOLD

    return {
        "symbol": symbol,
        "direction": direction.lower(),
        "engines": engines,
        "count": count,
        "elevated": elevated,
        "avg_confidence": avg_conf,
        "size_bonus": ELEVATED_SIZE_BONUS if elevated else 0.0,
    }


def get_consensus_snapshot() -> List[Dict]:
    """Return snapshot of all active consensus events (no lock — read-only for API)."""
    now = time.time()
    result = []
    for (symbol, direction), votes in list(_votes.items()):
        active = [v for v in votes if now - v.timestamp < CONSENSUS_WINDOW_SECONDS]
        if not active:
            continue
        engines = [v.engine for v in active]
        avg_conf = round(sum(v.confidence for v in active) / len(active), 1)
        result.append({
            "symbol": symbol,
            "direction": direction,
            "engines": engines,
            "count": len(engines),
            "elevated": len(engines) >= CONSENSUS_THRESHOLD,
            "avg_confidence": avg_conf,
        })
    return sorted(result, key=lambda x: -x["count"])
