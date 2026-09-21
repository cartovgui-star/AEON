"""
Stats & Analytics Telegram Commands
/stats, /accuracy, /leaderboard, /insights — all read from paper_trades (live governed data).
Legacy trading_stats / signal_history no longer used.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

_CLOSED = {"$in": ["closed", "profit", "stopped", "liquidated"]}


async def _closed_trades(db, days=30):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return await db.paper_trades.find(
        {"status": _CLOSED, "closed_at": {"$gte": cutoff}},
        {"realized_pnl": 1, "pnl_pct": 1, "symbol": 1, "engine": 1,
         "direction": 1, "account_id": 1, "closed_at": 1}
    ).to_list(length=2000)


def _calc_stats(trades):
    if not trades:
        return None
    wins = [t for t in trades if (t.get("realized_pnl") or 0) > 0]
    losses = [t for t in trades if (t.get("realized_pnl") or 0) <= 0]
    n = len(trades)
    wr = len(wins) / n * 100 if n else 0
    total_pnl = sum(t.get("realized_pnl") or 0 for t in trades)
    avg_win = sum(t.get("realized_pnl") or 0 for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.get("realized_pnl") or 0 for t in losses) / len(losses) if losses else 0
    gross_win = sum(t.get("realized_pnl") or 0 for t in wins)
    gross_loss = abs(sum(t.get("realized_pnl") or 0 for t in losses))
    pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else None
    return {"n": n, "wins": len(wins), "losses": len(losses), "wr": wr,
            "total_pnl": total_pnl, "avg_win": avg_win, "avg_loss": avg_loss, "pf": pf}


async def handle_stats(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    try:
        import app_state
        db = app_state.db
        if db is None:
            return "❌ DB not ready", "stats"

        trades_30 = await _closed_trades(db, days=30)
        trades_7  = await _closed_trades(db, days=7)
        open_count = await db.paper_trades.count_documents({"status": "open"})

        s30 = _calc_stats(trades_30)
        s7  = _calc_stats(trades_7)

        def _row(label, s):
            if not s:
                return "{}: no data".format(label)
            pf_part = " | PF {}".format(s["pf"]) if s["pf"] else ""
            return "{}: WR {:.1f}% | {}/{} | PnL ${:+,.0f}{}".format(
                label, s["wr"], s["wins"], s["n"],
                s["total_pnl"], pf_part)

        lines = [
            "📊 PAPER TRADING STATS",
            "",
            _row("7d ", s7),
            _row("30d", s30),
            "",
            "Open positions: {}".format(open_count),
        ]
        if s30:
            lines += [
                "",
                "Avg win  ${:+,.2f} | Avg loss ${:,.2f}".format(
                    s30["avg_win"], abs(s30["avg_loss"])),
            ]
        lines.append("\n/leaderboard — top coins | /accuracy — by direction")
        return "\n".join(lines), "stats"
    except Exception as e:
        logger.error("Stats error: %s", e)
        return "❌ Error fetching stats: {}".format(str(e)), "stats"


async def handle_accuracy(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    try:
        import app_state
        db = app_state.db
        if db is None:
            return "❌ DB not ready", "stats"

        trades = await _closed_trades(db, days=14)
        if not trades:
            return "🎯 No closed trade data in last 14 days.", "stats"

        longs  = [t for t in trades if (t.get("direction") or "").upper() == "LONG"]
        shorts = [t for t in trades if (t.get("direction") or "").upper() == "SHORT"]

        def _acc(subset):
            if not subset:
                return None, 0
            w = sum(1 for t in subset if (t.get("realized_pnl") or 0) > 0)
            return round(w / len(subset) * 100, 1), len(subset)

        long_acc,  long_n  = _acc(longs)
        short_acc, short_n = _acc(shorts)

        # By engine
        from collections import defaultdict
        by_engine = defaultdict(list)
        for t in trades:
            by_engine[t.get("engine", "unknown")].append(t)

        lines = [
            "🎯 ACCURACY (14 days — {} trades)".format(len(trades)),
            "",
            "LONG:  {}% ({} trades)".format(long_acc or "n/a", long_n),
            "SHORT: {}% ({} trades)".format(short_acc or "n/a", short_n),
            "",
            "By engine:",
        ]
        for eng, etrades in sorted(by_engine.items(), key=lambda x: -len(x[1]))[:8]:
            w = sum(1 for t in etrades if (t.get("realized_pnl") or 0) > 0)
            acc = round(w / len(etrades) * 100, 1) if etrades else 0
            lines.append("  {} — {}% ({})".format(eng[:22], acc, len(etrades)))

        return "\n".join(lines), "stats"
    except Exception as e:
        logger.error("Accuracy error: %s", e)
        return "❌ Error: {}".format(str(e)), "stats"


async def handle_leaderboard(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    try:
        import app_state
        db = app_state.db
        if db is None:
            return "❌ DB not ready", "stats"

        pipeline = [
            {"$match": {"status": _CLOSED,
                        "closed_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}}},
            {"$group": {
                "_id": "$symbol",
                "total": {"$sum": 1},
                "wins":  {"$sum": {"$cond": [{"$gt": ["$realized_pnl", 0]}, 1, 0]}},
                "pnl":   {"$sum": "$realized_pnl"},
            }},
            {"$match": {"total": {"$gte": 2}}},
            {"$sort": {"pnl": -1}},
            {"$limit": 10},
        ]
        results = await db.paper_trades.aggregate(pipeline).to_list(length=10)

        if not results:
            return "🏆 Not enough data yet (need ≥2 closed trades per coin).", "stats"

        lines = ["🏆 TOP COINS (30d paper trades)", ""]
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(results):
            sym = (r["_id"] or "?").replace("/USDT", "")
            wr = round(r["wins"] / r["total"] * 100) if r["total"] else 0
            prefix = medals[i] if i < 3 else "{}. ".format(i + 1)
            lines.append("{} {}: ${:+,.0f} | {}% WR | {} trades".format(
                prefix, sym, r["pnl"], wr, r["total"]))

        return "\n".join(lines), "stats"
    except Exception as e:
        logger.error("Leaderboard error: %s", e)
        return "❌ Error: {}".format(str(e)), "stats"


async def handle_insights(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    try:
        import app_state
        db = app_state.db
        if db is None:
            return "❌ DB not ready", "stats"

        trades = await _closed_trades(db, days=7)
        s = _calc_stats(trades)
        lines = ["💡 TRADING INSIGHTS (7d)", ""]
        if not s:
            lines.append("No closed trades in the last 7 days yet.")
        else:
            if s["wr"] >= 60:
                lines.append("✅ Strong win rate ({:.0f}%) — strategy in form.".format(s["wr"]))
            elif s["wr"] < 40:
                lines.append("⚠️ Win rate low ({:.0f}%) — gate thresholds may need review.".format(s["wr"]))
            else:
                lines.append("🟡 Win rate neutral ({:.0f}%) — watch for trend.".format(s["wr"]))

            if s["total_pnl"] > 0:
                lines.append("📈 Profitable week: ${:+,.0f}".format(s["total_pnl"]))
            else:
                lines.append("📉 Drawdown week: ${:,.0f} — stay disciplined.".format(s["total_pnl"]))

            if s["pf"] and s["pf"] >= 1.5:
                lines.append("✅ Profit factor {:.2f} — positive expectancy.".format(s["pf"]))
            elif s["pf"] and s["pf"] < 1.0:
                lines.append("⚠️ Profit factor {:.2f} — losses outpacing wins.".format(s["pf"]))

        lines.append("\n/stats for full breakdown | /fw for FW_V2 operator view")
        return "\n".join(lines), "stats"
    except Exception as e:
        logger.error("Insights error: %s", e)
        return "❌ Error: {}".format(str(e)), "stats"


STATS_HANDLERS = {
    '/stats':       handle_stats,
    '/accuracy':    handle_accuracy,
    '/acc':         handle_accuracy,
    '/leaderboard': handle_leaderboard,
    '/lb':          handle_leaderboard,
    '/insights':    handle_insights,
}


async def route_stats_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    text_lower = text.lower().strip()
    for pattern, handler in STATS_HANDLERS.items():
        if text_lower == pattern or text_lower.startswith(pattern + ' '):
            return await handler(text, chat_id, context)
    return None
