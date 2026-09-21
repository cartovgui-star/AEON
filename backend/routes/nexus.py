from fastapi import APIRouter
from datetime import datetime, timezone
import app_state

router = APIRouter()


@router.get("/api/nexus/awareness")
async def get_nexus_awareness():
    """Latest NEXUS awareness snapshot (ORACLE_SENSE output)."""
    if app_state.db is None:
        return {"error": "db not ready"}
    doc = await app_state.db["nexus_awareness"].find_one(
        {}, {"_id": 0},
        sort=[("timestamp", -1)]
    )
    return doc or {}


@router.get("/api/nexus/config")
async def get_nexus_config():
    """Current live NEXUS config (what AEON reads every 30s)."""
    if app_state.db is None:
        return {"error": "db not ready"}
    doc = await app_state.db["nexus_config"].find_one({"_id": "live"}, {"_id": 0})
    return doc or {}


@router.get("/api/nexus/heals")
async def get_nexus_heals(limit: int = 20):
    """Recent HEALER actions."""
    if app_state.db is None:
        return []
    docs = await app_state.db["nexus_heals"].find(
        {}, {"_id": 0},
        sort=[("timestamp", -1)],
        limit=limit
    ).to_list(limit)
    return docs


@router.get("/api/nexus/adaptations")
async def get_nexus_adaptations(limit: int = 20):
    """Recent MORPHEUS regime adaptations."""
    if app_state.db is None:
        return []
    docs = await app_state.db["nexus_adaptations"].find(
        {}, {"_id": 0},
        sort=[("timestamp", -1)],
        limit=limit
    ).to_list(limit)
    return docs


@router.get("/api/nexus/alerts")
async def get_nexus_alerts(limit: int = 20):
    """Recent WARDEN alerts."""
    if app_state.db is None:
        return []
    docs = await app_state.db["nexus_alerts"].find(
        {}, {"_id": 0},
        sort=[("timestamp", -1)],
        limit=limit
    ).to_list(limit)
    return docs


@router.get("/api/nexus/heartbeat")
async def get_nexus_heartbeat():
    """Latest NEXUS heartbeat."""
    if app_state.db is None:
        return {"error": "db not ready"}
    doc = await app_state.db["nexus_heartbeat"].find_one(
        {}, {"_id": 0},
        sort=[("timestamp", -1)]
    )
    return doc or {}


@router.get("/api/nexus/suspended-engines")
async def get_nexus_suspended_engines():
    """Engines currently suspended by HEALER."""
    if app_state.db is None:
        return []
    docs = await app_state.db["nexus_suspended_engines"].find(
        {}, {"_id": 0}
    ).to_list(50)
    return docs


@router.get("/api/nexus/awareness-feed")
async def get_nexus_awareness_feed(limit: int = 20):
    """
    Returns last 20 entries merged from nexus_awareness, nexus_heals, and
    nexus_adaptations, sorted by timestamp descending.
    Each entry has: type (SENSE/HEAL/ADAPT), timestamp, summary
    """
    if app_state.db is None:
        return []

    results = []

    # SENSE entries from nexus_awareness (latest snapshot)
    sense_docs = await app_state.db["nexus_awareness"].find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(5).to_list(5)
    for d in sense_docs:
        ts = d.get("timestamp")
        regime = d.get("market_regime", "")
        hurst = d.get("hurst_exponent")
        crisis = d.get("crisis_mode", False)
        cpu = d.get("cpu_pct")
        ram = d.get("ram_pct")
        parts = []
        if regime:
            parts.append(f"Regime: {regime}")
        if hurst is not None:
            parts.append(f"Hurst: {round(hurst, 3)}")
        if crisis:
            parts.append("CRISIS MODE")
        if cpu is not None:
            parts.append(f"CPU: {round(cpu, 1)}%")
        if ram is not None:
            parts.append(f"RAM: {round(ram, 1)}%")
        results.append({
            "type": "SENSE",
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else "",
            "summary": " | ".join(parts) if parts else "Awareness snapshot",
        })

    # HEAL entries from nexus_heals
    heal_docs = await app_state.db["nexus_heals"].find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(10).to_list(10)
    for d in heal_docs:
        ts = d.get("timestamp")
        heal_type = d.get("heal_type") or d.get("type") or "heal"
        action = d.get("action") or d.get("message") or d.get("reason") or ""
        results.append({
            "type": "HEAL",
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else "",
            "summary": f"{heal_type}: {action}" if action else heal_type,
        })

    # ADAPT entries from nexus_adaptations
    adapt_docs = await app_state.db["nexus_adaptations"].find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(10).to_list(10)
    for d in adapt_docs:
        ts = d.get("timestamp")
        from_r = d.get("from_regime", "")
        to_r = d.get("to_regime", "")
        action = d.get("action") or d.get("reason") or ""
        summary = f"{from_r} → {to_r}" if from_r and to_r else action
        if action and from_r and to_r:
            summary = f"{from_r} → {to_r}: {action}"
        results.append({
            "type": "ADAPT",
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else "",
            "summary": summary or "Regime adaptation",
        })

    # Sort all combined entries by timestamp descending
    def _sort_key(e):
        ts = e.get("timestamp", "")
        return ts if ts else ""

    results.sort(key=_sort_key, reverse=True)
    return results[:limit]


@router.post("/api/control/pause")
async def control_pause():
    """
    Pause trading by setting the crisis flag in nexus_config.
    AEON reads nexus_config every 30s and halts trade execution when crisis=True.
    """
    if app_state.db is None:
        return {"error": "db not ready"}
    try:
        await app_state.db["nexus_config"].update_one(
            {"_id": "live"},
            {"$set": {"crisis": True, "paused_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        # Also pause the autonomous trader in-memory
        if hasattr(app_state, "autonomous_trader_v2") and app_state.autonomous_trader_v2:
            app_state.autonomous_trader_v2.active = False
        return {"success": True, "message": "Trading paused — crisis mode activated"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/control/resume")
async def control_resume():
    """
    Resume trading from crisis mode.
    Clears the crisis flag in nexus_config and allows AEON to resume.
    """
    if app_state.db is None:
        return {"error": "db not ready"}
    try:
        await app_state.db["nexus_config"].update_one(
            {"_id": "live"},
            {"$set": {"crisis": False, "resumed_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        # Also resume the autonomous trader in-memory
        if hasattr(app_state, "autonomous_trader_v2") and app_state.autonomous_trader_v2:
            app_state.autonomous_trader_v2.active = True
        return {"success": True, "message": "Crisis mode cleared — trading resumed"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/nexus/status")
async def get_nexus_status():
    """
    Unified NEXUS status for the Lab page — config + heartbeat + recent heals + recent adaptations.
    Single call that surfaces everything the UI needs to show NEXUS health.
    """
    if app_state.db is None:
        return {"error": "db not ready", "live": False}

    try:
        config_doc = await app_state.db["nexus_config"].find_one({"_id": "live"}, {"_id": 0})
        heartbeat_doc = await app_state.db["nexus_heartbeat"].find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
        heals = await app_state.db["nexus_heals"].find({}, {"_id": 0}, sort=[("timestamp", -1)]).limit(5).to_list(5)
        adaptations = await app_state.db["nexus_adaptations"].find({}, {"_id": 0}, sort=[("timestamp", -1)]).limit(5).to_list(5)

        # Determine if NEXUS process is alive (heartbeat within last 90s)
        nexus_alive = False
        last_beat = None
        if heartbeat_doc and heartbeat_doc.get("timestamp"):
            ts = heartbeat_doc["timestamp"]
            if hasattr(ts, "timestamp"):
                age_s = (datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else datetime.now(timezone.utc) - ts).total_seconds()
                nexus_alive = age_s < 90
                last_beat = ts.isoformat()
            elif isinstance(ts, str):
                nexus_alive = True
                last_beat = ts

        # Convert datetime objects in heals/adaptations for JSON
        def _clean(docs):
            result = []
            for d in docs:
                cleaned = {}
                for k, v in d.items():
                    cleaned[k] = v.isoformat() if hasattr(v, "isoformat") else v
                result.append(cleaned)
            return result

        config = {}
        if config_doc:
            for k, v in config_doc.items():
                config[k] = v.isoformat() if hasattr(v, "isoformat") else v

        return {
            "live": nexus_alive,
            "last_heartbeat": last_beat,
            "config": config,
            "recent_heals": _clean(heals),
            "recent_adaptations": _clean(adaptations),
            "loop_errors": heartbeat_doc.get("loop_errors", 0) if heartbeat_doc else 0,
        }
    except Exception as e:
        return {"error": str(e), "live": False}
