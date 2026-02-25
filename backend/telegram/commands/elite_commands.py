"""
Elite Strategy v3 Command Handlers
Commands: /elite, /elite scan, /elite <symbol>, /elite on/off
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_elite_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /elite or /elite status command"""
    try:
        from elite_strategy_v3 import get_elite_strategy
        import app_state
        
        elite = get_elite_strategy(
            app_state.state.advanced_strategies,
            app_state.state.smc_analyzer,
            app_state.state.enhanced_intel
        )
        stats = elite.get_stats()
        settings = stats.get("settings", {})
        
        response = f"""🎯 ELITE STRATEGY v3

Status: {'🟢 ACTIVE' if stats.get('enabled') else '🔴 PAUSED'}

📊 STATISTICS
• Signals Generated: {stats.get('signals_generated', 0)}
• Signals Filtered: {stats.get('signals_filtered', 0)}
• Daily Trades: {stats.get('daily_trades', 0)}/{stats.get('max_daily_trades', 3)}

⚙️ SETTINGS (Ultra-Selective)
• Min Confidence: {settings.get('min_confidence', 92)}%
• Min R:R Ratio: {settings.get('min_rr_ratio', 2.5)}:1
• Min Volume: {settings.get('min_volume_ratio', 2.0)}x
• Min ADX: {settings.get('min_adx', 28)}
• BTC Alignment: {'Required' if settings.get('require_btc_alignment') else 'Optional'}
• MTF Confluence: {'Required' if settings.get('require_mtf_confluence') else 'Optional'}

🎯 Target: 60%+ Win Rate

Commands:
• /elite scan - Scan for elite signals
• /elite BTC - Analyze specific symbol
• /elite on/off - Toggle strategy"""
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "elite"


async def handle_elite_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /elite scan command"""
    try:
        from elite_strategy_v3 import get_elite_strategy
        from state import state
        
        elite = get_elite_strategy(
            state.advanced_strategies,
            state.smc_analyzer,
            state.enhanced_intel
        )
        signals = await elite.scan_all_elite()
        
        if signals:
            response = f"🎯 ELITE SIGNALS FOUND: {len(signals)}\n\n"
            for sig in signals[:5]:
                symbol = sig.get('symbol', '').replace('/USDT', '')
                direction = sig.get('direction', 'N/A')
                conf = sig.get('confidence', 0)
                rr = sig.get('rr_ratio', 0)
                mtf = sig.get('mtf_confluence', '0/3')
                
                dir_emoji = '🟢' if direction == 'LONG' else '🔴'
                response += f"""{dir_emoji} {symbol} {direction}
• Confidence: {conf}%
• R:R: {rr}:1
• MTF: {mtf}
• Entry: ${sig.get('entry_price', 0):,.2f}
• Stop: ${sig.get('stop_price', 0):,.2f}
• Target: ${sig.get('target_price', 0):,.2f}

"""
        else:
            stats = elite.get_stats()
            top_filters = list(stats.get('filter_reasons', {}).items())[:3]
            response = "🎯 No elite signals right now.\n\n"
            response += "Top filter reasons:\n"
            for reason, count in top_filters:
                response += f"• {reason}: {count}\n"
            response += "\nElite Strategy is ultra-selective for high win rate."
    except Exception as e:
        response = f"❌ Error scanning: {str(e)}"
    
    return response, "elite"


async def handle_elite_analyze(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /elite <symbol> command"""
    parts = text.lower().split()
    if len(parts) < 2:
        return await handle_elite_status(text, chat_id, context)
    
    symbol = parts[1].upper()
    
    try:
        from elite_strategy_v3 import get_elite_strategy
        from state import state
        
        elite = get_elite_strategy(
            state.advanced_strategies,
            state.smc_analyzer,
            state.enhanced_intel
        )
        signal = await elite.analyze_elite_signal(symbol + "/USDT", "4h")
        
        if signal:
            dir_emoji = '🟢' if signal.get('direction') == 'LONG' else '🔴'
            response = f"""🎯 ELITE SIGNAL: {symbol}

{dir_emoji} {signal.get('direction')} | Confidence: {signal.get('confidence')}%

📊 ANALYSIS
• R:R Ratio: {signal.get('rr_ratio')}:1
• MTF Confluence: {signal.get('mtf_confluence')}
• BTC Trend: {signal.get('btc_trend')}
• Volume: {signal.get('volume_ratio', 0):.1f}x
• ADX: {signal.get('adx', 0):.0f}

💰 TRADE SETUP
• Entry: ${signal.get('entry_price', 0):,.2f}
• Stop: ${signal.get('stop_price', 0):,.2f}
• Target: ${signal.get('target_price', 0):,.2f}

✅ CONFIRMATIONS:
"""
            for conf in signal.get('confirmations', [])[:5]:
                response += f"• {conf}\n"
        else:
            stats = elite.get_stats()
            response = f"❌ No elite signal for {symbol}\n\n"
            response += "Recent filter reasons:\n"
            for reason, count in list(stats.get('filter_reasons', {}).items())[:5]:
                response += f"• {reason}: {count}\n"
    except Exception as e:
        response = f"❌ Error analyzing {symbol}: {str(e)}"
    
    return response, "elite"


async def handle_elite_toggle(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /elite on/off command"""
    parts = text.lower().split()
    enabled = parts[1] == 'on' if len(parts) > 1 else True
    
    try:
        from elite_strategy_v3 import get_elite_strategy
        from state import state
        
        elite = get_elite_strategy(
            state.advanced_strategies,
            state.smc_analyzer,
            state.enhanced_intel
        )
        elite.enabled = enabled
        
        if enabled:
            response = "🟢 Elite Strategy v3 ENABLED\n\nUltra-selective mode for 60%+ win rate."
        else:
            response = "🔴 Elite Strategy v3 DISABLED"
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "elite"


# Export handlers
ELITE_HANDLERS = {
    '/elite': handle_elite_status,
    '/elite status': handle_elite_status,
    '/elite scan': handle_elite_scan,
    '/elite on': handle_elite_toggle,
    '/elite off': handle_elite_toggle,
}


async def route_elite_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route elite strategy commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/elite' or text_lower == '/elite status':
        return await handle_elite_status(text, chat_id, context)
    elif text_lower == '/elite scan':
        return await handle_elite_scan(text, chat_id, context)
    elif text_lower == '/elite on':
        return await handle_elite_toggle(text, chat_id, context)
    elif text_lower == '/elite off':
        return await handle_elite_toggle(text, chat_id, context)
    elif text_lower.startswith('/elite '):
        # Check if it's a symbol analysis
        parts = text_lower.split()
        if len(parts) >= 2 and parts[1] not in ['on', 'off', 'scan', 'status']:
            return await handle_elite_analyze(text, chat_id, context)
    
    return None
