"""
Phase 3 — Engine health scoring.

Scores each engine from paper_trades history using a shrinkage-adjusted
formula that weights expectancy and profit quality over raw win rate.

Formula:
  raw   = 0.40 × expectancy_score
        + 0.30 × profit_factor_score
        + 0.20 × win_rate_score
        − 0.10 × liquidation_penalty
  score = shrinkage × raw + (1 − shrinkage) × 50
  shrinkage = n_cohorts / (n_cohorts + 20)   ← uses independent signal cohorts

Cohort detection:
  Trades with the same symbol + direction opened within COHORT_WINDOW_SECONDS
  of each other are grouped as a single signal echoed to multiple accounts.
  Shrinkage uses n_cohorts (independent signals), not raw trade count.
  Per-trade PnL metrics still use all clean trades for representative sizing.

Tiers: A ≥ 70 | B 55–69 | C 40–54 | D < 40 | insufficient_data if n_cohorts < 3

Malformed trade detection:
  LONG with stop_loss >= entry_price → malformed
  SHORT with stop_loss <= entry_price → malformed
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

WIN_REASONS   = {"take_profit", "trailing_stop"}
LOSS_REASONS  = {"stop_loss", "liquidation"}
LIQ_REASON    = "liquidation"
STALE_REASONS = {"stale_cleanup"}

SHRINKAGE_K           = 20   # soft shrinkage denominator (n / (n + K))
PROMOTE_MIN_TRADES    = 20   # minimum n_cohorts to be eligible for promote_candidate
COHORT_WINDOW_SECONDS = 60   # trades within this window = same signal (multi-account echo)

CANONICAL_ENGINE_NAMES: List[str] = [
    "FREE_WILL_V2",
    "HYPER_ACCURACY",
    "VOLUME_PROFILE",
    "AUTONOMOUS_V2",
    "DUAL_DAY_TRADER",
    "DUAL_LONG_TERM",
    "VWAP_SCALPER",
    "YOLO_ENGINE",
    "ELITE_STRATEGY",
    "TCN_NEURAL",
    "INSTITUTIONAL_SCALPER",
]

TIER_THRESHOLDS = {"A": 70.0, "B": 55.0, "C": 40.0}


def _assign_tier(score: float) -> str:
    if score >= TIER_THRESHOLDS["A"]:
        return "A"
    if score >= TIER_THRESHOLDS["B"]:
        return "B"
    if score >= TIER_THRESHOLDS["C"]:
        return "C"
    return "D"


@dataclass
class EngineHealth:
    engine: str
    score: float                    # 0-100, shrinkage-adjusted
    tier: str                       # "A"|"B"|"C"|"D"|"insufficient_data"
    n_clean: int                    # wins + losses (stale excluded), raw trade count
    n_total: int                    # all closed trades in window
    n_cohorts: int                  # independent signal cohorts (used for shrinkage)
    shrinkage_factor: float         # n_cohorts / (n_cohorts + 20)
    malformed_trades: int           # trades with SL on wrong side of entry

    # Core quality metrics (computed across all clean trades for representative sizing)
    win_rate: float
    avg_win_pct: float              # avg realized_pnl / initial_margin × 100 for wins
    avg_loss_pct: float             # same for losses (negative)
    expectancy_pct: float           # win_rate × avg_win + loss_rate × avg_loss
    profit_factor: float            # gross_profit / |gross_loss|
    liquidation_rate: float         # liqs / n_clean

    # Execution profile
    leverage_profile: dict          # mean, p50, p90, max
    account_exposure: dict          # {account_id: trade_count}

    # Metadata
    lookback_days: int
    data_since: Optional[datetime]
    computed_at: datetime

    def promote_eligible(self) -> bool:
        return self.tier == "A" and self.n_cohorts >= PROMOTE_MIN_TRADES

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "score": self.score,
            "tier": self.tier,
            "n_clean": self.n_clean,
            "n_total": self.n_total,
            "n_cohorts": self.n_cohorts,
            "shrinkage_factor": self.shrinkage_factor,
            "malformed_trades": self.malformed_trades,
            "promote_eligible": self.promote_eligible(),
            "win_rate": self.win_rate,
            "avg_win_pct": self.avg_win_pct,
            "avg_loss_pct": self.avg_loss_pct,
            "expectancy_pct": self.expectancy_pct,
            "profit_factor": self.profit_factor,
            "liquidation_rate": self.liquidation_rate,
            "leverage_profile": self.leverage_profile,
            "account_exposure": self.account_exposure,
            "lookback_days": self.lookback_days,
            "data_since": self.data_since.isoformat() if self.data_since else None,
            "computed_at": self.computed_at.isoformat(),
        }


class EngineHealthScorer:
    """
    Computes EngineHealth objects from paper_trades.
    All methods are stateless — safe to call concurrently.
    """

    async def compute_all(self, db, days: int = 7) -> Dict[str, EngineHealth]:
        results: Dict[str, EngineHealth] = {}
        for engine in CANONICAL_ENGINE_NAMES:
            results[engine] = await self.compute_one(db, engine, days)
        return results

    async def compute_one(self, db, engine: str, days: int = 7) -> EngineHealth:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        trades = await db.paper_trades.find(
            {"strategy": engine, "opened_at": {"$gte": since}},
            {
                "realized_pnl": 1, "initial_margin": 1, "close_reason": 1,
                "opened_at": 1, "leverage": 1, "account_id": 1, "id": 1,
                "direction": 1, "symbol": 1, "entry_price": 1, "stop_loss": 1,
            }
        ).to_list(length=20000)
        return self._compute(engine, trades, days)

    # ── Cohort detection ──────────────────────────────────────────────────────

    @staticmethod
    def _count_cohorts(trades: list) -> int:
        """
        Count independent signal cohorts. Trades with the same symbol + direction
        opened within COHORT_WINDOW_SECONDS of each other are a single cohort
        (same signal echoed to multiple accounts).

        Returns the number of distinct independent signals.
        """
        if not trades:
            return 0

        window = timedelta(seconds=COHORT_WINDOW_SECONDS)
        # Sort by symbol, direction, then open time
        keyed = []
        for t in trades:
            ot = t.get("opened_at")
            if ot is None:
                continue
            # Ensure timezone-aware for comparison
            if isinstance(ot, datetime) and ot.tzinfo is None:
                ot = ot.replace(tzinfo=timezone.utc)
            keyed.append((t.get("symbol", ""), t.get("direction", ""), ot))

        keyed.sort(key=lambda x: (x[0], x[1], x[2]))

        cohort_count = 0
        last_sym, last_dir, last_time = None, None, None
        for sym, direction, ot in keyed:
            if (sym != last_sym or direction != last_dir
                    or last_time is None or (ot - last_time) > window):
                cohort_count += 1
                last_sym, last_dir, last_time = sym, direction, ot
            # else: same cohort — update last_time to extend window
            last_time = ot

        return cohort_count

    @staticmethod
    def _count_malformed(trades: list) -> int:
        """
        Count trades where the stop_loss is on the wrong side of entry.
        LONG: stop_loss must be below entry_price
        SHORT: stop_loss must be above entry_price
        """
        count = 0
        for t in trades:
            direction = (t.get("direction") or "").upper()
            entry = t.get("entry_price") or 0
            sl    = t.get("stop_loss")
            if entry <= 0 or sl is None:
                continue
            if direction == "LONG" and sl >= entry:
                count += 1
            elif direction == "SHORT" and sl <= entry:
                count += 1
        return count

    # ── Static scoring helpers ────────────────────────────────────────────────

    @staticmethod
    def _compute(engine: str, trades: list, lookback_days: int) -> EngineHealth:
        wins   = [t for t in trades if t.get("close_reason") in WIN_REASONS]
        losses = [t for t in trades if t.get("close_reason") in LOSS_REASONS]
        liqs   = [t for t in trades if t.get("close_reason") == LIQ_REASON]
        stale  = [t for t in trades if t.get("close_reason") in STALE_REASONS]

        n_clean  = len(wins) + len(losses)
        n_total  = n_clean + len(stale)
        n_cohorts = EngineHealthScorer._count_cohorts(wins + losses)
        malformed = EngineHealthScorer._count_malformed(trades)

        # Per-trade PnL as % of initial_margin
        def _pnl_pct(t: dict) -> Optional[float]:
            im = t.get("initial_margin") or 0
            return (t.get("realized_pnl", 0) / im * 100) if im > 0 else None

        win_pcts  = [p for t in wins   for p in [_pnl_pct(t)] if p is not None]
        loss_pcts = [p for t in losses for p in [_pnl_pct(t)] if p is not None]

        win_rate     = len(wins) / n_clean if n_clean > 0 else 0.0
        avg_win_pct  = sum(win_pcts)  / len(win_pcts)  if win_pcts  else 0.0
        avg_loss_pct = sum(loss_pcts) / len(loss_pcts) if loss_pcts else 0.0
        expectancy   = win_rate * avg_win_pct + (1 - win_rate) * avg_loss_pct

        gross_profit = sum(t.get("realized_pnl", 0) for t in wins)
        gross_loss   = abs(sum(t.get("realized_pnl", 0) for t in losses))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = 5.0   # no losses yet — cap at 5 to avoid inf
        else:
            profit_factor = 1.0   # zero activity

        liq_rate = len(liqs) / n_clean if n_clean > 0 else 0.0

        # Leverage profile
        levers = sorted(t.get("leverage") or 0 for t in trades if t.get("leverage"))
        leverage_profile: dict = {}
        if levers:
            n = len(levers)
            leverage_profile = {
                "mean": round(sum(levers) / n, 1),
                "p50":  levers[n // 2],
                "p90":  levers[min(int(n * 0.9), n - 1)],
                "max":  levers[-1],
            }

        # Account exposure
        account_exposure: dict = {}
        for t in trades:
            acc = t.get("account_id", "unknown")
            account_exposure[acc] = account_exposure.get(acc, 0) + 1

        # Earliest trade date
        dates = [t["opened_at"] for t in trades if "opened_at" in t]
        data_since = min(dates) if dates else None

        # Compute shrinkage-adjusted score using n_cohorts for confidence weighting
        if n_cohorts < 3:
            return EngineHealth(
                engine=engine, score=50.0, tier="insufficient_data",
                n_clean=n_clean, n_total=n_total,
                n_cohorts=n_cohorts, shrinkage_factor=0.0,
                malformed_trades=malformed,
                win_rate=round(win_rate, 4), avg_win_pct=round(avg_win_pct, 2),
                avg_loss_pct=round(avg_loss_pct, 2), expectancy_pct=round(expectancy, 2),
                profit_factor=round(profit_factor, 2), liquidation_rate=round(liq_rate, 4),
                leverage_profile=leverage_profile, account_exposure=account_exposure,
                lookback_days=lookback_days, data_since=data_since,
                computed_at=datetime.now(timezone.utc),
            )

        shrinkage = n_cohorts / (n_cohorts + SHRINKAGE_K)

        expectancy_score = max(0.0, min(100.0, (expectancy + 5.0) / 10.0 * 100.0))
        pf_score         = max(0.0, min(100.0, profit_factor / 3.0 * 100.0))
        wr_score         = win_rate * 100.0
        liq_penalty      = liq_rate * 100.0

        raw   = 0.40 * expectancy_score + 0.30 * pf_score + 0.20 * wr_score - 0.10 * liq_penalty
        score = round(max(0.0, min(100.0, shrinkage * raw + (1 - shrinkage) * 50.0)), 2)
        tier  = _assign_tier(score)

        return EngineHealth(
            engine=engine, score=score, tier=tier,
            n_clean=n_clean, n_total=n_total,
            n_cohorts=n_cohorts,
            shrinkage_factor=round(shrinkage, 3),
            malformed_trades=malformed,
            win_rate=round(win_rate, 4),
            avg_win_pct=round(avg_win_pct, 2),
            avg_loss_pct=round(avg_loss_pct, 2),
            expectancy_pct=round(expectancy, 2),
            profit_factor=round(profit_factor, 2),
            liquidation_rate=round(liq_rate, 4),
            leverage_profile=leverage_profile,
            account_exposure=account_exposure,
            lookback_days=lookback_days,
            data_since=data_since,
            computed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def score_trade_list(trades: list, engine: str = "?") -> EngineHealth:
        """Score an arbitrary list of trade dicts. Used by governance for weekly bucketing."""
        return EngineHealthScorer._compute(engine, trades, lookback_days=7)
