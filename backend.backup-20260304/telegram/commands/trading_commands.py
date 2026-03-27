"""
Trading Stats & Auto Trade Command Handlers
Commands: /stats, /auto, /autotrade, /riskcheck, /strategy, /accuracy, /leaderboard
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_stats(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /stats command"""
    import app_state
    from autonomous_trader_v2 import autonomous_trader_v2
    
    try:
        stats = await autonomous_trader_v2.get_stats()
        
        total = stats.get("total_trades", 0)
        wins = stats.get("winning_positions", 0)
        losses = stats.get("losing_positions", 0)
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        response = f"""📊 TRADING STATISTICS

📈 PERFORMANCE
• Total Trades: {total}
• Wins: {wins} | Losses: {losses}
• Win Rate: {win_rate:.1f}%

🔄 ACTIVE
• Status: {'🟢 ACTIVE' if stats.get('active') else '🔴 PAUSED'}
• Open Positions: {stats.get('open_positions', 0)}
• Signals Today: {stats.get('total_signals_analyzed', 0)}

⚙️ SETTINGS
• Min Confidence: {stats.get('min_confidence', 85)}%
• Min Confirmations: {stats.get('min_confirmations', 4)}"""
    except Exception as e:
        response = f"❌ Error getting stats: {str(e)}"
    
    return response, "trading"


async def handle_auto_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /auto, /autotrade command"""
    from autonomous_trader_v2 import autonomous_trader_v2
    
    try:
        stats = await autonomous_trader_v2.get_stats()
        
        response = f"""🤖 AUTONOMOUS TRADING

Status: {'🟢 ACTIVE' if stats.get('active') else '🔴 PAUSED'}

📊 TODAY
• Signals Analyzed: {stats.get('total_signals_analyzed', 0)}
• Trades Opened: {stats.get('today_trades', 0)}
• Open Positions: {stats.get('open_positions', 0)}

⚙️ CONFIGURATION
• Min Confidence: {stats.get('min_confidence', 85)}%
• Min Confirmations: {stats.get('min_confirmations', 4)}
• Max Open Trades: {stats.get('max_open_trades', 5)}

Commands:
• /auto on - Enable auto trading
• /auto off - Disable auto trading"""
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "trading"


async def handle_auto_toggle(text: str, chat_id: int, context: dict, enabled: bool) -> Tuple[str, str]:
    """Handle /auto on or /auto off command"""
    from autonomous_trader_v2 import autonomous_trader_v2
    
    try:
        autonomous_trader_v2.is_active = enabled
        
        if enabled:
            response = """🟢 AUTO TRADING ENABLED

The bot will now automatically:
• Scan for opportunities
• Open trades meeting criteria
• Manage positions

Stay tuned for trade alerts!"""
        else:
            response = """🔴 AUTO TRADING DISABLED

Auto trading is now paused.
Manual trades and alerts still work.

Re-enable: /auto on"""
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "trading"


async def handle_risk_check(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /riskcheck, /risk command"""
    from autonomous_trader_v2 import autonomous_trader_v2
    import app_state
    
    try:
        stats = await autonomous_trader_v2.get_stats()
        
        # Get market conditions
        fng = await app_state.market_intel.get_fear_greed()
        fng_value = fng.get("value", 50)
        
        # Risk assessment
        open_pos = stats.get("open_positions", 0)
        max_pos = stats.get("max_open_trades", 5)
        exposure = (open_pos / max_pos * 100) if max_pos > 0 else 0
        
        # Determine risk level
        if exposure > 80 or fng_value > 80 or fng_value < 20:
            risk_level = "🔴 HIGH"
            risk_advice = "Consider reducing exposure"
        elif exposure > 50 or fng_value > 70 or fng_value < 30:
            risk_level = "🟡 MEDIUM"
            risk_advice = "Monitor positions closely"
        else:
            risk_level = "🟢 LOW"
            risk_advice = "Conditions are favorable"
        
        response = f"""🛡️ RISK CHECK

Overall Risk: {risk_level}

📊 EXPOSURE
• Open Positions: {open_pos}/{max_pos}
• Exposure: {exposure:.0f}%

😱 MARKET SENTIMENT
• Fear & Greed: {fng_value}/100
• Status: {fng.get('classification', 'Neutral')}

💡 ADVICE
{risk_advice}"""
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "trading"


async def handle_strategy(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /strategy command"""
    from autonomous_trader_v2 import autonomous_trader_v2
    
    try:
        strategy = await autonomous_trader_v2.get_strategy_info()
        
        response = f"""⚙️ TRADING STRATEGY

📋 ACTIVE STRATEGY
• Name: {strategy.get('name', 'Default')}
• Type: {strategy.get('type', 'Trend Following')}

🎯 ENTRY CRITERIA
• Min Confidence: {strategy.get('min_confidence', 85)}%
• Min Confirmations: {strategy.get('min_confirmations', 4)}
• MTF Required: {strategy.get('mtf_required', True)}

📊 FILTERS
• 200 EMA: {'✅' if strategy.get('ema_200_filter') else '❌'}
• ADX: {'✅' if strategy.get('adx_filter') else '❌'}
• Volume: {'✅' if strategy.get('volume_filter') else '❌'}
• Session: {'✅' if strategy.get('session_filter') else '❌'}

💰 RISK MANAGEMENT
• R:R Ratio: {strategy.get('min_rr_ratio', 2.0)}:1
• Stop Loss: ATR-based
• Take Profit: Multiple targets"""
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "trading"


async def handle_accuracy(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /accuracy, /acc command"""
    import app_state
    
    try:
        # Get accuracy from database
        accuracy = await app_state.db.signal_accuracy.find_one({"type": "overall"})
        
        if accuracy:
            response = f"""🎯 SIGNAL ACCURACY

Overall: {accuracy.get('overall_accuracy', 0):.1f}%

By Timeframe:
• 5m: {accuracy.get('5m_accuracy', 0):.1f}%
• 15m: {accuracy.get('15m_accuracy', 0):.1f}%
• 1h: {accuracy.get('1h_accuracy', 0):.1f}%
• 4h: {accuracy.get('4h_accuracy', 0):.1f}%

By Direction:
• Long: {accuracy.get('long_accuracy', 0):.1f}%
• Short: {accuracy.get('short_accuracy', 0):.1f}%"""
        else:
            response = "📊 Not enough data for accuracy metrics yet."
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "trading"


async def handle_leaderboard(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /leaderboard, /lb command"""
    import app_state
    
    try:
        # Get coin performance leaderboard
        leaderboard = await app_state.db.coin_performance.find({}).sort("win_rate", -1).limit(10).to_list(10)
        
        response = "🏆 COIN LEADERBOARD (by win rate)\n\n"
        
        if leaderboard:
            for i, coin in enumerate(leaderboard, 1):
                symbol = coin.get("symbol", "???")
                win_rate = coin.get("win_rate", 0)
                trades = coin.get("total_trades", 0)
                response += f"{i}. {symbol}: {win_rate:.1f}% ({trades} trades)\n"
        else:
            response += "No performance data yet. Keep trading!"
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "trading"


# Export handlers
TRADING_HANDLERS = {
    '/stats': handle_stats,
    '/auto': handle_auto_status,
    '/autotrade': handle_auto_status,
    '/riskcheck': handle_risk_check,
    '/risk': handle_risk_check,
    '/strategy': handle_strategy,
    '/accuracy': handle_accuracy,
    '/acc': handle_accuracy,
    '/leaderboard': handle_leaderboard,
    '/lb': handle_leaderboard,
}


async def route_trading_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route trading commands"""
    text_lower = text.lower().strip()
    
    # Handle toggle commands
    if text_lower == '/auto on':
        return await handle_auto_toggle(text, chat_id, context, enabled=True)
    elif text_lower == '/auto off':
        return await handle_auto_toggle(text, chat_id, context, enabled=False)
    
    handler = TRADING_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)
    
    return None
