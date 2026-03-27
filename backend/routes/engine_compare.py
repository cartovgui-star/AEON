"""
Engine Comparison API Routes
GET /api/engines/compare        - Side-by-side engine stats from latest snapshot
GET /api/engines/snapshots      - Historical snapshots (trend data)
GET /api/engines/confirmations  - Top confirmation signals by win rate
GET /api/engines/outcomes       - FW/Dual alert outcome stats
"""
from fastapi import APIRouter, Query
from datetime import datetime, timezone, timedelta
from typing import Optional
import app_state

router = APIRouter()

ENGINE_DISPLAY = {
    "autonomous_v2":   "Autonomous V2",
    "free_will_v2":    "Free Will V2",
    "dual_day_trader": "Day Trader",
    "dual_long_term":  "Long Term",
    "elite_v3":        "Elite V3",
    "vwap_scalper":    "VWAP Scalper",
    "yolo":            "YOLO",
}


@router.get("/compare")
async def compare_engines():
    """Side-by-side comparison of all engines from the latest snapshot"""
    db = app_state.db
    if db is None:
        return {"error": "Database not available"}

    latest = await db.engine_snapshots.find_one(sort=[("timestamp", -1)])
    if not latest:
        return {"error": "No snapshots yet — data collector starts collecting hourly. Check back soon."}

    engines_raw = latest.get("engines", {})
    comparison = []

    for engine_id, display_name in ENGINE_DISPLAY.items():
        stats = engines_raw.get(engine_id)
        if not stats or "error" in stats:
            continue

        comparison.append({
            "id": engine_id,
            "name": display_name,
            "active": stats.get("active", False),
            "win_rate": stats.get("win_rate"),
            "total_trades": (
                stats.get("total_trades")
                or stats.get("total_alerts")
                or stats.get("total_signals")
            ),
            "wins": stats.get("wins"),
            "losses": stats.get("losses"),
            "total_pnl_pct": stats.get("total_pnl_pct"),
            "profit_factor": stats.get("profit_factor"),
            "expectancy": stats.get("expectancy"),
            "signals_today": (
                stats.get("daily_alerts")
                or stats.get("signals_today")
                or stats.get("daily_signals")
            ),
            "raw": stats,
        })

    # Sort: engines with win_rate first (descending), then rest
    comparison.sort(key=lambda x: x.get("win_rate") or -1, reverse=True)

    ts = latest.get("timestamp")
    snapshot_age_min = int((datetime.now(timezone.utc) - ts).total_seconds() // 60) if ts else None

    return {
        "snapshot_time": ts.isoformat() if ts else None,
        "snapshot_age_minutes": snapshot_age_min,
        "engines": comparison,
        "total_engines": len(comparison),
    }


@router.get("/snapshots")
async def get_snapshots(hours: int = Query(24, ge=1, le=168)):
    """Historical engine snapshots for the last N hours (for trend charts)"""
    db = app_state.db
    if db is None:
        return {"error": "Database not available"}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    raw = await db.engine_snapshots.find(
        {"timestamp": {"$gte": cutoff}},
        sort=[("timestamp", 1)]
    ).to_list(200)

    snapshots = []
    for s in raw:
        snapshots.append({
            "timestamp": s["timestamp"].isoformat(),
            "engines": s.get("engines", {}),
        })

    return {
        "hours": hours,
        "count": len(snapshots),
        "snapshots": snapshots,
    }


@router.get("/confirmations")
async def get_confirmation_accuracy(min_samples: int = Query(3, ge=1)):
    """Which confirmation signals correlate most with wins"""
    db = app_state.db
    if db is None:
        return {"error": "Database not available"}

    records = await db.confirmation_accuracy.find(
        {"total": {"$gte": min_samples}},
        sort=[("win_rate", -1)]
    ).to_list(100)

    for r in records:
        r.pop("_id", None)

    return {
        "min_samples": min_samples,
        "total_tracked": len(records),
        "confirmations": records,
    }


@router.get("/outcomes")
async def get_alert_outcomes(
    engine: Optional[str] = Query(None, description="free_will | dual | None for both"),
    days: int = Query(7, ge=1, le=30)
):
    """WIN/LOSS/PENDING stats for Free Will and Dual Engine alerts"""
    db = app_state.db
    if db is None:
        return {"error": "Database not available"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    collections = []

    if engine in (None, "free_will"):
        collections.append(("free_will_alerts", "Free Will V2"))
    if engine in (None, "dual"):
        collections.append(("dual_alerts", "Dual Engine"))

    results = {}
    for col_name, display_name in collections:
        col = db[col_name]
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$ifNull": ["$outcome", "PENDING"]},
                "count": {"$sum": 1},
                "avg_pnl": {"$avg": "$pnl_pct"},
            }},
        ]
        rows = await col.aggregate(pipeline).to_list(10)

        stats = {"PENDING": 0, "WIN": 0, "LOSS": 0, "EXPIRED": 0}
        avg_pnl: dict = {}
        for row in rows:
            key = row["_id"]
            stats[key] = row["count"]
            avg_pnl[key] = round(row.get("avg_pnl") or 0, 2)

        total_resolved = stats["WIN"] + stats["LOSS"]
        win_rate = round(stats["WIN"] / total_resolved * 100, 1) if total_resolved > 0 else None

        results[col_name] = {
            "engine": display_name,
            "win_rate": win_rate,
            "wins": stats["WIN"],
            "losses": stats["LOSS"],
            "pending": stats["PENDING"],
            "expired": stats["EXPIRED"],
            "avg_win_pnl": avg_pnl.get("WIN"),
            "avg_loss_pnl": avg_pnl.get("LOSS"),
        }

    return {"days": days, "engines": results}
