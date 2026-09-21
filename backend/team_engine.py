"""
AEON Research Team Engine
All 10 specialists. Runs at 6:00, 12:45, and 19:00 in your configured timezone.
Set TEAM_TIMEZONE in .env (e.g. America/New_York, America/Chicago, Europe/London).
Manual trigger available via /team_run (Telegram) or POST /api/team/run.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import anthropic

from team.base import AnalysisResult, make_rec_doc, make_research_doc

logger = logging.getLogger(__name__)

# ── Schedule config ───────────────────────────────────────────────────────────
# Three fixed times per day. Change TEAM_TIMEZONE in .env for your local time.
SCHEDULE_TIMES = [(6, 0), (12, 45), (19, 0)]   # (hour, minute)
TEAM_TIMEZONE  = os.getenv("TEAM_TIMEZONE", "America/New_York")
VIEWS_CACHE_TTL = 300     # seconds between refreshing active gates from DB

def _next_run_seconds() -> float:
    """Return seconds until the next scheduled team cycle."""
    try:
        tz = ZoneInfo(TEAM_TIMEZONE)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
        logger.warning(f"[TEAM] Unknown timezone '{TEAM_TIMEZONE}', falling back to UTC")

    now = datetime.now(tz)
    candidates = []
    for hour, minute in SCHEDULE_TIMES:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            candidates.append(candidate)

    if not candidates:
        # All times passed today — next is tomorrow's first slot
        tomorrow_first = (now + timedelta(days=1)).replace(
            hour=SCHEDULE_TIMES[0][0], minute=SCHEDULE_TIMES[0][1], second=0, microsecond=0
        )
        candidates.append(tomorrow_first)

    next_run = min(candidates)
    secs     = (next_run - now).total_seconds()
    logger.info(
        f"[TEAM] Next cycle at {next_run.strftime('%H:%M')} {TEAM_TIMEZONE} "
        f"({secs/3600:.1f}h from now)"
    )
    return max(secs, 60)

# ── Roster — Phase 1 active, rest stubbed ────────────────────────────────────
SPECIALISTS = {
    "SIGMA": {
        "title":   "Quantitative Mathematician",
        "persona": "AEON's Quantitative Mathematician. Speaks in Kelly fractions, z-scores, and expected values.",
        "phase":   1,
        "color":   "#60a5fa",   # blue
        "emoji":   "Σ",
    },
    "VEGA": {
        "title":   "On-Chain Analyst",
        "persona": "AEON's On-Chain Analyst. Reads blockchain flows, whale movements, exchange inflows.",
        "phase":   1,
        "color":   "#34d399",   # green
        "emoji":   "⛓",
    },
    "ZETA": {
        "title":   "Derivatives Desk",
        "persona": "AEON's Derivatives Specialist. Funding rates, OI, L/S ratios, liq clusters.",
        "phase":   1,
        "color":   "#f97316",   # orange
        "emoji":   "∂",
    },
    # Phase 2 — all now active
    "NOVA":    {"title": "Data Scientist",    "phase": 2, "color": "#a78bfa", "emoji": "✦"},
    "MAXWELL": {"title": "Physicist",         "phase": 2, "color": "#fb7185", "emoji": "∇"},
    "KEPLER":  {"title": "Cycle Analyst",     "phase": 2, "color": "#fbbf24", "emoji": "⊙"},
    "DANTE":   {"title": "Technical Analyst", "phase": 2, "color": "#e879f9", "emoji": "◈"},
    "ECHO":    {"title": "Sentiment Analyst", "phase": 2, "color": "#22d3ee", "emoji": "◎"},
    "ATLAS":   {"title": "Macro Economist",   "phase": 2, "color": "#94a3b8", "emoji": "⊕"},
    "AEGIS":   {"title": "Risk Manager",      "phase": 2, "color": "#f43f5e", "emoji": "⊛",
                "note": "Personal account only"},
}

# ── In-memory active gate cache ───────────────────────────────────────────────
_active_views: List[Dict] = []
_last_views_refresh: float = 0.0

# ── Module-level references (set by init) ─────────────────────────────────────
_db             = None
_market_intel   = None
_coinglass_intel = None
_anthropic      = None


def init_team_engine(db, market_intel=None, coinglass_intel=None):
    global _db, _market_intel, _coinglass_intel, _anthropic
    _db              = db
    _market_intel    = market_intel
    _coinglass_intel = coinglass_intel
    _anthropic       = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    logger.info("[TEAM] Engine initialised — all 10 specialists active")


# ── Claude brief generation ───────────────────────────────────────────────────

async def _generate_brief(specialist: str, persona: str, analysis: AnalysisResult) -> str:
    """Generate a 2-sentence research brief in the specialist's voice using claude-haiku."""
    if _anthropic is None:
        return " | ".join(analysis.observations[:2])

    obs_text = "\n".join(f"• {o}" for o in analysis.observations[:5])
    rec_line = (
        f"\nRecommendation: {analysis.recommendation.reasoning}"
        if analysis.recommendation else ""
    )
    prompt = (
        f"You are {specialist}, {persona}\n\n"
        f"Current analysis (signal: {analysis.signal.value}, confidence: {analysis.confidence}/100):\n"
        f"{obs_text}{rec_line}\n\n"
        f"Write exactly 2 sentences as {specialist}. "
        "Stay completely in character. Be specific with numbers. "
        "No preamble, no 'As {specialist}', just speak."
    )
    try:
        msg = await _anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=160,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.warning(f"[TEAM] Claude brief failed for {specialist}: {e}")
        return " ".join(analysis.observations[:2]) if analysis.observations else "Analysis complete."


# ── Individual agent runners ──────────────────────────────────────────────────

async def _run_sigma():
    try:
        from team.sigma import analyze, PERSONA
        return await analyze(_db), PERSONA
    except Exception as e:
        logger.error(f"[SIGMA] Failed: {e}"); return None, ""

async def _run_vega():
    try:
        from team.vega import analyze, PERSONA
        return await analyze(_db, _market_intel), PERSONA
    except Exception as e:
        logger.error(f"[VEGA] Failed: {e}"); return None, ""

async def _run_zeta():
    try:
        from team.zeta import analyze, PERSONA
        return await analyze(_db, _market_intel, _coinglass_intel), PERSONA
    except Exception as e:
        logger.error(f"[ZETA] Failed: {e}"); return None, ""

async def _run_nova():
    try:
        from team.nova import analyze, PERSONA
        return await analyze(_db), PERSONA
    except Exception as e:
        logger.error(f"[NOVA] Failed: {e}"); return None, ""

async def _run_maxwell():
    try:
        from team.maxwell import analyze, PERSONA
        return await analyze(_db, _market_intel), PERSONA
    except Exception as e:
        logger.error(f"[MAXWELL] Failed: {e}"); return None, ""

async def _run_kepler():
    try:
        from team.kepler import analyze, PERSONA
        return await analyze(_db, _market_intel), PERSONA
    except Exception as e:
        logger.error(f"[KEPLER] Failed: {e}"); return None, ""

async def _run_dante():
    try:
        from team.dante import analyze, PERSONA
        return await analyze(_db, _market_intel), PERSONA
    except Exception as e:
        logger.error(f"[DANTE] Failed: {e}"); return None, ""

async def _run_echo():
    try:
        from team.echo import analyze, PERSONA
        return await analyze(_db, _market_intel), PERSONA
    except Exception as e:
        logger.error(f"[ECHO] Failed: {e}"); return None, ""

async def _run_atlas():
    try:
        from team.atlas import analyze, PERSONA
        return await analyze(_db, _market_intel), PERSONA
    except Exception as e:
        logger.error(f"[ATLAS] Failed: {e}"); return None, ""

async def _run_aegis():
    try:
        from team.aegis import analyze, PERSONA
        return await analyze(_db), PERSONA
    except Exception as e:
        logger.error(f"[AEGIS] Failed: {e}"); return None, ""


# ── Full cycle ────────────────────────────────────────────────────────────────

async def run_team_cycle():
    """Run all Phase 1 agents, generate briefs, store results, queue recommendations."""
    if _db is None:
        logger.warning("[TEAM] run_team_cycle called before init")
        return

    logger.info("[TEAM] ═══ Starting research cycle — all 10 specialists ═══")
    agents = [
        ("SIGMA",   _run_sigma),
        ("VEGA",    _run_vega),
        ("ZETA",    _run_zeta),
        ("NOVA",    _run_nova),
        ("MAXWELL", _run_maxwell),
        ("KEPLER",  _run_kepler),
        ("DANTE",   _run_dante),
        ("ECHO",    _run_echo),
        ("ATLAS",   _run_atlas),
        ("AEGIS",   _run_aegis),
    ]

    new_recs     = []
    all_results  = []   # (name, analysis, brief) — for consolidated Telegram

    for name, runner in agents:
        try:
            analysis, persona = await runner()
            if analysis is None:
                continue

            brief = await _generate_brief(name, persona, analysis)

            # Store research doc
            research_doc = make_research_doc(name, analysis, brief)
            await _db.team_research.insert_one(research_doc)

            all_results.append((name, analysis, brief))

            # Queue recommendation if present
            if analysis.recommendation:
                rec_doc = make_rec_doc(name, analysis, brief)
                await _db.team_recommendations.insert_one(rec_doc)
                new_recs.append((name, rec_doc))
                logger.info(f"[{name}] Recommendation queued: {rec_doc['type']} — {rec_doc['rec_id'][:8]}")

            logger.info(f"[{name}] {analysis.signal.value} ({analysis.confidence}%) — brief stored")

        except Exception as e:
            logger.error(f"[TEAM] Cycle error for {name}: {e}")

    # Send consolidated Telegram briefing from all specialists
    await _send_team_briefing(all_results, new_recs)

    logger.info(f"[TEAM] ═══ Cycle complete — {len(new_recs)} recommendation(s) pending ═══")


async def _send_team_briefing(results: List, new_recs: List):
    """
    Send one consolidated Telegram message with every specialist's signal + brief.
    Then send individual alerts for each recommendation.
    """
    if not results:
        return
    try:
        from paper_trading import _notify
        from datetime import datetime, timezone
        import zoneinfo

        tz_name  = os.getenv("TEAM_TIMEZONE", "America/Chicago")
        tz       = zoneinfo.ZoneInfo(tz_name)
        now_str  = datetime.now(tz).strftime("%b %d · %I:%M %p %Z")

        # Signal emoji map
        sig_emoji = {
            "BULLISH":  "🟢",
            "BEARISH":  "🔴",
            "NEUTRAL":  "⚪",
            "VOLATILE": "🟡",
            "CAUTION":  "🟠",
        }

        lines = [f"🧠 AEON RESEARCH DESK  {now_str}\n"]

        for name, analysis, brief in results:
            info  = SPECIALISTS.get(name, {})
            emoji = info.get("emoji", "•")
            sig   = analysis.signal.value
            conf  = analysis.confidence
            se    = sig_emoji.get(sig, "⚪")
            # Trim brief to ~120 chars for Telegram readability
            short_brief = (brief[:118] + "…") if len(brief) > 120 else brief
            lines.append(f"{se} {emoji} {name} · {conf}%")
            lines.append(f"   {short_brief}")
            if analysis.recommendation:
                lines.append(f"   ⚠️ Recommendation pending")
            lines.append("")

        if new_recs:
            lines.append(f"⚠️ {len(new_recs)} recommendation(s) require your approval")
            lines.append("Use /team to view · /team_approve <id> to activate")

        await _notify("\n".join(lines))

    except Exception as e:
        logger.warning(f"[TEAM] Telegram briefing failed: {e}")

    # Also send individual alerts for recommendations
    if new_recs:
        await _notify_recommendations(new_recs)


async def _notify_recommendations(recs: List):
    """Send Telegram notification for pending recommendations."""
    try:
        from paper_trading import _notify
        for name, rec in recs:
            specialist_info = SPECIALISTS.get(name, {})
            emoji  = specialist_info.get("emoji", "•")
            type_  = rec["type"].replace("_", " ").title()
            params = rec["params"]
            sym    = params.get("symbol", "ALL")
            dur    = rec["duration_hours"]

            detail = ""
            if rec["type"] == "block_direction":
                detail = f"Block {params.get('direction','?')} on {sym}"
            elif rec["type"] == "avoid_symbol":
                detail = f"Avoid {sym} entirely"
            elif rec["type"] == "raise_confidence":
                detail = f"Min confidence → {params.get('min_confidence','?')}%"

            msg = (
                f"{emoji} TEAM RECOMMENDATION\n"
                f"{name} · {specialist_info.get('title','')}\n\n"
                f"Type: {type_}\n"
                f"Action: {detail}\n"
                f"Duration: {dur}h if approved\n\n"
                f"Reasoning:\n{rec['reasoning'][:200]}\n\n"
                f"ID: {rec['rec_id'][:12]}\n"
                f"Approve: /team_approve {rec['rec_id'][:12]}\n"
                f"Reject:  /team_reject {rec['rec_id'][:12]}"
            )
            await _notify(msg)
    except Exception as e:
        logger.warning(f"[TEAM] Telegram notify failed: {e}")


# ── Gate check (called by aeon_engine_system) ─────────────────────────────────

async def _refresh_active_views():
    """Reload active approved recommendations from DB into memory cache."""
    global _active_views, _last_views_refresh
    if _db is None:
        return
    try:
        now = datetime.now(timezone.utc)
        views = await _db.team_recommendations.find(
            {"status": "approved", "active_until": {"$gt": now}}
        ).to_list(50)
        _active_views = [{k: v for k, v in v.items() if k != "_id"} for v in views]
        _last_views_refresh = time.time()
    except Exception as e:
        logger.debug(f"[TEAM] Active views refresh failed: {e}")


async def check_team_gate(signal: Dict, engine: str) -> Dict:
    """
    Called from submit_signal_gated() before executing a trade.
    Returns {"blocked": True, "specialist": name, "reason": str} or {"blocked": False}.
    No sizing changes — only blocks signals.

    Two-tier gate:
      Tier 1 — Auto-CAUTION: SIGMA or AEGIS at ≥85% CAUTION → raise confidence
               requirement to 85% without needing manual approval. These two
               specialists have access to system-level data (quant math, risk) and
               their high-confidence CAUTION is structurally meaningful.
      Tier 2 — Approved recommendations: manually-approved blocks from any specialist.
    """
    global _active_views, _last_views_refresh

    if time.time() - _last_views_refresh > VIEWS_CACHE_TTL:
        await _refresh_active_views()

    # ── Tier 1: Auto-CAUTION from SIGMA / AEGIS ───────────────────────────────
    if _db is not None:
        try:
            AUTO_CAUTION_SPECIALISTS = {"SIGMA", "AEGIS"}
            AUTO_CAUTION_MIN_CONF   = 85   # specialist confidence threshold to auto-apply
            AUTO_CAUTION_TRADE_CONF = 85   # minimum trade confidence required to pass
            sig_conf = float(signal.get("confidence", 80))

            for spec_name in AUTO_CAUTION_SPECIALISTS:
                latest = await _db.team_research.find_one(
                    {"specialist": spec_name},
                    sort=[("created_at", -1)]
                )
                if latest and latest.get("signal") == "CAUTION":
                    spec_conf = int(latest.get("confidence", 0))
                    if spec_conf >= AUTO_CAUTION_MIN_CONF and sig_conf < AUTO_CAUTION_TRADE_CONF:
                        reason_text = latest.get("brief", "High-confidence caution signal")
                        logger.info(
                            f"🔬 [TEAM AUTO-CAUTION] {spec_name} at {spec_conf}% CAUTION — "
                            f"blocking signal with confidence {sig_conf:.0f}% < {AUTO_CAUTION_TRADE_CONF}%"
                        )
                        return {
                            "blocked":    True,
                            "specialist": spec_name,
                            "reason": (
                                f"{spec_name} (auto-caution {spec_conf}%): "
                                f"trade confidence {sig_conf:.0f}% < {AUTO_CAUTION_TRADE_CONF}% required. "
                                f"{reason_text[:100]}"
                            ),
                        }
        except Exception as _ac_err:
            logger.debug(f"[TEAM AUTO-CAUTION] skipped: {_ac_err}")

    if not _active_views:
        return {"blocked": False}

    sym       = signal.get("symbol", "")
    direction = str(signal.get("direction", "")).upper()
    conf      = float(signal.get("confidence", 80))

    for view in _active_views:
        vtype  = view.get("type")
        params = view.get("params", {})
        name   = view.get("specialist", "TEAM")

        if vtype == "block_direction":
            v_sym = params.get("symbol")        # None = all symbols
            v_dir = params.get("direction", "").upper()
            if (v_sym is None or v_sym == sym) and v_dir == direction:
                return {
                    "blocked":    True,
                    "specialist": name,
                    "reason":     (
                        f"{name} has an active block on {direction} "
                        f"{'(all symbols)' if not v_sym else sym} — "
                        f"{view.get('reasoning', '')[:120]}"
                    ),
                }

        elif vtype == "avoid_symbol":
            v_sym = params.get("symbol")
            if v_sym and v_sym == sym:
                return {
                    "blocked":    True,
                    "specialist": name,
                    "reason":     f"{name} recommends avoiding {sym}: {view.get('reasoning','')[:120]}",
                }

        elif vtype == "raise_confidence":
            v_sym      = params.get("symbol")
            v_min_conf = float(params.get("min_confidence", 80))
            if (v_sym is None or v_sym == sym) and conf < v_min_conf:
                return {
                    "blocked":    True,
                    "specialist": name,
                    "reason":     (
                        f"{name} requires confidence ≥ {v_min_conf:.0f}% "
                        f"(signal has {conf:.0f}%)"
                    ),
                }

    return {"blocked": False}


# ── Approval / Rejection ─────────────────────────────────────────────────────

async def approve_recommendation(rec_id: str) -> Dict:
    """Mark a recommendation as approved and set it active."""
    if _db is None:
        return {"error": "Team engine not initialised"}

    rec = await _db.team_recommendations.find_one(
        {"rec_id": {"$regex": f"^{rec_id}"}, "status": "pending"}
    )
    if not rec:
        return {"error": f"No pending recommendation matching '{rec_id}'"}

    dur   = rec.get("duration_hours", 4)
    until = datetime.now(timezone.utc) + timedelta(hours=dur)
    await _db.team_recommendations.update_one(
        {"_id": rec["_id"]},
        {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc),
                  "active_until": until}},
    )
    # Force immediate cache refresh
    global _last_views_refresh
    _last_views_refresh = 0.0

    specialist = rec.get("specialist", "TEAM")
    logger.info(f"[TEAM] ✅ {specialist} recommendation {rec_id[:12]} APPROVED — active for {dur}h")
    return {"success": True, "specialist": specialist, "active_until": until.isoformat(),
            "type": rec.get("type"), "params": rec.get("params")}


async def reject_recommendation(rec_id: str) -> Dict:
    """Mark a recommendation as rejected."""
    if _db is None:
        return {"error": "Team engine not initialised"}

    result = await _db.team_recommendations.update_one(
        {"rec_id": {"$regex": f"^{rec_id}"}, "status": "pending"},
        {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        return {"error": f"No pending recommendation matching '{rec_id}'"}

    logger.info(f"[TEAM] ❌ Recommendation {rec_id[:12]} REJECTED")
    return {"success": True}


# ── Background loop ───────────────────────────────────────────────────────────

async def run_loop(_cycle_hours: int = 2):
    """
    Background task — runs at scheduled times (6:00, 12:45, 19:00 in TEAM_TIMEZONE).
    Short boot delay so server fully initialises before first cycle.
    """
    logger.info(
        f"[TEAM] Scheduler started — runs at 06:00, 12:45, 19:00 ({TEAM_TIMEZONE})"
    )
    await asyncio.sleep(90)   # wait 90s after boot
    while True:
        secs = _next_run_seconds()
        await asyncio.sleep(secs)
        try:
            await run_team_cycle()
        except Exception as e:
            logger.error(f"[TEAM] Cycle error: {e}")


async def run_now():
    """Manual trigger — fires a full cycle immediately."""
    logger.info("[TEAM] ⚡ Manual trigger — running cycle now")
    await run_team_cycle()
