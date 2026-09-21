"""
Trading Mode & Strategy Command Handlers
Commands: /strategy, /mode

NOTE: /stats, /accuracy, /leaderboard → stats_commands.py (live paper_trades)
      /auto, /auto on/off, /riskcheck  → auto_commands.py
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


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


async def handle_mode(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /mode command - show or set trading mode"""
    import app_state

    parts = text.lower().split()

    MODES = {
        "yolo":     {"conf": 50, "confirms": 1, "rr": 1.0, "emoji": "🚀", "desc": "MAX trading, no filters!"},
        "easy":     {"conf": 70, "confirms": 2, "rr": 1.5, "emoji": "🟢", "desc": "More trades, lower filters"},
        "balanced": {"conf": 80, "confirms": 3, "rr": 2.0, "emoji": "🟡", "desc": "Moderate quality/quantity"},
        "strict":   {"conf": 85, "confirms": 4, "rr": 2.5, "emoji": "🟠", "desc": "Fewer, higher quality"},
        "elite":    {"conf": 90, "confirms": 5, "rr": 3.0, "emoji": "🔴", "desc": "Ultra-selective, best setups"},
    }

    trader = app_state.autonomous_trader_v2

    current = "custom"
    for mode_id, m in MODES.items():
        if getattr(trader, 'min_confidence', None) == m["conf"] and getattr(trader, 'min_confirmations', None) == m["confirms"]:
            current = mode_id
            break

    if len(parts) == 1:
        response = f"""⚙️ TRADING MODES

Current: {MODES.get(current, {}).get('emoji', '⚪')} {current.upper()}
• Confidence: {getattr(trader, 'min_confidence', '?')}%
• Confirmations: {getattr(trader, 'min_confirmations', '?')}
• R:R Ratio: {getattr(trader, 'min_rr_ratio', '?')}:1

📋 AVAILABLE MODES:
"""
        for mode_id, m in MODES.items():
            marker = "→ " if mode_id == current else "  "
            response += f"{marker}{m['emoji']} {mode_id.upper()} - {m['desc']}\n"

        response += "\nSet mode: /mode yolo|easy|balanced|strict|elite"
        return response, "trading"

    mode_id = parts[1]
    if mode_id not in MODES:
        return "❌ Invalid mode. Use: yolo, easy, balanced, strict, elite", "trading"

    mode = MODES[mode_id]
    trader.min_confidence = mode["conf"]
    trader.min_confirmations = mode["confirms"]
    trader.min_rr_ratio = mode["rr"]

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


TRADING_HANDLERS = {
    '/strategy': handle_strategy,
    '/mode':     handle_mode,
}


async def route_trading_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route trading mode/strategy commands"""
    text_lower = text.lower().strip()

    if text_lower.startswith('/mode'):
        return await handle_mode(text, chat_id, context)

    handler = TRADING_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)

    return None
