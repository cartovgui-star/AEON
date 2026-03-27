"""
VWAP Scalper Command Handlers
Commands: /vwap, /vwap scan, /vwap on/off
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_vwap_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /vwap command - show VWAP Scalper status"""
    import app_state
    
    try:
        scalper = app_state.vwap_scalper
        if not scalper:
            return "❌ VWAP Scalper not initialized", "vwap"
        
        stats = scalper.get_stats()
        
        response = f"""🎯 VWAP SCALPER STATUS

Status: {'🟢 ACTIVE' if stats['active'] else '🔴 PAUSED'}

📊 STRATEGY
• VWAP + EMA Cross + RSI
• Timeframe: 5m candles
• Risk: 0.3% SL / 0.6% TP (2:1 R:R)

📈 PERFORMANCE
• Total Trades: {stats['total_trades']}
• Win Rate: {stats['win_rate']}%
• Signals Today: {stats['signals_today']}/{stats['max_signals_per_day']}

⚙️ PARAMETERS
• EMA Fast: {stats['parameters']['ema_fast']}
• EMA Slow: {stats['parameters']['ema_slow']}
• RSI Period: {stats['parameters']['rsi_period']}

📡 Data: MEXC ✅

Commands:
• /vwap scan - Run immediate scan
• /vwap on/off - Toggle scalper"""
        
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "vwap"


async def handle_vwap_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /vwap scan command - run immediate scan"""
    import app_state
    
    try:
        scalper = app_state.vwap_scalper
        if not scalper:
            return "❌ VWAP Scalper not initialized", "vwap"
        
        signals = await scalper.scan_all_symbols()
        
        if not signals:
            return """🎯 VWAP SCAN COMPLETE

No signals found at this moment.

The strategy looks for:
• EMA9 crossing EMA21
• Price vs VWAP alignment
• RSI in 50-70 (long) or 30-50 (short)

Try again in a few minutes.""", "vwap"
        
        response = f"🎯 VWAP SCAN: {len(signals)} SIGNAL(S) FOUND\n\n"
        
        for sig in signals[:5]:  # Max 5 signals
            emoji = "🟢" if sig["direction"] == "LONG" else "🔴"
            symbol = sig["symbol"].replace("/USDT", "")
            
            response += f"""{emoji} {symbol} {sig['direction']}
• Entry: ${sig['entry_price']:.4f}
• Confidence: {sig['confidence']}%
• RSI: {sig['indicators']['rsi']:.1f}
• Data: {sig.get('data_source', 'unknown').upper()}

"""
        
        return response, "vwap"
        
    except Exception as e:
        response = f"❌ Scan error: {str(e)}"
        logger.error(f"VWAP scan error: {e}")
    
    return response, "vwap"


async def handle_vwap_toggle(text: str, chat_id: int, context: dict, enabled: bool) -> Tuple[str, str]:
    """Handle /vwap on or /vwap off command"""
    import app_state
    
    try:
        scalper = app_state.vwap_scalper
        if not scalper:
            return "❌ VWAP Scalper not initialized", "vwap"
        
        scalper.active = enabled
        
        if enabled:
            return """🟢 VWAP SCALPER ENABLED

The scalper will now:
• Scan every 5 minutes
• Look for EMA crossovers
• Check VWAP alignment
• Filter with RSI

Signals will be sent as alerts!""", "vwap"
        else:
            return """🔴 VWAP SCALPER DISABLED

Scanning paused.
Use /vwap on to restart.""", "vwap"
            
    except Exception as e:
        return f"❌ Error: {str(e)}", "vwap"


async def handle_vwap_analyze(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /vwap <symbol> - analyze specific symbol"""
    import app_state
    
    parts = text.upper().split()
    if len(parts) < 2:
        return "Usage: /vwap BTC or /vwap ETH", "vwap"
    
    symbol = parts[1].replace("/USDT", "") + "/USDT"
    
    try:
        scalper = app_state.vwap_scalper
        if not scalper:
            return "❌ VWAP Scalper not initialized", "vwap"
        
        signal = await scalper.analyze_symbol(symbol)
        
        if not signal:
            return f"""🎯 {symbol.replace('/USDT', '')} VWAP ANALYSIS

No signal at this moment.

The price is either:
• Not crossing EMA
• Wrong side of VWAP
• RSI not in optimal zone

Try again later or check /vwap scan for all symbols.""", "vwap"
        
        return scalper.format_signal_alert(signal), "vwap"
        
    except Exception as e:
        return f"❌ Error analyzing {symbol}: {str(e)}", "vwap"


# Export handlers
VWAP_HANDLERS = {
    '/vwap': handle_vwap_status,
}


async def route_vwap_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route VWAP commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/vwap':
        return await handle_vwap_status(text, chat_id, context)
    elif text_lower == '/vwap scan':
        return await handle_vwap_scan(text, chat_id, context)
    elif text_lower == '/vwap on':
        return await handle_vwap_toggle(text, chat_id, context, enabled=True)
    elif text_lower == '/vwap off':
        return await handle_vwap_toggle(text, chat_id, context, enabled=False)
    elif text_lower.startswith('/vwap '):
        return await handle_vwap_analyze(text, chat_id, context)
    
    return None
