"""Trading, Dual Engine, Learning, Bot Stats, User Profile routes."""
from fastapi import APIRouter, Request
from datetime import datetime, timezone
from starlette.responses import StreamingResponse
import os
import logging
import io
import csv
import app_state as state
from voice_tts import generate_speech
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
router = APIRouter()  # Prefix added when mounting


@router.post("/trading/toggle")
async def api_trading_toggle(active: bool = True):
    state.autonomous_trader_v2.active = active
    await state.autonomous_trader_v2.save_settings()
    return {"active": state.autonomous_trader_v2.active, "message": f"Trading {'activated' if active else 'paused'}", "engine": "v2"}


@router.get("/trading/summary")
async def api_trading_summary():
    return await state.autonomous_trader_v2.get_stats()


@router.get("/trading/opportunities")
async def api_trading_opportunities():
    return await state.autonomous_trader_v2.scan_all_markets()


@router.get("/trading/strategy")
async def api_strategy_weights():
    return {
        "weights": state.autonomous_trader.strategy_weights,
        "performance": state.autonomous_trader.strategy_performance,
        "active": state.autonomous_trader.active,
        "min_confidence": state.autonomous_trader.min_confidence,
        "note": "This is v1 legacy data. Use /trading/v2/stats for v2 engine."
    }


@router.get("/trading/analyze/{symbol}")
async def api_analyze_symbol(symbol: str, timeframe: str = "4h"):
    return await state.autonomous_trader_v2.analyze_signal(symbol.upper() + "/USDT", timeframe)


@router.get("/trading/v2/stats")
async def api_trading_v2_stats():
    return await state.autonomous_trader_v2.get_stats()


@router.get("/stats/dashboard")
async def api_stats_dashboard():
    """Get comprehensive dashboard stats including best/worst pairs, blacklist, and scaling status"""
    trader = state.autonomous_trader_v2
    
    # Get best/worst pairs
    pair_data = trader.get_best_worst_pairs()
    
    # Get pairs on cooldown
    cooldowns = []
    for symbol, until in trader.pair_cooldowns.items():
        time_left = (until - datetime.now(timezone.utc)).total_seconds() / 60
        if time_left > 0:
            cooldowns.append({
                "symbol": symbol,
                "minutes_left": round(time_left, 0),
                "until": until.isoformat()
            })
    
    # Get position scaling status
    positions_pending_scale = [
        {"symbol": t["symbol"], "current_size": t["position_size"], "full_size": t.get("original_full_size", t["position_size"])}
        for t in trader.open_trades if t.get("pending_scale_in", False)
    ]
    
    # Get filter statistics
    filter_stats = trader.get_filter_stats()
    
    return {
        "best_pairs": pair_data.get("best", []),
        "worst_pairs": pair_data.get("worst", []),
        "blacklisted_pairs": pair_data.get("blacklisted", []),
        "pairs_on_cooldown": cooldowns,
        "position_scaling": {
            "enabled": trader.position_scaling_enabled,
            "initial_entry_pct": trader.initial_entry_pct,
            "pending_scale_ins": len(positions_pending_scale),
            "positions": positions_pending_scale,
            "min_profit_for_scale": trader.scale_in_min_profit_pct,
            "max_hours_for_scale": trader.scale_in_max_hours
        },
        "trading_config": {
            "min_confidence": trader.min_confidence,
            "min_confirmations": trader.min_confirmations,
            "min_rr_ratio": trader.min_rr_ratio,
            "max_open_trades": trader.max_open_trades,
            "cooldown_hours": trader.cooldown_hours,
            "ema_200_filter": trader.ema_200_filter_enabled,
            "adx_filter": trader.adx_filter_enabled,
            "volume_filter": trader.volume_filter_enabled,
            "session_filter": trader.session_filter_enabled
        },
        "filter_stats": filter_stats,
        "current_session": trader.get_current_session()
    }


@router.get("/trading/v2/filter-stats")
async def api_filter_stats():
    """Get detailed breakdown of how many signals were filtered by each rule"""
    return state.autonomous_trader_v2.get_filter_stats()


@router.post("/trading/v2/set-confidence")
async def api_set_confidence(request: Request):
    """Set minimum confidence level for autonomous trader"""
    try:
        data = await request.json()
        min_conf = data.get("min_confidence", 80)
        min_conf = max(60, min(98, min_conf))
        state.autonomous_trader_v2.min_confidence = min_conf
        await state.autonomous_trader_v2.save_settings()
        return {"success": True, "min_confidence": min_conf}
    except Exception as e:
        return {"error": str(e)}


@router.post("/trading/v2/toggle-scaling")
async def api_toggle_scaling(enabled: bool = True):
    """Toggle position scaling feature"""
    state.autonomous_trader_v2.position_scaling_enabled = enabled
    return {
        "success": True,
        "position_scaling_enabled": enabled,
        "message": f"Position scaling {'enabled' if enabled else 'disabled'}"
    }


@router.get("/trading/v2/open")
async def api_trading_v2_open():
    return {
        "open_trades": state.autonomous_trader_v2.open_trades,
        "total_open": len(state.autonomous_trader_v2.open_trades)
    }


@router.get("/trading/v2/closed")
async def api_trading_v2_closed():
    return {
        "closed_trades": state.autonomous_trader_v2.closed_trades[-20:],
        "total_closed": len(state.autonomous_trader_v2.closed_trades)
    }


@router.get("/trades/closed")
async def api_trades_closed():
    trades = []
    for t in state.autonomous_trader_v2.closed_trades:
        trades.append({
            "id": t.get("id", ""),
            "symbol": t.get("symbol", ""),
            "direction": t.get("direction", ""),
            "entry_price": t.get("entry_price", 0),
            "exit_price": t.get("exit_price", 0),
            "pnl_pct": t.get("pnl_pct", 0),
            "closed_at": t.get("exit_time", t.get("closed_at", "")),
            "timestamp": t.get("exit_time", t.get("closed_at", "")),
            "exit_reason": t.get("exit_reason", ""),
            "style": t.get("style", ""),
            "notes": t.get("notes", ""),
            "notes_updated_at": t.get("notes_updated_at", ""),
        })
    return {"trades": trades, "total": len(trades)}


@router.get("/trades/export")
async def api_trades_export():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Symbol", "Direction", "Entry", "Exit", "PnL%", "Exit Reason", "Style"])

    for t in state.autonomous_trader_v2.closed_trades:
        ts = t.get("exit_time", t.get("closed_at", ""))
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        writer.writerow([
            str(ts), t.get("symbol", ""), t.get("direction", ""),
            t.get("entry_price", 0), t.get("exit_price", 0),
            round(t.get("pnl_pct", 0), 2), t.get("exit_reason", ""), t.get("style", ""),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=aeon_trades_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


@router.get("/trading/v2/pnl-history")
async def api_trading_v2_pnl_history():
    history = []
    cumulative_pnl = 0
    for trade in state.autonomous_trader_v2.closed_trades:
        cumulative_pnl += trade.get("pnl_pct", 0)
        history.append({
            "timestamp": trade.get("exit_time", trade.get("closed_at", datetime.now(timezone.utc))).isoformat() if isinstance(trade.get("exit_time"), datetime) else str(trade.get("exit_time", "")),
            "symbol": trade.get("symbol", ""),
            "pnl": trade.get("pnl_pct", 0),
            "cumulative_pnl": round(cumulative_pnl, 2),
            "direction": trade.get("direction", ""),
            "result": "WIN" if trade.get("pnl_pct", 0) > 0 else "LOSS"
        })
    return {
        "history": history, "total_trades": len(history),
        "total_pnl": round(cumulative_pnl, 2),
        "wins": len([h for h in history if h["result"] == "WIN"]),
        "losses": len([h for h in history if h["result"] == "LOSS"])
    }


@router.get("/trading/v2/live-positions")
async def api_trading_v2_live_positions():
    positions = []
    total_pnl = 0
    for trade in state.autonomous_trader_v2.open_trades:
        try:
            ticker = await state.market_intel.get_ticker(trade["symbol"])
            current_price = ticker.get("price", 0) if ticker and "error" not in ticker else 0
            entry = trade.get("entry_price", 0)
            direction = trade.get("direction", "")
            if entry and current_price:
                pnl_pct = ((current_price - entry) / entry) * 100 if direction == "LONG" else ((entry - current_price) / entry) * 100
            else:
                pnl_pct = 0
            total_pnl += pnl_pct
            positions.append({
                "id": trade.get("id"), "symbol": trade.get("symbol"), "direction": direction,
                "entry_price": entry, "current_price": current_price,
                "stop_price": trade.get("stop_price"), "target_price": trade.get("target_price"),
                "trail_stop": trade.get("trail_stop"), "pnl_pct": round(pnl_pct, 2),
                "confidence": trade.get("confidence"), "timeframe": trade.get("timeframe"),
                "trade_type": trade.get("trade_type", "SWING"),
                "leverage": trade.get("leverage", 10),
                "position_size": trade.get("position_size", 1000),
                "entry_time": trade.get("entry_time").isoformat() if isinstance(trade.get("entry_time"), datetime) else str(trade.get("entry_time", "")),
                "confirmations": trade.get("confirmations", [])[:3]
            })
        except Exception as e:
            logger.error(f"Error getting live position data: {e}")
    return {"positions": positions, "total_positions": len(positions), "total_pnl_pct": round(total_pnl, 2), "data_source": "MEXC Live"}


@router.post("/trading/v2/confidence")
async def api_trading_v2_confidence(min_conf: int = 85):
    state.autonomous_trader_v2.min_confidence = max(70, min(98, min_conf))
    await state.autonomous_trader_v2.save_settings()
    return {"min_confidence": state.autonomous_trader_v2.min_confidence}


@router.post("/trading/v2/close/{symbol}")
async def api_trading_v2_close(symbol: str):
    symbol_full = symbol.upper() + "/USDT"
    for i, trade in enumerate(state.autonomous_trader_v2.open_trades):
        if trade.get("symbol") == symbol_full:
            ticker = await state.market_intel.get_ticker(symbol_full)
            current_price = ticker.get("price", 0) if "error" not in ticker else 0
            entry = trade.get("entry_price", 0)
            direction = trade.get("direction", "")
            pnl = 0
            if entry and current_price:
                pnl = ((current_price - entry) / entry) * 100 if direction == "LONG" else ((entry - current_price) / entry) * 100
            closed_trade = state.autonomous_trader_v2.open_trades.pop(i)
            closed_trade["exit_price"] = current_price
            closed_trade["pnl_pct"] = pnl
            closed_trade["exit_reason"] = "API_MANUAL_CLOSE"
            closed_trade["closed_at"] = datetime.now(timezone.utc).isoformat()
            state.autonomous_trader_v2.closed_trades.append(closed_trade)
            return {"status": "closed", "trade": closed_trade}
    return {"error": f"No open trade found for {symbol_full}"}


@router.post("/trades/{trade_id}/notes")
async def api_add_trade_notes(trade_id: str, request: Request):
    """Add or update notes for a specific trade"""
    try:
        data = await request.json()
        notes = data.get("notes", "")
        
        # Update in open trades
        for trade in state.autonomous_trader_v2.open_trades:
            if trade.get("id") == trade_id:
                trade["notes"] = notes
                trade["notes_updated_at"] = datetime.now(timezone.utc).isoformat()
                # Update in database
                await state.autonomous_trader_v2.db.v2_open_trades.update_one(
                    {"id": trade_id},
                    {"$set": {"notes": notes, "notes_updated_at": datetime.now(timezone.utc)}}
                )
                return {"status": "success", "trade_id": trade_id, "notes": notes}
        
        # Update in closed trades
        for trade in state.autonomous_trader_v2.closed_trades:
            if trade.get("id") == trade_id:
                trade["notes"] = notes
                trade["notes_updated_at"] = datetime.now(timezone.utc).isoformat()
                # Update in database
                await state.autonomous_trader_v2.db.v2_closed_trades.update_one(
                    {"id": trade_id},
                    {"$set": {"notes": notes, "notes_updated_at": datetime.now(timezone.utc)}}
                )
                return {"status": "success", "trade_id": trade_id, "notes": notes}
        
        return {"error": "Trade not found", "trade_id": trade_id}, 404
    except Exception as e:
        logger.error(f"Error adding trade notes: {e}")
        return {"error": str(e)}, 500


@router.get("/trades/{trade_id}/notes")
async def api_get_trade_notes(trade_id: str):
    """Get notes for a specific trade"""
    # Check open trades
    for trade in state.autonomous_trader_v2.open_trades:
        if trade.get("id") == trade_id:
            return {
                "trade_id": trade_id,
                "notes": trade.get("notes", ""),
                "notes_updated_at": trade.get("notes_updated_at", "")
            }
    
    # Check closed trades
    for trade in state.autonomous_trader_v2.closed_trades:
        if trade.get("id") == trade_id:
            return {
                "trade_id": trade_id,
                "notes": trade.get("notes", ""),
                "notes_updated_at": trade.get("notes_updated_at", "")
            }
    
    return {"error": "Trade not found", "trade_id": trade_id}, 404


@router.post("/trading/v2/trail/{symbol}")
async def api_trading_v2_trail(symbol: str, trail_pct: float = 3.0):
    symbol_full = symbol.upper() + "/USDT"
    trail_pct = max(1, min(20, trail_pct))
    for trade in state.autonomous_trader_v2.open_trades:
        if trade.get("symbol") == symbol_full:
            ticker = await state.market_intel.get_ticker(symbol_full)
            current_price = ticker.get("price", 0) if "error" not in ticker else 0
            direction = trade.get("direction", "")
            new_stop = current_price * (1 - trail_pct / 100) if direction == "LONG" else current_price * (1 + trail_pct / 100)
            old_stop = trade.get("trail_stop", 0)
            trade["trail_stop"] = new_stop
            trade["trail_pct"] = trail_pct
            return {"status": "updated", "symbol": symbol_full, "old_stop": old_stop, "new_stop": new_stop, "trail_pct": trail_pct}
    return {"error": f"No open trade found for {symbol_full}"}


@router.post("/trading/v2/tp/{symbol}")
async def api_trading_v2_tp(symbol: str, price: float):
    symbol_full = symbol.upper() + "/USDT"
    for trade in state.autonomous_trader_v2.open_trades:
        if trade.get("symbol") == symbol_full:
            old_tp = trade.get("target_price", 0)
            trade["target_price"] = price
            return {"status": "updated", "symbol": symbol_full, "old_tp": old_tp, "new_tp": price}
    return {"error": f"No open trade found for {symbol_full}"}


# Dual Engine
@router.get("/dual/stats")
async def api_dual_stats():
    return state.dual_engine.get_stats()


@router.post("/dual/toggle")
async def api_dual_toggle(active: bool = True):
    state.dual_engine.active = active
    return {"status": "ok", "active": active}


@router.post("/dual/day-trader/toggle")
async def api_dual_day_trader_toggle(active: bool = True):
    state.dual_engine.day_trader.active = active
    return {"status": "ok", "day_trader_active": active}


@router.post("/dual/long-term/toggle")
async def api_dual_long_term_toggle(active: bool = True):
    state.dual_engine.long_term.active = active
    return {"status": "ok", "long_term_active": active}


@router.post("/dual/day-trader/confidence")
async def api_dual_day_trader_confidence(min_conf: int = 75):
    min_conf = max(65, min(95, min_conf))
    state.dual_engine.day_trader.min_confidence = min_conf
    return {"status": "ok", "day_trader_min_confidence": min_conf}


@router.post("/dual/long-term/confidence")
async def api_dual_long_term_confidence(min_conf: int = 88):
    min_conf = max(75, min(95, min_conf))
    state.dual_engine.long_term.min_confidence = min_conf
    return {"status": "ok", "long_term_min_confidence": min_conf}


# Free Will v2
@router.get("/freewill/stats")
async def api_freewill_stats():
    return await state.free_will_v2.get_stats()


@router.get("/freewill/scan/{symbol}")
async def api_freewill_scan_symbol(symbol: str, timeframe: str = "1h"):
    return await state.free_will_v2.analyze_setup_full(symbol.upper() + "/USDT", timeframe)


@router.post("/freewill/toggle")
async def api_freewill_toggle(active: bool = True):
    state.free_will_v2.active = active
    return {"active": state.free_will_v2.active}


@router.post("/freewill/confidence")
async def api_freewill_confidence(min_conf: int = 80):
    state.free_will_v2.min_confidence = max(70, min(95, min_conf))
    return {"min_confidence": state.free_will_v2.min_confidence}


# Strategy Health
@router.get("/strategy-health/status")
async def api_strategy_health():
    return state.strategy_health.get_status()


@router.get("/strategy-health/ranking")
async def api_strategy_health_ranking():
    return {"ranking": state.strategy_health.get_ranking()}


@router.post("/strategy-health/record")
async def api_strategy_health_record(request: Request):
    data = await request.json()
    return state.strategy_health.record_trade(data.get("strategy_id", ""), data.get("pnl_pct", 0), data.get("symbol", ""))


@router.post("/strategy-health/unbench/{strategy_id}")
async def api_strategy_unbench(strategy_id: str):
    return state.strategy_health.force_unbench(strategy_id)


# Alerts
@router.get("/alerts/stats")
async def api_alerts_stats():
    return state.price_alert_system.get_stats()


@router.get("/alerts/dashboard")
async def api_alerts_dashboard(limit: int = 20, unread_only: bool = False):
    return {
        "alerts": state.price_alert_system.get_dashboard_alerts(limit, unread_only),
        "total": len(state.price_alert_system.dashboard_alerts),
        "unread": len([a for a in state.price_alert_system.dashboard_alerts if not a.get("read")])
    }


@router.post("/alerts/mark-read/{dashboard_id}")
async def api_alerts_mark_read(dashboard_id: str):
    return {"success": state.price_alert_system.mark_alert_read(dashboard_id)}


@router.post("/alerts/clear")
async def api_alerts_clear():
    state.price_alert_system.clear_all_dashboard_alerts()
    return {"success": True}


@router.post("/alerts/add")
async def api_alerts_add(request: Request):
    data = await request.json()
    symbol = data.get("symbol", "BTC") + "/USDT"
    target_price = data.get("target_price", 0)
    direction = data.get("direction", "above")
    chat_id = data.get("chat_id")
    if not target_price:
        return {"error": "target_price required"}
    return state.price_alert_system.add_price_alert(symbol, target_price, direction, chat_id)


@router.delete("/alerts/{alert_id}")
async def api_alerts_remove(alert_id: str):
    return state.price_alert_system.remove_alert(alert_id)


@router.get("/alerts/custom")
async def api_alerts_list(chat_id: int = None):
    return {"alerts": state.price_alert_system.list_alerts(chat_id)}


@router.post("/alerts/threshold")
async def api_alerts_threshold(request: Request):
    data = await request.json()
    for key, value in data.items():
        if key in state.price_alert_system.auto_alert_thresholds:
            state.price_alert_system.auto_alert_thresholds[key] = value
    return {"thresholds": state.price_alert_system.auto_alert_thresholds}


# MEXC & Bot
# MEXC & Bot
# Note: /api/mexc/live remains in server.py to avoid circular import with get_mexc_orderbook

@router.get("/bot/stats")
async def api_stats():
    total = await state.db.chat_messages.count_documents({})
    unique = len(await state.db.chat_messages.distinct("chat_id"))
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await state.db.chat_messages.count_documents({"timestamp": {"$gte": today}})
    freewill = await state.db.user_settings.count_documents({"free_will": True})
    return {
        "total_messages": total, "unique_users": unique,
        "messages_today": today_count, "freewill_users": freewill,
        "active_users": len(state.chat_ids)
    }


@router.get("/bot/messages")
async def api_messages(limit: int = 50, context: str = None):
    query = {"context": context} if context else {}
    return await state.db.chat_messages.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


@router.get("/bot/test")
async def api_test():
    try:
        btc = await state.market_intel.get_technical_analysis("BTCUSDT", "1h")
        binance_ok = "error" not in btc
        chat = LlmChat(api_key=state.emergent_key, session_id="test", system_message="Test").with_model("openai", "gpt-4o-mini")
        await chat.send_message(UserMessage(text="Hi"))
        return {"status": "success", "llm": True, "binance": binance_ok, "mexc": bool(os.environ.get('MEXC_API_KEY')), "telegram": bool(os.environ.get('TELEGRAM_TOKEN')), "users": len(state.chat_ids)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# User Profile
@router.get("/user/profile")
async def api_user_profile(chat_id: int = None):
    if not chat_id and state.chat_ids:
        chat_id = list(state.chat_ids)[0]
    elif not chat_id:
        return {"error": "No users found"}
    return await state.user_profiler.get_profile_summary(chat_id)


@router.get("/user/profile/{chat_id}")
async def api_user_profile_by_id(chat_id: int):
    return await state.user_profiler.get_profile_summary(chat_id)


@router.post("/user/profile/{chat_id}/fact")
async def api_add_user_fact(chat_id: int, request: Request):
    data = await request.json()
    fact = data.get("fact", "")
    category = data.get("category", "general")
    if not fact:
        return {"error": "Fact is required"}
    await state.user_profiler.add_key_fact(chat_id, fact, category)
    return {"status": "ok", "fact": fact}


# Voice
@router.post("/voice/respond")
async def api_voice_respond(request: Request):
    try:
        data = await request.json()
        user_text = data.get("text", "")
        voice = data.get("voice", "guy")
        if not user_text:
            return {"error": "No text provided"}
        voice_llm = LlmChat(
            api_key=state.emergent_key, session_id="voice-conversation",
            system_message="You are Aeon, a confident trading buddy having a voice conversation. Keep responses SHORT (1-3 sentences). Be conversational. No bullet points or lists. No markdown. Speak like talking to a friend. Be direct and insightful."
        ).with_model("openai", "gpt-4o-mini")
        aeon_text = await voice_llm.send_message(UserMessage(text=user_text))
        speech = await generate_speech(aeon_text, voice)
        if not speech.get("success"):
            return {"error": speech.get("error", "TTS failed")}
        return {"success": True, "text": aeon_text, "audio": speech.get("audio"), "format": "mp3"}
    except Exception as e:
        logger.error(f"Voice respond error: {e}")
        return {"error": str(e)}


# Learning
@router.get("/learning/stats")
async def api_learning_stats():
    return await state.learning_system.get_prediction_stats()


@router.get("/learning/open")
async def api_open_predictions():
    return await state.learning_system.get_open_predictions()
