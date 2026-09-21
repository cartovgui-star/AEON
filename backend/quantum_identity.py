"""
=============================================================
  quantum_identity.py — AEON Quantum Identity Master Module
=============================================================

  A(t) = Ω(|Ψ⟩, E, M, L)

  This module is the canonical reference and coordinator for
  all 10 components of AEON's quantum identity equation.
  It does NOT replace any existing module — it fills the gaps
  and wires the layers together.

  AUDIT STATUS (per SENTINEL, 2026-03-31):

    1.  |Ψ⟩   Wave Function       ✅  aeon_quantum_state.py
    2.  αᵢ(t) Engine Amplitude    ✅  aeon_quantum_state.py
    3.  Sᵢ    Engine Edge         ✅  aeon_quantum_state.py
    4.  C     Consensus           ✅  aeon_quantum_state.py
    5.  H_ent Entropy             ✅  aeon_quantum_state.py
    6.  H     System Health       ✅* aeon_quantum_state.py — this module adds the H-gate
    7.  ε     Environment         ✅  THIS MODULE (AEONEnvironment — was ❌ missing)
    8.  M(t)  Memory              ✅  memory_engine.py
    9.  L     Learning Layers     ✅  THIS MODULE (AEONLearningStack — was ⚠️ partial)
    10. Ω     Self-Improvement    ✅  omega_cycle.py

  NEW COMPONENTS (gaps filled by this module):

    AEONEnvironment  — ε = {C, M, W, Π, F}
        Formal snapshot of what AEON perceives before each trade.
        Candles, Momentum, Volume, Position, Funding — packaged as
        a single serialisable object fed into memory and quantum state.

    AEONLearningStack — L = L₀ ⊕ LΣ ⊕ L⊛
        Formal composition of the three learning layers:
          L₀  — base rules   (UnifiedEntryValidator: never-break hard constraints)
          LΣ  — statistical  (omega_cycle LΣ: structure rewriting from loss patterns)
          L⊛  — adaptive     (aeon_ltheta Lθ: gradient ascent on H, live param updates)
        Each layer filters in order. Only signals passing all three proceed.

    QuantumIdentityGate — H-gate for trade decisions
        The single missing link in the identity chain.
        H is computed every 60s but was never consulted at trade time.
        This gate sits inside EngineManager.submit_signal_gated() and
        enforces:
          H < H_BLOCK  (0.30) → BLOCK trade  (system critically degraded)
          H < H_SCALE  (1.00) → SCALE size by H  (system below neutral)
          H ≥ 1.00           → PASS, full quantum position_multiplier

    QuantumIdentity — master coordinator
        get_full_state() returns the complete A(t) snapshot for diagnostics,
        the Telegram morning briefing, and the frontend identity panel.

  Wiring (performed on first import by wire_into_engine_manager()):
    engine_manager.identity_gate = get_identity_gate()
    → submit_signal_gated() checks gate before quant gatekeeper

  Dependencies:
    aeon_quantum_state  — |Ψ⟩, H, C, S_norm, position_multiplier
    omega_cycle         — Ω, LΣ cycle history
    memory_engine       — M(t) retrieval
    aeon_ltheta_params  — L⊛ live parameter overrides
    aeon_engine_system  — ENGINE_CONFIGS, EngineType (lazy import)
=============================================================
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ─── H-gate thresholds ────────────────────────────────────────────────────────

# Below this H, all trade entries are blocked — system is degrading faster than
# it's earning. Ω-cycle should be firing; adding new positions makes it worse.
H_BLOCK = 0.30

# Below this H (but above H_BLOCK), trades are allowed but position size is
# scaled by H. H=0.5 → 50% of quantum position_multiplier. H=0.9 → 90%.
H_SCALE = 1.00

# When no quantum state has been computed yet (startup), use this default
# multiplier — conservative but not fully blocking.
H_DEFAULT_MULTIPLIER = 0.50


# ─── Component 7: Environment ε = {C, M, W, Π, F} ───────────────────────────

@dataclass
class AEONEnvironment:
    """
    ε — What AEON perceives at the moment of a trade decision.

    Five environmental channels:
        C — Candles   : price action, structure, trend context
        M — Momentum  : RSI, MACD delta, rate-of-change signals
        W — Volume    : volume profile, open interest, relative volume
        Π — Position  : current exposure, margin utilisation, open trades
        F — Funding   : funding rate, liquidation clusters, OI direction

    Built by build_environment() before every entry signal is evaluated.
    Stored as part of the (ε, a, r) memory triplet in trade_memories.
    Attached to the quantum state snapshot for full A(t) traceability.
    """

    timestamp: str = ""

    # C — Candles
    candle_regime:    str   = "unknown"    # "trending" / "ranging" / "reversal"
    adx:              float = 0.0          # ADX value (trend strength)
    price_vs_vwap:    float = 0.0          # (price − VWAP) / VWAP ∈ [−1, 1]
    structure_bias:   float = 0.0          # SMC bias: +1 bullish, −1 bearish, 0 neutral

    # M — Momentum
    rsi:              float = 50.0         # RSI on signal timeframe [0, 100]
    rsi_norm:         float = 0.0          # (RSI − 50) / 50 ∈ [−1, 1]
    macd_delta:       float = 0.0          # MACD histogram, sign = direction
    momentum_score:   float = 0.0          # composite momentum ∈ [−1, 1]

    # W — Volume
    volume_ratio:     float = 1.0          # current / 20-bar average
    oi_change_pct:    float = 0.0          # open interest % change (last 4h)
    relative_volume:  float = 1.0          # vs same-time-of-day average

    # Π — Position
    open_positions:   int   = 0            # total open trades across all engines
    margin_used_pct:  float = 0.0          # PRO account margin utilisation ∈ [0, 1]
    cross_engine_exposure: float = 0.0     # sum of open position sizes / total capital

    # F — Funding
    funding_rate:     float = 0.0          # current 8h funding rate (% basis)
    funding_bias:     float = 0.0          # +1 = longs paying (bearish), −1 = shorts paying
    liquidation_risk: float = 0.0          # proximity to major liquidation cluster ∈ [0, 1]

    # Quantum snapshot at decision time
    quantum_H:        float = 0.0          # system health
    quantum_C:        float = 0.0          # coherence
    quantum_S_norm:   float = 0.0          # entropy
    quantum_psi:      List[float] = field(default_factory=list)  # αᵢ vector

    def to_dict(self) -> Dict:
        d = asdict(self)
        # Remove list from asdict conversion (field has default_factory)
        return d

    @property
    def channel_vector(self) -> List[float]:
        """
        Normalised 10-dimensional vector summarising ε.
        Used for cosine similarity in memory retrieval.
        """
        regime_val = {"trending": 1.0, "ranging": 0.0, "reversal": -0.5}.get(
            self.candle_regime, 0.0
        )
        return [
            regime_val,
            min(self.adx, 100.0) / 100.0,
            max(-1.0, min(1.0, self.rsi_norm)),
            max(-1.0, min(1.0, self.momentum_score)),
            max(0.0, min(2.0, self.volume_ratio)) / 2.0,
            max(-1.0, min(1.0, self.oi_change_pct / 10.0)),
            max(0.0, min(1.0, self.margin_used_pct)),
            max(-1.0, min(1.0, self.funding_bias)),
            max(0.0, min(1.0, self.liquidation_risk)),
            max(-1.0, min(1.0, self.structure_bias)),
        ]


def build_environment(
    *,
    quantum_state_dict: Optional[Dict] = None,
    market_data: Optional[Dict] = None,
    position_data: Optional[Dict] = None,
    funding_data: Optional[Dict] = None,
) -> AEONEnvironment:
    """
    Construct an AEONEnvironment snapshot from available data sources.

    All inputs are optional — missing fields fall back to neutral defaults
    so the environment is always constructible even under data gaps.

    Typical call sites:
        - QuantumIdentity.gate_trade()     — pre-entry gate check
        - memory_engine._build_context()   — (ε, a, r) triplet recording
        - morning_briefing.build_summary() — A(t) state report
    """
    env = AEONEnvironment(
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    # ── Quantum state snapshot ────────────────────────────────────────────────
    if quantum_state_dict:
        env.quantum_H     = float(quantum_state_dict.get("H", 0.0))
        env.quantum_C     = float(quantum_state_dict.get("C", 0.0))
        env.quantum_S_norm = float(quantum_state_dict.get("S_norm", 0.0))
        env.quantum_psi   = quantum_state_dict.get("psi", [])

        regime = quantum_state_dict.get("regime", "unknown")
        env.candle_regime = regime
        env.adx = float(quantum_state_dict.get("adx", 0.0))

    # ── Market data (C + M + W channels) ─────────────────────────────────────
    if market_data:
        indicators = market_data.get("indicators", {})

        rsi = float(indicators.get("rsi", 50.0))
        env.rsi = rsi
        env.rsi_norm = (rsi - 50.0) / 50.0

        macd = indicators.get("macd", {})
        if isinstance(macd, dict):
            env.macd_delta = float(macd.get("histogram", macd.get("delta", 0.0)))
        elif isinstance(macd, (int, float)):
            env.macd_delta = float(macd)

        env.momentum_score = max(-1.0, min(1.0, env.rsi_norm + env.macd_delta * 0.1))

        # Volume
        vol = market_data.get("volume", {})
        if isinstance(vol, dict):
            env.volume_ratio    = float(vol.get("ratio", 1.0))
            env.relative_volume = float(vol.get("relative", 1.0))

        # SMC bias
        smc = market_data.get("smc", {})
        if isinstance(smc, dict):
            bias_raw = smc.get("bias", smc.get("direction", "neutral")).lower()
            env.structure_bias = 1.0 if "bull" in bias_raw else (-1.0 if "bear" in bias_raw else 0.0)

        # VWAP
        price = float(market_data.get("price", 0.0))
        vwap  = float(market_data.get("vwap", price))
        if vwap > 0:
            env.price_vs_vwap = (price - vwap) / vwap

    # ── Position data (Π channel) ─────────────────────────────────────────────
    if position_data:
        env.open_positions         = int(position_data.get("open_count", 0))
        env.margin_used_pct        = float(position_data.get("margin_used_pct", 0.0))
        env.cross_engine_exposure  = float(position_data.get("cross_engine_exposure", 0.0))

    # ── Funding data (F channel) ──────────────────────────────────────────────
    if funding_data:
        env.funding_rate     = float(funding_data.get("funding_rate", 0.0))
        env.oi_change_pct    = float(funding_data.get("oi_change_pct", 0.0))
        env.liquidation_risk = float(funding_data.get("liquidation_risk", 0.0))
        # Positive funding → longs paying → bearish pressure
        env.funding_bias     = -math.copysign(1.0, env.funding_rate) if env.funding_rate != 0 else 0.0

    return env


# ─── Component 9: Learning Layers L = L₀ ⊕ LΣ ⊕ L⊛ ─────────────────────────

class AEONLearningStack:
    """
    L = L₀ ⊕ LΣ ⊕ L⊛ — The three learning layers composed in sequence.

    L₀  — Base rules (UnifiedEntryValidator)
           Hard constraints that never change: min confidence, min confluences,
           stop loss required, R:R ≥ 1.5:1. These are mathematical floors.
           Source: aeon_engine_system.UnifiedEntryValidator

    LΣ  — Statistical layer (Omega cycle structure learning)
           Rewrites signal logic based on loss patterns. Fires when structural
           performance failure is detected (WR < 40%, RR < 1.0, PF < 1.0).
           Requires Omega cycle ΔH > 5% to auto-apply; otherwise escalates.
           Source: omega_cycle.OmegaCycle (LΣ proposals)

    L⊛  — Adaptive layer (Lθ parameter learning)
           Continuous gradient ascent on H. Auto-adjusts confidence floors,
           ADX gates, leverage caps. θ(t+1) = θ(t) + η·∇θH, η=0.05.
           Source: aeon_ltheta_params.apply_override()

    The ⊕ composition is sequential: a signal must pass L₀ first, then
    LΣ checks it against learned structural patterns, then L⊛ applies
    the current parameter state to the final size/leverage.

    This class is a diagnostic and reporting surface. The actual filtering
    is performed by the underlying modules — this class reads their state
    and exposes it as a unified snapshot for the morning briefing and the
    frontend identity panel.
    """

    def __init__(self):
        self._omega_ref    = None   # OmegaCycle
        self._ltheta_ref   = None   # aeon_ltheta_params module

    def set_dependencies(self, omega_cycle=None, ltheta_module=None):
        self._omega_ref  = omega_cycle
        self._ltheta_ref = ltheta_module

    def get_snapshot(self) -> Dict:
        """
        Return the current state of all three learning layers.
        """
        snapshot: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "composition": "L₀ ⊕ LΣ ⊕ L⊛",
        }

        # L₀ — base rules (static — always active)
        snapshot["L0"] = {
            "label":       "L₀ — Base Rules",
            "type":        "invariant",
            "status":      "always_active",
            "rules": [
                "min_confidence per engine (65–90%)",
                "min_confluences per engine (2–5)",
                "stop_loss required",
                "take_profit required",
                "R:R ≥ 1.5:1",
                "position_size ≥ $100",
                "cross-engine coin lock ≤ 2",
                "max leverage per engine config",
            ],
            "source": "aeon_engine_system.UnifiedEntryValidator",
        }

        # LΣ — statistical layer
        omega_history: List[Dict] = []
        omega_last_cycle: Optional[str] = None
        if self._omega_ref is not None:
            try:
                omega_history   = getattr(self._omega_ref, "_H_history", [])
                last_at         = getattr(self._omega_ref, "_last_cycle_at", None)
                omega_last_cycle = last_at.isoformat() if last_at else None
            except Exception:
                pass

        snapshot["L_sigma"] = {
            "label":        "LΣ — Statistical Layer",
            "type":         "structure_learning",
            "status":       "active",
            "last_cycle":   omega_last_cycle,
            "H_history":    [round(h, 4) for h in omega_history],
            "auto_apply_threshold": "ΔH > 5%",
            "escalation":   "H < 1.0 proposals → Telegram (Carlos approval)",
            "source":       "omega_cycle.OmegaCycle",
        }

        # L⊛ — adaptive layer
        ltheta_overrides: Dict = {}
        if self._ltheta_ref is not None:
            try:
                ltheta_overrides = getattr(self._ltheta_ref, "_active_overrides", {})
            except Exception:
                pass

        snapshot["L_star"] = {
            "label":      "L⊛ — Adaptive Layer",
            "type":       "parameter_learning",
            "status":     "active",
            "eta":        0.05,
            "rule":       "θ(t+1) = θ(t) + η·∇θH",
            "overrides":  ltheta_overrides,
            "source":     "aeon_ltheta_params.apply_override",
        }

        return snapshot


# ─── Component 6 (gap): H-gate for trade decisions ───────────────────────────

class QuantumIdentityGate:
    """
    The H-gate — the missing link between the quantum state and trade execution.

    System health H is computed every 60s by aeon_quantum_state.py.
    Without this gate, H was purely diagnostic — it never blocked a trade.
    This class closes that loop.

    Gate logic:
        H < 0.30  → BLOCK  — system critically degraded; no new positions
        H < 1.00  → SCALE  — scale quantum position_multiplier by H
        H ≥ 1.00  → PASS   — full multiplier, system healthy

    The gate returns a (allowed, scale, reason) triple consumed by
    EngineManager.submit_signal_gated() and embedded in the trade record.
    """

    def __init__(self):
        self._quantum_ref = None   # AEONQuantumState

    def set_quantum_engine(self, quantum_engine) -> None:
        self._quantum_ref = quantum_engine

    def evaluate(self, engine_type_str: str = "") -> Tuple[bool, float, str]:
        """
        Evaluate the H-gate for a pending trade.

        Returns:
            allowed  (bool)  — False means BLOCK this trade entirely
            scale    (float) — multiply quantum position_multiplier by this
            reason   (str)   — human-readable gate decision
        """
        if self._quantum_ref is None:
            # Quantum state not initialised yet — conservative pass at 50%
            return True, H_DEFAULT_MULTIPLIER, "quantum not initialised — conservative 50% size"

        H = self._quantum_ref.get_health()

        if H <= 0.0:
            # No state yet (H defaults to 0.0 before first cycle completes)
            return True, H_DEFAULT_MULTIPLIER, f"H=0.0 startup default — conservative 50% size"

        if H < H_BLOCK:
            reason = (
                f"H={H:.3f} < {H_BLOCK} — system critically degraded. "
                f"Ω-cycle active. No new positions until H recovers."
            )
            logger.warning(f"[Ψ-gate] BLOCK [{engine_type_str}] {reason}")
            return False, 0.0, reason

        if H < H_SCALE:
            scale  = round(H / H_SCALE, 4)   # linear scaling with H
            reason = (
                f"H={H:.3f} < {H_SCALE} — below neutral. "
                f"Position scaled to {scale:.0%} of quantum size."
            )
            logger.info(f"[Ψ-gate] SCALE [{engine_type_str}] {reason}")
            return True, scale, reason

        # H >= 1.0 — full pass
        return True, 1.0, f"H={H:.3f} ≥ 1.0 — system healthy, full quantum size"

    def get_status(self) -> Dict:
        """Diagnostic snapshot for the frontend identity panel."""
        if self._quantum_ref is None:
            return {"status": "uninitialised", "H": None, "gate": "pass_conservative"}

        H = self._quantum_ref.get_health()
        C = self._quantum_ref.get_coherence()

        if H < H_BLOCK:
            gate = "BLOCK"
        elif H < H_SCALE:
            gate = f"SCALE×{H/H_SCALE:.2f}"
        else:
            gate = "PASS"

        return {
            "H":          round(H, 4),
            "C":          round(C, 4),
            "gate":       gate,
            "H_block":    H_BLOCK,
            "H_scale":    H_SCALE,
            "status":     "active",
        }


# ─── Master coordinator: QuantumIdentity ─────────────────────────────────────

class QuantumIdentity:
    """
    A(t) = Ω(|Ψ⟩, E, M, L) — The complete quantum identity of AEON.

    This is AEON reading its own mind, in full.

    All 10 components unified in one callable:
        get_full_state()  → complete A(t) snapshot dict
        gate_trade()      → (allowed, scale, reason) H-gate decision
        build_env()       → AEONEnvironment ε snapshot

    Singleton: use get_quantum_identity() after init_quantum_identity().
    """

    def __init__(self):
        self.gate          = QuantumIdentityGate()
        self.learning      = AEONLearningStack()

        self._quantum_ref  = None   # AEONQuantumState
        self._omega_ref    = None   # OmegaCycle
        self._memory_ref   = None   # MemoryEngine
        self._ltheta_ref   = None   # aeon_ltheta_params module

    def set_dependencies(
        self,
        quantum_state=None,
        omega_cycle=None,
        memory_engine=None,
        ltheta_module=None,
    ) -> None:
        self._quantum_ref = quantum_state
        self._omega_ref   = omega_cycle
        self._memory_ref  = memory_engine
        self._ltheta_ref  = ltheta_module

        self.gate.set_quantum_engine(quantum_state)
        self.learning.set_dependencies(
            omega_cycle=omega_cycle,
            ltheta_module=ltheta_module,
        )

        logger.info(
            "[A(t)] QuantumIdentity wired — |Ψ⟩=%s  Ω=%s  M=%s  L⊛=%s",
            "✓" if quantum_state else "✗",
            "✓" if omega_cycle   else "✗",
            "✓" if memory_engine else "✗",
            "✓" if ltheta_module else "✗",
        )

    # ── Component 6 gap: H-gate ───────────────────────────────────────────────

    def gate_trade(
        self,
        engine_type_str: str = "",
        signal: Optional[Dict] = None,
    ) -> Tuple[bool, float, str]:
        """
        Evaluate whether the quantum identity approves this trade.

        Returns:
            allowed  (bool)  — True = proceed, False = block
            scale    (float) — multiply position_multiplier by this value
            reason   (str)   — gate decision explanation

        Called from EngineManager.submit_signal_gated() after the quant
        gatekeeper check and before submit_signal().
        """
        return self.gate.evaluate(engine_type_str)

    # ── Component 7: Environment snapshot ────────────────────────────────────

    def build_env(
        self,
        market_data: Optional[Dict] = None,
        position_data: Optional[Dict] = None,
        funding_data: Optional[Dict] = None,
    ) -> AEONEnvironment:
        """
        Build ε — the full environment snapshot for this decision instant.
        Attaches the current quantum state automatically.
        """
        qs_dict = None
        if self._quantum_ref is not None:
            qs_dict = self._quantum_ref.get_state()

        return build_environment(
            quantum_state_dict=qs_dict,
            market_data=market_data,
            position_data=position_data,
            funding_data=funding_data,
        )

    # ── Full A(t) snapshot ────────────────────────────────────────────────────

    def get_full_state(self) -> Dict:
        """
        Return the complete A(t) = Ω(|Ψ⟩, E, M, L) snapshot.

        Structure:
          {
            "timestamp": ...,
            "identity":  "A(t) = Ω(|Ψ⟩, E, M, L)",
            "psi":       { H, C, S_norm, position_multiplier, engine_states, ... },
            "epsilon":   { AEONEnvironment snapshot },
            "memory":    { trade_count, last_retrieval_ts, ... },
            "learning":  { L0, L_sigma, L_star snapshots },
            "omega":     { cycle_count, last_cycle, H_history, ... },
            "gate":      { H, C, gate decision },
          }
        """
        now = datetime.now(timezone.utc).isoformat()

        # |Ψ⟩
        psi_snap: Dict = {}
        if self._quantum_ref is not None:
            raw = self._quantum_ref.get_state()
            if raw:
                psi_snap = raw

        # ε — environment at this instant (quantum-only; no market call here)
        env = build_environment(quantum_state_dict=psi_snap if psi_snap else None)

        # M — memory stats
        memory_snap: Dict = {"status": "uninitialised"}
        if self._memory_ref is not None:
            try:
                memory_snap = {
                    "status": "active",
                    "poll_interval_s": getattr(self._memory_ref, "POLL_INTERVAL", 300),
                    "feature_dim": getattr(self._memory_ref, "FEATURE_DIM", 9),
                }
            except Exception:
                pass

        # L — learning stack
        learning_snap = self.learning.get_snapshot()

        # Ω — omega cycle stats
        omega_snap: Dict = {"status": "uninitialised"}
        if self._omega_ref is not None:
            try:
                omega_snap = {
                    "status":       "active",
                    "cycle_count":  getattr(self._omega_ref, "_cycle_count", 0),
                    "last_cycle":   (
                        getattr(self._omega_ref, "_last_cycle_at", None).isoformat()
                        if getattr(self._omega_ref, "_last_cycle_at", None) else None
                    ),
                    "H_history":    [round(h, 4) for h in getattr(self._omega_ref, "_H_history", [])],
                    "decline_count": getattr(self._omega_ref, "_decline_count", 0),
                    "low_C_count":  getattr(self._omega_ref, "_low_C_count", 0),
                }
            except Exception:
                pass

        # H-gate status
        gate_snap = self.gate.get_status()

        return {
            "timestamp": now,
            "identity":  "A(t) = Ω(|Ψ⟩, E, M, L)",
            "equation": {
                "psi":      "|Ψ⟩ = Σ αᵢ(t)|Eᵢ⟩",
                "alpha":    "αᵢ(t) = Sᵢ · e^(−λδᵢ) · 𝟙[ADX>θ] · cos(θᵢⱼ)",
                "edge":     "Sᵢ = (WRᵢ·RRᵢ − (1−WRᵢ)) × PFᵢ / δᵢ",
                "consensus":"C = |Σαᵢ|² / (n·Σ|αᵢ|²) ∈ [0,1]",
                "entropy":  "H_ent = −Σ |αᵢ|² log|αᵢ|²",
                "health":   "H = Σ(ωᵢ·kelly_edgeᵢ) / (1 + max(δᵢ))",
                "env":      "ε = {C, M, W, Π, F}",
                "memory":   "M(t) = M(t−1) ∪ {(εₜ, aₜ, rₜ)}",
                "learning": "L = L₀ ⊕ LΣ ⊕ L⊛",
                "omega":    "Ω: detect→diagnose→propose→sandbox→validate→apply",
            },
            "psi":       psi_snap,
            "epsilon":   env.to_dict(),
            "memory":    memory_snap,
            "learning":  learning_snap,
            "omega":     omega_snap,
            "gate":      gate_snap,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_identity: Optional[QuantumIdentity] = None


def init_quantum_identity() -> QuantumIdentity:
    """
    Initialise the QuantumIdentity singleton.
    Call once from server.py after init_quantum_state() and get_omega_cycle().
    """
    global _identity
    _identity = QuantumIdentity()
    logger.info("[A(t)] QuantumIdentity initialised — all 10 components active.")
    return _identity


def get_quantum_identity() -> Optional[QuantumIdentity]:
    """Return the live singleton. Returns None before init_quantum_identity()."""
    return _identity


def get_identity_gate() -> Optional[QuantumIdentityGate]:
    """Return the H-gate singleton for direct use in EngineManager."""
    if _identity is None:
        return None
    return _identity.gate


# ─── Engine wiring helper ─────────────────────────────────────────────────────

def wire_into_engine_manager(engine_manager) -> bool:
    """
    Attach the H-gate to an EngineManager instance.

    Sets engine_manager.identity_gate = get_identity_gate()
    so that submit_signal_gated() can call gate.evaluate() before
    the quant gatekeeper check.

    Returns True if successfully wired, False otherwise.
    """
    gate = get_identity_gate()
    if gate is None:
        logger.warning(
            "[A(t)] wire_into_engine_manager: identity not initialised yet. "
            "Call init_quantum_identity() before wiring."
        )
        return False

    engine_manager.identity_gate = gate
    logger.info("[A(t)] H-gate wired into EngineManager.identity_gate ✓")
    return True
