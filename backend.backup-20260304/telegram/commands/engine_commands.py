"""
Engine Management Command Handlers
Commands: /engines, /engine <id> on/off, /engine <id> set
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Engine configurations
ENGINE_CONFIG = {
    "1": {
        "id": "autonomous_v2",
        "name": "Autonomous Trader V2.1",
        "emoji": "🤖",
        "description": "Smart Money Concepts + Multi-timeframe",
        "settings_keys": ["min_confidence", "max_daily_trades", "use_smc"]
    },
    "2": {
        "id": "free_will_v2", 
        "name": "Free Will Engine",
        "emoji": "🧠",
        "description": "High-confidence alerts with reasoning",
        "settings_keys": ["confidence_threshold", "min_confirmations", "cooldown_minutes"]
    },
    "3": {
        "id": "scalper",
        "name": "Aggressive Scalper",
        "emoji": "⚡",
        "description": "Quick scalp signals with auto-learning",
        "settings_keys": ["profit_target", "stop_loss", "volume_threshold"]
    },
    "4": {
        "id": "day_trader",
        "name": "Day Trader",
        "emoji": "📈",
        "description": "Intraday opportunities",
        "settings_keys": ["risk_per_trade", "max_positions"]
    },
    "5": {
        "id": "long_term",
        "name": "Long Term Advisor",
        "emoji": "🏦",
        "description": "Weekly/Monthly position ideas",
        "settings_keys": ["min_holding_days", "portfolio_allocation"]
    },
    "6": {
        "id": "paper_trading",
        "name": "Paper Trading",
        "emoji": "📝",
        "description": "Demo trading accounts (Pro + Starter)",
        "settings_keys": ["pro_balance", "starter_balance", "default_leverage"]
    }
}


async def get_engine_status(engine_id: str) -> dict:
    """Get the current status of an engine"""
    config = ENGINE_CONFIG.get(engine_id, {})
    internal_id = config.get("id", "")
    
    try:
        if internal_id == "autonomous_v2":
            from autonomous_trader_v2 import autonomous_trader
            return {
                "enabled": autonomous_trader.is_active,
                "settings": {
                    "min_confidence": autonomous_trader.min_confidence,
                    "max_daily_trades": autonomous_trader.max_daily_trades,
                    "use_smc": getattr(autonomous_trader, 'use_smc', True)
                }
            }
        elif internal_id == "free_will_v2":
            from free_will_v2 import free_will_engine
            return {
                "enabled": free_will_engine.enabled,
                "settings": {
                    "confidence_threshold": free_will_engine.confidence_threshold,
                    "min_confirmations": free_will_engine.min_confirmations,
                    "cooldown_minutes": free_will_engine.cooldown_minutes
                }
            }
        elif internal_id == "scalper":
            from aggressive_scalper import scalper
            settings = scalper.get_settings()
            return {
                "enabled": settings.get("enabled", True),
                "settings": settings
            }
        elif internal_id == "paper_trading":
            from paper_trading import paper_trading
            accounts = paper_trading.get_accounts_summary()
            return {
                "enabled": True,
                "settings": {
                    "pro_balance": accounts.get("pro", {}).get("balance", 50000),
                    "starter_balance": accounts.get("starter", {}).get("balance", 1500),
                    "total_trades": accounts.get("total_trades", 0)
                }
            }
        else:
            return {"enabled": False, "settings": {}}
    except Exception as e:
        logger.error(f"Error getting engine status {engine_id}: {e}")
        return {"enabled": False, "settings": {}, "error": str(e)}


async def toggle_engine(engine_id: str, enabled: bool) -> dict:
    """Toggle an engine on/off"""
    config = ENGINE_CONFIG.get(engine_id, {})
    internal_id = config.get("id", "")
    
    try:
        if internal_id == "autonomous_v2":
            from autonomous_trader_v2 import autonomous_trader
            autonomous_trader.is_active = enabled
            return {"success": True, "engine": config.get("name"), "enabled": enabled}
        elif internal_id == "free_will_v2":
            from free_will_v2 import free_will_engine
            free_will_engine.enabled = enabled
            return {"success": True, "engine": config.get("name"), "enabled": enabled}
        elif internal_id == "scalper":
            from aggressive_scalper import scalper
            scalper.settings["enabled"] = enabled
            return {"success": True, "engine": config.get("name"), "enabled": enabled}
        else:
            return {"success": False, "error": "Engine cannot be toggled"}
    except Exception as e:
        logger.error(f"Error toggling engine {engine_id}: {e}")
        return {"success": False, "error": str(e)}


async def update_engine_setting(engine_id: str, key: str, value: any) -> dict:
    """Update a specific engine setting"""
    config = ENGINE_CONFIG.get(engine_id, {})
    internal_id = config.get("id", "")
    
    try:
        if internal_id == "autonomous_v2":
            from autonomous_trader_v2 import autonomous_trader
            if key == "min_confidence":
                autonomous_trader.min_confidence = int(value)
            elif key == "max_daily_trades":
                autonomous_trader.max_daily_trades = int(value)
            return {"success": True, "key": key, "value": value}
            
        elif internal_id == "free_will_v2":
            from free_will_v2 import free_will_engine
            if key == "confidence_threshold":
                free_will_engine.confidence_threshold = int(value)
            elif key == "min_confirmations":
                free_will_engine.min_confirmations = int(value)
            elif key == "cooldown_minutes":
                free_will_engine.cooldown_minutes = int(value)
            return {"success": True, "key": key, "value": value}
            
        elif internal_id == "scalper":
            from aggressive_scalper import scalper
            if key in scalper.settings:
                # Type conversion
                if isinstance(scalper.settings[key], float):
                    scalper.settings[key] = float(value)
                elif isinstance(scalper.settings[key], int):
                    scalper.settings[key] = int(value)
                else:
                    scalper.settings[key] = value
                return {"success": True, "key": key, "value": value}
            return {"success": False, "error": f"Unknown setting: {key}"}
        else:
            return {"success": False, "error": "Engine settings not configurable"}
    except Exception as e:
        logger.error(f"Error updating engine setting {engine_id}.{key}: {e}")
        return {"success": False, "error": str(e)}


async def handle_engines_list(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /engines command - list all engines"""
    response = "🔧 TRADING ENGINES\n\n"
    
    for num, config in ENGINE_CONFIG.items():
        status = await get_engine_status(num)
        enabled = status.get("enabled", False)
        status_emoji = "🟢" if enabled else "🔴"
        
        response += f"{config['emoji']} [{num}] {config['name']}\n"
        response += f"   Status: {status_emoji} {'ON' if enabled else 'OFF'}\n"
        response += f"   {config['description']}\n\n"
    
    response += """Commands:
• /engine <id> - View engine details
• /engine <id> on/off - Toggle engine
• /engine <id> set <param> <value>"""
    
    return response, "engines"


async def handle_engine_command(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /engine <id> [on/off/set] commands"""
    parts = text.lower().split()
    
    if len(parts) < 2:
        return await handle_engines_list(text, chat_id, context)
    
    engine_id = parts[1]
    
    if engine_id not in ENGINE_CONFIG:
        return f"❌ Unknown engine ID: {engine_id}\n\nValid IDs: 1-6", "engines"
    
    config = ENGINE_CONFIG[engine_id]
    
    # Just /engine <id> - show details
    if len(parts) == 2:
        status = await get_engine_status(engine_id)
        enabled = status.get("enabled", False)
        settings = status.get("settings", {})
        
        response = f"""{config['emoji']} {config['name']}

Status: {'🟢 ACTIVE' if enabled else '🔴 PAUSED'}
{config['description']}

⚙️ SETTINGS:"""
        
        for key, value in settings.items():
            response += f"\n• {key}: {value}"
        
        response += f"\n\nToggle: /engine {engine_id} on/off"
        response += f"\nConfigure: /engine {engine_id} set <param> <value>"
        
        return response, "engines"
    
    # /engine <id> on/off
    if parts[2] in ['on', 'off']:
        enabled = parts[2] == 'on'
        result = await toggle_engine(engine_id, enabled)
        
        if result.get("success"):
            return f"{'🟢' if enabled else '🔴'} {config['name']} is now {'ON' if enabled else 'OFF'}", "engines"
        else:
            return f"❌ Failed: {result.get('error', 'Unknown error')}", "engines"
    
    # /engine <id> set <key> <value>
    if parts[2] == 'set' and len(parts) >= 5:
        key = parts[3]
        value = parts[4]
        
        result = await update_engine_setting(engine_id, key, value)
        
        if result.get("success"):
            return f"✅ {config['name']}: {key} = {value}", "engines"
        else:
            return f"❌ Failed: {result.get('error', 'Unknown error')}", "engines"
    
    return "❓ Unknown command. Use:\n• /engine <id> on/off\n• /engine <id> set <param> <value>", "engines"


# Export handlers
ENGINE_HANDLERS = {
    '/engines': handle_engines_list,
    '/engine': handle_engine_command,
}

async def route_engine_command(text: str, chat_id: int, context: dict) -> tuple:
    """Route engine commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/engines' or text_lower == '/engine':
        return await handle_engines_list(text, chat_id, context)
    elif text_lower.startswith('/engine '):
        return await handle_engine_command(text, chat_id, context)
    
    return None, None
