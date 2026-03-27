"""
Engine Management Command Handlers
Commands: /engines, /engines compare, /engine <id> on/off, /engine <id> set
"""
import logging
from datetime import datetime, timezone, timedelta

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
    import app_state
    config = ENGINE_CONFIG.get(engine_id, {})
    internal_id = config.get("id", "")
    
    try:
        if internal_id == "autonomous_v2":
            trader = app_state.autonomous_trader_v2
            return {
                "enabled": trader.active,
                "settings": {
                    "min_confidence": trader.min_confidence,
                    "max_daily_trades": getattr(trader, 'max_daily_trades', 10),
                    "use_smc": getattr(trader, 'use_smc', True)
                }
            }
        elif internal_id == "free_will_v2":
            fw = app_state.free_will_v2
            return {
                "enabled": fw.active,
                "settings": {
                    "confidence_threshold": fw.min_confidence,
                    "min_confirmations": getattr(fw, 'min_confirmations', 3),
                    "cooldown_minutes": getattr(fw, 'cooldown_minutes', 30)
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
    import app_state
    config = ENGINE_CONFIG.get(engine_id, {})
    internal_id = config.get("id", "")
    
    try:
        if internal_id == "autonomous_v2":
            app_state.autonomous_trader_v2.active = enabled
            await app_state.autonomous_trader_v2.save_settings()
            return {"success": True, "engine": config.get("name"), "enabled": enabled}
        elif internal_id == "free_will_v2":
            app_state.free_will_v2.active = enabled
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
    import app_state
    config = ENGINE_CONFIG.get(engine_id, {})
    internal_id = config.get("id", "")
    
    try:
        if internal_id == "autonomous_v2":
            trader = app_state.autonomous_trader_v2
            if key == "min_confidence":
                trader.min_confidence = int(value)
            elif key == "max_daily_trades":
                trader.max_daily_trades = int(value)
            await trader.save_settings()
            return {"success": True, "key": key, "value": value}
            
        elif internal_id == "free_will_v2":
            fw = app_state.free_will_v2
            if key == "confidence_threshold":
                fw.min_confidence = int(value)
            elif key == "min_confirmations":
                fw.min_confirmations = int(value)
            elif key == "cooldown_minutes":
                fw.cooldown_minutes = int(value)
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


async def handle_engines_compare(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /engines compare - side-by-side performance of all engines"""
    import app_state

    try:
        db = app_state.db
        if db is None:
            return "❌ Database not available", "engines"

        latest = await db.engine_snapshots.find_one(sort=[("timestamp", -1)])
        if not latest:
            return (
                "📊 No engine data yet.\n\nThe data collector saves hourly snapshots — "
                "check back in ~60 minutes!",
                "engines"
            )

        engines = latest.get("engines", {})
        ts = latest.get("timestamp")
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_min = int((datetime.now(timezone.utc) - ts).total_seconds() // 60) if ts else 0

        engine_display = {
            "autonomous_v2":   "🤖 Autonomous V2",
            "free_will_v2":    "🧠 Free Will V2",
            "dual_day_trader": "⚡ Day Trader",
            "dual_long_term":  "🏦 Long Term",
            "elite_v3":        "🎯 Elite V3",
            "vwap_scalper":    "📊 VWAP Scalper",
            "yolo":            "🚀 YOLO",
        }

        response = f"📊 ENGINE COMPARISON (updated {age_min}m ago)\n\n"

        for engine_id, display_name in engine_display.items():
            stats = engines.get(engine_id)
            if not stats or "error" in stats:
                continue

            active = stats.get("active", False)
            status = "🟢" if active else "🔴"
            win_rate = stats.get("win_rate")
            total = (
                stats.get("total_trades")
                or stats.get("total_alerts")
                or stats.get("total_signals")
                or 0
            )
            pnl = stats.get("total_pnl_pct")
            signals_today = (
                stats.get("daily_alerts")
                or stats.get("signals_today")
                or stats.get("daily_signals")
                or 0
            )
            profit_factor = stats.get("profit_factor")

            response += f"{status} {display_name}\n"
            if win_rate is not None:
                response += f"   WR: {win_rate}%  Trades: {total}"
                if profit_factor:
                    response += f"  PF: {profit_factor}"
            else:
                response += f"   Signals today: {signals_today}  Total: {total}"
            if pnl is not None:
                sign = "+" if pnl >= 0 else ""
                response += f"  PnL: {sign}{pnl:.1f}%"
            response += "\n\n"

        # Alert outcomes (7 day)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            fw_wins = await db.free_will_alerts.count_documents({"outcome": "WIN", "timestamp": {"$gte": cutoff}})
            fw_losses = await db.free_will_alerts.count_documents({"outcome": "LOSS", "timestamp": {"$gte": cutoff}})
            du_wins = await db.dual_alerts.count_documents({"outcome": "WIN", "timestamp": {"$gte": cutoff}})
            du_losses = await db.dual_alerts.count_documents({"outcome": "LOSS", "timestamp": {"$gte": cutoff}})

            fw_total = fw_wins + fw_losses
            du_total = du_wins + du_losses

            if fw_total > 0 or du_total > 0:
                response += "🎯 ALERT OUTCOMES (7d)\n"
                if fw_total > 0:
                    fw_wr = round(fw_wins / fw_total * 100, 1)
                    response += f"Free Will: {fw_wr}% WR ({fw_wins}W/{fw_losses}L)\n"
                if du_total > 0:
                    du_wr = round(du_wins / du_total * 100, 1)
                    response += f"Dual Engine: {du_wr}% WR ({du_wins}W/{du_losses}L)\n"
                response += "\n"
        except Exception:
            pass

        # Top confirmations
        try:
            top_confs = await db.confirmation_accuracy.find(
                {"total": {"$gte": 3}},
                sort=[("win_rate", -1)]
            ).limit(5).to_list(5)
            if top_confs:
                response += "🏆 TOP CONFIRMATIONS\n"
                for c in top_confs:
                    name = c.get("confirmation", "?")[:35]
                    wr = c.get("win_rate", 0)
                    total = c.get("total", 0)
                    response += f"• {name}: {wr}% ({total} samples)\n"
        except Exception:
            pass

        response += "\n/engines - Full engine list"
        return response, "engines"

    except Exception as e:
        logger.error(f"engines compare error: {e}")
        return f"❌ Error: {str(e)}", "engines"


# Export handlers
ENGINE_HANDLERS = {
    '/engines': handle_engines_list,
    '/engines compare': handle_engines_compare,
    '/engine': handle_engine_command,
}

async def route_engine_command(text: str, chat_id: int, context: dict) -> tuple:
    """Route engine commands"""
    text_lower = text.lower().strip()

    if text_lower == '/engines compare':
        return await handle_engines_compare(text, chat_id, context)
    elif text_lower == '/engines' or text_lower == '/engine':
        return await handle_engines_list(text, chat_id, context)
    elif text_lower.startswith('/engine '):
        return await handle_engine_command(text, chat_id, context)

    return None, None
