"""
Phase 1 — Central paper-only risk policy.

Evaluates a TradeCandidate against each account and returns per-account
AccountDecision objects. Does not touch routing or position logic.

Modes:
  "advisory"  — logs issues as advisory notes; only portfolio heat triggers
                hard REJECT. Safe to enable immediately.
  "enforce"   — all violations become hard REJECTs. Enable after advisory
                mode has been observed for a while.

What this policy checks (dedup/conflict NOT here — that stays in route_signal_to_accounts):
  1. Portfolio heat     — hard block in both modes when >= MAX_PORTFOLIO_HEAT
  2. Balance floor      — advisory or enforce depending on mode
  3. BTC-ecosystem cluster — advisory or enforce depending on mode
  4. Account max leverage — advisory note (never hard-blocks leverage in Phase 1)

StressMonitor state is consumed as input (stress_level, stress_multiplier).
It is never recomputed here.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from candidate_trade import AccountDecision, TradeCandidate
from portfolio_heat import MAX_CLUSTER_LONGS, MAX_PORTFOLIO_HEAT, PortfolioHeat

logger = logging.getLogger(__name__)

BALANCE_FLOOR_PCT: float = 0.05   # reject if balance < 5% of starting_balance


class RiskPolicy:
    """
    Paper-only risk policy. Stateless per evaluation — safe to call concurrently.

    Args:
        mode: "advisory" (default, Phase 1) or "enforce"
    """

    def __init__(self, mode: str = "advisory"):
        if mode not in ("advisory", "enforce"):
            raise ValueError(f"Invalid RiskPolicy mode: {mode!r}. Use 'advisory' or 'enforce'.")
        self.mode = mode
        self._heat = PortfolioHeat()
        logger.info(f"[RiskPolicy] Initialized in {mode.upper()} mode")

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        candidate: TradeCandidate,
        accounts_data: dict,
        stress_level: Optional[float] = None,
        stress_multiplier: Optional[float] = None,
    ) -> Dict[str, AccountDecision]:
        """
        Evaluate candidate for every account in accounts_data.

        accounts_data: Dict[account_id → account_doc].
            Each account_doc should have "_config" merged in
            (i.e. {**live_account, "_config": ACCOUNTS[acc_id]}).

        Returns Dict[account_id → AccountDecision].
        """
        decisions: Dict[str, AccountDecision] = {}

        for account_id, account_data in accounts_data.items():
            decisions[account_id] = self._evaluate_account(
                candidate=candidate,
                account_id=account_id,
                account_data=account_data,
                stress_multiplier=stress_multiplier,
            )

        return decisions

    # ── Internal ──────────────────────────────────────────────────────────────

    def _evaluate_account(
        self,
        candidate: TradeCandidate,
        account_id: str,
        account_data: dict,
        stress_multiplier: Optional[float],
    ) -> AccountDecision:
        config = account_data.get("_config", {})
        starting_balance = float(account_data.get("starting_balance") or 1.0)
        balance = float(account_data.get("balance") or 0.0)

        heat = self._heat.compute(account_id, account_data)

        advisory_notes: list = []
        rejection_reasons: list = []

        # ── 1. Portfolio heat (hard block in both modes) ──────────────────────
        if heat.is_overheated:
            rejection_reasons.append(
                f"Portfolio heat {heat.total_heat:.1%} >= {MAX_PORTFOLIO_HEAT:.0%} threshold "
                f"(long {heat.long_heat:.1%} / short {heat.short_heat:.1%})"
            )

        # ── 2. Balance floor ──────────────────────────────────────────────────
        floor = starting_balance * BALANCE_FLOOR_PCT
        if balance < floor:
            msg = (
                f"Balance ${balance:.2f} below floor ${floor:.2f} "
                f"({BALANCE_FLOOR_PCT:.0%} of ${starting_balance:.2f})"
            )
            if self.mode == "enforce":
                rejection_reasons.append(msg)
            else:
                advisory_notes.append(f"[ADVISORY] {msg}")

        # ── 3. BTC-ecosystem cluster long alert ───────────────────────────────
        if heat.cluster_alert and candidate.direction.upper() == "LONG":
            msg = (
                f"BTC-ecosystem cluster: {heat.cluster_long_count} correlated longs open "
                f"(threshold: {MAX_CLUSTER_LONGS})"
            )
            if self.mode == "enforce":
                rejection_reasons.append(msg)
            else:
                advisory_notes.append(f"[ADVISORY] {msg}")

        # ── 4. Account max leverage (advisory only, never hard-blocks in Phase 1) ──
        max_leverage = config.get("max_leverage", 20)
        if candidate.requested_leverage > max_leverage:
            advisory_notes.append(
                f"[ADVISORY] Requested leverage {candidate.requested_leverage}x "
                f"exceeds account profile max {max_leverage}x for {account_id}"
            )

        # ── 5. Duplicate symbol in heat report ────────────────────────────────
        if candidate.symbol in heat.duplicate_symbols:
            advisory_notes.append(
                f"[ADVISORY] {candidate.symbol} already has >1 open position on {account_id}"
            )

        # Determine verdict
        if rejection_reasons:
            verdict = "REJECT"
        elif advisory_notes:
            verdict = "ADVISORY"
        else:
            verdict = "APPROVE"

        # Approved sizing defaults to stress multiplier (policy does not further reduce in Phase 1)
        size_mult = stress_multiplier if stress_multiplier is not None else 1.0

        if verdict == "REJECT":
            logger.info(
                f"[RiskPolicy/{self.mode.upper()}] {account_id} REJECT "
                f"{candidate.symbol} {candidate.direction}: "
                + "; ".join(rejection_reasons)
            )
        elif advisory_notes:
            logger.debug(
                f"[RiskPolicy/ADVISORY] {account_id} {candidate.symbol}: "
                + "; ".join(advisory_notes)
            )

        return AccountDecision(
            account_id=account_id,
            verdict=verdict,
            advisory_notes=advisory_notes,
            rejection_reasons=rejection_reasons,
            requested_leverage=candidate.requested_leverage,
            approved_leverage=candidate.requested_leverage,  # Phase 1: no leverage reduction
            requested_size_multiplier=size_mult,
            approved_size_multiplier=size_mult,
            heat_score=heat.total_heat,
            long_heat=heat.long_heat,
            short_heat=heat.short_heat,
        )
