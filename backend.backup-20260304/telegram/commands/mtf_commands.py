"""
MTF Confluence & Scalper Command Handlers
Commands: /mtf, /confluence, /scalper, /scalp
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def handle_mtf_scan(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /mtf command - scan all for MTF confluence"""
    from aggressive_scalper import scalper
    
    try:
        result = await scalper.scan_mtf_confluence(min_confluence=2)
        summary = result.get("summary", {})
        best = result.get("best_setup")
        
        response = f"""📊 MTF CONFLUENCE ANALYSIS

Scanned: {summary.get('scanned_symbols', 15)} symbols across 5m/15m/30m

🎯 STRONG (3/3): {summary.get('strong_setups', 0)} setups
📈 MODERATE (2/3): {summary.get('moderate_setups', 0)} setups
📊 Actionable: {summary.get('total_actionable', 0)} total

"""
        if best:
            symbol = best.get('symbol', '').replace('/USDT', '')
            direction = best.get('consensus_direction', 'N/A')
            conf = best.get('weighted_confidence', 0)
            level = best.get('confluence_level', 'N/A')
            
            response += f"""🏆 BEST SETUP: {symbol}
• Direction: {'🟢 LONG' if direction == 'LONG' else '🔴 SHORT' if direction == 'SHORT' else '⚪ ' + direction}
• Confluence: {level} ({best.get('confluence_count', 'N/A')})
• Confidence: {conf}%
• {best.get('recommendation', '')}

"""
        # Show strong setups
        strong = result.get("strong_confluence", [])[:3]
        if strong:
            response += "🎯 STRONG SETUPS:\n"
            for s in strong:
                sym = s.get('symbol', '').replace('/USDT', '')
                dir_emoji = '🟢' if s.get('consensus_direction') == 'LONG' else '🔴'
                response += f"• {sym} {dir_emoji} {s.get('consensus_direction')} ({s.get('weighted_confidence', 0)}%)\n"
        else:
            response += "No strong setups right now.\n"
        
        response += "\nTrade STRONG (3/3) with larger size, MODERATE (2/3) with standard size."
        
    except Exception as e:
        logger.error(f"MTF confluence error: {e}")
        response = "❌ Error scanning MTF confluence. Try again."
    
    return response, "scalper"


async def handle_mtf_symbol(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /mtf <symbol> command - analyze specific symbol"""
    from aggressive_scalper import scalper
    
    parts = text.lower().split()
    if len(parts) >= 2:
        symbol = parts[1].upper()
        try:
            result = await scalper.analyze_mtf_confluence(symbol)
            
            direction = result.get('consensus_direction', 'NEUTRAL')
            level = result.get('confluence_level', 'NONE')
            conf = result.get('weighted_confidence', 0)
            
            dir_emoji = '🟢' if direction == 'LONG' else '🔴' if direction == 'SHORT' else '⚪'
            level_emoji = '🎯' if level == 'STRONG' else '📈' if level == 'MODERATE' else '📊' if level == 'WEAK' else '⚫'
            
            response = f"""{level_emoji} MTF CONFLUENCE: {symbol}

Direction: {dir_emoji} {direction}
Confluence: {level} ({result.get('confluence_count', 'N/A')})
Confidence: {conf}%

📊 BY TIMEFRAME:"""
            
            for tf, data in result.get('timeframes', {}).items():
                signal = data.get('signal', 0)
                strength = data.get('strength', 0)
                reason = data.get('reason', 'No signal')
                
                if signal == 1:
                    response += f"\n• {tf}: 🟢 BUY (str:{strength}) - {reason}"
                elif signal == -1:
                    response += f"\n• {tf}: 🔴 SELL (str:{strength}) - {reason}"
                else:
                    response += f"\n• {tf}: ⚪ HOLD"
            
            response += f"\n\n💡 {result.get('recommendation', 'Analyze further before trading.')}"
            
        except Exception as e:
            response = f"❌ Error analyzing {symbol}: {str(e)}"
    else:
        response = "Usage: /mtf BTC"
    
    return response, "scalper"


async def handle_scalper_status(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /scalper command - show scalper status"""
    from aggressive_scalper import scalper
    from scalper_learning import auto_learner, v2_integration
    
    settings = scalper.get_settings()
    learning = await scalper.get_learning_status()
    v2_status = await scalper.get_v2_integration_status()
    
    response = f"""⚡ AGGRESSIVE SCALPER

Status: {'🟢 ACTIVE' if settings.get('enabled', True) else '🔴 PAUSED'}

⚙️ SETTINGS
• Profit Target: {settings.get('profit_target', 0.8)}%
• Stop Loss: {settings.get('stop_loss', 0.4)}%
• Volume Threshold: {settings.get('volume_threshold', 1.5)}x
• RSI Range: {settings.get('rsi_oversold', 30)}-{settings.get('rsi_overbought', 70)}

🧠 AUTO-LEARNING
• Status: {'ON' if learning.get('auto_learn_enabled') else 'OFF'}
• Optimizations: {learning.get('optimizations_run', 0)}

🔗 V2.1 INTEGRATION
• Status: {'CONNECTED' if v2_status.get('enabled') else 'DISABLED'}
• Queued Signals: {v2_status.get('queued_count', 0)}

Scalper runs alongside V2.1 with auto-learning!"""
    
    return response, "scalper"


# Export handlers
MTF_HANDLERS = {
    '/mtf': handle_mtf_scan,
    '/confluence': handle_mtf_scan,
    '/scalper': handle_scalper_status,
    '/scalp': handle_scalper_status,
}

# Handler for /mtf with symbol argument
async def route_mtf_command(text: str, chat_id: int, context: dict) -> tuple:
    """Route MTF commands based on arguments"""
    text_lower = text.lower().strip()
    
    if text_lower == '/mtf' or text_lower == '/confluence':
        return await handle_mtf_scan(text, chat_id, context)
    elif text_lower.startswith('/mtf '):
        return await handle_mtf_symbol(text, chat_id, context)
    elif text_lower == '/scalper' or text_lower == '/scalp':
        return await handle_scalper_status(text, chat_id, context)
    
    return None, None
