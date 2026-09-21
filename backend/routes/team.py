"""
AEON Research Team — API Routes
GET  /api/team/roster          → all 10 specialists + their status
GET  /api/team/research        → latest research brief per specialist
GET  /api/team/recommendations → pending + recent recommendations
GET  /api/team/active          → currently active approved gates
POST /api/team/approve/{id}    → approve a pending recommendation
POST /api/team/reject/{id}     → reject a pending recommendation
POST /api/team/run             → manually trigger a team cycle (dev)
POST /api/team/chat            → send message to a specialist, get reply
GET  /api/team/chat/{spec}     → chat history for a specialist
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/roster")
async def api_team_roster():
    """Return all 10 specialists with their phase, title, and latest signal."""
    import app_state
    import team_engine as te

    roster = []
    db = app_state.db

    for name, info in te.SPECIALISTS.items():
        latest = None
        if db is not None:
            try:
                doc = await db.team_research.find_one(
                    {"specialist": name},
                    sort=[("created_at", -1)]
                )
                if doc:
                    latest = {
                        "signal":     doc.get("signal"),
                        "confidence": doc.get("confidence"),
                        "brief":      doc.get("brief"),
                        "has_rec":    doc.get("has_rec", False),
                        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                    }
            except Exception:
                pass

        roster.append({
            "name":    name,
            "title":   info.get("title", ""),
            "emoji":   info.get("emoji", "•"),
            "color":   info.get("color", "#ffffff"),
            "phase":   info.get("phase", 1),
            "active":  True,
            "latest":  latest,
        })

    active_count = sum(1 for s in roster if s["latest"] is not None)
    return {"specialists": roster, "phase": 2, "active_count": active_count}


@router.get("/research")
async def api_team_research(limit: int = 3):
    """Latest research brief per specialist (one per specialist)."""
    import app_state
    db = app_state.db
    if db is None:
        return {"research": []}

    pipeline = [
        {"$sort":  {"created_at": -1}},
        {"$group": {"_id": "$specialist", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "specialist": 1, "signal": 1, "confidence": 1,
                      "brief": 1, "observations": 1, "has_rec": 1, "rec_type": 1,
                      "error": 1, "created_at": 1}},
    ]
    docs = await db.team_research.aggregate(pipeline).to_list(10)
    for d in docs:
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
    return {"research": docs}


@router.get("/recommendations")
async def api_team_recommendations(status: str = "all", limit: int = 20):
    """Pending, approved, rejected, and expired recommendations."""
    import app_state
    db = app_state.db
    if db is None:
        return {"recommendations": []}

    query = {}
    if status != "all":
        query["status"] = status

    docs = await db.team_recommendations.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    for d in docs:
        for field in ("created_at", "expires_at", "approved_at", "rejected_at", "active_until"):
            if isinstance(d.get(field), datetime):
                d[field] = d[field].isoformat()

    return {"recommendations": docs}


@router.get("/active")
async def api_team_active():
    """Currently active approved gates."""
    import app_state
    db = app_state.db
    if db is None:
        return {"active": []}

    now  = datetime.now(timezone.utc)
    docs = await db.team_recommendations.find(
        {"status": "approved", "active_until": {"$gt": now}},
        {"_id": 0}
    ).to_list(20)

    for d in docs:
        for field in ("created_at", "expires_at", "approved_at", "active_until"):
            if isinstance(d.get(field), datetime):
                d[field] = d[field].isoformat()
        # Add time remaining
        if d.get("active_until"):
            try:
                au = datetime.fromisoformat(d["active_until"].replace("Z", "+00:00"))
                d["hours_remaining"] = round((au - now).total_seconds() / 3600, 1)
            except Exception:
                pass

    return {"active": docs, "count": len(docs)}


@router.post("/approve/{rec_id}")
async def api_approve_recommendation(rec_id: str):
    """Approve a pending recommendation — activates the gate."""
    import team_engine as te
    result = await te.approve_recommendation(rec_id)
    if result.get("error"):
        return {"success": False, "error": result["error"]}

    # Telegram confirmation
    try:
        from paper_trading import _notify
        name  = result.get("specialist", "TEAM")
        until = result.get("active_until", "")
        await _notify(
            f"✅ Approved — {name} recommendation active\n"
            f"Type: {result.get('type','')}\n"
            f"Active until: {until[:16].replace('T',' ')} UTC"
        )
    except Exception:
        pass

    return result


@router.post("/reject/{rec_id}")
async def api_reject_recommendation(rec_id: str):
    """Reject a pending recommendation."""
    import team_engine as te
    result = await te.reject_recommendation(rec_id)
    return result


@router.post("/run")
async def api_team_run():
    """Manually trigger a full team cycle immediately."""
    import team_engine as te
    import asyncio
    asyncio.create_task(te.run_now())
    return {"message": "Team cycle triggered — all 10 specialists running now"}


@router.get("/stats")
async def api_team_stats():
    """Recommendation track record — how often each specialist was right."""
    import app_state
    db = app_state.db
    if db is None:
        return {"stats": {}}

    pipeline = [
        {"$group": {
            "_id":      "$specialist",
            "total":    {"$sum": 1},
            "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}},
            "rejected": {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}},
            "pending":  {"$sum": {"$cond": [{"$eq": ["$status", "pending"]},  1, 0]}},
        }},
    ]
    docs = await db.team_recommendations.aggregate(pipeline).to_list(20)
    return {"stats": {d["_id"]: {k: v for k, v in d.items() if k != "_id"} for d in docs}}


# ── Team Chat ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    specialist: str
    message: str
    thread_id: Optional[str] = None


def _load_specialist_persona(name: str) -> str:
    """Load PERSONA string from the team module."""
    try:
        import importlib
        mod = importlib.import_module(f"team.{name.lower()}")
        return getattr(mod, "PERSONA", "")
    except Exception:
        return ""


async def _get_market_context(db) -> str:
    """Fetch current market snapshot for specialist context."""
    lines = []
    try:
        doc = await db["current_market_regime"].find_one({"_id": "live"})
        if doc:
            lines.append(f"Market regime: {doc.get('regime','?')} | Trend: {doc.get('trend_regime','?')}")
            lines.append(f"BTC dominance: {doc.get('btc_dominance','?')} | Fear/Greed: {doc.get('fear_greed_index','?')}")
    except Exception:
        pass
    try:
        nc = await db["nexus_config"].find_one({"_id": "live"})
        if nc:
            lines.append(f"NEXUS regime: {nc.get('regime','?')} | Position modifier: {nc.get('position_modifier',1.0)}")
    except Exception:
        pass
    try:
        from market_intelligence import get_market_intel
        mi = get_market_intel()
        if mi:
            ticker = await mi.get_ticker("BTC/USDT")
            if ticker:
                lines.append(f"BTC price: ${ticker.get('last','?'):,}")
    except Exception:
        pass
    return "\n".join(lines) if lines else "Market data temporarily unavailable."


@router.post("/chat")
async def api_team_chat(req: ChatRequest):
    """Send a message to a specialist and get a reply from Claude."""
    import app_state
    import anthropic as _anthropic_lib
    import team_engine as te

    db = app_state.db
    name = req.specialist.upper()
    if name not in te.SPECIALISTS:
        return {"error": f"Unknown specialist: {name}"}

    spec_info = te.SPECIALISTS[name]
    persona   = _load_specialist_persona(name) or spec_info.get("persona", f"AEON's {spec_info.get('title','specialist')}.")

    # Load latest research for context
    research_ctx = ""
    if db is not None:
        try:
            doc = await db.team_research.find_one({"specialist": name}, sort=[("created_at", -1)])
            if doc:
                research_ctx = (
                    f"\nYour latest analysis:\n"
                    f"  Signal: {doc.get('signal','?')} | Confidence: {doc.get('confidence','?')}%\n"
                    f"  Brief: {doc.get('brief','')}\n"
                )
                obs = doc.get("observations", [])
                if obs:
                    research_ctx += "  Findings:\n" + "\n".join(f"    • {o}" for o in obs[:5])
        except Exception:
            pass

    # Market context
    market_ctx = ""
    if db is not None:
        try:
            market_ctx = "\nCurrent market snapshot:\n" + await _get_market_context(db)
        except Exception:
            pass

    # Load prior messages for thread continuity (last 8)
    prior_messages = []
    if db is not None and req.thread_id:
        try:
            history = await db.team_chat.find(
                {"thread_id": req.thread_id},
                {"_id": 0, "role": 1, "content": 1}
            ).sort("ts", 1).limit(8).to_list(8)
            prior_messages = [{"role": m["role"], "content": m["content"]} for m in history]
        except Exception:
            pass

    system_prompt = (
        f"You are {name}, {persona}\n\n"
        "You are part of the AEON Research Team — a group of 10 specialist AI analysts "
        "working with Carlos, the operator and creator of AEON, a crypto paper-trading AI system. "
        "Carlos built you and trusts you. You know him well.\n\n"
        "Your role:\n"
        "- Be warm, direct, and genuinely helpful — like a trusted colleague.\n"
        "- Stay completely in character. Speak through the lens of your specialty.\n"
        "- Reference your current analysis when relevant.\n"
        "- Be concise (2–4 sentences) unless Carlos needs more depth.\n"
        "- Never say 'As an AI' — you are a specialist, not a language model.\n"
        "- You have access to AEON's live data, gate pipeline, and trading performance.\n\n"
        f"{research_ctx}"
        f"{market_ctx}"
    )

    messages = prior_messages + [{"role": "user", "content": req.message}]

    try:
        client  = _anthropic_lib.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        resp    = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system_prompt,
            messages=messages,
        )
        reply = resp.content[0].text.strip()
    except Exception as e:
        logger.error(f"[TEAM CHAT] Claude call failed: {e}")
        return {"error": "Claude unavailable right now. Try again in a moment."}

    # Generate a stable thread_id if not provided
    thread_id = req.thread_id or f"{name.lower()}_{int(datetime.now(timezone.utc).timestamp())}"

    # Persist both turns
    now = datetime.now(timezone.utc)
    if db is not None:
        try:
            await db.team_chat.insert_many([
                {"thread_id": thread_id, "specialist": name, "role": "user",      "content": req.message, "ts": now},
                {"thread_id": thread_id, "specialist": name, "role": "assistant",  "content": reply,       "ts": now},
            ])
        except Exception as e:
            logger.debug(f"[TEAM CHAT] Persist failed: {e}")

    return {
        "reply":       reply,
        "specialist":  name,
        "thread_id":   thread_id,
        "ts":          now.isoformat(),
    }


@router.get("/chat/{specialist}")
async def api_team_chat_history(specialist: str, limit: int = 40):
    """Chat history for a given specialist (latest first, then reversed for display)."""
    import app_state
    db = app_state.db
    if db is None:
        return {"messages": []}

    name = specialist.upper()
    docs = await db.team_chat.find(
        {"specialist": name},
        {"_id": 0, "role": 1, "content": 1, "ts": 1, "thread_id": 1}
    ).sort("ts", -1).limit(limit).to_list(limit)

    docs.reverse()
    for d in docs:
        if hasattr(d.get("ts"), "isoformat"):
            d["ts"] = d["ts"].isoformat()

    return {"messages": docs, "specialist": name}
