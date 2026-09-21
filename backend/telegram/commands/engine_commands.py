"""
Engine Management Command Handlers
Commands: /engines, /engine <name> on|off, /governance
Reflects the real 9-engine AEON roster with live governance data.
"""
import inspect
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Real engine roster — IDs match EngineType values in aeon_engine_system.py
REAL_ENGINES = [
    {"id": "autonomous_trader_v2",  "name": "Autonomous Trader V2",  "emoji": "🤖", "state_attr": "autonomous_trader_v2"},
    {"id": "free_will_v2",          "name": "Free Will V2",          "emoji": "🧠", "state_attr": "free_will_v2"},
    {"id": "dual_engine",           "name": "Dual Engine",           "emoji": "⚡", "state_attr": "dual_engine"},
    {"id": "yolo_engine",           "name": "YOLO Engine",           "emoji": "🚀", "state_attr": "yolo_engine"},
    {"id": "vwap_scalper",          "name": "VWAP Scalper",          "emoji": "📊", "state_attr": "vwap_scalper"},
    {"id": "elite_strategy",        "name": "Elite Strategy V3",     "emoji": "🎯", "state_attr": None},
    {"id": "institutional_scalper", "name": "Institutional Scalper", "emoji": "🏛️", "state_attr": "inst_scalper"},
    {"id": "tcn_neural",            "name": "TCN Neural (E9)",       "emoji": "🔮", "state_attr": "tcn_engine"},
    {"id": "quant_analyzer",        "name": "Quant Analyzer",        "emoji": "🔬", "state_attr": "quant_analyzer"},
]

_GOV_EMOJI = {
    "promote_candidate": "⬆️",
    "monitor":           "👁️",
    "restricted":        "⚠️",
    "sandbox_only":      "🧪",
    "disable_candidate": "🛑",
    "insufficient_data": "📉",
}


def _get_engine_obj(engine):
    import app_state
    attr = engine.get("state_attr")
    if not attr:
        return None
    return getattr(app_state, attr, None)


def _is_active(engine):
    obj = _get_engine_obj(engine)
    if obj is None:
        return None
    return getattr(obj, "active", None)


async def _persist_engine_state(engine, obj):
    save_settings = getattr(obj, "save_settings", None)
    if callable(save_settings):
        result = save_settings()
        if inspect.isawaitable(result):
            await result
        return "persisted"

    # Some engines currently expose runtime flags only. Keep the toggle, but
    # make it explicit to operators that this one is session-scoped.
    return "session_only"


async def _get_governance_map(db):
    if db is None:
        return {}
    try:
        docs = await db.engine_governance.find(
            {},
            {"_id": 0, "engine": 1, "recommendation": 1, "current_tier": 1,
             "current_score": 1, "consecutive_d_weeks": 1}
        ).to_list(length=50)
        return {d["engine"]: d for d in docs}
    except Exception:
        return {}


async def handle_engines_list(text, chat_id, context):
    import app_state
    try:
        gov_map = await _get_governance_map(app_state.db)
        lines = ["🔧 AEON ENGINES (9)", ""]
        for eng in REAL_ENGINES:
            active = _is_active(eng)
            if active is True:
                status = "🟢"
            elif active is False:
                status = "🔴"
            else:
                status = "⚫"
            gov = gov_map.get(eng["id"], {})
            rec = gov.get("recommendation", "")
            tier = gov.get("current_tier", "")
            score = gov.get("current_score")
            gov_part = ""
            if rec:
                rec_emoji = _GOV_EMOJI.get(rec, "❓")
                gov_part = " | {} {}".format(rec_emoji, rec.replace("_", " "))
                if tier and tier not in ("insufficient_data", ""):
                    gov_part += " [{}]".format(tier)
                    if score is not None:
                        gov_part += " {:.0f}".format(score)
            lines.append("{} {} {}{}".format(status, eng["emoji"], eng["name"], gov_part))
        lines.extend(["", "Toggle: /engine <name> on|off", "Governance: /governance"])
        return "\n".join(lines), "engines"
    except Exception as e:
        logger.error("engines list error: %s", e)
        return "❌ Error: {}".format(str(e)), "engines"


async def handle_engine_command(text, chat_id, context):
    parts = text.lower().split()
    if len(parts) < 2:
        return await handle_engines_list(text, chat_id, context)

    name_frag = parts[1]
    match = next((e for e in REAL_ENGINES if name_frag in e["id"]), None)
    if not match:
        valid = ", ".join(e["id"] for e in REAL_ENGINES)
        return "❌ Unknown engine: {}\n\nValid names:\n{}".format(name_frag, valid), "engines"

    if len(parts) == 2:
        import app_state
        active = _is_active(match)
        gov_map = await _get_governance_map(app_state.db)
        gov = gov_map.get(match["id"], {})
        lines = [
            "{} {} {}".format("🟢" if active else ("🔴" if active is False else "⚫"), match["emoji"], match["name"]),
            "Status: {}".format("active" if active else ("inactive" if active is False else "unknown")),
        ]
        if gov:
            rec = gov.get("recommendation", "n/a")
            tier = gov.get("current_tier", "n/a")
            score = gov.get("current_score") or 0
            d_weeks = gov.get("consecutive_d_weeks", 0)
            lines.extend([
                "Governance: {} [{}] score {:.1f}".format(rec, tier, score),
                "D-weeks: {}".format(d_weeks),
            ])
        lines.append("\nToggle: /engine {} on|off".format(match["id"]))
        return "\n".join(lines), "engines"

    action = parts[2] if len(parts) > 2 else ""
    if action not in ("on", "off"):
        return "❓ Use: /engine <name> on|off", "engines"

    enabled = action == "on"
    obj = _get_engine_obj(match)
    if obj is None:
        return "❌ {} cannot be toggled via Telegram (no state handle).".format(match["name"]), "engines"
    try:
        obj.active = enabled
        icon = "🟢" if enabled else "🔴"
        state = "ON" if enabled else "OFF"
        persist_state = await _persist_engine_state(match, obj)
        if persist_state == "persisted":
            return "{} {} is now {} and persisted.".format(icon, match["name"], state), "engines"
        return "{} {} is now {} for this session only.".format(icon, match["name"], state), "engines"
    except Exception as e:
        return "❌ Toggle failed: {}".format(str(e)), "engines"


async def handle_governance(text, chat_id, context):
    import app_state
    try:
        if app_state.db is None:
            return "❌ DB not ready", "engines"
        gov_map = await _get_governance_map(app_state.db)
        if not gov_map:
            return "📋 GOVERNANCE\n\nNo governance data yet. Runs weekly after sufficient trade volume.", "engines"
        lines = ["📋 ENGINE GOVERNANCE", ""]
        for eng in REAL_ENGINES:
            gov = gov_map.get(eng["id"])
            if not gov:
                lines.append("⚫ {} — no data".format(eng["name"]))
                continue
            rec = gov.get("recommendation", "n/a")
            tier = gov.get("current_tier", "?")
            score = gov.get("current_score") or 0
            d_weeks = gov.get("consecutive_d_weeks", 0)
            rec_emoji = _GOV_EMOJI.get(rec, "❓")
            line = "{} {} — {} [{}] {:.0f}".format(rec_emoji, eng["name"], rec.replace("_", " "), tier, score)
            if d_weeks > 0:
                line += " | D×{}".format(d_weeks)
            lines.append(line)
        return "\n".join(lines), "engines"
    except Exception as e:
        logger.error("governance error: %s", e)
        return "❌ Error: {}".format(str(e)), "engines"


async def handle_engines_compare(text, chat_id, context):
    """Legacy compare from engine_snapshots."""
    import app_state
    try:
        db = app_state.db
        if db is None:
            return "❌ Database not available", "engines"
        latest = await db.engine_snapshots.find_one(sort=[("timestamp", -1)])
        if not latest:
            return "📊 No engine snapshot data yet.", "engines"
        engines = latest.get("engines", {})
        ts = latest.get("timestamp")
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_min = int((datetime.now(timezone.utc) - ts).total_seconds() // 60) if ts else 0
        engine_display = {
            "autonomous_v2":   "🤖 Autonomous V2",
            "free_will_v2":    "🧠 Free Will V2",
            "dual_day_trader": "⚡ Day Trader",
            "dual_long_term":  "🏦 Long Term",
            "elite_v3":        "🎯 Elite V3",
            "vwap_scalper":    "📊 VWAP Scalper",
            "yolo":            "🚀 YOLO",
        }
        response = "📊 ENGINE SNAPSHOT ({}m ago)\n\n".format(age_min)
        for engine_id, display_name in engine_display.items():
            stats = engines.get(engine_id)
            if not stats or "error" in stats:
                continue
            active = stats.get("active", False)
            win_rate = stats.get("win_rate")
            total = (stats.get("total_trades") or stats.get("total_alerts")
                     or stats.get("total_signals") or 0)
            pnl = stats.get("total_pnl_pct")
            status = "🟢" if active else "🔴"
            response += "{} {}\n".format(status, display_name)
            if win_rate is not None:
                response += "   WR: {}%  Trades: {}".format(win_rate, total)
            else:
                response += "   Signals today: {}  Total: {}".format(
                    stats.get("daily_alerts") or 0, total)
            if pnl is not None:
                sign = "+" if pnl >= 0 else ""
                response += "  PnL: {}{:.1f}%".format(sign, pnl)
            response += "\n\n"
        response += "/engines — Full engine list\n/governance — Governance states"
        return response, "engines"
    except Exception as e:
        logger.error("engines compare error: %s", e)
        return "❌ Error: {}".format(str(e)), "engines"


ENGINE_HANDLERS = {
    '/engines':    handle_engines_list,
    '/engines compare': handle_engines_compare,
    '/engine':     handle_engine_command,
    '/governance': handle_governance,
    '/gov':        handle_governance,
}


async def route_engine_command(text, chat_id, context):
    text_lower = text.lower().strip()
    if text_lower == '/engines compare':
        return await handle_engines_compare(text, chat_id, context)
    if text_lower in ('/engines', '/engine'):
        return await handle_engines_list(text, chat_id, context)
    if text_lower.startswith('/engine '):
        return await handle_engine_command(text, chat_id, context)
    if text_lower in ('/governance', '/gov'):
        return await handle_governance(text, chat_id, context)
    if text_lower.startswith('/engine_coins'):
        return await handle_engine_coins(text, chat_id, context)
    return None, None


async def handle_engine_coins(text: str, chat_id: int, context: dict) -> tuple:
    """
    /engine_coins {engine} {action} {coin}

    Actions:
    view       → show current coins
    add {coin} → add coin to engine
    remove {coin} → remove coin from engine
    reset      → reset to default top 20
    all        → show all engines
    """
    from engine_coin_config import get_coin_config

    config = get_coin_config()
    if not config:
        return "❌ Config not initialized", None

    parts = text.strip().split()

    if len(parts) < 2 or parts[1] == "all":
        # Show all engines
        all_status = await config.get_all_status()
        msg = "📊 **ENGINE COIN CONFIG**\n\n"
        for engine, status in all_status.items():
            msg += f"🔧 {engine}\n"
            msg += f"   Coins: {status['count']} "
            msg += "✅ (default)" if status['is_default'] else "⚙️ (custom)"
            coin_names = [c.split('/')[0] for c in status['coins'][:5]]
            msg += f"\n   {', '.join(coin_names)}"
            if status['count'] > 5:
                msg += f", +{status['count']-5} more\n\n"
            else:
                msg += "\n\n"
        return msg, None

    engine = parts[1]
    action = parts[2] if len(parts) > 2 else "view"
    coin = parts[3] if len(parts) > 3 else None

    if action == "view":
        status = await config.get_status(engine)
        msg = f"📊 **{engine}**\n\n"
        msg += f"Coins ({status['count']}):\n"
        coins_str = ", ".join([c.split("/")[0] for c in status['coins']])
        msg += f"`{coins_str}`\n\n"
        msg += f"Status: {'✅ Default (top 20)' if status['is_default'] else '⚙️ Custom'}"
        return msg, None

    elif action == "add" and coin:
        if not coin.endswith("/USDT"):
            coin = f"{coin}/USDT"
        success = await config.add_coin(engine, coin)
        if success:
            status = await config.get_status(engine)
            return f"✅ Added {coin} to {engine}\nTotal coins: {status['count']}", None
        else:
            return f"⚠️ {coin} already in {engine}", None

    elif action == "remove" and coin:
        if not coin.endswith("/USDT"):
            coin = f"{coin}/USDT"
        success = await config.remove_coin(engine, coin)
        if success:
            status = await config.get_status(engine)
            return f"✅ Removed {coin} from {engine}\nTotal coins: {status['count']}", None
        else:
            return f"❌ {coin} not in {engine}", None

    elif action == "reset":
        await config.reset_to_default(engine)
        return f"🔄 {engine} reset to default top 20 coins", None

    else:
        msg = """
Usage:
/engine_coins autonomous_trader view
/engine_coins free_will_v2 add NEAR
/engine_coins yolo_engine remove SUI
/engine_coins elite_strategy reset
/engine_coins all
        """.strip()
        return msg, None
