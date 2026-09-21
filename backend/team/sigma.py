"""
SIGMA — AEON's Quantitative Mathematician
Probability theory, Kelly criterion, statistical edge, correlation analysis.
Answers: Is our edge real? Are we sizing correctly? Are the engines correlated?
"""

import logging
import math
from typing import Any, Dict, List

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Quantitative Mathematician. You speak in probabilities, expected values, "
    "and Kelly fractions. Precise, dry, unsentimentally mathematical. "
    "You only recommend action when the numbers demand it."
)


async def analyze(db) -> AnalysisResult:
    """
    Pull closed trade history and engine stats from MongoDB.
    Compute Kelly edge, win rate significance, and engine correlation.
    """
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation = None

    try:
        # ── 1. Pull last 100 closed trades ───────────────────────────────────
        trades = await db.paper_trades.find(
            {"status": {"$in": ["stopped", "profit", "liquidated", "closed"]},
             "realized_pnl": {"$exists": True}},
            {"realized_pnl": 1, "strategy": 1, "direction": 1, "leverage": 1,
             "margin": 1, "close_reason": 1}
        ).sort("closed_at", -1).limit(100).to_list(100)

        if len(trades) < 10:
            return AnalysisResult(
                specialist="SIGMA", signal=MarketSignal.NEUTRAL, confidence=30,
                observations=["Insufficient trade history for statistical analysis (< 10 trades)."],
                raw_data={"n": len(trades)}
            )

        pnls   = [t.get("realized_pnl", 0) for t in trades]
        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        n      = len(pnls)
        wr     = len(wins) / n if n else 0
        avg_w  = sum(wins)   / len(wins)   if wins   else 0
        avg_l  = abs(sum(losses) / len(losses)) if losses else 1
        rr     = avg_w / avg_l if avg_l else 0

        # Kelly fraction: f* = (bp - q) / b  where b=RR, p=winrate, q=1-p
        kelly = ((rr * wr) - (1 - wr)) / rr if rr > 0 else 0
        kelly_pct = round(kelly * 100, 2)

        raw.update({"n": n, "win_rate": round(wr, 4), "avg_win": round(avg_w, 2),
                    "avg_loss": round(avg_l, 2), "rr": round(rr, 3), "kelly_pct": kelly_pct})

        observations.append(
            f"Sample: {n} trades | WR {wr*100:.1f}% | R:R {rr:.2f} | Kelly edge {kelly_pct:+.1f}%"
        )

        # ── 2. Statistical significance (binomial p-value approximation) ─────
        # H0: true win rate = 50%. z = (wr - 0.5) / sqrt(0.25/n)
        z = (wr - 0.5) / math.sqrt(0.25 / n)
        significant = abs(z) > 1.96   # 95% confidence
        raw["z_score"] = round(z, 3)
        observations.append(
            f"Statistical significance: z={z:.2f} ({'SIGNIFICANT ✓' if significant else 'NOT YET SIGNIFICANT'})"
        )

        # ── 3. Per-engine breakdown ───────────────────────────────────────────
        engine_stats: Dict[str, Dict] = {}
        for t in trades:
            eng = t.get("strategy", "unknown")
            if eng not in engine_stats:
                engine_stats[eng] = {"wins": 0, "losses": 0, "pnl": 0.0}
            pnl = t.get("realized_pnl", 0)
            if pnl > 0:
                engine_stats[eng]["wins"] += 1
            else:
                engine_stats[eng]["losses"] += 1
            engine_stats[eng]["pnl"] += pnl

        worst_engine = min(engine_stats.items(),
                          key=lambda x: x[1]["pnl"], default=(None, {}))
        if worst_engine[0]:
            we_name = worst_engine[0]
            we_data = worst_engine[1]
            we_total = we_data["wins"] + we_data["losses"]
            we_wr = we_data["wins"] / we_total if we_total else 0
            raw["worst_engine"] = {"name": we_name, "wr": round(we_wr, 3),
                                   "pnl": round(we_data["pnl"], 2)}
            observations.append(
                f"Weakest engine: {we_name} — WR {we_wr*100:.0f}% | PnL ${we_data['pnl']:+.0f}"
            )

        # ── 4. Determine signal and recommendation ────────────────────────────
        if kelly < -0.05:
            # Negative Kelly — we are below break-even as a system
            signal     = MarketSignal.CAUTION
            confidence = min(95, 50 + int(abs(kelly) * 300))
            observations.append(
                f"NEGATIVE KELLY ({kelly_pct:+.1f}%) — system edge is below break-even. "
                "Raising confidence gate recommended."
            )
            recommendation = Recommendation(
                type=RecType.RAISE_CONFIDENCE,
                reasoning=(
                    f"Kelly fraction is {kelly_pct:+.1f}%. "
                    "Below-breakeven edge requires raising the confidence bar to filter lower-quality setups."
                ),
                confidence=0.80,
                params={"min_confidence": 82, "symbol": None},
                duration_hours=8,
            )
        elif kelly < 0.02:
            signal     = MarketSignal.CAUTION
            confidence = 55
            observations.append(f"Thin edge (Kelly {kelly_pct:+.1f}%) — proceed with caution.")
        elif wr > 0.58 and kelly > 0.08:
            signal     = MarketSignal.BULLISH
            confidence = 80
            observations.append(f"Strong edge confirmed (Kelly {kelly_pct:+.1f}%, WR {wr*100:.1f}%).")
        else:
            signal     = MarketSignal.NEUTRAL
            confidence = 60
            observations.append(f"Edge exists but modest (Kelly {kelly_pct:+.1f}%). Standard operation.")

        return AnalysisResult(
            specialist="SIGMA",
            signal=signal,
            confidence=confidence,
            observations=observations,
            recommendation=recommendation,
            raw_data=raw,
        )

    except Exception as e:
        logger.error(f"[SIGMA] Analysis error: {e}")
        return AnalysisResult(
            specialist="SIGMA", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Analysis failed — data pipeline error."],
            error=str(e),
        )
