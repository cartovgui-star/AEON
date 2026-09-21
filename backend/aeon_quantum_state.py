"""
=============================================================
  aeon_quantum_state.py — The Quantum State of AEON
=============================================================

  Position in the identity: A(t) = Ω(|Ψ⟩, E, M, L)

  This module computes |Ψ⟩ — the quantum superposition of all
  engine states. It is not a utility. It is the state function.

  |Ψ⟩ = Σ αᵢ(t)|Eᵢ⟩

  αᵢ(t) = Sᵢ · e^(−λδᵢ) · 𝟙[ADX>θ] · (1 − ρᵢ_max)

  Sᵢ     = [(WRᵢ · RRᵢ − (1−WRᵢ)) × PFᵢ] / max(δᵢ, 0.01)
  H      = Σ(ωᵢSᵢ) / max(δᵢ)         system health
  C      = (Σαᵢ)² / (n · Σαᵢ²)        coherence ∈ [0,1]
  S_ent  = −Σ pᵢ log(pᵢ)              entropy
  S_norm = S_ent / log(n)              normalized entropy ∈ [0,1]
  size   = base × C × (1 − S_norm)    position multiplier

  (1 − ρᵢ_max) operationalizes cos(θᵢⱼ) from the identity.
  An engine correlated to another loses amplitude. Earned, not assigned.

  Run interval : 60 seconds
  Persistence  : MongoDB `states` collection (rolling 10,000 entries)
  Exposure     : get_quantum_state() singleton for engine_manager,
                 omega_cycle, and the frontend WebSocket feed
=============================================================
"""

import asyncio
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

LAMBDA          = 2.0    # drawdown decay rate in αᵢ(t) = Sᵢ · e^(−λδᵢ)
ADX_THETA       = 20.0   # regime gate threshold — ranging markets silence engines
BASE_SIZE_USD   = 1_000  # base position size for the size(t) formula
LOOP_INTERVAL   = 60     # seconds between state computations
TRADE_LOOKBACK  = 50     # closed paper trades per engine for WR/RR/PF
STATES_CAP      = 10_000 # max rows kept in MongoDB states collection

# Minimum δᵢ denominator — prevents Sᵢ explosion when drawdown is zero
DELTA_FLOOR     = 0.01

# When an engine has fewer than this many closed trades, use neutral priors
MIN_TRADES_FOR_EDGE = 5

# ─── Engine registry ──────────────────────────────────────────────────────────
# Maps EngineType to the strategy/engine label patterns used in paper_trades.
# Populated at runtime once EngineType is importable.

_ENGINE_STRATEGY_MAP: Dict = {}


def _build_strategy_map(EngineType) -> Dict:
    return {
        EngineType.ELITE_STRATEGY:        ["ELITE", "elite_strategy"],
        EngineType.YOLO_ENGINE:           ["YOLO", "yolo_engine"],
        EngineType.VWAP_SCALPER:          ["VWAP_SCALP", "vwap_scalper"],
        EngineType.AUTONOMOUS_TRADER_V2:  ["AUTONOMOUS", "autonomous_trader"],
        EngineType.FREE_WILL_V2:          ["FREE_WILL", "free_will"],
        EngineType.DAY_TRADER:            ["DAY_TRADER", "day_trader"],
        EngineType.DUAL_ENGINE:           ["DUAL", "dual_engine"],
        EngineType.INSTITUTIONAL_SCALPER: ["INSTITUTIONAL_SCALPER", "institutional_scalper"],
        EngineType.TCN_NEURAL:            ["tcn_neural", "TCN_NEURAL"],
    }


# ─── Data structures ──────────────────────────────────────────────────────────

class EngineQuantumStats:
    """
    All inputs needed to compute αᵢ for one engine.
    These are measurements — not parameters. They are recomputed each cycle.
    """
    __slots__ = [
        "engine_id", "win_rate", "reward_risk", "profit_factor",
        "drawdown_norm", "direction_bias", "trade_count",
        "recent_directions",   # List[float]: +1 LONG, −1 SHORT, last N
    ]

    def __init__(self, engine_id: str):
        self.engine_id      = engine_id
        self.win_rate       = 0.5    # prior: coin flip
        self.reward_risk    = 1.5    # prior: neutral R:R
        self.profit_factor  = 1.0    # prior: break-even
        self.drawdown_norm  = DELTA_FLOOR
        self.direction_bias = 0.0    # ∈ [−1, +1]
        self.trade_count    = 0
        self.recent_directions: List[float] = []


class QuantumStateSnapshot:
    """
    A single computed state of |Ψ⟩.
    This is what gets cached, logged to MongoDB, and served to the frontend.
    """
    def __init__(self):
        self.timestamp: str = ""
        self.engine_states: List[Dict] = []   # per-engine αᵢ, Sᵢ, δᵢ, etc.
        self.psi: List[float] = []            # [α₁, α₂, ..., α₇]
        self.H: float = 0.0                   # system health
        self.C: float = 0.0                   # coherence
        self.S_ent: float = 0.0              # entropy (nats)
        self.S_norm: float = 0.0             # normalized entropy ∈ [0,1]
        self.position_multiplier: float = 0.0 # size(t) / BASE_SIZE_USD
        self.adx: float = 0.0                # BTC/USDT 1h ADX
        self.regime: str = "unknown"         # "trending" or "ranging"
        self.n_active: int = 0               # engines with α > 0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "engine_states": self.engine_states,
            "psi": [round(a, 6) for a in self.psi],
            "H": round(self.H, 4),
            "C": round(self.C, 4),
            "S_ent": round(self.S_ent, 4),
            "S_norm": round(self.S_norm, 4),
            "position_multiplier": round(self.position_multiplier, 4),
            "position_usd": round(self.position_multiplier * BASE_SIZE_USD, 2),
            "adx": round(self.adx, 2),
            "regime": self.regime,
            "n_active": self.n_active,
            "base_size_usd": BASE_SIZE_USD,
        }


# ─── Core computation ─────────────────────────────────────────────────────────

class AEONQuantumState:
    """
    The quantum state engine.

    Runs every 60 seconds. Reads from MongoDB paper_trades and the live
    engine_manager. Produces |Ψ⟩ — the full superposition of engine states.

    This is AEON reading its own mind.
    """

    def __init__(self, db=None):
        self.db = db
        self.market_intel = None

        self._state: Optional[QuantumStateSnapshot] = None
        self._lock = asyncio.Lock()

        # Import EngineType lazily to avoid circular imports
        self._EngineType = None
        self._engine_manager = None

    def set_dependencies(self, market_intel=None, engine_manager=None):
        self.market_intel = market_intel
        self._engine_manager = engine_manager

    def _ensure_engine_type(self):
        if self._EngineType is None:
            try:
                from aeon_engine_system import EngineType, get_engine_manager
                self._EngineType = EngineType
                if self._engine_manager is None:
                    self._engine_manager = get_engine_manager()
                global _ENGINE_STRATEGY_MAP
                _ENGINE_STRATEGY_MAP = _build_strategy_map(EngineType)
            except ImportError as e:
                logger.error(f"[Ψ] Cannot import EngineType: {e}")

    # ── Data acquisition ──────────────────────────────────────────────────────

    async def _fetch_paper_trade_stats(self, engine_type) -> EngineQuantumStats:
        """
        Query MongoDB paper_trades for one engine's last TRADE_LOOKBACK closed trades.
        Computes WR, RR, PF, direction_bias.
        Falls back to neutral priors if insufficient data.
        """
        stats = EngineQuantumStats(engine_type.value)

        if self.db is None:
            return stats

        # Match on strategy label or signal_data.engine
        labels = _ENGINE_STRATEGY_MAP.get(engine_type, [engine_type.value])
        strategy_regex_parts = "|".join(labels)

        try:
            cursor = self.db["paper_trades"].find(
                {
                    "status": "closed",
                    "$or": [
                        {"strategy": {"$regex": strategy_regex_parts, "$options": "i"}},
                        {"signal_data.engine": {"$in": labels}},
                    ],
                },
                sort=[("closed_at", -1)],
                limit=TRADE_LOOKBACK,
            )
            trades = await cursor.to_list(length=TRADE_LOOKBACK)
        except Exception as e:
            logger.debug(f"[Ψ] DB query failed for {engine_type.value}: {e}")
            return stats

        if len(trades) < MIN_TRADES_FOR_EDGE:
            stats.trade_count = len(trades)
            return stats   # not enough data — neutral priors hold

        wins, losses = 0, 0
        gross_profit, gross_loss = 0.0, 0.0
        recent_dirs: List[float] = []

        for t in trades:
            # Resolve PnL (multiple possible field names — see Session 15 fix)
            pnl = (
                t.get("unrealized_pnl_pct")
                or t.get("pnl_pct")
                or (
                    t["realized_pnl"] / t["margin"] * 100
                    if t.get("realized_pnl") and t.get("margin")
                    else None
                )
                or 0.0
            )

            direction_raw = (
                t.get("direction")
                or t.get("signal_data", {}).get("direction", "")
            ).upper()
            direction_val = 1.0 if direction_raw == "LONG" else -1.0 if direction_raw == "SHORT" else 0.0
            recent_dirs.append(direction_val)

            if pnl > 0:
                wins += 1
                gross_profit += pnl
            else:
                losses += 1
                gross_loss += abs(pnl)

        total = wins + losses
        if total == 0:
            return stats

        stats.trade_count    = total
        stats.win_rate       = wins / total
        stats.profit_factor  = gross_profit / gross_loss if gross_loss > 0 else 2.0
        stats.reward_risk    = (
            (gross_profit / wins) / (gross_loss / losses)
            if wins > 0 and losses > 0
            else 1.5
        )
        stats.direction_bias = sum(recent_dirs) / len(recent_dirs) if recent_dirs else 0.0
        stats.recent_directions = recent_dirs
        return stats

    async def _fetch_drawdown(self, engine_type) -> float:
        """
        Normalized drawdown δᵢ ∈ [DELTA_FLOOR, 1.0].

        Uses engine_manager's live daily_pnl and ENGINE_CONFIGS max_daily_loss.
        Falls back to DELTA_FLOOR (no drawdown) when data is unavailable.
        """
        if self._engine_manager is None:
            return DELTA_FLOOR
        try:
            cfg     = self._engine_manager.ENGINE_CONFIGS.get(engine_type)
            e_stats = self._engine_manager.engine_stats.get(engine_type)

            if cfg is None or e_stats is None:
                return DELTA_FLOOR

            max_loss = getattr(cfg, "max_daily_loss", 500.0)
            daily_pnl = getattr(e_stats, "daily_pnl", 0.0)

            if daily_pnl >= 0:
                return DELTA_FLOOR   # engine is profitable today

            # Normalize current loss vs allowed maximum
            current_loss = abs(daily_pnl)
            delta = min(current_loss / max(max_loss, 1.0), 1.0)
            return max(delta, DELTA_FLOOR)
        except Exception as e:
            logger.debug(f"[Ψ] Drawdown fetch failed for {engine_type.value}: {e}")
            return DELTA_FLOOR

    async def _fetch_adx(self) -> float:
        """Fetch BTC/USDT 1h ADX as the regime indicator for all engines."""
        if self.market_intel is None:
            return 0.0
        try:
            ta = await self.market_intel.get_technical_analysis("BTC/USDT", "1h")
            return float(ta.get("indicators", {}).get("adx", 0.0)) if ta else 0.0
        except Exception as e:
            logger.debug(f"[Ψ] ADX fetch failed: {e}")
            return 0.0

    # ── Mathematics ───────────────────────────────────────────────────────────

    @staticmethod
    def _edge_score(wr: float, rr: float, pf: float, delta: float) -> float:
        """
        Sᵢ = [(WRᵢ · RRᵢ − (1−WRᵢ)) × PFᵢ] / δᵢ

        This is the mathematical proof an engine must satisfy to earn amplitude.
        Negative Sᵢ means the engine is destroying edge, not creating it.
        The δᵢ denominator penalizes engines that are currently in drawdown:
        an engine losing money is worth less per unit of edge.
        """
        raw = (wr * rr - (1.0 - wr)) * pf
        return raw / max(delta, DELTA_FLOOR)

    @staticmethod
    def _drawdown_decay(delta: float, lam: float = LAMBDA) -> float:
        """
        e^(−λδ)  — an engine on a losing streak decays exponentially.

        δ=0.01 (healthy): decay = e^(-0.02) ≈ 0.98  → nearly full amplitude
        δ=0.50 (50% loss): decay = e^(-1.0)  ≈ 0.37  → more than halved
        δ=1.00 (full loss): decay = e^(-2.0) ≈ 0.14  → almost silenced
        """
        return math.exp(-lam * delta)

    @staticmethod
    def _independence(engine_idx: int, all_dirs: List[List[float]]) -> float:
        """
        (1 − ρᵢ_max) — operationalizes cos(θᵢⱼ) from the identity.

        ρᵢ_max = max pairwise Pearson correlation of engine i with any other engine.
        Fully correlated engine (ρ=1) → independence = 0 → amplitude = 0.
        Orthogonal engine (ρ=0) → independence = 1 → full amplitude.

        Minimum floor: 0.10 so no engine is ever completely silenced by correlation alone.
        """
        dirs_i = all_dirs[engine_idx]
        if len(dirs_i) < 3:
            return 1.0   # insufficient history — assume independent

        def pearson(a: List[float], b: List[float]) -> float:
            n = min(len(a), len(b))
            if n < 3:
                return 0.0
            a, b = a[-n:], b[-n:]
            ma, mb = sum(a) / n, sum(b) / n
            num = sum((a[k] - ma) * (b[k] - mb) for k in range(n))
            da  = sum((a[k] - ma) ** 2 for k in range(n)) ** 0.5
            db  = sum((b[k] - mb) ** 2 for k in range(n)) ** 0.5
            if da == 0 or db == 0:
                return 0.0
            return num / (da * db)

        max_rho = 0.0
        for j, dirs_j in enumerate(all_dirs):
            if j == engine_idx:
                continue
            rho = abs(pearson(dirs_i, dirs_j))
            if rho > max_rho:
                max_rho = rho

        return max(1.0 - max_rho, 0.10)

    @staticmethod
    def _coherence(alphas: List[float]) -> float:
        """
        C = (Σαᵢ)² / (n · Σαᵢ²)  ∈ [0, 1]

        C = 1: all engines fully agree (same direction, equal amplitudes)
        C = 0: engines perfectly cancel (LONG and SHORT at equal strength)

        By Cauchy-Schwarz: (Σαᵢ)² ≤ n · Σαᵢ²  so C ∈ [0,1] always.
        """
        n = len(alphas)
        if n == 0:
            return 0.0
        sum_alpha = sum(alphas)
        sum_sq    = sum(a ** 2 for a in alphas)
        if sum_sq == 0:
            return 0.0
        return (sum_alpha ** 2) / (n * sum_sq)

    @staticmethod
    def _entropy(alphas: List[float]) -> Tuple[float, float]:
        """
        S_ent  = −Σ pᵢ log(pᵢ)   where pᵢ = |αᵢ|² / Σ|αᵢ|²
        S_norm = S_ent / log(n)    normalized ∈ [0, 1]

        High entropy: engines are equally active → AEON is uncertain → reduce size.
        Low entropy:  one or few engines dominate → clear signal → full size.
        """
        n = len(alphas)
        if n == 0:
            return 0.0, 0.0

        probs_raw = [a ** 2 for a in alphas]
        total = sum(probs_raw)
        if total == 0:
            return math.log(n) if n > 1 else 0.0, 1.0   # max entropy

        probs = [p / total for p in probs_raw]
        S = -sum(p * math.log(p) for p in probs if p > 0)
        S_norm = S / math.log(n) if n > 1 else 0.0
        return S, min(S_norm, 1.0)

    @staticmethod
    def _system_health(kelly_edges: List[float], deltas: List[float],
                       weights: Optional[List[float]] = None) -> float:
        """
        H = Σ(ωᵢ · kelly_edgeᵢ) / (1 + max(δᵢ))

        kelly_edgeᵢ = (WRᵢ · RRᵢ − (1−WRᵢ)) × PFᵢ   [raw edge, no δ division]

        H > 1: system earns more edge than its worst drawdown costs.
        H < 1: system needs improvement — Ω-cycle should fire.

        Scale reference:
          neutral priors (WR=0.5, RR=1.5, PF=1.0) → H ≈ 0.25  triggers Ω
          good performance (WR=0.6, RR=2.0, PF=2.0) → H ≈ 1.58  healthy
          excellent        (WR=0.65, RR=2.5, PF=3.0) → H ≈ 3.5   strong

        Previous formula passed Sᵢ = kelly/δᵢ then divided by max(δᵢ) again,
        creating H ≈ 5000 when δ=0.01 (no drawdown) — the Ω-cycle never triggered.
        This formula measures H once, correctly, on a [0, ~10] scale.
        """
        if not kelly_edges or not deltas:
            return 0.0
        n = len(kelly_edges)
        w = weights if weights else [1.0 / n] * n
        weighted_sum = sum(w[i] * max(kelly_edges[i], 0.0) for i in range(n))
        max_delta    = max(deltas) if deltas else DELTA_FLOOR
        return weighted_sum / (1.0 + max_delta)

    # ── Full state computation ────────────────────────────────────────────────

    async def compute_state(self) -> QuantumStateSnapshot:
        """
        The full Ω measurement.

        1. Gather per-engine stats from MongoDB + engine_manager
        2. Compute Sᵢ (edge score) for each engine
        3. Fetch ADX regime gate
        4. Compute independence (1 − ρᵢ_max) from correlation matrix
        5. Compute αᵢ(t) = Sᵢ · e^(−λδᵢ) · 𝟙[ADX>θ] · independence
        6. Sign αᵢ by engine direction bias (LONG+, SHORT−, neutral=0)
        7. Compute H, C, S_ent, S_norm, size(t)
        8. Persist to MongoDB
        9. Cache and return
        """
        self._ensure_engine_type()
        if self._EngineType is None:
            return QuantumStateSnapshot()

        engines = list(_ENGINE_STRATEGY_MAP.keys())
        n = len(engines)

        snapshot = QuantumStateSnapshot()
        snapshot.timestamp = datetime.now(timezone.utc).isoformat()

        # ── 1. Gather stats concurrently ─────────────────────────────────────
        adx_task   = asyncio.create_task(self._fetch_adx())
        stats_tasks = [
            asyncio.create_task(self._fetch_paper_trade_stats(e))
            for e in engines
        ]
        delta_tasks = [
            asyncio.create_task(self._fetch_drawdown(e))
            for e in engines
        ]

        adx     = await adx_task
        stat_list  = await asyncio.gather(*stats_tasks,  return_exceptions=True)
        delta_list = await asyncio.gather(*delta_tasks, return_exceptions=True)

        # Replace exceptions with defaults
        stat_list  = [
            s if isinstance(s, EngineQuantumStats) else EngineQuantumStats(engines[i].value)
            for i, s in enumerate(stat_list)
        ]
        delta_list = [
            d if isinstance(d, float) else DELTA_FLOOR
            for d in delta_list
        ]

        snapshot.adx    = adx
        snapshot.regime = "trending" if adx >= ADX_THETA else "ranging"
        # Soft fade: linear ramp from 0.20 at ADX=0 to 1.0 at ADX=30.
        # Hard binary gate (was 0 when ADX<20) killed all trades in ranging markets
        # which is ~60% of session time.  Now engines trade at reduced amplitude
        # in ranging conditions instead of going fully silent.
        regime_gate = max(0.20, min(1.0, adx / 30.0))

        # ── 2. Edge scores Sᵢ ────────────────────────────────────────────────
        edge_scores = [
            self._edge_score(
                stat_list[i].win_rate,
                stat_list[i].reward_risk,
                stat_list[i].profit_factor,
                delta_list[i],
            )
            for i in range(n)
        ]

        # ── 3. Drawdown decay e^(−λδᵢ) ───────────────────────────────────────
        decays = [self._drawdown_decay(delta_list[i]) for i in range(n)]

        # ── 4. Independence (1 − ρᵢ_max) ─────────────────────────────────────
        all_dirs = [stat_list[i].recent_directions for i in range(n)]
        independence = [
            self._independence(i, all_dirs) for i in range(n)
        ]

        # ── 5–6. αᵢ(t) — signed by direction bias ────────────────────────────
        alphas_unsigned = [
            max(edge_scores[i], 0.0) * decays[i] * regime_gate * independence[i]
            for i in range(n)
        ]
        direction_signs = [stat_list[i].direction_bias for i in range(n)]
        # When direction bias is 0 (balanced or no data), keep magnitude positive
        # for entropy/coherence math but mark as 0 in signed sense.
        alphas_signed = [
            alphas_unsigned[i] * (direction_signs[i] if direction_signs[i] != 0 else 1.0)
            for i in range(n)
        ]

        snapshot.psi = alphas_signed

        # ── 7. System metrics ─────────────────────────────────────────────────
        # Raw Kelly edges for H — no per-engine δ division (that's for Sᵢ/αᵢ only).
        # H uses a single denominator (1 + max_delta) so it stays on a [0, ~10] scale.
        kelly_edges = [
            (stat_list[i].win_rate * stat_list[i].reward_risk
             - (1.0 - stat_list[i].win_rate)) * stat_list[i].profit_factor
            for i in range(n)
        ]
        snapshot.H = self._system_health(kelly_edges, delta_list)

        # Coherence uses signed alphas — captures direction agreement
        snapshot.C = self._coherence(alphas_signed)

        # Entropy uses unsigned magnitudes — captures concentration of energy
        snapshot.S_ent, snapshot.S_norm = self._entropy(alphas_unsigned)

        # Position multiplier: size(t) = base × C × (1 − S_norm)
        snapshot.position_multiplier = snapshot.C * (1.0 - snapshot.S_norm)

        snapshot.n_active = sum(1 for a in alphas_unsigned if a > 0)

        # ── 8. Per-engine state records ───────────────────────────────────────
        snapshot.engine_states = [
            {
                "engine":        engines[i].value,
                "alpha":         round(alphas_signed[i], 6),
                "alpha_mag":     round(alphas_unsigned[i], 6),
                "S":             round(edge_scores[i], 4),
                "kelly_edge":    round(kelly_edges[i], 4),
                "delta":         round(delta_list[i], 4),
                "decay":         round(decays[i], 4),
                "independence":  round(independence[i], 4),
                "regime_gate":   regime_gate,
                "win_rate":      round(stat_list[i].win_rate, 4),
                "reward_risk":   round(stat_list[i].reward_risk, 4),
                "profit_factor": round(stat_list[i].profit_factor, 4),
                "direction_bias":round(stat_list[i].direction_bias, 4),
                "trade_count":   stat_list[i].trade_count,
            }
            for i in range(n)
        ]

        # ── 9. Persist to MongoDB ─────────────────────────────────────────────
        await self._persist(snapshot)

        return snapshot

    async def _persist(self, snapshot: QuantumStateSnapshot):
        """Write state to MongoDB states collection. Cap at STATES_CAP rows."""
        if self.db is None:
            return
        try:
            doc = snapshot.to_dict()
            await self.db["states"].insert_one(doc)
            # Rolling window: prune oldest if over cap
            count = await self.db["states"].count_documents({})
            if count > STATES_CAP:
                oldest = await self.db["states"].find_one(sort=[("timestamp", 1)])
                if oldest:
                    await self.db["states"].delete_one({"_id": oldest["_id"]})
        except Exception as e:
            logger.error(f"[Ψ] MongoDB persist failed: {e}")

    # ── Public interface ──────────────────────────────────────────────────────

    def get_state(self) -> Optional[Dict]:
        """
        Synchronous getter — returns the last computed state as a dict.
        Called by engine_manager and omega_cycle without awaiting.
        Returns None if no state has been computed yet.
        """
        if self._state is None:
            return None
        return self._state.to_dict()

    def get_position_multiplier(self) -> float:
        """
        Returns size(t) / BASE_SIZE_USD ∈ [0, 1].
        0 = do not trade. 1 = full base size. Called by engine_manager.
        """
        if self._state is None:
            return 0.5   # no data yet — conservative default
        return self._state.position_multiplier

    def get_health(self) -> float:
        """Returns current H. Engine_manager checks H > 1 before approving trades."""
        if self._state is None:
            return 0.0
        return self._state.H

    def get_coherence(self) -> float:
        """Returns C ∈ [0, 1]. Omega cycle uses this to gate structural changes."""
        if self._state is None:
            return 0.0
        return self._state.C

    # ── Background loop ───────────────────────────────────────────────────────

    async def run_loop(self):
        """
        Compute |Ψ⟩ every LOOP_INTERVAL seconds.
        This is the heartbeat of AEON's self-awareness.
        """
        logger.info(
            "[Ψ] Quantum state engine started — computing every %ds. "
            "Base size: $%d. ADX gate: %.0f. λ=%.1f.",
            LOOP_INTERVAL, BASE_SIZE_USD, ADX_THETA, LAMBDA,
        )

        while True:
            try:
                state = await self.compute_state()
                async with self._lock:
                    self._state = state

                logger.info(
                    "[Ψ] |Ψ⟩ computed — H=%.3f  C=%.3f  S=%.3f  size=%.2f%%  "
                    "active=%d/%d  regime=%s  ADX=%.1f",
                    state.H,
                    state.C,
                    state.S_norm,
                    state.position_multiplier * 100,
                    state.n_active,
                    len(state.engine_states),
                    state.regime,
                    state.adx,
                )

                # Warn when health crosses below 1 — the system is spending more than it earns.
                # Log only on transition (healthy→unhealthy) or once per hour while unhealthy,
                # instead of every LOOP_INTERVAL seconds. Ω-cycle (6h loop) handles the action.
                if state.H < 1.0:
                    was_ok = getattr(self, "_last_H_ok", True)
                    last_warn = getattr(self, "_last_H_warn_ts", 0)
                    now_ts = time.time()
                    if was_ok or (now_ts - last_warn) >= 3600:
                        logger.warning(
                            "[Ψ] H=%.3f < 1.0 — AEON is spending more edge than it earns. "
                            "Ω-cycle will act on next 6h tick.",
                            state.H,
                        )
                        self._last_H_warn_ts = now_ts
                    self._last_H_ok = False
                else:
                    self._last_H_ok = True

                # Warn when coherence is below 0.4 — engines are diverging
                if state.C < 0.4 and state.n_active > 1:
                    logger.warning(
                        "[Ψ] C=%.3f < 0.4 — engine disagreement high. "
                        "Position multiplier suppressed.",
                        state.C,
                    )

            except Exception as e:
                logger.error(f"[Ψ] State computation failed: {e}", exc_info=True)

            await asyncio.sleep(LOOP_INTERVAL)


# ─── Singleton ────────────────────────────────────────────────────────────────

_quantum_state_engine: Optional[AEONQuantumState] = None


def init_quantum_state(db=None) -> AEONQuantumState:
    """Initialise the global quantum state engine. Call once from server.py."""
    global _quantum_state_engine
    _quantum_state_engine = AEONQuantumState(db)
    return _quantum_state_engine


def get_quantum_state_engine() -> Optional[AEONQuantumState]:
    """Return the live singleton. Returns None before init_quantum_state() is called."""
    return _quantum_state_engine


def get_state() -> Optional[Dict]:
    """Module-level shortcut for engine_manager and omega_cycle."""
    if _quantum_state_engine is None:
        return None
    return _quantum_state_engine.get_state()
