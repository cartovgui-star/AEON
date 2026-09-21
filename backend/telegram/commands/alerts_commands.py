"""
Alert & Notification Telegram Commands
/alerts              — list active price alerts
/alert [sym] [price] — add alert
/alert remove [n]    — remove alert by number
"""
from typing import Tuple, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


async def handle_alerts_list(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /alerts command"""
    try:
        import app_state

        db = app_state.db
        if db is None:
            return "❌ Database not available", "alerts"

        alerts = await db.price_alerts.find(
            {"chat_id": chat_id, "active": True}
        ).to_list(length=50)

        if alerts:
            response = "🔔 YOUR PRICE ALERTS\n\n"
            for i, alert in enumerate(alerts, 1):
                symbol = (alert.get('symbol') or 'N/A').replace('/USDT', '')
                target = alert.get('target_price', 0) or 0
                direction = alert.get('direction', 'above')
                current = alert.get('current_price', 0) or 0
                emoji = "📈" if direction == 'above' else "📉"
                response += f"{i}. {emoji} {symbol} → ${target:,.2f}\n"
                response += f"   Current: ${current:,.2f} ({direction})\n\n"
            response += "Use /alert remove [number] to delete"
        else:
            response = """🔔 No active alerts.

To set an alert:
/alert BTC 70000 above
/alert ETH 3000 below

Alerts trigger when price crosses your target."""

    except Exception as e:
        logger.error(f"Alerts list error: {e}")
        response = f"❌ Error: {str(e)}"

    return response, "alerts"


async def handle_alert_add(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /alert [symbol] [price] [direction] command"""
    try:
        import app_state

        parts = text.split()
        if len(parts) < 3:
            return "Usage: /alert BTC 70000 [above/below]\nExample: /alert ETH 3000 below", "alerts"

        symbol = parts[1].upper()
        if not symbol.endswith('/USDT'):
            symbol = f"{symbol}/USDT"

        try:
            target_price = float(parts[2].replace(',', ''))
        except ValueError:
            return "❌ Invalid price format. Use: /alert BTC 70000", "alerts"

        direction = parts[3].lower() if len(parts) > 3 else 'above'
        if direction not in ('above', 'below'):
            direction = 'above'

        db = app_state.db
        if db is None:
            return "❌ Database not available", "alerts"

        # Get current price from OKX
        current_price = 0
        try:
            ticker = await app_state.market_intel.get_ticker(symbol)
            if ticker and "error" not in ticker:
                current_price = ticker.get('price', 0) or 0
        except Exception:
            pass

        alert = {
            "chat_id": chat_id,
            "symbol": symbol,
            "target_price": target_price,
            "direction": direction,
            "current_price": current_price,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "triggered": False,
        }

        await db.price_alerts.insert_one(alert)

        symbol_clean = symbol.replace('/USDT', '')
        emoji = "📈" if direction == 'above' else "📉"
        cross_word = "rises above" if direction == 'above' else "drops below"
        response = f"""✅ Alert Created!

{emoji} {symbol_clean}
Target: ${target_price:,.2f} ({direction})
Current: ${current_price:,.2f}

You'll be notified when price {cross_word} ${target_price:,.2f}"""

    except Exception as e:
        logger.error(f"Alert add error: {e}")
        response = f"❌ Error: {str(e)}"

    return response, "alerts"


async def handle_alert_remove(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /alert remove [number] command"""
    try:
        import app_state

        parts = text.split()
        if len(parts) < 3:
            return "Usage: /alert remove 1\nUse /alerts to see numbered list", "alerts"

        try:
            alert_num = int(parts[2])
        except ValueError:
            return "❌ Invalid alert number. Use: /alert remove 1", "alerts"

        db = app_state.db
        if db is None:
            return "❌ Database not available", "alerts"

        alerts = await db.price_alerts.find(
            {"chat_id": chat_id, "active": True}
        ).to_list(length=50)

        if alert_num < 1 or alert_num > len(alerts):
            return f"❌ Invalid alert number. You have {len(alerts)} alerts.", "alerts"

        alert = alerts[alert_num - 1]
        await db.price_alerts.update_one(
            {"_id": alert["_id"]},
            {"$set": {"active": False}}
        )

        symbol = (alert.get('symbol') or 'N/A').replace('/USDT', '')
        response = f"✅ Alert removed: {symbol} @ ${alert.get('target_price', 0):,.2f}"

    except Exception as e:
        logger.error(f"Alert remove error: {e}")
        response = f"❌ Error: {str(e)}"

    return response, "alerts"


ALERT_HANDLERS = {
    '/alerts':     handle_alerts_list,
    '/alert list': handle_alerts_list,
}


async def route_alert_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route alert commands"""
    text_lower = text.lower().strip()

    if text_lower in ('/alerts', '/alert list'):
        return await handle_alerts_list(text, chat_id, context)

    if text_lower.startswith('/alert remove'):
        return await handle_alert_remove(text, chat_id, context)

    if text_lower.startswith('/alert '):
        return await handle_alert_add(text, chat_id, context)

    return None
