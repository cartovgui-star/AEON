from fastapi import APIRouter
from typing import List, Dict, Any
from collections import defaultdict
import app_state

router = APIRouter()


@router.get("/api/analytics/report")
async def get_analytics_report():
    if app_state.analytics_engine is None:
        return {"error": "Analytics engine not initialized"}
    return await app_state.analytics_engine.get_full_report()


@router.get("/api/analytics/equity-curve")
async def get_equity_curve(account_id: str = None, days: int = 60):
    if app_state.analytics_engine is None:
        return []
    return await app_state.analytics_engine.get_equity_curve(account_id, days)


@router.get("/api/analytics/win-rates")
async def get_win_rates():
    if app_state.analytics_engine is None:
        return {}
    return await app_state.analytics_engine.get_win_rate_breakdown()


@router.get("/api/analytics/top-performers")
async def get_top_performers():
    if app_state.analytics_engine is None:
        return {}
    return await app_state.analytics_engine.get_top_performers()


@router.get("/api/analytics/drawdown")
async def get_drawdown():
    if app_state.analytics_engine is None:
        return {}
    return await app_state.analytics_engine.get_drawdown_analysis()


@router.get("/api/analytics/recent")
async def get_recent_trades(limit: int = 50):
    if app_state.analytics_engine is None:
        return []
    return await app_state.analytics_engine.get_recent_trades(limit)


# ── GET /api/analytics/performance ───────────────────────────────────────────
# Aggregated stats by engine and by hour-of-day, sourced directly from MongoDB
# paper_trades collection so it reflects all accounts.
# Response shape:
#   {
#     "by_engine": [{name, win_rate, avg_pnl, trade_count, profit_factor}],
#     "by_hour":   [{hour, pnl, trades}]
#   }
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/analytics/performance")
async def get_performance_breakdown():
    """
    Aggregated performance stats by engine and by hour-of-day.
    Reads from MongoDB paper_trades (closed trades only).
    """
    if app_state.db is None:
        return {"by_engine": [], "by_hour": []}

    try:
        closed = await app_state.db.paper_trades.find(
            {"status": "closed"},
            {"engine": 1, "realized_pnl": 1, "closed_at": 1, "direction": 1}
        ).sort("closed_at", -1).limit(2000).to_list(2000)
    except Exception as e:
        return {"by_engine": [], "by_hour": [], "error": str(e)}

    # ── By engine aggregation ─────────────────────────────────────────────────
    eng_stats: Dict[str, Dict] = defaultdict(lambda: {
        "trade_count": 0, "wins": 0, "losses": 0,
        "total_pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0,
    })
    hour_stats: Dict[int, Dict] = defaultdict(lambda: {"pnl": 0.0, "trades": 0})

    for t in closed:
        pnl    = float(t.get("realized_pnl") or 0)
        engine = t.get("engine") or t.get("strategy") or "unknown"
        s      = eng_stats[engine]
        s["trade_count"] += 1
        s["total_pnl"]   += pnl
        if pnl > 0:
            s["wins"]      += 1
            s["gross_win"] += pnl
        else:
            s["losses"]     += 1
            s["gross_loss"] += abs(pnl)

        # Hour-of-day bucketing
        closed_at = t.get("closed_at")
        if closed_at:
            try:
                from datetime import timezone
                if hasattr(closed_at, "hour"):
                    h = closed_at.hour
                else:
                    from datetime import datetime
                    h = datetime.fromisoformat(str(closed_at)).replace(tzinfo=timezone.utc).hour
                hour_stats[h]["pnl"]    += pnl
                hour_stats[h]["trades"] += 1
            except Exception:
                pass

    by_engine = []
    for eng, s in sorted(eng_stats.items()):
        tc    = s["trade_count"]
        wins  = s["wins"]
        gw    = s["gross_win"]
        gl    = s["gross_loss"]
        by_engine.append({
            "name":          eng,
            "trade_count":   tc,
            "win_rate":      round(wins / tc * 100, 1) if tc else 0.0,
            "avg_pnl":       round(s["total_pnl"] / tc, 2) if tc else 0.0,
            "total_pnl":     round(s["total_pnl"], 2),
            "profit_factor": round(gw / gl, 2) if gl > 0 else (float("inf") if gw > 0 else 0.0),
        })

    by_hour = [
        {"hour": h, "pnl": round(v["pnl"], 2), "trades": v["trades"]}
        for h, v in sorted(hour_stats.items())
    ]

    return {"by_engine": by_engine, "by_hour": by_hour, "total_trades": len(closed)}


@router.get("/api/analytics/hourly-heatmap")
async def get_hourly_heatmap():
    """
    24-slot time-of-day win rate grid from closed paper_trades.
    Returns one object per UTC hour: { hour, win_rate, trade_count, avg_pnl, insufficient_data }.
    HourlyHeatmap.jsx polls this every 2 minutes.
    """
    if app_state.db is None:
        return [{"hour": h, "win_rate": 0, "trade_count": 0, "avg_pnl": 0.0, "insufficient_data": True} for h in range(24)]

    from datetime import datetime, timezone
    from collections import defaultdict

    try:
        closed = await app_state.db.paper_trades.find(
            {"status": "closed"},
            {"realized_pnl": 1, "closed_at": 1}
        ).sort("closed_at", -1).limit(3000).to_list(3000)
    except Exception:
        return [{"hour": h, "win_rate": 0, "trade_count": 0, "avg_pnl": 0.0, "insufficient_data": True} for h in range(24)]

    buckets: Dict[int, Dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0.0})
    for t in closed:
        pnl = float(t.get("realized_pnl") or 0)
        ca  = t.get("closed_at")
        if not ca:
            continue
        try:
            if hasattr(ca, "hour"):
                h = ca.hour
            else:
                h = datetime.fromisoformat(str(ca).replace("Z", "+00:00")).replace(tzinfo=timezone.utc).hour
        except Exception:
            continue
        b = buckets[h]
        b["total_pnl"] += pnl
        if pnl > 0:
            b["wins"] += 1
        else:
            b["losses"] += 1

    result = []
    for h in range(24):
        b  = buckets[h]
        tc = b["wins"] + b["losses"]
        result.append({
            "hour":             h,
            "trade_count":      tc,
            "win_rate":         round(b["wins"] / tc * 100, 1) if tc else 0.0,
            "avg_pnl":          round(b["total_pnl"] / tc, 2) if tc else 0.0,
            "insufficient_data": tc < 10,
        })
    return result


@router.get("/api/trades/post-mortem")
async def get_post_mortem_trades(limit: int = 20):
    """Returns closed losing trades with post-mortem analysis fields."""
    if app_state.db is None:
        return []
    from datetime import datetime, timezone

    query = {
        "status": {"$in": ["closed", "stopped", "liquidated"]},
        "realized_pnl": {"$lt": 0},
    }
    trades = await app_state.db.paper_trades.find(
        query, {"_id": 0}
    ).sort("closed_at", -1).limit(limit).to_list(limit)

    result = []
    for t in trades:
        opened = t.get("opened_at") or t.get("timestamp")
        closed = t.get("closed_at")
        duration_min = None
        if opened and closed:
            try:
                if isinstance(opened, str):
                    opened = datetime.fromisoformat(opened.replace("Z", "+00:00"))
                if isinstance(closed, str):
                    closed = datetime.fromisoformat(closed.replace("Z", "+00:00"))
                duration_min = round((closed.timestamp() - opened.timestamp()) / 60, 1)
            except Exception:
                pass

        result.append({
            "symbol": t.get("symbol"),
            "direction": t.get("direction"),
            "entry_price": t.get("entry_price"),
            "exit_price": t.get("exit_price"),
            "pnl": round(t.get("realized_pnl") or 0, 2),
            "engine": t.get("strategy") or t.get("engine"),
            "regime_at_entry": t.get("regime_at_entry") or (t.get("signal_data") or {}).get("regime"),
            "h_value_at_entry": t.get("h_value_at_entry") or (t.get("signal_data") or {}).get("h_value"),
            "stop_loss": t.get("stop_loss"),
            "close_reason": t.get("close_reason") or t.get("orphan_reason"),
            "duration_min": duration_min,
            "account_id": t.get("account_id"),
        })

    return result
