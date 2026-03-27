"""
Help & General Command Handlers
Commands: /help, /start, /menu, /commands, /settings, /ping, /status
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

HELP_TEXT = """🤖 AEON TRADING BOT — COMMAND LIST

📊 MARKET
• /market — Global market summary
• /fear /fng — Fear & Greed Index
• /movers /gainers — Top gainers/losers
• /trending /hot — Trending coins

🔍 PRICE & ANALYSIS
• /price [coin] — Live price (BTC/ETH/SOL default)
• /top100 /top — Top coins by volume
• /scan [coin] — Deep scan with entry/exit zones
• /quick [coin] — Quick opportunity check
• /ta [coin] [tf] — Technical indicators
• /quant — Quant scan top 10 coins (score ranked)
• /quant [coin] — Deep 10-factor quant report

📡 DERIVATIVES & INTEL
• /funding [coin] — Aggregated funding rates
• /positions [coin] — Long/short ratio
• /oi [coin] — Open interest
• /news — Latest crypto news
• /whales — Whale activity & large moves
• /onchain /chain — BTC on-chain data
• /intel — Full market intelligence report

🎯 SIGNALS
• /elite — Elite strategy status
• /elite scan — Scan for high-conf signals
• /elite [coin] — Analyze specific coin
• /elite on /elite off — Toggle elite alerts
• /vwap — VWAP scalper status
• /vwap scan — Run VWAP scan now
• /vwap [coin] — VWAP analysis for coin
• /vwap on /vwap off — Toggle VWAP alerts
• /yolo — YOLO mode status/scan
• /mtf /confluence — Multi-timeframe scan
• /mtf [coin] — MTF analysis for coin

🤖 AUTO TRADING
• /auto — Trading status
• /auto on /auto off — Toggle auto trading
• /open — View open positions
• /opps — Current opportunities
• /mode — Change risk mode (yolo/easy/balanced/strict/elite)
• /risk /riskcheck — Risk assessment
• /strategy — Strategy weights

📈 STATS
• /stats — Full performance stats
• /accuracy /acc — Signal accuracy breakdown
• /leaderboard /lb — Top performing coins

💼 PAPER TRADING
• /accounts — View PRO + STARTER accounts
• /pro — PRO account details ($50K)
• /starter — STARTER account details ($1.5K)
• /paper [coin] — Check position for coin
• /addmargin [pro|starter] [amount] — Add margin

🔧 ENGINES
• /engines — List all trading engines
• /engine [id] on/off — Toggle engine

🔔 ALERTS
• /alerts — View your price alerts
• /alert [coin] [price] — Add price alert
• /alert remove [coin] — Remove alert

🧮 CALCULATORS
• /calc [entry] [exit] [size] [lev] [dir] — PnL calc
• /calcsize [bal] [risk%] [entry] [stop] [lev] — Position size

🧠 LEARNING
• /learn — Learning system stats
• /insights — AI trading insights
• /patterns — Detected market patterns

🤖 AI MODEL
• /claude — Switch to Claude Sonnet
• /gemini — Switch to Gemini Flash
• /model — Current model

⚙️ SETTINGS & INFO
• /settings — Your preferences
• /voice on/off — Voice responses
• /status — System status (all engines)
• /ping — Bot health check
• /help — This menu
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
    from feed_health import feed_health

    now = datetime.now(timezone.utc)
    response = f"""🏓 PONG!

Bot: 🟢 Online
{feed_health.status_line()}
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"""
    return response, "general"


async def handle_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /status command"""
    import app_state
    from autonomous_trader_v2 import autonomous_trader_v2
    from elite_strategy_v3 import get_elite_strategy
    from feed_health import feed_health

    try:
        v2_stats = await autonomous_trader_v2.get_stats()
        elite = get_elite_strategy(app_state.advanced_strategies, None, app_state.enhanced_intel)
        elite_stats = elite.get_stats()

        response = f"""📊 SYSTEM STATUS

📡 DATA FEEDS
{feed_health.status_line()}

🤖 AUTONOMOUS V2.1
Status: {'🟢 ACTIVE' if v2_stats.get('active') else '🔴 PAUSED'}
Today's Signals: {v2_stats.get('total_signals_analyzed', 0)}
Open Positions: {v2_stats.get('open_positions', 0)}

🎯 ELITE STRATEGY V3
Status: {'🟢 ACTIVE' if elite_stats.get('enabled') else '🔴 PAUSED'}
Mode: {elite_stats.get('mode', 'STRICT')}
Signals Generated: {elite_stats.get('signals_generated', 0)}

💼 PAPER TRADING
Accounts: PRO ($50K) + STARTER ($1.5K)"""
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
        model = user_settings.get("model", "claude")

        response = f"""⚙️ YOUR SETTINGS

🔔 Alerts: {'ON' if alerts else 'OFF'}
🎤 Voice: {'ON' if voice else 'OFF'}
🤖 AI Model: {model.upper()}

Change with:
• /alerts [on/off]
• /voice [on/off]
• /claude or /gemini"""
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
