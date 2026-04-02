"""
Signal Deduplicator — prevents duplicate and contradicting Telegram alerts.
All engine signals MUST pass through this before sending.

Dedup key: {pair}:{direction}:{engine}:{15min_bucket}
Storage: MongoDB "signal_cooldowns" collection (survives restarts)
"""

import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# In-memory cache structure:
#   _cache["{pair}:{direction}:{engine}:{bucket}"] = timestamp (float)
#   _coin_last["{pair}"] = {"direction": str, "timestamp": float}


class SignalDeduplicator:
    """
    Prevents duplicate and contradicting engine signals from firing as Telegram alerts.

    Dedup window  : 15 minutes per pair+direction+engine bucket
    Contradiction : 10 minutes — suppresses opposite direction on same pair
    TTL in Mongo  : 30 minutes (signal_cooldowns collection)
    """

    def __init__(self):
        self._db = None
        # {bucket_key: unix_ts_float}
        self._cache: Dict[str, float] = {}
        # {pair_upper: {"direction": str, "ts": float}}
        self._coin_last: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    async def check(self, pair: str, direction: str, engine: str) -> Tuple[bool, str]:
        """
        Returns (allowed, reason).
        allowed=True  → signal may fire
        allowed=False → signal suppressed; reason explains why
        """
        pair_u = pair.upper()
        dir_u  = direction.upper()
        now_ts = datetime.now(timezone.utc).timestamp()
        bucket = int(math.floor(now_ts / 900))  # 15-min window
        key    = f"{pair_u}:{dir_u}:{engine}:{bucket}"

        async with self._lock:
            # 1. Same pair+direction+engine in current 15-min bucket
            if key in self._cache:
                return False, f"duplicate: {pair_u} {dir_u} [{engine}] already fired this 15-min window"

            # 2. Contradiction guard — opposite direction in last 10 min
            coin_state = self._coin_last.get(pair_u)
            if coin_state:
                last_dir = coin_state.get("direction", "")
                last_ts  = coin_state.get("ts", 0.0)
                age_sec  = now_ts - last_ts
                if last_dir and last_dir != dir_u and age_sec < 600:
                    return False, (
                        f"contradiction: {pair_u} {dir_u} conflicts with recent "
                        f"{last_dir} ({age_sec:.0f}s ago)"
                    )

        return True, "ok"

    async def record(self, pair: str, direction: str, engine: str) -> None:
        """Save signal to MongoDB and in-memory cache."""
        pair_u = pair.upper()
        dir_u  = direction.upper()
        now    = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        bucket = int(math.floor(now_ts / 900))
        key    = f"{pair_u}:{dir_u}:{engine}:{bucket}"

        async with self._lock:
            self._cache[key] = now_ts
            self._coin_last[pair_u] = {"direction": dir_u, "ts": now_ts}
            self._prune_cache(now_ts)

        # Persist to MongoDB (non-fatal if DB is unavailable)
        if self._db is not None:
            try:
                expires_at = now + timedelta(minutes=30)
                await self._db.signal_cooldowns.update_one(
                    {"_key": key},
                    {"$set": {
                        "_key":       key,
                        "pair":       pair_u,
                        "direction":  dir_u,
                        "engine":     engine,
                        "bucket":     bucket,
                        "timestamp":  now,
                        "expires_at": expires_at,
                    }},
                    upsert=True,
                )
            except Exception as exc:
                logger.debug(f"[SignalDedup] MongoDB record failed (non-fatal): {exc}")

    async def mark_position_closed(self, pair: str) -> None:
        """
        Clear cooldown for a pair so the next signal fires freely.
        Called when a position is closed.
        """
        pair_u = pair.upper()
        async with self._lock:
            # Remove all in-memory entries for this pair
            to_del = [k for k in self._cache if k.startswith(f"{pair_u}:")]
            for k in to_del:
                del self._cache[k]
            self._coin_last.pop(pair_u, None)

        if self._db is not None:
            try:
                await self._db.signal_cooldowns.delete_many({"pair": pair_u})
            except Exception as exc:
                logger.debug(f"[SignalDedup] MongoDB clear failed (non-fatal): {exc}")

    async def load_from_db(self) -> None:
        """Called at startup to reload state from MongoDB."""
        if self._db is None:
            logger.warning("[SignalDedup] No DB — starting with empty in-memory state")
            return

        try:
            now_ts  = datetime.now(timezone.utc).timestamp()
            cursor  = self._db.signal_cooldowns.find(
                {"expires_at": {"$gt": datetime.now(timezone.utc)}}
            )
            loaded = 0
            async for doc in cursor:
                key = doc.get("_key")
                ts  = doc.get("timestamp")
                if key and ts:
                    if isinstance(ts, datetime):
                        ts = ts.timestamp()
                    self._cache[key] = ts
                    loaded += 1

                # Rebuild coin-last from most recent per pair
                pair_u = doc.get("pair", "")
                dir_u  = doc.get("direction", "")
                if pair_u and ts:
                    existing = self._coin_last.get(pair_u, {})
                    if ts > existing.get("ts", 0.0):
                        self._coin_last[pair_u] = {"direction": dir_u, "ts": ts}

            logger.info(f"[SignalDedup] Loaded {loaded} active cooldowns from MongoDB")

            # Ensure TTL index exists
            try:
                await self._db.signal_cooldowns.create_index(
                    "expires_at", expireAfterSeconds=0, background=True
                )
            except Exception:
                pass

        except Exception as exc:
            logger.warning(f"[SignalDedup] load_from_db failed (non-fatal): {exc}")

    async def log_suppression(
        self, pair: str, direction: str, engine: str, reason: str
    ) -> None:
        """Log a suppressed signal to MongoDB collection suppressed_signals."""
        if self._db is None:
            return
        try:
            await self._db.suppressed_signals.insert_one({
                "pair":      pair.upper(),
                "direction": direction.upper(),
                "engine":    engine,
                "reason":    reason,
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception as exc:
            logger.debug(f"[SignalDedup] log_suppression failed (non-fatal): {exc}")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _prune_cache(self, now_ts: float) -> None:
        """Remove entries older than 30 minutes (called inside lock)."""
        cutoff = now_ts - 1800
        stale  = [k for k, v in self._cache.items() if v < cutoff]
        for k in stale:
            del self._cache[k]

        coin_cutoff = now_ts - 600
        stale_coins = [p for p, v in self._coin_last.items() if v.get("ts", 0) < coin_cutoff]
        for p in stale_coins:
            del self._coin_last[p]


# ── Module-level singleton ────────────────────────────────────────────────────

signal_deduplicator = SignalDeduplicator()


def init_signal_deduplicator(db) -> SignalDeduplicator:
    """
    Wire the singleton to the motor DB instance.
    Call once from server.py after DB is available.
    Returns the singleton for convenience.
    """
    signal_deduplicator._db = db
    return signal_deduplicator
