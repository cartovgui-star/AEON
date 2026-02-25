"""
Help & General Command Handlers
Commands: /help, /start, /menu, /commands, /settings, /ping, /status
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

HELP_TEXT = """🤖 AEON TRADING BOT

📊 MARKET COMMANDS
• /market - Market summary
• /fear, /fng - Fear & Greed Index
• /movers - Top gainers/losers
• /trending - Trending coins
• /whales - Whale activity
• /news - Latest crypto news

📈 TRADING COMMANDS
• /stats - Trading statistics
• /auto [on/off] - Auto trading toggle
• /scan [symbol] - Scan for opportunities
• /risk - Risk check

🎯 ELITE STRATEGY
• /elite - Elite strategy status
• /elite scan - Scan for elite signals
• /elite relaxed - More signals (70% conf)
• /elite strict - Fewer signals (92% conf)
• /elite backtest - Run backtest

📊 MTF CONFLUENCE
• /mtf - Scan all for MTF confluence
• /mtf BTC - Analyze specific symbol
• /confluence - Alias for /mtf

💼 PAPER TRADING
• /accounts - View paper accounts
• /pro - PRO account ($50K)
• /starter - STARTER account ($1.5K)
• /paper [symbol] - Check position

🔧 ENGINES
• /engines - List all engines
• /engine [id] - Engine details
• /engine [id] on/off - Toggle engine

🧠 AI MODEL
• /openai - Switch to GPT-4o
• /claude - Switch to Claude
• /model - Current model status

⚙️ SETTINGS
• /settings - Your preferences
• /alerts - Manage alerts
• /voice [on/off] - Voice responses

❓ SUPPORT
• /help - This menu
• /ping - Check bot status
"""


async def handle_help(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /help command"""
    return HELP_TEXT, "help"


async def handle_start(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /start command"""
    response = """👋 Welcome to AEON Trading Bot!

I'm your intelligent crypto trading assistant with:
• 🤖 Autonomous trading strategies
• 📊 Real-time market analysis
• 🎯 Elite high-win-rate signals
• 📈 Multi-timeframe confluence
• 💼 Paper trading simulation

Get started:
• /market - See market overview
• /elite scan - Find trading opportunities
• /help - See all commands

Let's make some gains! 🚀"""
    return response, "general"


async def handle_ping(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /ping command"""
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    response = f"""🏓 PONG!

Status: 🟢 Online
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC

All systems operational."""
    return response, "general"


async def handle_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /status command"""
    import app_state
    from autonomous_trader_v2 import autonomous_trader_v2
    from elite_strategy_v3 import get_elite_strategy
    
    try:
        v2_stats = await autonomous_trader_v2.get_stats()
        elite = get_elite_strategy(app_state.advanced_strategies, None, app_state.enhanced_intel)
        elite_stats = elite.get_stats()
        
        response = f"""📊 SYSTEM STATUS

🤖 AUTONOMOUS V2.1
Status: {'🟢 ACTIVE' if v2_stats.get('active') else '🔴 PAUSED'}
Today's Signals: {v2_stats.get('total_signals_analyzed', 0)}
Open Positions: {v2_stats.get('open_positions', 0)}

🎯 ELITE STRATEGY V3
Status: {'🟢 ACTIVE' if elite_stats.get('enabled') else '🔴 PAUSED'}
Mode: {elite_stats.get('mode', 'STRICT')}
Signals Generated: {elite_stats.get('signals_generated', 0)}

💼 PAPER TRADING
Accounts: PRO ($50K) + STARTER ($1.5K)

All engines running normally."""
    except Exception as e:
        response = f"❌ Error getting status: {str(e)}"
    
    return response, "general"


async def handle_settings(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /settings command"""
    import app_state
    
    try:
        user_settings = await app_state.get_user_settings(chat_id)
        
        voice = user_settings.get("voice_enabled", False)
        alerts = user_settings.get("alerts_enabled", True)
        model = user_settings.get("model", "openai")
        
        response = f"""⚙️ YOUR SETTINGS

🔔 Alerts: {'ON' if alerts else 'OFF'}
🎤 Voice: {'ON' if voice else 'OFF'}
🤖 AI Model: {model.upper()}

Change with:
• /alerts [on/off]
• /voice [on/off]
• /openai or /claude"""
    except Exception as e:
        response = f"❌ Error getting settings: {str(e)}"
    
    return response, "settings"


async def handle_menu(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /menu command"""
    response = """📱 QUICK MENU

1️⃣ /market - Market overview
2️⃣ /elite scan - Trading signals
3️⃣ /mtf - MTF confluence scan
4️⃣ /accounts - Paper trading
5️⃣ /stats - Your statistics
6️⃣ /help - Full command list

What would you like to do?"""
    return response, "general"


# Export handlers
GENERAL_HANDLERS = {
    '/help': handle_help,
    '/start': handle_start,
    '/ping': handle_ping,
    '/status': handle_status,
    '/settings': handle_settings,
    '/menu': handle_menu,
    '/commands': handle_help,
}


async def route_general_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route general commands"""
    text_lower = text.lower().strip()
    
    handler = GENERAL_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)
    
    return None
