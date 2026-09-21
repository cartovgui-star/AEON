"""
KEPLER — AEON's Cycle Analyst
Market periodicity, time-based patterns, hour-of-day and day-of-week rhythms.
Answers: Are we in a historically strong or weak window right now?
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Cycle Analyst. You see the rhythms in markets — the recurring patterns "
    "that repeat across hours, days, and weeks. You speak about 'cycle positions', "
    "'historical windows', and 'periodic resonance'. Methodical. Pattern-obsessed."
)


async def analyze(db, market_intel=None) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation = None

    now = datetime.now(timezone.utc)
    current_hour = now.hour
    current_dow  = now.weekday()  # 0=Mon, 6=Sun
    dow_names    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    try:
        # ── 1. Hour-of-day win rate analysis ─────────────────────────────────
        trades = await db.paper_trades.find(
            {"status": {"$in": ["stopped", "profit", "closed"]},
             "realized_pnl": {"$exists": True},
             "opened_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=60)}},
            {"realized_pnl": 1, "opened_at": 1, "direction": 1}
        ).limit(500).to_list(500)

        if len(trades) < 20:
            return AnalysisResult(
                specialist="KEPLER", signal=MarketSignal.NEUTRAL, confidence=25,
                observations=["Insufficient trade history for cycle analysis (< 20 trades)."]
            )

        hour_stats: Dict[int, Dict] = defaultdict(lambda: {"wins": 0, "total": 0})
        dow_stats:  Dict[int, Dict] = defaultdict(lambda: {"wins": 0, "total": 0})

        for t in trades:
            opened = t.get("opened_at")
            if not opened:
                continue
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            h   = opened.hour
            dow = opened.weekday()
            pnl = t.get("realized_pnl", 0)

            hour_stats[h]["total"] += 1
            dow_stats[dow]["total"] += 1
            if pnl > 0:
                hour_stats[h]["wins"] += 1
                dow_stats[dow]["wins"] += 1

        # Current hour win rate
        ch_stats = hour_stats.get(current_hour, {"wins": 0, "total": 0})
        ch_wr    = ch_stats["wins"] / ch_stats["total"] if ch_stats["total"] >= 5 else None
        raw["current_hour"] = current_hour
        raw["current_dow"]  = dow_names[current_dow]

        if ch_wr is not None:
            observations.append(
                f"Hour {current_hour:02d}:00 UTC historical WR: {ch_wr*100:.0f}% "
                f"({ch_stats['total']} trades)"
            )
            raw["hour_wr"] = round(ch_wr, 3)
        else:
            observations.append(f"Hour {current_hour:02d}:00 UTC — insufficient sample (< 5 trades).")

        # Best / worst hours
        qualified_hours = {h: s for h, s in hour_stats.items() if s["total"] >= 5}
        if qualified_hours:
            best_h  = max(qualified_hours, key=lambda h: qualified_hours[h]["wins"] / qualified_hours[h]["total"])
            worst_h = min(qualified_hours, key=lambda h: qualified_hours[h]["wins"] / qualified_hours[h]["total"])
            best_wr  = qualified_hours[best_h]["wins"]  / qualified_hours[best_h]["total"]
            worst_wr = qualified_hours[worst_h]["wins"] / qualified_hours[worst_h]["total"]
            raw["best_hour"]  = {"hour": best_h,  "wr": round(best_wr,  3)}
            raw["worst_hour"] = {"hour": worst_h, "wr": round(worst_wr, 3)}
            observations.append(
                f"Best window: {best_h:02d}:00 UTC ({best_wr*100:.0f}% WR) | "
                f"Worst: {worst_h:02d}:00 UTC ({worst_wr*100:.0f}% WR)"
            )

        # ── 2. Day-of-week analysis ───────────────────────────────────────────
        cd_stats = dow_stats.get(current_dow, {"wins": 0, "total": 0})
        cd_wr    = cd_stats["wins"] / cd_stats["total"] if cd_stats["total"] >= 5 else None
        if cd_wr is not None:
            observations.append(
                f"{dow_names[current_dow]} historical WR: {cd_wr*100:.0f}% ({cd_stats['total']} trades)"
            )
            raw["dow_wr"] = round(cd_wr, 3)

        # ── 3. BTC weekly cycle positioning ──────────────────────────────────
        if market_intel:
            try:
                df = await market_intel.get_klines("BTC/USDT", timeframe="1d", limit=14)
                if df is not None and len(df) >= 7:
                    closes  = df["close"].values
                    week1   = closes[-7:]
                    week2   = closes[-14:-7]
                    w1_ret  = (week1[-1] - week1[0]) / week1[0] * 100
                    w2_ret  = (week2[-1] - week2[0]) / week2[0] * 100
                    raw["weekly_return"] = {"this_week": round(w1_ret, 2), "last_week": round(w2_ret, 2)}
                    observations.append(
                        f"BTC weekly cycle: this week {w1_ret:+.1f}% | last week {w2_ret:+.1f}%"
                    )
            except Exception as e:
                logger.debug(f"[KEPLER] Weekly cycle: {e}")

        # ── 4. Signal and recommendation ─────────────────────────────────────
        scores = []
        if ch_wr is not None:
            scores.append(ch_wr)
        if cd_wr is not None:
            scores.append(cd_wr)

        avg_score = sum(scores) / len(scores) if scores else 0.5

        if avg_score >= 0.58:
            signal     = MarketSignal.BULLISH
            confidence = min(75, 50 + int((avg_score - 0.5) * 200))
        elif avg_score <= 0.42:
            signal     = MarketSignal.CAUTION
            confidence = min(70, 50 + int((0.5 - avg_score) * 200))
            if avg_score <= 0.38:
                recommendation = Recommendation(
                    type=RecType.RAISE_CONFIDENCE,
                    reasoning=(
                        f"Current time window (hour {current_hour:02d}:00, {dow_names[current_dow]}) "
                        f"has historically low win rate ({avg_score*100:.0f}%). "
                        "Cycle analysis suggests caution — raising confidence bar."
                    ),
                    confidence=0.70,
                    params={"min_confidence": 80, "symbol": None},
                    duration_hours=3,
                )
        else:
            signal     = MarketSignal.NEUTRAL
            confidence = 50

        if not observations:
            observations.append("Cycle analysis complete — no significant patterns detected.")

        return AnalysisResult(
            specialist="KEPLER",
            signal=signal,
            confidence=confidence,
            observations=observations,
            recommendation=recommendation,
            raw_data=raw,
        )

    except Exception as e:
        logger.error(f"[KEPLER] Analysis error: {e}")
        return AnalysisResult(
            specialist="KEPLER", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Cycle analysis failed — data pipeline error."],
            error=str(e),
        )
