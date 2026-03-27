"""
YOLO Engine Telegram Commands
Commands: /yolo, /yolo scan, /yolo on/off
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_yolo_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /yolo command - show YOLO Engine status"""
    import app_state
    
    try:
        engine = app_state.yolo_engine
        if not engine:
            return "❌ YOLO Engine not initialized", "yolo"
        
        stats = engine.get_stats()
        s = stats["stats"]
        l = stats["limits"]
        f = stats["filters"]
        
        response = f"""🚀 YOLO ENGINE STATUS

Status: {'🟢 ACTIVE' if stats['active'] else '🔴 PAUSED'}

⚙️ SETTINGS (Independent Engine)
• Min Confidence: {stats['min_confidence']}%
• Confirmations: {stats['min_confirmations']}
• Leverage: {stats['leverage_range']}

🚫 FILTERS (ALL OFF)
• EMA: {'ON' if f['ema'] else 'OFF'}
• ADX: {'ON' if f['adx'] else 'OFF'}
• Volume: {'ON' if f['volume'] else 'OFF'}
• Session: {'ON' if f['session'] else 'OFF'}
• BTC Alignment: {'ON' if f['btc_alignment'] else 'OFF'}

📊 STATS
• Total Signals: {s['total_signals']}
• Today: {s['signals_today']}
• Trades Opened: {s['trades_opened']}
• Win Rate: {s['win_rate']}%

⚡ LIMITS
• Max Daily Signals: {l['max_daily_signals']}
• Max Open Trades: {l['max_open_trades']}
• Cooldown: {l['cooldown_seconds']}s

Commands:
• /yolo scan - Run immediate scan
• /yolo on/off - Toggle engine"""
        
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "yolo"


async def handle_yolo_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /yolo scan command"""
    import app_state
    
    try:
        engine = app_state.yolo_engine
        if not engine:
            return "❌ YOLO Engine not initialized", "yolo"
        
        signals = await engine.scan_markets()
        
        if not signals:
            return """🚀 YOLO SCAN COMPLETE

No signals at this moment.

YOLO accepts ANY signal above 50% confidence.
Markets may be ranging or waiting for entry.

Try again in a few minutes.""", "yolo"
        
        response = f"🚀 YOLO SCAN: {len(signals)} SIGNAL(S)\n\n"
        
        for sig in signals[:5]:
            emoji = "🟢" if sig["direction"] == "LONG" else "🔴"
            symbol = sig["symbol"].replace("/USDT", "")
            
            response += f"""{emoji} {symbol} {sig['direction']}
• Entry: ${sig['entry_price']:.4f}
• Leverage: {sig['leverage']}x
• Confidence: {sig['confidence']}%

"""
        
        return response, "yolo"
        
    except Exception as e:
        logger.error(f"YOLO scan error: {e}")
        return f"❌ Scan error: {str(e)}", "yolo"


async def handle_yolo_toggle(text: str, chat_id: int, context: dict, enabled: bool) -> Tuple[str, str]:
    """Handle /yolo on or /yolo off command"""
    import app_state
    
    try:
        engine = app_state.yolo_engine
        if not engine:
            return "❌ YOLO Engine not initialized", "yolo"
        
        engine.active = enabled
        
        if enabled:
            return """🚀 YOLO ENGINE ENABLED

Maximum aggression activated!
• 50% min confidence
• 1 confirmation only
• ALL filters OFF
• Up to 100x leverage

Scanning every 3 minutes...""", "yolo"
        else:
            return """🔴 YOLO ENGINE DISABLED

Aggressive trading paused.
Use /yolo on to restart.""", "yolo"
            
    except Exception as e:
        return f"❌ Error: {str(e)}", "yolo"


# Route YOLO commands
async def route_yolo_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route YOLO commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/yolo':
        return await handle_yolo_status(text, chat_id, context)
    elif text_lower == '/yolo scan':
        return await handle_yolo_scan(text, chat_id, context)
    elif text_lower == '/yolo on':
        return await handle_yolo_toggle(text, chat_id, context, enabled=True)
    elif text_lower == '/yolo off':
        return await handle_yolo_toggle(text, chat_id, context, enabled=False)
    
    return None
