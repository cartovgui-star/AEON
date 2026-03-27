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
    import app_state
    
    try:
        app_state.autonomous_trader_v2.active = enabled
        await app_state.autonomous_trader_v2.save_settings()
        
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


async def handle_mode(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /mode command - show or set trading mode"""
    import app_state
    
    parts = text.lower().split()
    
    # Trading mode presets
    MODES = {
        "yolo": {"conf": 50, "confirms": 1, "rr": 1.0, "emoji": "🚀", "desc": "MAX trading, no filters!"},
        "easy": {"conf": 70, "confirms": 2, "rr": 1.5, "emoji": "🟢", "desc": "More trades, lower filters"},
        "balanced": {"conf": 80, "confirms": 3, "rr": 2.0, "emoji": "🟡", "desc": "Moderate quality/quantity"},
        "strict": {"conf": 85, "confirms": 4, "rr": 2.5, "emoji": "🟠", "desc": "Fewer, higher quality"},
        "elite": {"conf": 90, "confirms": 5, "rr": 3.0, "emoji": "🔴", "desc": "Ultra-selective, best setups"}
    }
    
    trader = app_state.autonomous_trader_v2
    
    # Detect current mode
    current = "custom"
    for mode_id, m in MODES.items():
        if trader.min_confidence == m["conf"] and trader.min_confirmations == m["confirms"]:
            current = mode_id
            break
    
    # Just /mode - show current and available
    if len(parts) == 1:
        response = f"""⚙️ TRADING MODES

Current: {MODES.get(current, {}).get('emoji', '⚪')} {current.upper()}
• Confidence: {trader.min_confidence}%
• Confirmations: {trader.min_confirmations}
• R:R Ratio: {trader.min_rr_ratio}:1

📋 AVAILABLE MODES:
"""
        for mode_id, m in MODES.items():
            marker = "→ " if mode_id == current else "  "
            response += f"{marker}{m['emoji']} {mode_id.upper()} - {m['desc']}\n"
        
        response += "\nSet mode: /mode yolo|easy|balanced|strict|elite"
        return response, "trading"
    
    # /mode <mode_id> - set mode
    mode_id = parts[1]
    if mode_id not in MODES:
        return "❌ Invalid mode. Use: yolo, easy, balanced, strict, elite", "trading"
    
    mode = MODES[mode_id]
    
    # Apply settings
    trader.min_confidence = mode["conf"]
    trader.min_confirmations = mode["confirms"]
    trader.min_rr_ratio = mode["rr"]
    
    # Adjust filters based on mode
    if mode_id == "yolo":
        trader.ema_200_filter_enabled = False
        trader.adx_filter_enabled = False
        trader.session_filter_enabled = False
        trader.volume_filter_enabled = False
        trader.max_open_trades = 50
    elif mode_id == "easy":
        trader.ema_200_filter_enabled = False
        trader.adx_filter_enabled = False
        trader.session_filter_enabled = False
        trader.max_open_trades = 10
    elif mode_id == "balanced":
        trader.ema_200_filter_enabled = True
        trader.adx_filter_enabled = False
        trader.session_filter_enabled = False
        trader.max_open_trades = 7
    elif mode_id == "strict":
        trader.ema_200_filter_enabled = True
        trader.adx_filter_enabled = True
        trader.session_filter_enabled = True
        trader.max_open_trades = 5
    else:  # elite
        trader.ema_200_filter_enabled = True
        trader.adx_filter_enabled = True
        trader.session_filter_enabled = True
        trader.max_open_trades = 3
    
    await trader.save_settings()
    
    response = f"""{mode['emoji']} MODE SET: {mode_id.upper()}

✅ Settings Applied:
• Min Confidence: {mode['conf']}%
• Confirmations: {mode['confirms']}
• R:R Ratio: {mode['rr']}:1
• Max Trades: {trader.max_open_trades}

{mode['desc']}

Use /stats to monitor performance."""
    
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
    '/mode': handle_mode,
}


async def route_trading_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route trading commands"""
    text_lower = text.lower().strip()
    
    # Handle toggle commands
    if text_lower == '/auto on':
        return await handle_auto_toggle(text, chat_id, context, enabled=True)
    elif text_lower == '/auto off':
        return await handle_auto_toggle(text, chat_id, context, enabled=False)
    
    # Handle mode commands
    if text_lower.startswith('/mode'):
        return await handle_mode(text, chat_id, context)
    
    handler = TRADING_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)
    
    return None
