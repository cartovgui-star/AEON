"""
Phase 1 — Trade candidate journal.

Persists every TradeCandidate (approved, advisory, or gate-rejected) to MongoDB
collection "trade_candidates" with a 30-day TTL index.

All writes are fire-and-forget via asyncio.create_task() to keep the
gate/routing pipeline non-blocking. Use log_async() when a confirmed write
is required (e.g. tests or startup checks).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from candidate_trade import TradeCandidate

logger = logging.getLogger(__name__)

COLLECTION = "trade_candidates"
TTL_SECONDS = 30 * 24 * 3600   # 30 days


class TradeJournal:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._indexes_created = False

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, candidate: TradeCandidate) -> None:
        """
        Non-blocking fire-and-forget. Safe to call from anywhere in an async context.
        Errors are logged but never raised.
        """
        try:
            asyncio.create_task(self._write(candidate))
        except RuntimeError:
            # No running event loop (e.g. called from sync context during tests)
            logger.warning(
                f"[TradeJournal] No event loop — skipping journal for {candidate.candidate_id}"
            )

    async def log_async(self, candidate: TradeCandidate) -> bool:
        """Awaitable version. Returns True on success."""
        return await self._write(candidate)

    async def ensure_indexes(self) -> None:
        if self._indexes_created:
            return
        col = self.db[COLLECTION]
        await col.create_index("created_at", expireAfterSeconds=TTL_SECONDS)
        await col.create_index("symbol")
        await col.create_index("engine")
        await col.create_index("gate_passed")
        await col.create_index([("symbol", 1), ("created_at", -1)])
        await col.create_index([("engine", 1), ("created_at", -1)])
        self._indexes_created = True
        logger.info(f"[TradeJournal] Indexes ensured on '{COLLECTION}' (TTL={TTL_SECONDS}s)")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _write(self, candidate: TradeCandidate) -> bool:
        try:
            await self.ensure_indexes()
            await self.db[COLLECTION].insert_one(candidate.to_dict())
            return True
        except Exception as e:
            logger.error(
                f"[TradeJournal] Write failed for {candidate.candidate_id} "
                f"({candidate.symbol} {candidate.direction}): {e}"
            )
            return False
