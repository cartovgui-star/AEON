"""
Free Will Engine v2 Telegram Commands
Commands: /fw, /fw scan, /fw on/off, /fw stats
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_fw_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /fw — full Free Will engine status"""
    import app_state

    try:
        engine = app_state.free_will_v2
        if not engine:
            return "Free Will Engine not initialized.", "fw"

        stats = await engine.get_stats()

        daily_used = stats.get("daily_alerts", 0)
        daily_max  = stats.get("max_daily_alerts", 20)
        remaining  = daily_max - daily_used

        recent_dirs = stats.get("recent_directions", {})
        dir_lines = ""
        for sym, d in list(recent_dirs.items())[:5]:
            arrow = "LONG" if d == "LONG" else "SHORT"
            dir_lines += f"  {sym.replace('/USDT','')}: {arrow}\n"
        if not dir_lines:
            dir_lines = "  No recent direction locks\n"

        response = f"""FREE WILL ENGINE v2

Status: {"ACTIVE" if stats.get("active") else "PAUSED"}
Strategy: Proactive 24/7 scanning — alerts WITHOUT being asked

CONFIGURATION
Min Confidence: {stats.get("min_confidence", 75)}%
Min Confirmations: {stats.get("min_confirmations", 3)}
Alert Cooldown: {stats.get("alert_cooldown_mins", 30)} min per symbol
Direction Lock: {stats.get("direction_lock_hours", 4)}h (no flip-flopping)
Pairs Monitored: {stats.get("pairs_monitored", 0)}
Timeframes: {", ".join(stats.get("timeframes", []))}

TODAY'S ACTIVITY
Alerts Sent: {daily_used}/{daily_max} ({remaining} remaining)
Setups Analyzed: {stats.get("setups_analyzed", 0)}
Contradictions Blocked: {stats.get("contradictions_blocked", 0)}
Total Alerts All-Time: {stats.get("total_alerts_sent", 0)}

RECENT DIRECTION LOCKS
{dir_lines}
DATA SOURCES
{chr(10).join("  - " + s for s in stats.get("data_sources", []))}

Commands:
/fw scan — run immediate full scan
/fw stats — performance breakdown
/fw on — resume scanning
/fw off — pause engine"""

        return response, "fw"

    except Exception as e:
        logger.error(f"handle_fw_status error: {e}", exc_info=True)
        return f"Error: {str(e)}", "fw"


async def handle_fw_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /fw scan — trigger immediate Free Will scan"""
    import app_state

    try:
        engine = app_state.free_will_v2
        if not engine:
            return "Free Will Engine not initialized.", "fw"

        if not engine.active:
            return "Engine is paused. Use /fw on to restart.", "fw"

        signals = await engine.scan_all()

        if not signals:
            stats = await engine.get_stats()
            return f"""FREE WILL SCAN — NOTHING FOUND

No high-confidence setups at this moment.

The engine looks for:
- RSI divergence + market structure
- VWAP confirmation
- CVD order flow alignment
- Options/derivatives confirmation (BTC/ETH)
- Fear & Greed context

Setups analyzed today: {stats.get("setups_analyzed", 0)}
Daily alerts used: {stats.get("daily_alerts", 0)}/{stats.get("max_daily_alerts", 20)}

Scans run continuously. Alerts sent automatically when criteria met.""", "fw"

        response = f"FREE WILL SCAN — {len(signals)} SIGNAL(S)\n\n"

        for sig in signals[:5]:
            direction = sig.get("direction", "?")
            symbol    = sig.get("symbol", "?").replace("/USDT", "")
            conf      = sig.get("confidence", 0)
            tf        = sig.get("timeframe", "?")
            entry     = sig.get("entry_price", 0)
            sl        = sig.get("stop_price", 0)
            tp        = sig.get("target_price", 0)
            confs     = sig.get("confirmations", [])

            response += f"""{direction}  {symbol}  ({tf})
Confidence: {conf}%
Entry: ${entry:,.4f}
SL: ${sl:,.4f}   TP: ${tp:,.4f}
Confirmations: {", ".join(confs[:3])}

"""

        if len(signals) > 5:
            response += f"... and {len(signals) - 5} more signal(s)"

        return response, "fw"

    except Exception as e:
        logger.error(f"handle_fw_scan error: {e}", exc_info=True)
        return f"Scan error: {str(e)}", "fw"


async def handle_fw_stats(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /fw stats — performance from MongoDB"""
    import app_state
    from datetime import datetime, timedelta, timezone

    try:
        engine = app_state.free_will_v2
        if not engine:
            return "Free Will Engine not initialized.", "fw"

        db = app_state.db
        if db is None:
            return "Database not available.", "fw"

        since = datetime.now(timezone.utc) - timedelta(days=7)

        pipeline = [
            {"$match": {"engine": "free_will_v2", "closed_at": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total":  {"$sum": 1},
                "wins":   {"$sum": {"$cond": [{"$gt": ["$pnl_pct", 0]}, 1, 0]}},
                "pnl":    {"$sum": "$pnl_pct"},
                "best":   {"$max": "$pnl_pct"},
                "worst":  {"$min": "$pnl_pct"},
            }},
        ]

        results = await db["paper_trades"].aggregate(pipeline).to_list(1)
        row = results[0] if results else {}

        total = row.get("total", 0)
        wins  = row.get("wins", 0)
        wr    = (wins / total * 100) if total > 0 else 0

        live_stats = await engine.get_stats()

        response = f"""FREE WILL ENGINE — 7-DAY STATS

SIGNAL PERFORMANCE (paper trades)
Trades: {total}
Win Rate: {wr:.1f}% ({wins} wins / {total - wins} losses)
Total PnL: {row.get("pnl", 0):+.2f}%
Best Trade: {row.get("best", 0):+.2f}%
Worst Trade: {row.get("worst", 0):+.2f}%

ENGINE ACTIVITY
Setups Analyzed: {live_stats.get("setups_analyzed", 0)}
Alerts Sent: {live_stats.get("total_alerts_sent", 0)}
Contradictions Blocked: {live_stats.get("contradictions_blocked", 0)}
Daily Alerts Today: {live_stats.get("daily_alerts", 0)}/{live_stats.get("max_daily_alerts", 20)}"""

        return response, "fw"

    except Exception as e:
        logger.error(f"handle_fw_stats error: {e}", exc_info=True)
        return f"Error: {str(e)}", "fw"


async def handle_fw_toggle(
    text: str, chat_id: int, context: dict, enabled: bool
) -> Tuple[str, str]:
    """Handle /fw on and /fw off"""
    import app_state

    try:
        engine = app_state.free_will_v2
        if not engine:
            return "Free Will Engine not initialized.", "fw"

        engine.active = enabled

        if enabled:
            return """FREE WILL ENGINE ENABLED

Now scanning 24/7 across all monitored pairs.
Alerts fire automatically when confidence and confirmations are met.
No manual trigger needed — it watches the market for you.

Use /fw to see status.""", "fw"
        else:
            return """FREE WILL ENGINE PAUSED

Proactive scanning stopped.
No new alerts will be sent until re-enabled.
Existing direction locks remain in memory.

Use /fw on to resume.""", "fw"

    except Exception as e:
        logger.error(f"handle_fw_toggle error: {e}", exc_info=True)
        return f"Error: {str(e)}", "fw"


async def route_fw_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route /fw and /freewill commands"""
    text_lower = text.lower().strip()

    if text_lower in ("/fw", "/freewill"):
        return await handle_fw_status(text, chat_id, context)
    elif text_lower in ("/fw scan", "/freewill scan"):
        return await handle_fw_scan(text, chat_id, context)
    elif text_lower in ("/fw stats", "/freewill stats"):
        return await handle_fw_stats(text, chat_id, context)
    elif text_lower in ("/fw on", "/freewill on"):
        return await handle_fw_toggle(text, chat_id, context, enabled=True)
    elif text_lower in ("/fw off", "/freewill off"):
        return await handle_fw_toggle(text, chat_id, context, enabled=False)

    return None
