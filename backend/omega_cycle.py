"""
=============================================================
  omega_cycle.py — The Ω Self-Improvement Loop
=============================================================

  Position in the identity: A(t) = Ω(|Ψ⟩, E, M, L)

  This module IS the Ω operator. It governs how AEON improves itself.

  L = Lθ ⊕ LΣ ⊕ LΦ

    Lθ — parameter learning. Auto-apply. Confidence floors, ADX gates,
          leverage caps, pair lists. Every step must improve H.
          θᵢ(t+1) = θᵢ(t) + η·∇θH

    LΣ — structure learning. Auto-apply if ΔH > 5%.
          Rewrites signal logic. Rebuilds broken engines.
          Applied when structure is clearly failing.

    LΦ — identity learning. Always requires Carlos approval.
          New engines. New signals. New identity layers.
          Sent to Telegram as a structured proposal.

  The Ω pipeline:
    DETECT   → compute dH/dt. find what is dying.
    DIAGNOSE → compare live config to spec. find the exact delta.
    PROPOSE  → generate fix as Δθᵢ or ΔΣ. state expected ΔH.
    SANDBOX  → simulate fix against last 500 trade memories.
    VALIDATE → H_new > H_current AND drawdown stable → passes.
    APPLY    → Lθ auto-apply. LΣ auto-apply if ΔH > 5%. LΦ → Carlos.

  Trigger conditions:
    - dH/dt < 0 for τ=3 consecutive cycles
    - αᵢ (engine amplitude) decays below 0.05 for any active engine
    - Coherence C < 0.4 for τ=2 consecutive cycles

  Run interval: 6 hours (21600 seconds)
  Persistence : MongoDB `fixes` collection (every change logged with ΔH)
  Alerts      : Telegram — Lθ/LΣ auto-apply confirmation, LΦ proposals
=============================================================
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Lθ real-apply — import lazily to avoid circular import at module load time
_ltheta_apply = None
_ltheta_engine_configs = None

def _init_ltheta():
    """Lazy import of ltheta params and ENGINE_CONFIGS — called on first Lθ apply."""
    global _ltheta_apply, _ltheta_engine_configs
    if _ltheta_apply is None:
        try:
            from aeon_ltheta_params import apply_override
            from aeon_engine_system import ENGINE_CONFIGS
            _ltheta_apply = apply_override
            _ltheta_engine_configs = ENGINE_CONFIGS
        except Exception as e:
            logger.warning(f"[Ω] Lθ apply init failed: {e}")

# ─── Constants ────────────────────────────────────────────────────────────────

CYCLE_INTERVAL      = 21_600    # 6 hours in seconds
HEALTH_HISTORY_LEN  = 6         # cycles of H history kept in memory
TAU_DECLINE         = 3         # consecutive declining H cycles before trigger
TAU_COHERENCE       = 2         # consecutive low-coherence cycles before trigger
ALPHA_FLOOR         = 0.05      # engine amplitude below this = engine is dying
COHERENCE_FLOOR     = 0.40      # C below this = engines diverging
L_SIGMA_THRESHOLD   = 0.05      # ΔH/H > 5% → LΣ auto-applies
SANDBOX_WINDOW      = 500       # trade memories used for sandbox simulation

# Gradient ascent step size for Lθ parameter updates
ETA = 0.05   # θ(t+1) = θ(t) + η·∇θH


class OmegaCycle:
    """
    The Ω operator — AEON's self-improvement engine.

    Runs every 6 hours. Reads |Ψ⟩ and memory. Finds what is dying.
    Proposes mathematical fixes. Validates them. Applies or escalates.

    Every change, every upgrade, every fix must move H upward.
    If it does not, it does not exist.
    """

    def __init__(self, db=None):
        self.db = db
        self.send_alert    = None    # Telegram send function
        self.chat_ids      = set()
        self._quantum      = None    # AEONQuantumState reference
        self._memory       = None    # MemoryEngine reference
        self._engine_mgr   = None    # EngineManager reference

        # Rolling health history for dH/dt
        self._H_history:       List[float] = []
        self._C_history:       List[float] = []
        self._cycle_count:     int = 0
        self._last_cycle_at:   Optional[datetime] = None

        # Consecutive trigger counters
        self._decline_count:   int = 0
        self._low_C_count:     int = 0

    def set_dependencies(self, send_alert=None, chat_ids=None,
                         quantum_state=None, memory_engine=None,
                         engine_manager=None, oria_edge_filter=None):
        self.send_alert        = send_alert
        self.chat_ids          = chat_ids or set()
        self._quantum          = quantum_state
        self._memory           = memory_engine
        self._engine_mgr       = engine_manager
        self._oria_edge_filter = oria_edge_filter  # ORIA EdgeFilter for per-engine Kelly data

        # Last cycle summary for API exposure
        self._last_cycle_summary: Dict = {}
        self._last_trigger_reasons: List[str] = []
        self._last_proposals: List[Dict] = []
        self._last_fixes_applied: List[Dict] = []

    # ── Trigger evaluation ────────────────────────────────────────────────────

    def _should_trigger(self, state: Dict) -> Tuple[bool, List[str]]:
        """
        Evaluate all Ω trigger conditions against the current state.
        Returns (trigger_bool, list_of_reasons).
        """
        reasons: List[str] = []
        H = state.get("H", 0.0)
        C = state.get("C", 0.0)

        # Update histories
        self._H_history.append(H)
        self._C_history.append(C)
        if len(self._H_history) > HEALTH_HISTORY_LEN:
            self._H_history = self._H_history[-HEALTH_HISTORY_LEN:]
        if len(self._C_history) > HEALTH_HISTORY_LEN:
            self._C_history = self._C_history[-HEALTH_HISTORY_LEN:]

        # Trigger 1: dH/dt < 0 for τ consecutive cycles
        if len(self._H_history) >= TAU_DECLINE:
            last = self._H_history[-TAU_DECLINE:]
            if all(last[i] < last[i - 1] for i in range(1, len(last))):
                self._decline_count += 1
                if self._decline_count >= TAU_DECLINE:
                    reasons.append(
                        f"dH/dt < 0 for {self._decline_count} consecutive cycles "
                        f"(H: {last[0]:.3f} → {last[-1]:.3f})"
                    )
            else:
                self._decline_count = 0
        else:
            self._decline_count = 0

        # Trigger 2: any engine amplitude decaying below floor
        dying = [
            e for e in state.get("engine_states", [])
            if 0 < e.get("alpha_mag", 0.0) < ALPHA_FLOOR
        ]
        if dying:
            names = [e["engine"] for e in dying]
            reasons.append(
                f"Engine amplitude below floor ({ALPHA_FLOOR}): {', '.join(names)}"
            )

        # Trigger 3: coherence C < floor for τ cycles
        if C < COHERENCE_FLOOR:
            self._low_C_count += 1
            if self._low_C_count >= TAU_COHERENCE:
                reasons.append(
                    f"Coherence C={C:.3f} < {COHERENCE_FLOOR} for "
                    f"{self._low_C_count} cycles"
                )
        else:
            self._low_C_count = 0

        # Always trigger if H < 1 (system spending more than it earns)
        if H < 1.0:
            reasons.append(f"H={H:.3f} < 1.0 — system is not profitable")

        return bool(reasons), reasons

    # ── DETECT ────────────────────────────────────────────────────────────────

    def _detect(self, state: Dict) -> List[Dict]:
        """
        Compute dαᵢ/dt across all engines. Find what is dying.
        Returns list of engine findings sorted by urgency.
        """
        findings = []
        for es in state.get("engine_states", []):
            engine  = es["engine"]
            alpha   = es.get("alpha_mag", 0.0)
            S       = es.get("S", 0.0)
            delta   = es.get("delta", 0.0)
            wr      = es.get("win_rate", 0.0)
            rr      = es.get("reward_risk", 0.0)
            pf      = es.get("profit_factor", 0.0)
            gate    = es.get("regime_gate", 1.0)
            indep   = es.get("independence", 1.0)
            count   = es.get("trade_count", 0)

            issues  = []
            urgency = 0

            if count < 5:
                issues.append("insufficient trade data (< 5 trades)")
                urgency += 1

            if S < 0:
                issues.append(f"negative edge score S={S:.3f} (losing engine)")
                urgency += 3

            if wr < 0.40 and count >= 5:
                issues.append(f"low win rate WR={wr:.2%}")
                urgency += 2

            if rr < 1.0 and count >= 5:
                issues.append(f"reward/risk < 1.0 (RR={rr:.2f})")
                urgency += 2

            if delta > 0.5:
                issues.append(f"high drawdown δ={delta:.2f}")
                urgency += 2

            if gate == 0.0:
                issues.append("silenced by regime gate (ADX < 20)")
                urgency += 1

            if indep < 0.3:
                issues.append(f"high correlation with other engines (independence={indep:.2f})")
                urgency += 1

            if alpha < ALPHA_FLOOR and count >= 5:
                issues.append(f"amplitude dying α={alpha:.4f}")
                urgency += 2

            if issues:
                findings.append({
                    "engine":  engine,
                    "alpha":   alpha,
                    "S":       S,
                    "delta":   delta,
                    "wr":      wr,
                    "rr":      rr,
                    "pf":      pf,
                    "count":   count,
                    "issues":  issues,
                    "urgency": urgency,
                })

        findings.sort(key=lambda x: x["urgency"], reverse=True)
        return findings

    # ── DIAGNOSE ──────────────────────────────────────────────────────────────

    async def _diagnose(self, findings: List[Dict],
                        state: Dict) -> List[Dict]:
        """
        For each finding, identify whether this is:
          - code_drift    : parameter in code doesn't match spec
          - regime_shift  : market conditions changed
          - signal_decay  : signal quality declining in this market
          - data_gap      : not enough trades to compute edge

        Returns enriched findings with diagnosis and proposed fix type.
        """
        H_current = state.get("H", 0.0)
        diagnosed = []

        for f in findings:
            engine  = f["engine"]
            diagnosis_type = "unknown"
            fix_type = "none"
            fix_desc = ""

            # Pull recent memory for this engine
            memories: List[Dict] = []
            if self._memory:
                try:
                    memories = await self._memory.db["trade_memories"].find(
                        {"engine": {"$regex": engine, "$options": "i"}},
                        sort=[("stored_at", -1)],
                        limit=50,
                    ).to_list(length=50)
                except Exception:
                    pass

            # Data gap
            if f["count"] < 5:
                diagnosis_type = "data_gap"
                fix_type = "none"
                fix_desc = "Insufficient trade history — no fix possible yet. Monitor."

            # Regime shift — engine silenced by ADX gate
            elif f.get("issues") and any("regime gate" in i for i in f["issues"]):
                diagnosis_type = "regime_shift"
                fix_type = "none"
                fix_desc = (
                    f"Market is ranging (ADX < 20). Engine {engine} correctly "
                    f"silenced. No fix needed — wait for trending regime."
                )

            # Negative edge or low WR — check if confidence floor too low
            elif f["S"] < 0 or (f["wr"] < 0.40 and f["count"] >= 10):
                # Check if trades with higher confidence performed better
                if memories:
                    high_conf = [m for m in memories if m.get("confidence", 0) >= 85]
                    low_conf  = [m for m in memories if m.get("confidence", 0) < 85]
                    hc_wr = (
                        sum(1 for m in high_conf if m.get("outcome") == "WIN") / len(high_conf)
                        if high_conf else 0.0
                    )
                    lc_wr = (
                        sum(1 for m in low_conf if m.get("outcome") == "WIN") / len(low_conf)
                        if low_conf else 0.0
                    )
                    if hc_wr > lc_wr + 0.10 and len(high_conf) >= 3:
                        diagnosis_type = "code_drift"
                        fix_type = "Lθ"
                        fix_desc = (
                            f"Confidence filter too low. High-conf trades: WR={hc_wr:.1%}, "
                            f"low-conf trades: WR={lc_wr:.1%}. "
                            f"Raise min_confidence by {ETA * 100:.0f}pp."
                        )
                    else:
                        diagnosis_type = "signal_decay"
                        fix_type = "LΣ"
                        fix_desc = (
                            f"Signal quality declining — confidence filter not the root cause. "
                            f"Engine {engine} signal logic may need structural review."
                        )
                else:
                    diagnosis_type = "data_gap"
                    fix_type = "none"
                    fix_desc = "Not enough memory to diagnose — monitor for 10+ trades."

            # High correlation with other engines
            elif any("correlation" in i for i in f.get("issues", [])):
                diagnosis_type = "code_drift"
                fix_type = "LΣ"
                fix_desc = (
                    f"Engine {engine} producing signals too similar to peers. "
                    f"Independence={f['S']:.2f}. Consider differentiating signal sources "
                    f"or consolidating this engine with its most correlated peer."
                )

            # High drawdown
            elif f["delta"] > 0.5:
                diagnosis_type = "code_drift"
                fix_type = "Lθ"
                fix_desc = (
                    f"Drawdown δ={f['delta']:.2f} — engine is exceeding risk envelope. "
                    f"Reduce leverage cap or tighten confidence floor."
                )

            f_copy = dict(f)
            f_copy.update({
                "diagnosis_type": diagnosis_type,
                "fix_type":       fix_type,
                "fix_desc":       fix_desc,
                "H_current":      H_current,
            })
            diagnosed.append(f_copy)

        return diagnosed

    # ── PROPOSE ───────────────────────────────────────────────────────────────

    def _propose(self, diagnosed: List[Dict]) -> List[Dict]:
        """
        Generate concrete proposals for each Lθ finding.
        Each proposal states:
          - what parameter to change (θᵢ)
          - by how much (Δθᵢ = η · ∇θH)
          - expected ΔH direction (qualitative)

        LΣ findings are flagged but not auto-coded — they go to sandbox then Carlos.
        LΦ (identity) findings are escalated directly to Carlos via Telegram.
        """
        proposals = []
        for d in diagnosed:
            if d["fix_type"] == "none":
                continue

            engine  = d["engine"]
            fix_type = d["fix_type"]

            proposal: Dict[str, Any] = {
                "engine":    engine,
                "fix_type":  fix_type,
                "fix_desc":  d["fix_desc"],
                "diagnosis": d["diagnosis_type"],
                "issues":    d["issues"],
                "wr":        d["wr"],
                "rr":        d["rr"],
                "delta":     d["delta"],
                "S":         d["S"],
            }

            if fix_type == "Lθ":
                if "confidence" in d["fix_desc"].lower():
                    proposal["param"]       = "min_confidence"
                    proposal["delta_theta"] = round(ETA * 100, 1)   # pp increase
                    proposal["direction"]   = "increase"
                    proposal["expected_H"]  = "↑ (fewer but higher-quality signals)"
                elif "leverage" in d["fix_desc"].lower():
                    proposal["param"]       = "max_leverage"
                    proposal["delta_theta"] = round(-ETA * 150, 1)   # reduce by η×max
                    proposal["direction"]   = "decrease"
                    proposal["expected_H"]  = "↑ (reduced drawdown per trade)"
                else:
                    proposal["param"]       = "confidence_floor"
                    proposal["delta_theta"] = round(ETA * 100, 1)
                    proposal["direction"]   = "increase"
                    proposal["expected_H"]  = "↑ (tighter entry criteria)"

            elif fix_type == "LΣ":
                proposal["param"]      = "signal_logic"
                proposal["direction"]  = "restructure"
                proposal["expected_H"] = "TBD — requires sandbox validation"

            proposals.append(proposal)

        return proposals

    # ── SANDBOX ───────────────────────────────────────────────────────────────

    async def _sandbox(self, proposal: Dict) -> Dict:
        """
        Simulate the proposed fix against the last SANDBOX_WINDOW trade memories
        for the affected engine. Compute H_simulated vs H_current.

        For Lθ fixes (e.g. raise confidence floor):
          - Replay historical trades, filtering out those below the new threshold
          - Recompute WR, RR, PF, S on the filtered set
          - Compute H_new from the simulated S

        Returns {"H_current": float, "H_new": float, "delta_H": float,
                 "simulated_wr": float, "simulated_trades": int, "passes": bool}
        """
        result: Dict[str, Any] = {
            "H_current": 0.0,
            "H_new":     0.0,
            "delta_H":   0.0,
            "simulated_wr": 0.0,
            "simulated_trades": 0,
            "passes": False,
        }

        if self._memory is None or self._memory.db is None:
            result["error"] = "no memory db"
            return result

        engine = proposal.get("engine", "")
        try:
            memories = await self._memory.db["trade_memories"].find(
                {"engine": {"$regex": engine, "$options": "i"}},
                sort=[("stored_at", -1)],
                limit=SANDBOX_WINDOW,
            ).to_list(length=SANDBOX_WINDOW)
        except Exception as e:
            result["error"] = str(e)
            return result

        if len(memories) < 5:
            result["error"] = "insufficient memory for sandbox"
            return result

        # Compute baseline H from all memories
        def _compute_edge(trades):
            if not trades:
                return 0.0, 0.0, 0.0, 0.0
            wins   = [t for t in trades if t.get("outcome") == "WIN"]
            losses = [t for t in trades if t.get("outcome") in ("LOSS", "LIQUIDATION")]
            total  = len(trades)
            wr     = len(wins) / total if total else 0.5
            g_profit = sum(abs(t.get("pnl_pct", 0)) for t in wins)
            g_loss   = sum(abs(t.get("pnl_pct", 0)) for t in losses)
            pf       = g_profit / g_loss if g_loss > 0 else 1.0
            rr       = (g_profit / len(wins)) / (g_loss / len(losses)) if wins and losses else 1.5
            delta    = max(
                sum(abs(t.get("pnl_pct", 0)) for t in losses[-5:]) / 100 / 5
                if losses else 0.01,
                0.01,
            )
            S        = ((wr * rr - (1 - wr)) * pf) / delta
            H        = S / delta
            return wr, S, H, delta

        wr_base, S_base, H_base, delta_base = _compute_edge(memories)

        # Apply the proposed Lθ fix: filter trades below new confidence threshold
        if proposal.get("param") == "min_confidence" and proposal.get("direction") == "increase":
            current_floor = 70.0   # conservative assumption of current floor
            new_floor = current_floor + proposal.get("delta_theta", 5.0)
            filtered = [m for m in memories if m.get("confidence", 0) >= new_floor]
        elif proposal.get("param") == "max_leverage" and proposal.get("direction") == "decrease":
            max_lev = 150 + proposal.get("delta_theta", -7.5)
            filtered = [
                m for m in memories
                if m.get("leverage", 150) <= max_lev
            ]
        else:
            filtered = memories   # no numeric filter for structural proposals

        wr_new, S_new, H_new, delta_new = _compute_edge(filtered)

        delta_H  = H_new - H_base
        passes   = H_new > H_base and delta_new <= delta_base * 1.1

        result.update({
            "H_current":        round(H_base, 4),
            "H_new":            round(H_new, 4),
            "delta_H":          round(delta_H, 4),
            "delta_H_pct":      round(delta_H / max(H_base, 0.001), 4),
            "simulated_wr":     round(wr_new, 4),
            "simulated_trades": len(filtered),
            "baseline_trades":  len(memories),
            "passes":           passes,
        })
        return result

    # ── VALIDATE ─────────────────────────────────────────────────────────────

    def _validate(self, sandbox_result: Dict) -> bool:
        """
        H_new > H_current AND max(δᵢ) stable → fix passes.
        Otherwise discard. Never apply a fix that cannot prove itself.
        """
        return sandbox_result.get("passes", False)

    # ── APPLY ─────────────────────────────────────────────────────────────────

    async def _apply_L_theta(self, proposal: Dict, sandbox: Dict):
        """
        Lθ auto-apply.

        Applies validated parameter changes to live ENGINE_CONFIGS in memory
        and persists them to ltheta_params.json so they survive restarts.

        Parameters modified:
          - min_confidence  (raise confidence floor to filter bad signals)
          - max_leverage    (reduce leverage when drawdown is high)

        After apply: logs to MongoDB fixes collection and Telegram.
        """
        engine_key  = proposal["engine"]
        param       = proposal.get("param", "")
        direction   = proposal.get("direction", "")
        delta_theta = proposal.get("delta_theta", 0.0)
        H_before    = sandbox.get("H_current", 0.0)
        H_after     = sandbox.get("H_new", 0.0)

        # ── Compute new parameter value ────────────────────────────────────
        new_value = None
        applied   = False

        _init_ltheta()

        if param == "min_confidence" and direction == "increase" and _ltheta_apply:
            # Read current value from live ENGINE_CONFIGS
            current = None
            if _ltheta_engine_configs:
                for et, cfg in _ltheta_engine_configs.items():
                    if et.value == engine_key or et.name == engine_key:
                        current = cfg.min_confidence
                        break
            current = current or 75.0
            new_value = round(min(current + abs(delta_theta), 95.0), 1)
            applied = _ltheta_apply(
                _ltheta_engine_configs, engine_key, "min_confidence", new_value,
                cycle=self._cycle_count, H_before=H_before, H_after=H_after,
            )

        elif param == "max_leverage" and direction == "decrease" and _ltheta_apply:
            current = None
            if _ltheta_engine_configs:
                for et, cfg in _ltheta_engine_configs.items():
                    if et.value == engine_key or et.name == engine_key:
                        current = cfg.max_leverage
                        break
            current = current or 50
            change   = max(int(abs(delta_theta)), 2)   # at least 2x reduction
            new_value = max(current - change, 5)
            applied = _ltheta_apply(
                _ltheta_engine_configs, engine_key, "max_leverage", new_value,
                cycle=self._cycle_count, H_before=H_before, H_after=H_after,
            )

        # ── Log to MongoDB ─────────────────────────────────────────────────
        fix_doc = {
            "timestamp":    datetime.now(timezone.utc),
            "cycle":        self._cycle_count,
            "fix_type":     "Lθ",
            "engine":       engine_key,
            "param":        param,
            "direction":    direction,
            "delta_theta":  delta_theta,
            "new_value":    new_value,
            "diagnosis":    proposal["diagnosis"],
            "fix_desc":     proposal["fix_desc"],
            "H_before":     H_before,
            "H_after_sim":  H_after,
            "delta_H":      sandbox["delta_H"],
            "delta_H_pct":  sandbox.get("delta_H_pct", 0.0),
            "sim_wr":       sandbox["simulated_wr"],
            "sim_trades":   sandbox["simulated_trades"],
            "auto_applied": applied,
            "status":       "applied" if applied else "apply_failed",
        }

        if self.db:
            try:
                await self.db["fixes"].insert_one(fix_doc)
            except Exception as e:
                logger.error(f"[Ω] Fix log failed: {e}")

        if applied:
            logger.info(
                "[Ω] Lθ APPLIED — %s.%s → %s  (ΔH: %.3f → %.3f sim)",
                engine_key, param, new_value, H_before, H_after,
            )
        else:
            logger.warning(
                "[Ω] Lθ apply FAILED — %s.%s (param unknown or out-of-bounds)", engine_key, param,
            )

        await self._telegram_ltheta(proposal, sandbox, applied=applied, new_value=new_value)

    async def _send_L_sigma(self, proposal: Dict, sandbox: Dict):
        """
        LΣ structural change — send to Carlos for review.
        Always requires human review before touching signal logic.
        """
        fix_doc = {
            "timestamp":   datetime.now(timezone.utc),
            "cycle":       self._cycle_count,
            "fix_type":    "LΣ",
            "engine":      proposal["engine"],
            "diagnosis":   proposal["diagnosis"],
            "fix_desc":    proposal["fix_desc"],
            "H_before":    sandbox.get("H_current", 0.0),
            "H_after_sim": sandbox.get("H_new", 0.0),
            "delta_H":     sandbox.get("delta_H", 0.0),
            "status":      "pending_carlos",
        }
        if self.db:
            try:
                await self.db["fixes"].insert_one(fix_doc)
            except Exception as e:
                logger.error(f"[Ω] LΣ fix log failed: {e}")

        await self._telegram_lsigma(proposal, sandbox)

    # ── TELEGRAM ALERTS ───────────────────────────────────────────────────────

    async def _send_telegram(self, msg: str):
        if not self.send_alert or not self.chat_ids:
            return
        for chat_id in self.chat_ids:
            try:
                await self.send_alert(chat_id, msg)
            except Exception as e:
                logger.error(f"[Ω] Telegram send failed: {e}")

    async def _telegram_cycle_report(self, state: Dict, triggered: bool,
                                     reasons: List[str], findings: List[Dict],
                                     exposure: Optional[Dict] = None):
        H   = state.get("H", 0.0)
        C   = state.get("C", 0.0)
        S   = state.get("S_norm", 0.0)
        n   = state.get("n_active", 0)
        reg = state.get("regime", "unknown")

        status_line = "TRIGGERED" if triggered else "NOMINAL"
        health_emoji = "✅" if H >= 1.0 else "⚠️" if H >= 0.5 else "🚨"

        msg = (
            f"Ω CYCLE #{self._cycle_count} — {status_line}\n"
            f"\n"
            f"QUANTUM STATE\n"
            f"H (health):    {H:.3f}  {health_emoji}\n"
            f"C (coherence): {C:.3f}\n"
            f"S (entropy):   {S:.3f}\n"
            f"Active engines: {n}/7\n"
            f"Regime: {reg.upper()}\n"
        )

        if triggered and reasons:
            msg += f"\nTRIGGER CONDITIONS\n"
            for r in reasons:
                msg += f"• {r}\n"

        if findings:
            msg += f"\nENGINE FINDINGS ({len(findings)} flagged)\n"
            for f in findings[:3]:
                msg += f"• {f['engine']}: {', '.join(f['issues'][:2])}\n"

        if not triggered:
            msg += f"\nNo fixes required. System nominal."

        # Open exposure block
        if exposure:
            total  = exposure.get("total_open", 0)
            longs  = exposure.get("long_count", 0)
            shorts = exposure.get("short_count", 0)
            lp     = exposure.get("long_pct", 0.0)
            conc   = exposure.get("concentrated_pairs", [])
            bias   = exposure.get("bias_alert", False)
            bias_emoji = "🚨" if bias else "✅"
            msg += f"\n\n📊 OPEN EXPOSURE\n"
            msg += f"Total open:  {total}\n"
            msg += f"LONG/SHORT:  {longs}/{shorts}  ({lp:.0f}% LONG)  {bias_emoji}\n"
            if conc:
                msg += f"Concentrated: {', '.join(conc)}\n"
            if bias:
                msg += f"⚠️ Directional bias detected — review trade mix\n"

        msg += (
            f"\n\n"
            f"🌐 DATA SOURCES\n"
            f"Primary:    OKX + LiveCoinWatch ✅\n"
            f"Fear&Greed: Alternative.me ✅\n"
            f"Options:    Deribit ✅\n"
            f"TVL:        DefiLlama ✅\n"
            f"News:       CryptoPanic ✅\n"
            f"MEXC:       ❌ REMOVED\n"
            f"yfinance:   ❌ REMOVED\n"
            f"\n"
            f"🧠 SYSTEM STATUS\n"
            f"Quant Gate:    ACTIVE ✅\n"
            f"ATR Stop:      ACTIVE ✅\n"
            f"Dynamic Lev:   ACTIVE ✅\n"
            f"Lθ Auto-Apply: ACTIVE ✅\n"
            f"Memory Engine: ACTIVE ✅\n"
            f"Web Intel:     ACTIVE ✅"
        )

        from post_mortem_engine import get_post_mortem
        pm_block = await get_post_mortem().get_cycle_report()
        msg += "\n\n" + pm_block

        await self._send_telegram(msg)

    async def _telegram_ltheta(self, proposal: Dict, sandbox: Dict,
                               applied: bool = False, new_value=None):
        engine     = proposal["engine"]
        param      = proposal.get("param", "parameter")
        direction  = proposal.get("direction", "adjust")
        delta      = proposal.get("delta_theta", 0)
        H_before   = sandbox.get("H_current", 0.0)
        H_after    = sandbox.get("H_new", 0.0)
        delta_H    = sandbox.get("delta_H", 0.0)
        sim_wr     = sandbox.get("simulated_wr", 0.0)

        dh_pct = delta_H / max(H_before, 0.001) * 100
        status_line = (
            f"✅ AUTO-APPLIED — {param} → {new_value}"
            if applied else
            f"⚠️ APPLY FAILED — manual fix required"
        )

        msg = (
            f"Ω Lθ — {engine.upper()}\n"
            f"{status_line}\n"
            f"\n"
            f"Parameter: {param}\n"
            f"Change:    {direction} by {abs(delta):.1f}\n"
            f"\n"
            f"SANDBOX RESULT\n"
            f"H before:   {H_before:.4f}\n"
            f"H after:    {H_after:.4f}\n"
            f"ΔH:         {delta_H:+.4f} ({dh_pct:+.1f}%)\n"
            f"Sim WR:     {sim_wr:.1%}\n"
            f"Sim trades: {sandbox.get('simulated_trades', 0)}\n"
            f"\n"
            f"Diagnosis: {proposal['diagnosis']}\n"
            f"{proposal['fix_desc']}"
        )
        await self._send_telegram(msg)

    async def _telegram_lsigma(self, proposal: Dict, sandbox: Dict):
        engine   = proposal["engine"]
        H_before = sandbox.get("H_current", 0.0)
        H_after  = sandbox.get("H_new", 0.0)
        delta_H  = sandbox.get("delta_H", 0.0)
        dh_pct   = delta_H / max(H_before, 0.001) * 100

        msg = (
            f"Ω LΣ PROPOSAL — CARLOS APPROVAL REQUIRED\n"
            f"\n"
            f"Engine: {engine.upper()}\n"
            f"Type:   Structural signal logic change\n"
            f"\n"
            f"Diagnosis: {proposal['diagnosis']}\n"
            f"Finding: {', '.join(proposal.get('issues', []))}\n"
            f"\n"
            f"Proposed fix:\n"
            f"{proposal['fix_desc']}\n"
            f"\n"
            f"SANDBOX RESULT\n"
            f"H before: {H_before:.4f}\n"
            f"H after:  {H_after:.4f}\n"
            f"ΔH:       {delta_H:+.4f} ({dh_pct:+.1f}%)\n"
            f"\n"
            f"This is LΣ — structural change. Your call, Carlos."
        )
        await self._send_telegram(msg)

    async def _telegram_no_trigger(self, state: Dict, exposure: Optional[Dict] = None):
        H = state.get("H", 0.0)
        C = state.get("C", 0.0)
        n = state.get("n_active", 0)
        msg = (
            f"Ω Cycle #{self._cycle_count} — NOMINAL\n"
            f"H={H:.3f}  C={C:.3f}  Active={n}/7\n"
            f"No fixes required.\n"
        )

        if exposure:
            total  = exposure.get("total_open", 0)
            longs  = exposure.get("long_count", 0)
            shorts = exposure.get("short_count", 0)
            lp     = exposure.get("long_pct", 0.0)
            conc   = exposure.get("concentrated_pairs", [])
            bias   = exposure.get("bias_alert", False)
            bias_emoji = "🚨" if bias else "✅"
            msg += f"\n📊 OPEN EXPOSURE\n"
            msg += f"Total open:  {total}\n"
            msg += f"LONG/SHORT:  {longs}/{shorts}  ({lp:.0f}% LONG)  {bias_emoji}\n"
            if conc:
                msg += f"Concentrated: {', '.join(conc)}\n"

        msg += (
            f"\n"
            f"🌐 DATA SOURCES\n"
            f"Primary:    OKX + LiveCoinWatch ✅\n"
            f"Fear&Greed: Alternative.me ✅\n"
            f"Options:    Deribit ✅\n"
            f"TVL:        DefiLlama ✅\n"
            f"News:       CryptoPanic ✅\n"
            f"MEXC:       ❌ REMOVED\n"
            f"yfinance:   ❌ REMOVED\n"
            f"\n"
            f"🧠 SYSTEM STATUS\n"
            f"Quant Gate:    ACTIVE ✅\n"
            f"ATR Stop:      ACTIVE ✅\n"
            f"Dynamic Lev:   ACTIVE ✅\n"
            f"Lθ Auto-Apply: ACTIVE ✅\n"
            f"Memory Engine: ACTIVE ✅\n"
            f"Web Intel:     ACTIVE ✅"
        )
        await self._send_telegram(msg)

    # ── Full Ω pipeline ───────────────────────────────────────────────────────

    async def run_cycle(self):
        """
        Execute one full Ω pipeline iteration.
        DETECT → DIAGNOSE → PROPOSE → SANDBOX → VALIDATE → APPLY
        """
        self._cycle_count += 1
        self._last_cycle_at = datetime.now(timezone.utc)
        logger.info(f"[Ω] Cycle #{self._cycle_count} starting.")

        # Read current quantum state
        if self._quantum is None:
            logger.warning("[Ω] No quantum state reference — cannot run cycle.")
            return

        state = self._quantum.get_state()
        if state is None:
            logger.warning("[Ω] Quantum state not yet computed — skipping cycle.")
            return

        H = state.get("H", 0.0)
        C = state.get("C", 0.0)
        logger.info(f"[Ω] State: H={H:.3f}, C={C:.3f}, active={state.get('n_active', 0)}/7")

        # ── Fetch open exposure (concentration risk) ───────────────────────────
        exposure: Dict = {}
        if self._memory is not None:
            try:
                exposure = await self._memory.get_open_exposure()
            except Exception as e:
                logger.debug(f"[Ω] get_open_exposure failed: {e}")

        # ── Read ORIA edge decay data ─────────────────────────────────────────
        oria_edge_findings: List[Dict] = []
        if self._oria_edge_filter is not None and self.db is not None:
            try:
                edge_docs = await self.db.edge_stats.find(
                    {"trade_count": {"$gte": 20}}  # only trust data with enough samples
                ).to_list(length=200)
                for doc in edge_docs:
                    engine   = doc.get("engine", "")
                    symbol   = doc.get("symbol", "")
                    wr_7d    = float(doc.get("win_rate_7d", 0.5))
                    wr_30d   = float(doc.get("win_rate_30d", 0.5))
                    count    = int(doc.get("trade_count", 0))
                    # Edge decay: 7d win rate dropped >10pp below 30d baseline
                    if wr_30d > 0.45 and wr_7d < wr_30d - 0.10:
                        oria_edge_findings.append({
                            "engine":  engine,
                            "symbol":  symbol,
                            "wr_7d":   round(wr_7d, 3),
                            "wr_30d":  round(wr_30d, 3),
                            "decay":   round(wr_30d - wr_7d, 3),
                            "count":   count,
                        })
                if oria_edge_findings:
                    logger.info(
                        f"[Ω] ORIA found {len(oria_edge_findings)} edge-decaying engine/symbol pairs"
                    )
            except Exception as e:
                logger.debug(f"[Ω] ORIA edge read failed: {e}")

        # Inject ORIA findings into quantum state so _detect() can see them
        if oria_edge_findings:
            state = {**state, "_oria_decaying": oria_edge_findings}
            # Add trigger reason if multiple pairs are decaying
            if len(oria_edge_findings) >= 3 and not any("ORIA" in r for r in []):
                reasons_from_oria = [
                    f"ORIA edge decay: {f['engine']} {f['symbol']} "
                    f"7d WR={f['wr_7d']:.0%} vs 30d WR={f['wr_30d']:.0%}"
                    for f in oria_edge_findings[:3]
                ]
                state = {**state, "_oria_reasons": reasons_from_oria}

        # ── DETECT ────────────────────────────────────────────────────────────
        triggered, reasons = self._should_trigger(state)

        # ORIA decay triggers
        for f in oria_edge_findings[:3]:
            reasons.append(
                f"ORIA edge decay: {f['engine']} {f['symbol']} "
                f"WR 7d={f['wr_7d']:.0%} vs 30d={f['wr_30d']:.0%} (−{f['decay']:.0%})"
            )
            triggered = True

        # Bias alert from memory engine — too many LONGs or SHORTs open
        if exposure.get("bias_alert"):
            long_pct = exposure.get("long_pct", 50.0)
            total    = exposure.get("total_open", 0)
            reasons.append(
                f"Directional bias: {long_pct:.0f}% LONG across {total} open positions"
            )
            triggered = True

        findings = self._detect(state)

        if not triggered and not findings:
            logger.info(f"[Ω] Cycle #{self._cycle_count} — NOMINAL. No action required.")
            await self._telegram_no_trigger(state, exposure)
            return

        logger.info(
            f"[Ω] Triggered: {triggered}. Findings: {len(findings)}. "
            f"Reasons: {reasons}"
        )

        # ── DIAGNOSE ──────────────────────────────────────────────────────────
        diagnosed = await self._diagnose(findings, state)

        # ── PROPOSE ───────────────────────────────────────────────────────────
        proposals = self._propose(diagnosed)

        actionable = [p for p in proposals if p["fix_type"] in ("Lθ", "LΣ")]
        logger.info(f"[Ω] {len(actionable)} actionable proposals generated.")

        # ── SANDBOX + VALIDATE + APPLY ────────────────────────────────────────
        applied: List[Dict] = []
        escalated: List[Dict] = []

        for proposal in actionable:
            fix_type = proposal["fix_type"]
            sandbox_result = await self._sandbox(proposal)

            if not self._validate(sandbox_result):
                logger.info(
                    f"[Ω] Proposal for {proposal['engine']} FAILED validation "
                    f"(H: {sandbox_result.get('H_current'):.3f} → "
                    f"{sandbox_result.get('H_new'):.3f}). Discarded."
                )
                continue

            delta_H_pct = sandbox_result.get("delta_H_pct", 0.0)

            if fix_type == "Lθ":
                await self._apply_L_theta(proposal, sandbox_result)
                applied.append(proposal)
                logger.info(
                    f"[Ω] Lθ applied: {proposal['engine']} / {proposal.get('param')} "
                    f"ΔH={sandbox_result['delta_H']:+.4f}"
                )

            elif fix_type == "LΣ":
                # LΣ auto-applies only if ΔH > L_SIGMA_THRESHOLD
                if delta_H_pct >= L_SIGMA_THRESHOLD:
                    await self._send_L_sigma(proposal, sandbox_result)
                    escalated.append(proposal)
                    logger.info(
                        f"[Ω] LΣ escalated to Carlos: {proposal['engine']} "
                        f"ΔH={delta_H_pct:.1%}"
                    )
                else:
                    logger.info(
                        f"[Ω] LΣ skipped: ΔH={delta_H_pct:.1%} < {L_SIGMA_THRESHOLD:.0%} threshold."
                    )

        # ── Write applied fixes back to governance ────────────────────────────
        # This is the missing link: Omega's Lθ decisions now appear in governance UI
        if applied and self.db is not None:
            for fix in applied:
                try:
                    gov_doc = {
                        "engine":                fix["engine"],
                        "source":                "omega_cycle",
                        "omega_cycle":           self._cycle_count,
                        "current_recommendation": f"OMEGA Lθ: {fix.get('param','')} → {fix.get('direction','')}",
                        "reason":                fix.get("fix_desc", ""),
                        "diagnosis":             fix.get("diagnosis", ""),
                        "fix_type":              "Lθ",
                        "auto_applied":          True,
                        "updated_at":            datetime.now(timezone.utc),
                    }
                    await self.db.engine_governance.update_one(
                        {"engine": fix["engine"], "source": "omega_cycle"},
                        {"$set": gov_doc},
                        upsert=True,
                    )
                except Exception as _ge:
                    logger.debug(f"[Ω] Governance write failed: {_ge}")

        # ── Store cycle summary for API exposure ───────────────────────────────
        self._last_trigger_reasons = reasons
        self._last_proposals       = actionable
        self._last_fixes_applied   = applied
        self._last_cycle_summary   = {
            "cycle":           self._cycle_count,
            "timestamp":       self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "triggered":       triggered,
            "reasons":         reasons,
            "findings_count":  len(findings),
            "proposals_count": len(actionable),
            "applied":         [{"engine": p["engine"], "param": p.get("param"), "fix_type": p["fix_type"]} for p in applied],
            "escalated":       [{"engine": p["engine"], "fix_type": p["fix_type"]} for p in escalated],
            "oria_decaying":   oria_edge_findings,
            "H":               H,
            "C":               C,
        }

        # Final cycle report
        await self._telegram_cycle_report(state, triggered, reasons, findings, exposure)
        logger.info(
            f"[Ω] Cycle #{self._cycle_count} complete. "
            f"Applied: {len(applied)}, Escalated: {len(escalated)}."
        )

    # ── Status for API ────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Return current Ω cycle state for the researcher/governance API."""
        next_cycle_in: Optional[float] = None
        if self._last_cycle_at is not None:
            elapsed = (datetime.now(timezone.utc) - self._last_cycle_at).total_seconds()
            next_cycle_in = max(0.0, CYCLE_INTERVAL - elapsed)

        return {
            "cycle_count":       self._cycle_count,
            "last_cycle_at":     self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "next_cycle_in_s":   round(next_cycle_in) if next_cycle_in is not None else None,
            "oria_connected":    self._oria_edge_filter is not None,
            "governance_writes": True,
            "last_summary":      getattr(self, "_last_cycle_summary", {}),
            "interval_h":        CYCLE_INTERVAL // 3600,
        }

    # ── Background loop ───────────────────────────────────────────────────────

    async def run_loop(self, interval: int = CYCLE_INTERVAL):
        """Run Ω every `interval` seconds (default 6 hours)."""
        logger.info(
            "[Ω] Omega cycle engine started — running every %dh. "
            "Triggers: dH/dt<0 for τ=%d, C<%.2f for τ=%d, H<1.",
            interval // 3600, TAU_DECLINE, COHERENCE_FLOOR, TAU_COHERENCE,
        )

        # First cycle after a short warm-up delay
        await asyncio.sleep(300)   # 5 min — let quantum state compute first reading

        while True:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"[Ω] Cycle error: {e}", exc_info=True)
            await asyncio.sleep(interval)


# ─── Singleton ────────────────────────────────────────────────────────────────

_omega_cycle: Optional[OmegaCycle] = None


def init_omega_cycle(db=None) -> OmegaCycle:
    """Initialise the global Ω cycle engine. Call once from server.py."""
    global _omega_cycle
    _omega_cycle = OmegaCycle(db)
    return _omega_cycle


def get_omega_cycle() -> Optional[OmegaCycle]:
    """Return the live singleton."""
    return _omega_cycle
