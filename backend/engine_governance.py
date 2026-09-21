"""
Phase 3 — Engine governance actions and state management.

Evaluates weekly engine health buckets and emits governance recommendations.
Stores two MongoDB document types per engine:
  - engine_governance        (current state, always upsert)
  - engine_governance_log    (event log, appended only on change)

Actions (ascending severity):
  promote_candidate → monitor → restricted → sandbox_only → disable_candidate

Governance logging fires only when tier, recommendation, or material rationale changes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from engine_health import EngineHealth, EngineHealthScorer, CANONICAL_ENGINE_NAMES

# ── Constants ─────────────────────────────────────────────────────────────────

MIN_TRADES_FOR_PROMOTE       = 20   # n_clean threshold for promote_candidate
MIN_WEEKLY_TRADES_FOR_D_COUNT = 5   # ignore D weeks with fewer clean trades
CONSECUTIVE_D_FOR_SANDBOX    = 3    # weeks before sandbox_only
CONSECUTIVE_D_FOR_DISABLE    = 5    # weeks before disable_candidate

WEEKS_OF_HISTORY = 4                # rolling window for weekly buckets

# Score bands used for recommendation logic (mirrors tier thresholds)
PROMOTE_SCORE    = 70.0
MONITOR_SCORE    = 55.0
RESTRICT_SCORE   = 40.0


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class GovernanceState:
    engine: str
    recommendation: str              # promote_candidate|monitor|restricted|sandbox_only|disable_candidate
    rationale: str
    current_score: float
    current_tier: str
    consecutive_d_weeks: int
    n_clean_last_week: int
    promote_eligible: bool
    updated_at: datetime
    last_change_at: Optional[datetime] = None
    prev_recommendation: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "current_score": self.current_score,
            "current_tier": self.current_tier,
            "consecutive_d_weeks": self.consecutive_d_weeks,
            "n_clean_last_week": self.n_clean_last_week,
            "promote_eligible": self.promote_eligible,
            "updated_at": self.updated_at.isoformat(),
            "last_change_at": self.last_change_at.isoformat() if self.last_change_at else None,
            "prev_recommendation": self.prev_recommendation,
        }


@dataclass
class GovernanceEvent:
    engine: str
    event_type: str                  # "initial"|"tier_change"|"recommendation_change"|"rationale_change"
    recommendation: str
    prev_recommendation: Optional[str]
    tier: str
    score: float
    rationale: str
    consecutive_d_weeks: int
    occurred_at: datetime

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "event_type": self.event_type,
            "recommendation": self.recommendation,
            "prev_recommendation": self.prev_recommendation,
            "tier": self.tier,
            "score": self.score,
            "rationale": self.rationale,
            "consecutive_d_weeks": self.consecutive_d_weeks,
            "occurred_at": self.occurred_at.isoformat(),
        }


# ── Governance logic ──────────────────────────────────────────────────────────

class EngineGovernance:
    """
    Runs weekly health buckets against CANONICAL_ENGINE_NAMES and emits
    governance recommendations. All DB writes are async; safe to call from
    background tasks.
    """

    def __init__(self):
        self._scorer = EngineHealthScorer()

    # ── Public API ────────────────────────────────────────────────────────────

    async def run_all(self, db) -> Dict[str, GovernanceState]:
        """Evaluate governance for all canonical engines. Returns current states."""
        results: Dict[str, GovernanceState] = {}
        tasks = [self._run_one(db, engine) for engine in CANONICAL_ENGINE_NAMES]
        states = await asyncio.gather(*tasks, return_exceptions=True)
        for engine, state in zip(CANONICAL_ENGINE_NAMES, states):
            if isinstance(state, Exception):
                continue
            results[engine] = state
        return results

    async def run_one(self, db, engine: str) -> GovernanceState:
        return await self._run_one(db, engine)

    async def get_current_states(self, db) -> List[dict]:
        docs = await db.engine_governance.find(
            {}, {"_id": 0}
        ).sort("engine", 1).to_list(length=100)
        return docs

    async def get_log(self, db, limit: int = 50, engine: str = None) -> List[dict]:
        query = {"engine": engine} if engine else {}
        docs = await db.engine_governance_log.find(
            query, {"_id": 0}
        ).sort("occurred_at", -1).limit(limit).to_list(length=limit)
        return docs

    async def ensure_indexes(self, db) -> None:
        await db.engine_governance.create_index("engine", unique=True)
        await db.engine_governance_log.create_index([("engine", 1), ("occurred_at", -1)])
        await db.engine_governance_log.create_index("occurred_at")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run_one(self, db, engine: str) -> GovernanceState:
        weekly_buckets = await self._fetch_weekly_buckets(db, engine)
        current_health = await self._scorer.compute_one(db, engine, days=7)
        consecutive_d = self._count_consecutive_d_weeks(weekly_buckets)

        recommendation, rationale = self._decide(current_health, consecutive_d)
        promote_elig = current_health.promote_eligible()

        now = datetime.now(timezone.utc)
        state = GovernanceState(
            engine=engine,
            recommendation=recommendation,
            rationale=rationale,
            current_score=current_health.score,
            current_tier=current_health.tier,
            consecutive_d_weeks=consecutive_d,
            n_clean_last_week=current_health.n_clean,
            promote_eligible=promote_elig,
            updated_at=now,
        )

        await self._persist(db, state)
        return state

    async def _fetch_weekly_buckets(self, db, engine: str) -> List[EngineHealth]:
        """
        Returns up to WEEKS_OF_HISTORY scored EngineHealth objects,
        oldest-first. Uses non-overlapping 7-day windows.
        """
        buckets: List[EngineHealth] = []
        now = datetime.now(timezone.utc)
        for week_i in range(WEEKS_OF_HISTORY, 0, -1):
            week_end   = now - timedelta(days=7 * (week_i - 1))
            week_start = week_end - timedelta(days=7)
            trades = await db.paper_trades.find(
                {
                    "strategy": engine,
                    "opened_at": {"$gte": week_start, "$lt": week_end},
                    "status": "closed",
                },
                {
                    "realized_pnl": 1, "initial_margin": 1, "close_reason": 1,
                    "opened_at": 1, "leverage": 1, "account_id": 1,
                }
            ).to_list(length=5000)
            health = EngineHealthScorer.score_trade_list(trades, engine)
            buckets.append(health)
        return buckets

    @staticmethod
    def _count_consecutive_d_weeks(buckets: List[EngineHealth]) -> int:
        """
        Count trailing consecutive weeks with tier D and sufficient activity.
        Weeks with n_clean < MIN_WEEKLY_TRADES_FOR_D_COUNT are skipped (not counted,
        not reset).
        """
        count = 0
        for bucket in reversed(buckets):
            if bucket.tier == "insufficient_data":
                continue
            if bucket.n_clean < MIN_WEEKLY_TRADES_FOR_D_COUNT:
                continue
            if bucket.tier == "D":
                count += 1
            else:
                break
        return count

    @staticmethod
    def _decide(health: EngineHealth, consecutive_d: int) -> tuple[str, str]:
        """Return (recommendation, rationale) given current health."""
        tier  = health.tier
        score = health.score

        malformed_note = (
            f" ⚠ {health.malformed_trades} malformed stop placement(s) detected."
            if health.malformed_trades > 0 else ""
        )
        cohort_note = (
            f" Signal cohorts: {health.n_cohorts} independent signals "
            f"({health.n_clean} raw trades, {health.n_clean // max(health.n_cohorts, 1)}x echo)."
            if health.n_clean > health.n_cohorts else ""
        )

        if tier == "insufficient_data":
            return "monitor", (
                f"Insufficient data — fewer than 3 independent signal cohorts in window."
                f"{malformed_note}"
            )

        if consecutive_d >= CONSECUTIVE_D_FOR_DISABLE:
            return (
                "disable_candidate",
                f"{consecutive_d} consecutive D-tier weeks (≥{CONSECUTIVE_D_FOR_DISABLE}) "
                f"with sufficient activity. Score {score:.1f}. Engine is not generating edge."
                f"{cohort_note}{malformed_note}"
            )

        if consecutive_d >= CONSECUTIVE_D_FOR_SANDBOX:
            return (
                "sandbox_only",
                f"{consecutive_d} consecutive D-tier weeks (≥{CONSECUTIVE_D_FOR_SANDBOX}). "
                f"Score {score:.1f}. Isolate to sandbox until trend reverses."
                f"{cohort_note}{malformed_note}"
            )

        if tier == "D":
            return (
                "restricted",
                f"Tier D (score {score:.1f}). Poor expectancy or high liquidation rate. "
                f"Reduce position sizing until health improves."
                f"{cohort_note}{malformed_note}"
            )

        if tier == "C":
            return (
                "monitor",
                f"Tier C (score {score:.1f}). Below target edge — watch for trend."
                f"{cohort_note}{malformed_note}"
            )

        if tier == "B":
            if health.liquidation_rate > 0.10:
                return (
                    "monitor",
                    f"Tier B (score {score:.1f}) but liquidation rate "
                    f"{health.liquidation_rate:.1%} is elevated. Monitor closely."
                    f"{cohort_note}{malformed_note}"
                )
            return "monitor", (
                f"Tier B (score {score:.1f}). Performing adequately."
                f"{cohort_note}{malformed_note}"
            )

        # Tier A
        if health.promote_eligible():
            return (
                "promote_candidate",
                f"Tier A (score {score:.1f}) with {health.n_cohorts} independent signal cohorts "
                f"(≥{MIN_TRADES_FOR_PROMOTE} required). Strong edge — eligible for live promotion review."
                f"{malformed_note}"
            )
        return (
            "monitor",
            f"Tier A (score {score:.1f}) but only {health.n_cohorts} independent signal cohorts "
            f"(need {MIN_TRADES_FOR_PROMOTE} for promote_candidate). Continue accumulating data."
            f"{malformed_note}"
        )

    async def _persist(self, db, state: GovernanceState) -> None:
        """Upsert current state; append to log only on material change."""
        existing = await db.engine_governance.find_one(
            {"engine": state.engine}, {"_id": 0}
        )

        tier_changed          = existing and existing.get("current_tier")       != state.current_tier
        rec_changed           = existing and existing.get("recommendation")     != state.recommendation
        rationale_changed     = existing and existing.get("rationale")          != state.rationale
        is_new                = existing is None

        if is_new or tier_changed or rec_changed or rationale_changed:
            if existing:
                state.prev_recommendation = existing.get("recommendation")
                state.last_change_at = state.updated_at

            event_type = "initial" if is_new else (
                "tier_change"           if tier_changed  else
                "recommendation_change" if rec_changed   else
                "rationale_change"
            )
            event = GovernanceEvent(
                engine=state.engine,
                event_type=event_type,
                recommendation=state.recommendation,
                prev_recommendation=state.prev_recommendation,
                tier=state.current_tier,
                score=state.current_score,
                rationale=state.rationale,
                consecutive_d_weeks=state.consecutive_d_weeks,
                occurred_at=state.updated_at,
            )
            await db.engine_governance_log.insert_one(event.to_dict())

        doc = state.to_dict()
        await db.engine_governance.update_one(
            {"engine": state.engine},
            {"$set": doc},
            upsert=True,
        )
