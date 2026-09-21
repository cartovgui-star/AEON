"""
QUBO Position Sizer — quantum-inspired position-size multiplier.

Classic position sizing scales linearly off a single signal (ATR / leverage).
This module reframes "how many size-units should this trade take" as a small
QUBO (Quadratic Unconstrained Binary Optimization) problem and solves it with
simulated annealing — the same metaheuristic a quantum annealer approximates.

------------------------------------------------------------------------------
The problem
------------------------------------------------------------------------------
We allocate K identical "size quanta" (here K=4, so the multiplier lives on a
0.0 / 0.25 / 0.50 / 0.75 / 1.00 grid). Each quantum i is a binary x_i ∈ {0,1}
meaning "deploy this unit of size or not". We minimise an Ising-style energy:

    E(x) = − Σ_i  r·x_i                (linear: reward for deploying size)
           + Σ_i  c·x_i                (linear: per-unit risk cost)
           + Σ_{i<j} q·x_i·x_j         (quadratic: convex risk penalty —
                                        each added unit is costlier than the last)

  r  (reward field)  grows with edge quality: quant score, confidence, and
     directional conviction. High-edge trades want size ON.
  c  (cost field)    grows with per-trade risk: volatility (ATR%), leverage,
     and portfolio heat. Risky trades make every unit individually expensive.
  q  (coupling)      is the convexity that prevents all-or-nothing blow-ups:
     deploying many units simultaneously is super-linearly penalised, so the
     optimum is a *graded* allocation rather than max size on every green light.

Minimising E trades reward against convex risk, and the count of x_i = 1 at the
optimum, divided by K, is the position-size multiplier ∈ [0, 1].

------------------------------------------------------------------------------
Why this is better than linear ATR scaling
------------------------------------------------------------------------------
  • Convex coupling caps aggregate exposure automatically — it can't be gamed by
    a single euphoric input the way `size = f(confidence)` can.
  • It fuses edge AND risk AND portfolio heat into one objective, instead of
    multiplying independent ad-hoc factors.
  • It degrades gracefully: with K=4 the search space is 16 states, so annealing
    is exact-in-practice and costs microseconds.

Graceful degradation: any failure → returns 1.0 (full size, never block sizing).
"""

import logging
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Number of size quanta. K=4 → multiplier grid {0, .25, .5, .75, 1.0}.
_K = 4

# Annealing schedule. The state space is tiny (2^K = 16) so this is generous.
_SWEEPS = 60
_T_START = 2.0
_T_END = 0.05


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class QUBOFields:
    """Per-unit Ising fields derived from the trade context."""
    reward: float   # r — linear gain per deployed unit  (edge quality)
    cost: float     # c — linear risk per deployed unit   (volatility/leverage/heat)
    coupling: float # q — convex penalty per co-deployed pair


def build_fields(
    *,
    quant_score: float,
    confidence: float,
    atr_pct: float,
    leverage: float,
    portfolio_heat: float,
) -> QUBOFields:
    """
    Map trade context → Ising fields. All inputs are defensively normalised so
    out-of-range values can never produce a pathological allocation.

      quant_score    : 0–100 gate score        (higher → more reward)
      confidence     : 0–100 engine confidence  (higher → more reward)
      atr_pct        : recent ATR as % of price (higher → more cost)
      leverage       : intended leverage         (higher → more cost + coupling)
      portfolio_heat : 0–1 fraction of capital already at risk (higher → cost)
    """
    score_n = _clamp01(quant_score / 100.0)
    conf_n = _clamp01(confidence / 100.0)
    atr_n = _clamp01(atr_pct / 5.0)          # 5%+ ATR is "very volatile" → 1.0
    lev_n = _clamp01((leverage - 1.0) / 24.0)  # 1x→0, 25x→1
    heat_n = _clamp01(portfolio_heat)

    # Reward: blend of edge quality (score) and conviction (confidence).
    reward = 0.55 * score_n + 0.45 * conf_n

    # Cost: volatility dominates, leverage and existing heat add to it.
    cost = 0.50 * atr_n + 0.30 * lev_n + 0.20 * heat_n

    # Coupling (convexity): scales with leverage and heat — when the book is
    # already hot or leverage is high, piling on extra units is penalised hard.
    coupling = 0.12 + 0.20 * lev_n + 0.18 * heat_n

    return QUBOFields(reward=reward, cost=cost, coupling=coupling)


def _energy(state: List[int], f: QUBOFields) -> float:
    """Ising energy of a binary allocation state."""
    n_on = sum(state)
    linear = -f.reward * n_on + f.cost * n_on
    # quadratic over unordered pairs of deployed units = C(n_on, 2)
    pairs = n_on * (n_on - 1) / 2.0
    quad = f.coupling * pairs
    return linear + quad


def _anneal(f: QUBOFields, seed: int = 1337) -> Tuple[List[int], float]:
    """Simulated annealing over the 2^K binary states. Returns (best_state, E)."""
    rng = random.Random(seed)
    state = [0] * _K
    best = list(state)
    best_e = _energy(state, f)
    cur_e = best_e

    for sweep in range(_SWEEPS):
        frac = sweep / max(1, _SWEEPS - 1)
        temp = _T_START * ((_T_END / _T_START) ** frac)
        i = rng.randrange(_K)
        cand = list(state)
        cand[i] ^= 1
        cand_e = _energy(cand, f)
        delta = cand_e - cur_e
        if delta <= 0 or rng.random() < math.exp(-delta / max(temp, 1e-6)):
            state = cand
            cur_e = cand_e
            if cur_e < best_e:
                best_e = cur_e
                best = list(state)
    return best, best_e


def compute_qubo_multiplier(
    *,
    quant_score: float = 50.0,
    confidence: float = 70.0,
    atr_pct: float = 1.5,
    leverage: float = 5.0,
    portfolio_heat: float = 0.0,
) -> Tuple[float, Dict]:
    """
    Solve the QUBO and return (multiplier ∈ [0,1], breakdown).

    The multiplier scales an engine's intended position size. A floor of 0.25 is
    applied on the *passing* path so a signal that already cleared every gate is
    never sized to literal zero — the gates decide go/no-go, QUBO decides how big.

    Never raises — returns 1.0 on any internal failure.
    """
    try:
        f = build_fields(
            quant_score=quant_score,
            confidence=confidence,
            atr_pct=atr_pct,
            leverage=leverage,
            portfolio_heat=portfolio_heat,
        )
        best, energy = _anneal(f)
        units_on = sum(best)
        raw_mult = units_on / _K

        # Floor at 0.25 — the trade already passed every gate; don't null it out.
        multiplier = max(0.25, raw_mult)

        breakdown = {
            "multiplier": round(multiplier, 3),
            "units_on": units_on,
            "units_total": _K,
            "raw_multiplier": round(raw_mult, 3),
            "energy": round(energy, 4),
            "fields": {
                "reward": round(f.reward, 4),
                "cost": round(f.cost, 4),
                "coupling": round(f.coupling, 4),
            },
            "inputs": {
                "quant_score": quant_score,
                "confidence": confidence,
                "atr_pct": atr_pct,
                "leverage": leverage,
                "portfolio_heat": round(portfolio_heat, 4),
            },
        }
        logger.debug(
            f"[QUBO] units={units_on}/{_K} mult={multiplier:.2f} "
            f"r={f.reward:.2f} c={f.cost:.2f} q={f.coupling:.2f} E={energy:.3f}"
        )
        return multiplier, breakdown
    except Exception as e:
        logger.debug(f"[QUBO] sizing failed, defaulting to 1.0: {e}")
        return 1.0, {"multiplier": 1.0, "error": str(e)}
