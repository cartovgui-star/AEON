"""
Dual Trading Engine Telegram Commands
Commands: /dual, /dual scan, /dual on/off, /dual day, /dual longterm
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def _sub_engine_block(label: str, s: dict) -> str:
    """Format a single sub-engine stats block."""
    total  = s.get("total_signals", 0)
    alerts = s.get("daily_alerts", 0)
    max_a  = s.get("max_daily_alerts", 10)
    conf   = s.get("min_confidence", 80)
    tf     = s.get("timeframe", "?")
    style  = s.get("trade_style", "?")

    return (
        f"{label}\n"
        f"  Timeframe: {tf}   Style: {style}\n"
        f"  Min Confidence: {conf}%\n"
        f"  Signals (all-time): {total}\n"
        f"  Today: {alerts}/{max_a} alerts\n"
    )


async def handle_dual_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /dual — Dual Trading Engine status"""
    import app_state

    try:
        engine = app_state.dual_engine
        if not engine:
            return "Dual Trading Engine not initialized.", "dual"

        stats = engine.get_stats()
        dt    = stats.get("day_trader", {})
        lt    = stats.get("long_term", {})

        response = f"""DUAL TRADING ENGINE

Status: {"ACTIVE" if stats.get("active") else "PAUSED"}
Total Alerts Sent: {stats.get("total_alerts_sent", 0)}

Two independent sub-engines running different timeframes:

{_sub_engine_block("DAY TRADER (aggressive, short-term)", dt)}
{_sub_engine_block("LONG TERM (patient, structural setups)", lt)}

Commands:
/dual scan — scan both engines now
/dual day — Day Trader status + scan
/dual longterm — Long Term status + scan
/dual on — enable both
/dual off — pause both"""

        return response, "dual"

    except Exception as e:
        logger.error(f"handle_dual_status error: {e}", exc_info=True)
        return f"Error: {str(e)}", "dual"


async def handle_dual_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /dual scan — scan both sub-engines"""
    import app_state

    try:
        engine = app_state.dual_engine
        if not engine:
            return "Dual Trading Engine not initialized.", "dual"

        if not engine.active:
            return "Engine is paused. Use /dual on to restart.", "dual"

        results = await engine.scan_all_styles()
        day_sigs = results.get("day_trader", [])
        lt_sigs  = results.get("long_term", [])

        if not day_sigs and not lt_sigs:
            return """DUAL SCAN — NO SIGNALS

Neither sub-engine found a qualifying setup right now.

Day Trader needs: short-term momentum + tight R:R
Long Term needs: structural support/resistance + high confluence

Both engines block LONGs in bearish regimes and SHORTs in bullish regimes.""", "dual"

        response = f"DUAL SCAN — {len(day_sigs) + len(lt_sigs)} TOTAL SIGNAL(S)\n\n"

        if day_sigs:
            response += f"DAY TRADER ({len(day_sigs)} signal(s))\n"
            for sig in day_sigs[:3]:
                direction = sig.get("direction", "?")
                symbol    = sig.get("symbol", "?").replace("/USDT", "")
                conf      = sig.get("confidence", 0)
                entry     = sig.get("entry_price", 0)
                sl        = sig.get("stop_price", 0)
                tp        = sig.get("target_price", 0)
                reasons   = sig.get("long_reasons" if direction == "LONG" else "short_reasons", [])
                response += f"""  {direction}  {symbol}  {conf}%
  Entry: ${entry:,.4f}  SL: ${sl:,.4f}  TP: ${tp:,.4f}
  {", ".join(reasons[:2])}

"""

        if lt_sigs:
            response += f"LONG TERM ({len(lt_sigs)} signal(s))\n"
            for sig in lt_sigs[:3]:
                direction = sig.get("direction", "?")
                symbol    = sig.get("symbol", "?").replace("/USDT", "")
                conf      = sig.get("confidence", 0)
                entry     = sig.get("entry_price", 0)
                sl        = sig.get("stop_price", 0)
                tp        = sig.get("target_price", 0)
                reasons   = sig.get("long_reasons" if direction == "LONG" else "short_reasons", [])
                response += f"""  {direction}  {symbol}  {conf}%
  Entry: ${entry:,.4f}  SL: ${sl:,.4f}  TP: ${tp:,.4f}
  {", ".join(reasons[:2])}

"""

        return response, "dual"

    except Exception as e:
        logger.error(f"handle_dual_scan error: {e}", exc_info=True)
        return f"Scan error: {str(e)}", "dual"


async def _sub_scan(engine_attr: str, label: str, context_tag: str) -> Tuple[str, str]:
    """Helper — scan a single sub-engine and format results."""
    import app_state

    engine = app_state.dual_engine
    if not engine:
        return "Dual Trading Engine not initialized.", context_tag

    sub = getattr(engine, engine_attr, None)
    if not sub:
        return f"{label} sub-engine not found.", context_tag

    stats = sub.get_stats()
    signals = await sub.scan_all()

    header = (
        f"{label}\n"
        f"Status: {'ACTIVE' if engine.active else 'PAUSED'}\n"
        f"Confidence: {stats.get('min_confidence', 80)}%  "
        f"TF: {stats.get('timeframe', '?')}  "
        f"Style: {stats.get('trade_style', '?')}\n"
        f"Today: {stats.get('daily_alerts', 0)}/{stats.get('max_daily_alerts', 10)} alerts\n\n"
    )

    if not signals:
        return header + "No signals right now.", context_tag

    body = f"{len(signals)} signal(s) found:\n\n"
    for sig in signals[:4]:
        direction = sig.get("direction", "?")
        symbol    = sig.get("symbol", "?").replace("/USDT", "")
        conf      = sig.get("confidence", 0)
        entry     = sig.get("entry_price", 0)
        sl        = sig.get("stop_price", 0)
        tp        = sig.get("target_price", 0)
        body += f"{direction}  {symbol}  {conf}%\nEntry: ${entry:,.4f}  SL: ${sl:,.4f}  TP: ${tp:,.4f}\n\n"

    return header + body, context_tag


async def handle_dual_day(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /dual day — Day Trader sub-engine deep dive"""
    return await _sub_scan("day_trader", "DAY TRADER ENGINE", "dual")


async def handle_dual_longterm(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /dual longterm — Long Term sub-engine deep dive"""
    return await _sub_scan("long_term", "LONG TERM ENGINE", "dual")


async def handle_dual_toggle(
    text: str, chat_id: int, context: dict, enabled: bool
) -> Tuple[str, str]:
    """Handle /dual on and /dual off"""
    import app_state

    try:
        engine = app_state.dual_engine
        if not engine:
            return "Dual Trading Engine not initialized.", "dual"

        engine.active = enabled
        # Also toggle both sub-engines
        if hasattr(engine, "day_trader"):
            engine.day_trader.active = enabled
        if hasattr(engine, "long_term"):
            engine.long_term.active = enabled

        if enabled:
            return """DUAL TRADING ENGINE ENABLED

Both sub-engines are now active:
- Day Trader: scanning for momentum plays
- Long Term: scanning for structural setups

Alerts fire automatically when criteria are met.
Use /dual scan to check right now.""", "dual"
        else:
            return """DUAL TRADING ENGINE PAUSED

Day Trader and Long Term engines stopped.
No new alerts from either sub-engine.

Use /dual on to resume both.""", "dual"

    except Exception as e:
        logger.error(f"handle_dual_toggle error: {e}", exc_info=True)
        return f"Error: {str(e)}", "dual"


async def route_dual_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route /dual commands"""
    text_lower = text.lower().strip()

    if text_lower == "/dual":
        return await handle_dual_status(text, chat_id, context)
    elif text_lower == "/dual scan":
        return await handle_dual_scan(text, chat_id, context)
    elif text_lower == "/dual day":
        return await handle_dual_day(text, chat_id, context)
    elif text_lower in ("/dual longterm", "/dual long"):
        return await handle_dual_longterm(text, chat_id, context)
    elif text_lower == "/dual on":
        return await handle_dual_toggle(text, chat_id, context, enabled=True)
    elif text_lower == "/dual off":
        return await handle_dual_toggle(text, chat_id, context, enabled=False)

    return None
