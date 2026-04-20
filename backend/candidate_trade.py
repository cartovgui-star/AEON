"""
Phase 1 — Canonical trade candidate schema.

A TradeCandidate is created after a signal clears the gate pipeline and before
account routing. It carries the full lineage of a trade idea: what was requested,
what the policy approved, and what was ultimately executed — per account.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class AccountDecision:
    """
    Per-account risk evaluation result produced by RiskPolicy.
    Tracks the requested → approved → executed chain for leverage and sizing.
    """
    account_id: str

    # "APPROVE" | "ADVISORY" | "REJECT"
    verdict: str = "APPROVE"

    # Advisory notes (non-blocking in advisory mode)
    advisory_notes: List[str] = field(default_factory=list)

    # Hard rejection reasons (always blocking)
    rejection_reasons: List[str] = field(default_factory=list)

    # Leverage chain
    requested_leverage: int = 0
    approved_leverage: int = 0
    executed_leverage: Optional[int] = None   # filled after open_position returns

    # Size multiplier chain (1.0 = full size)
    requested_size_multiplier: float = 1.0    # from StressMonitor
    approved_size_multiplier: float = 1.0     # after policy (Phase 1: same as requested)
    executed_size_multiplier: Optional[float] = None  # filled after open_position returns

    # Heat snapshot at evaluation time
    heat_score: float = 0.0
    long_heat: float = 0.0
    short_heat: float = 0.0


@dataclass
class TradeCandidate:
    """
    Canonical schema for a trade idea moving through the pipeline.

    Lifecycle:
        created   → gate pipeline output (gate_passed=True)
        evaluated → RiskPolicy fills account_decisions
        routed    → route_signal_to_accounts fills route_results + routed_at
        journaled → TradeJournal persists to MongoDB
    """

    # Identity
    candidate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    direction: str = ""          # "LONG" | "SHORT"
    engine: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # What the engine requested
    confidence: float = 0.0
    confluences: int = 0
    requested_leverage: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    strategy: Optional[str] = None

    # Gate pipeline context (populated from gate outputs)
    mtf_score: Optional[float] = None
    quant_score: Optional[float] = None

    # StressMonitor state consumed as-is — not recomputed here
    stress_level: Optional[float] = None       # StressMonitor.stress_score
    stress_multiplier: Optional[float] = None  # StressMonitor.get_size_multiplier()[0]

    gate_passed: bool = False
    gate_rejection_reason: Optional[str] = None

    # Per-account decisions (keyed by account_id, filled by RiskPolicy)
    account_decisions: Dict[str, AccountDecision] = field(default_factory=dict)

    # Routing outcome
    routed_at: Optional[datetime] = None
    route_results: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize for MongoDB storage. Motor handles datetime natively."""
        return {
            "candidate_id": self.candidate_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "engine": self.engine,
            "created_at": self.created_at,
            "confidence": self.confidence,
            "confluences": self.confluences,
            "requested_leverage": self.requested_leverage,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strategy": self.strategy,
            "mtf_score": self.mtf_score,
            "quant_score": self.quant_score,
            "stress_level": self.stress_level,
            "stress_multiplier": self.stress_multiplier,
            "gate_passed": self.gate_passed,
            "gate_rejection_reason": self.gate_rejection_reason,
            "account_decisions": {
                acc_id: {
                    "verdict": d.verdict,
                    "advisory_notes": d.advisory_notes,
                    "rejection_reasons": d.rejection_reasons,
                    "requested_leverage": d.requested_leverage,
                    "approved_leverage": d.approved_leverage,
                    "executed_leverage": d.executed_leverage,
                    "requested_size_multiplier": d.requested_size_multiplier,
                    "approved_size_multiplier": d.approved_size_multiplier,
                    "executed_size_multiplier": d.executed_size_multiplier,
                    "heat_score": d.heat_score,
                    "long_heat": d.long_heat,
                    "short_heat": d.short_heat,
                }
                for acc_id, d in self.account_decisions.items()
            },
            "routed_at": self.routed_at,
            "route_results": self.route_results,
        }
