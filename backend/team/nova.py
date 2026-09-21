"""
NOVA — AEON's Data Scientist
ML pattern recognition, historical performance analysis, regime-engine matching.
Answers: Which engine is performing best RIGHT NOW? Which conditions historically win?
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Data Scientist. You speak in feature importance, correlation coefficients, "
    "and regime-conditional win rates. Cool, precise, evidence-driven. "
    "You only recommend what the historical data clearly supports."
)


async def analyze(db) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation = None

    try:
        # ── 1. Pull last 200 closed trades ───────────────────────────────────
        trades = await db.paper_trades.find(
            {"status": {"$in": ["stopped", "profit", "closed"]},
             "realized_pnl": {"$exists": True},
             "opened_at":    {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}},
            {"realized_pnl": 1, "strategy": 1, "direction": 1,
             "regime_at_open": 1, "opened_at": 1, "leverage": 1}
        ).sort("opened_at", -1).limit(200).to_list(200)

        if len(trades) < 10:
            return AnalysisResult(
                specialist="NOVA", signal=MarketSignal.NEUTRAL, confidence=25,
                observations=["Insufficient data for ML analysis (< 10 trades in 30d)."]
            )

        raw["n"] = len(trades)

        # ── 2. Engine performance in last 24h vs last 7d ─────────────────────
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        eng_24h: Dict[str, Dict] = defaultdict(lambda: {"wins": 0, "total": 0, "pnl": 0.0})
        eng_7d:  Dict[str, Dict] = defaultdict(lambda: {"wins": 0, "total": 0, "pnl": 0.0})

        for t in trades:
            eng = t.get("strategy", "unknown")
            pnl = t.get("realized_pnl", 0)
            opened = t.get("opened_at")
            if opened and opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)

            eng_7d[eng]["total"] += 1
            eng_7d[eng]["pnl"]   += pnl
            if pnl > 0:
                eng_7d[eng]["wins"] += 1

            if opened and opened >= cutoff_24h:
                eng_24h[eng]["total"] += 1
                eng_24h[eng]["pnl"]   += pnl
                if pnl > 0:
                    eng_24h[eng]["wins"] += 1

        # Best engine last 7d (min 5 trades)
        qualified = {k: v for k, v in eng_7d.items() if v["total"] >= 5}
        if qualified:
            best_eng = max(qualified, key=lambda k: qualified[k]["pnl"])
            b = qualified[best_eng]
            b_wr = b["wins"] / b["total"] if b["total"] else 0
            raw["best_engine_7d"] = {"name": best_eng, "wr": round(b_wr, 3),
                                     "pnl": round(b["pnl"], 2), "n": b["total"]}
            observations.append(
                f"Top engine (7d): {best_eng} — WR {b_wr*100:.0f}% | "
                f"PnL ${b['pnl']:+.0f} over {b['total']} trades"
            )

            worst_eng = min(qualified, key=lambda k: qualified[k]["pnl"])
            w = qualified[worst_eng]
            w_wr = w["wins"] / w["total"] if w["total"] else 0
            raw["worst_engine_7d"] = {"name": worst_eng, "wr": round(w_wr, 3), "pnl": round(w["pnl"], 2)}
            if w["pnl"] < -100:
                observations.append(
                    f"Underperformer (7d): {worst_eng} — WR {w_wr*100:.0f}% | PnL ${w['pnl']:+.0f}"
                )

        # ── 3. Regime-conditional win rates ──────────────────────────────────
        regime_stats: Dict[str, Dict] = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in trades:
            regime = t.get("regime_at_open", "unknown") or "unknown"
            pnl    = t.get("realized_pnl", 0)
            regime_stats[regime]["total"] += 1
            if pnl > 0:
                regime_stats[regime]["wins"] += 1

        for regime, stats in regime_stats.items():
            if stats["total"] >= 5:
                wr = stats["wins"] / stats["total"]
                raw.setdefault("regime_wr", {})[regime] = round(wr, 3)
                observations.append(f"Regime '{regime}': WR {wr*100:.0f}% ({stats['total']} trades)")

        # Get current regime
        try:
            current_regime_doc = await db.current_market_regime.find_one({})
            current_regime = (current_regime_doc or {}).get("regime", "unknown")
        except Exception:
            current_regime = "unknown"

        raw["current_regime"] = current_regime
        if current_regime != "unknown":
            cr_stats = regime_stats.get(current_regime, {})
            cr_wr    = cr_stats.get("wins", 0) / cr_stats["total"] if cr_stats.get("total", 0) > 0 else None
            if cr_wr is not None:
                observations.append(
                    f"Current regime '{current_regime}': historical WR {cr_wr*100:.0f}%"
                )

        # ── 4. Direction bias analysis ────────────────────────────────────────
        long_trades  = [t for t in trades if t.get("direction") == "LONG"]
        short_trades = [t for t in trades if t.get("direction") == "SHORT"]
        long_wr  = sum(1 for t in long_trades  if t.get("realized_pnl", 0) > 0) / len(long_trades)  if long_trades  else 0
        short_wr = sum(1 for t in short_trades if t.get("realized_pnl", 0) > 0) / len(short_trades) if short_trades else 0
        raw["direction_wr"] = {"long": round(long_wr, 3), "short": round(short_wr, 3)}
        observations.append(
            f"Direction WR: LONG {long_wr*100:.0f}% ({len(long_trades)} trades) | "
            f"SHORT {short_wr*100:.0f}% ({len(short_trades)} trades)"
        )

        # ── 5. Signal ─────────────────────────────────────────────────────────
        overall_wr = sum(1 for t in trades if t.get("realized_pnl", 0) > 0) / len(trades)

        if overall_wr >= 0.56:
            signal     = MarketSignal.BULLISH
            confidence = min(80, 50 + int((overall_wr - 0.5) * 200))
        elif overall_wr <= 0.44:
            signal     = MarketSignal.BEARISH
            confidence = min(75, 50 + int((0.5 - overall_wr) * 200))
            # Weak system performance — raise the bar
            if overall_wr <= 0.40:
                recommendation = Recommendation(
                    type=RecType.RAISE_CONFIDENCE,
                    reasoning=(
                        f"Historical win rate is {overall_wr*100:.1f}% over {len(trades)} trades. "
                        "Data suggests raising the confidence threshold to filter lower-quality setups."
                    ),
                    confidence=0.78,
                    params={"min_confidence": 80, "symbol": None},
                    duration_hours=6,
                )
        else:
            signal     = MarketSignal.NEUTRAL
            confidence = 55

        return AnalysisResult(
            specialist="NOVA",
            signal=signal,
            confidence=confidence,
            observations=observations,
            recommendation=recommendation,
            raw_data=raw,
        )

    except Exception as e:
        logger.error(f"[NOVA] Analysis error: {e}")
        return AnalysisResult(
            specialist="NOVA", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Analysis pipeline error — data unavailable."],
            error=str(e),
        )
