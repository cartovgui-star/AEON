"""
MAXWELL — AEON's Physicist
Momentum, entropy, wave mechanics, energy states. Extends AEON's quantum layer.
Answers: What is the market's kinetic state? Is it trending or dissipating energy?
"""

import logging
import math
from typing import Any, Dict, List

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Physicist. You apply classical and quantum mechanics to market dynamics — "
    "momentum conservation, entropy gradients, wave interference, energy states. "
    "You speak in physics metaphors but back them with real numbers."
)


async def analyze(db, market_intel=None) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation = None

    # ── 1. Pull quantum state from DB ────────────────────────────────────────
    try:
        from app_state import quantum_state
        if quantum_state:
            snap = quantum_state.get_snapshot() if hasattr(quantum_state, "get_snapshot") else {}
            H = snap.get("H", 0.5)
            C = snap.get("C", 0.5)
            S = snap.get("S", 0.5)
        else:
            state_doc = await db.states.find_one({}, sort=[("_id", -1)])
            if state_doc:
                H = float(state_doc.get("H", 0.5))
                C = float(state_doc.get("C", 0.5))
                S = float(state_doc.get("S", 0.5))
            else:
                H, C, S = 0.5, 0.5, 0.5

        raw.update({"H": round(H, 4), "C": round(C, 4), "S": round(S, 4)})

        # Thermodynamic interpretation
        # H = health/profitability (1.0 = perfectly profitable)
        # C = coherence (1.0 = all engines aligned)
        # S = entropy (1.0 = maximally disordered)

        free_energy = H * C * (1 - S)   # systems with high H, C, low S are exploitable
        raw["free_energy"] = round(free_energy, 4)

        observations.append(
            f"Quantum state — H:{H:.3f} C:{C:.3f} S:{S:.3f} | "
            f"Free energy: {free_energy:.3f}"
        )

        if S > 0.8:
            observations.append(
                f"ENTROPY CRITICAL ({S:.3f}) — market in disordered state. "
                "High-frequency signals unreliable."
            )
        elif C > 0.75 and H > 0.8:
            observations.append(
                f"High coherence + profitability — engines aligned, system in exploitable regime."
            )

    except Exception as e:
        H, C, S = 0.5, 0.5, 0.5
        logger.debug(f"[MAXWELL] Quantum state read failed: {e}")

    # ── 2. Price momentum (velocity + acceleration) ───────────────────────────
    if market_intel:
        for sym in ["BTC/USDT", "ETH/USDT"]:
            try:
                df = await market_intel.get_klines(sym, timeframe="1h", limit=24)
                if df is not None and len(df) >= 6:
                    closes = df["close"].values
                    # Velocity: % change over last 6h
                    velocity  = (closes[-1] - closes[-6]) / closes[-6] * 100
                    # Acceleration: velocity change (second derivative)
                    v_prev    = (closes[-4] - closes[-10]) / closes[-10] * 100 if len(closes) >= 10 else 0
                    accel     = velocity - v_prev
                    # Momentum energy: KE analog = 0.5 * v^2
                    ke        = 0.5 * velocity ** 2
                    base      = sym.split("/")[0]
                    raw[f"{base}_momentum"] = {
                        "velocity": round(velocity, 3),
                        "accel":    round(accel, 3),
                        "ke":       round(ke, 4),
                    }
                    obs = f"{base}: velocity {velocity:+.2f}%/6h | accel {accel:+.2f}%"
                    if abs(velocity) > 3:
                        obs += " ⚡ HIGH MOMENTUM"
                    observations.append(obs)
            except Exception as e:
                logger.debug(f"[MAXWELL] Momentum calc {sym}: {e}")

    # ── 3. Return distribution entropy ───────────────────────────────────────
    if market_intel:
        try:
            df = await market_intel.get_klines("BTC/USDT", timeframe="1h", limit=48)
            if df is not None and len(df) >= 20:
                returns = df["close"].pct_change().dropna().values
                # Bin returns into 10 buckets, compute Shannon entropy
                bins   = [-0.05, -0.03, -0.02, -0.01, -0.005, 0, 0.005, 0.01, 0.02, 0.03, 0.05]
                counts = [0] * (len(bins) + 1)
                for r in returns:
                    placed = False
                    for i, b in enumerate(bins):
                        if r < b:
                            counts[i] += 1
                            placed = True
                            break
                    if not placed:
                        counts[-1] += 1
                total    = len(returns)
                probs    = [c / total for c in counts if c > 0]
                entropy  = -sum(p * math.log(p + 1e-10) for p in probs) / math.log(len(probs) + 1)
                raw["return_entropy"] = round(entropy, 4)
                observations.append(
                    f"BTC return entropy: {entropy:.3f} "
                    f"({'HIGH DISORDER' if entropy > 0.85 else 'ORDERLY' if entropy < 0.6 else 'MODERATE'})"
                )
                if entropy > 0.88 and S > 0.75:
                    # Both quantum and return entropy high → chaotic market
                    recommendation = Recommendation(
                        type=RecType.RAISE_CONFIDENCE,
                        reasoning=(
                            f"Return entropy {entropy:.3f} and quantum entropy {S:.3f} both elevated. "
                            "Market is in a high-disorder state — noise dominates signal. "
                            "Raising confidence requirement to filter false positives."
                        ),
                        confidence=0.76,
                        params={"min_confidence": 83, "symbol": None},
                        duration_hours=4,
                    )
        except Exception as e:
            logger.debug(f"[MAXWELL] Entropy calc: {e}")

    # ── 4. Signal based on free energy + entropy ──────────────────────────────
    if not observations:
        return AnalysisResult(
            specialist="MAXWELL", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Data feeds unavailable for physics analysis."]
        )

    if S > 0.8 or raw.get("return_entropy", 0.5) > 0.88:
        signal     = MarketSignal.VOLATILE
        confidence = 65
    elif C > 0.7 and H > 0.8:
        signal     = MarketSignal.BULLISH
        confidence = 70
    elif H < 0.4:
        signal     = MarketSignal.BEARISH
        confidence = 60
    else:
        signal     = MarketSignal.NEUTRAL
        confidence = 55

    return AnalysisResult(
        specialist="MAXWELL",
        signal=signal,
        confidence=confidence,
        observations=observations,
        recommendation=recommendation,
        raw_data=raw,
    )
