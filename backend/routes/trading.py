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
from paper_trading import ACCOUNTS
import anthropic

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
    import asyncio
    try:
        return await asyncio.wait_for(state.autonomous_trader_v2.scan_all_markets(), timeout=20.0)
    except asyncio.TimeoutError:
        return []
    except Exception as e:
        logger.warning(f"Opportunities scan failed: {e}")
        return []


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


@router.get("/trading/v2/settings")
async def api_get_v2_settings():
    """Get all V2.1 trading settings"""
    trader = state.autonomous_trader_v2
    return {
        "min_confidence": trader.min_confidence,
        "min_confirmations": trader.min_confirmations,
        "min_rr_ratio": trader.min_rr_ratio,
        "max_open_trades": trader.max_open_trades,
        "ema_200_filter_enabled": trader.ema_200_filter_enabled,
        "adx_filter_enabled": trader.adx_filter_enabled,
        "volume_filter_enabled": trader.volume_filter_enabled,
        "session_filter_enabled": trader.session_filter_enabled,
        "position_scaling_enabled": trader.position_scaling_enabled,
        "active": trader.active,
    }


@router.post("/trading/v2/settings")
async def api_update_v2_settings(request: Request):
    """Update V2.1 trading settings"""
    try:
        data = await request.json()
        trader = state.autonomous_trader_v2
        
        # Update settings if provided
        if "min_confidence" in data:
            trader.min_confidence = max(60, min(98, data["min_confidence"]))
        if "min_confirmations" in data:
            trader.min_confirmations = max(1, min(6, data["min_confirmations"]))
        if "min_rr_ratio" in data:
            trader.min_rr_ratio = max(1.0, min(5.0, data["min_rr_ratio"]))
        if "max_open_trades" in data:
            trader.max_open_trades = max(1, min(20, data["max_open_trades"]))
        if "ema_200_filter_enabled" in data:
            trader.ema_200_filter_enabled = data["ema_200_filter_enabled"]
        if "adx_filter_enabled" in data:
            trader.adx_filter_enabled = data["adx_filter_enabled"]
        if "volume_filter_enabled" in data:
            trader.volume_filter_enabled = data["volume_filter_enabled"]
        if "session_filter_enabled" in data:
            trader.session_filter_enabled = data["session_filter_enabled"]
        if "position_scaling_enabled" in data:
            trader.position_scaling_enabled = data["position_scaling_enabled"]
        if "active" in data:
            trader.active = data["active"]
        
        # Save to database
        await trader.save_settings()
        
        return {
            "success": True,
            "message": "Settings updated",
            "settings": {
                "min_confidence": trader.min_confidence,
                "min_confirmations": trader.min_confirmations,
                "min_rr_ratio": trader.min_rr_ratio,
                "max_open_trades": trader.max_open_trades,
                "ema_200_filter_enabled": trader.ema_200_filter_enabled,
                "adx_filter_enabled": trader.adx_filter_enabled,
                "volume_filter_enabled": trader.volume_filter_enabled,
                "session_filter_enabled": trader.session_filter_enabled,
                "position_scaling_enabled": trader.position_scaling_enabled,
                "active": trader.active,
            }
        }
    except Exception as e:
        logger.error(f"Settings update error: {e}")
        return {"error": str(e)}


# Trading Mode Presets
TRADING_MODES = {
    "yolo": {
        "name": "YOLO Mode",
        "description": "Maximum trading activity. No filters. Trades everything.",
        "min_confidence": 50,
        "min_confirmations": 1,
        "min_rr_ratio": 1.0,
        "max_open_trades": 50,
        "ema_200_filter_enabled": False,
        "adx_filter_enabled": False,
        "volume_filter_enabled": False,
        "session_filter_enabled": False,
        "stop_loss_pct": 0.10,  # 10% SL (much wider)
        "take_profit_pct": 0.05,  # 5% TP
        "default_leverage": 5,  # Low leverage to avoid liquidation
    },
    "easy": {
        "name": "Easy Mode",
        "description": "More trades, lower requirements. Good for learning/testing.",
        "min_confidence": 70,
        "min_confirmations": 2,
        "min_rr_ratio": 1.5,
        "max_open_trades": 10,
        "ema_200_filter_enabled": False,
        "adx_filter_enabled": False,
        "volume_filter_enabled": True,
        "session_filter_enabled": False,
        "stop_loss_pct": 0.03,  # 3% SL
        "take_profit_pct": 0.06,  # 6% TP
        "default_leverage": 10,
    },
    "balanced": {
        "name": "Balanced Mode",
        "description": "Moderate filters. Balance between quantity and quality.",
        "min_confidence": 80,
        "min_confirmations": 3,
        "min_rr_ratio": 2.0,
        "max_open_trades": 7,
        "ema_200_filter_enabled": True,
        "adx_filter_enabled": False,
        "volume_filter_enabled": True,
        "session_filter_enabled": False,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
        "default_leverage": 15,
    },
    "strict": {
        "name": "Strict Mode",
        "description": "Fewer but higher quality trades. Best for experienced traders.",
        "min_confidence": 85,
        "min_confirmations": 4,
        "min_rr_ratio": 2.5,
        "max_open_trades": 5,
        "ema_200_filter_enabled": True,
        "adx_filter_enabled": True,
        "volume_filter_enabled": True,
        "session_filter_enabled": True,
        "stop_loss_pct": 0.015,
        "take_profit_pct": 0.03,
        "default_leverage": 20,
    },
    "elite": {
        "name": "Elite Mode",
        "description": "Ultra-selective. Only the best setups. Highest win rate target.",
        "min_confidence": 90,
        "min_confirmations": 5,
        "min_rr_ratio": 3.0,
        "max_open_trades": 3,
        "ema_200_filter_enabled": True,
        "adx_filter_enabled": True,
        "volume_filter_enabled": True,
        "session_filter_enabled": True,
    }
}


@router.get("/trading/modes")
async def api_get_trading_modes():
    """Get all available trading modes"""
    trader = state.autonomous_trader_v2
    current_mode = "custom"
    
    # Detect current mode
    for mode_id, mode in TRADING_MODES.items():
        if (trader.min_confidence == mode["min_confidence"] and
            trader.min_confirmations == mode["min_confirmations"] and
            trader.min_rr_ratio == mode["min_rr_ratio"]):
            current_mode = mode_id
            break
    
    return {
        "current_mode": current_mode,
        "modes": TRADING_MODES,
        "current_settings": {
            "min_confidence": trader.min_confidence,
            "min_confirmations": trader.min_confirmations,
            "min_rr_ratio": trader.min_rr_ratio,
            "max_open_trades": trader.max_open_trades,
        }
    }


@router.post("/trading/mode/{mode_id}")
async def api_set_trading_mode(mode_id: str):
    """Set trading mode preset"""
    if mode_id not in TRADING_MODES:
        return {"error": f"Invalid mode. Available: {list(TRADING_MODES.keys())}"}
    
    mode = TRADING_MODES[mode_id]
    trader = state.autonomous_trader_v2
    
    # Apply all mode settings
    trader.min_confidence = mode["min_confidence"]
    trader.min_confirmations = mode["min_confirmations"]
    trader.min_rr_ratio = mode["min_rr_ratio"]
    trader.max_open_trades = mode["max_open_trades"]
    trader.ema_200_filter_enabled = mode["ema_200_filter_enabled"]
    trader.adx_filter_enabled = mode["adx_filter_enabled"]
    trader.volume_filter_enabled = mode["volume_filter_enabled"]
    trader.session_filter_enabled = mode["session_filter_enabled"]
    
    # Also update Free Will v2 to match the mode
    if state.free_will_v2:
        state.free_will_v2.min_confidence = mode["min_confidence"]
        state.free_will_v2.min_confirmations = mode["min_confirmations"]
    
    # Save to database
    await trader.save_settings()
    
    return {
        "success": True,
        "mode": mode_id,
        "name": mode["name"],
        "description": mode["description"],
        "settings_applied": {
            "min_confidence": trader.min_confidence,
            "min_confirmations": trader.min_confirmations,
            "min_rr_ratio": trader.min_rr_ratio,
            "max_open_trades": trader.max_open_trades,
            "ema_200_filter_enabled": trader.ema_200_filter_enabled,
            "adx_filter_enabled": trader.adx_filter_enabled,
            "volume_filter_enabled": trader.volume_filter_enabled,
            "session_filter_enabled": trader.session_filter_enabled,
        }
    }




@router.get("/trading/v2/open")
async def api_trading_v2_open():
    # In-memory v2 trades
    v2_open = list(state.autonomous_trader_v2.open_trades)

    # Paper trades from MongoDB
    paper_open = []
    try:
        if state.db is not None:
            raw = await state.db.paper_trades.find({"status": "open"}).to_list(200)
            for t in raw:
                t.pop("_id", None)
                paper_open.append(t)
    except Exception as e:
        logger.warning(f"Could not load paper open trades: {e}")

    all_open = v2_open + paper_open
    return {
        "open_trades": all_open,
        "total_open": len(all_open),
        "v2_open": len(v2_open),
        "paper_open": len(paper_open),
    }


@router.get("/trading/v2/closed")
async def api_trading_v2_closed():
    # In-memory v2 trades (also in DB via load_settings)
    v2_closed = list(state.autonomous_trader_v2.closed_trades[-20:])

    # Paper trades from MongoDB — normalize fields for Trading history tab
    paper_closed = []
    try:
        if state.db is not None:
            raw = await state.db.paper_trades.find(
                {"status": "closed"},
                sort=[("closed_at", -1)]
            ).limit(2000).to_list(2000)
            for t in raw:
                t.pop("_id", None)
                # Normalize realized_pnl -> pnl_pct so Trading history tab renders correctly
                if "pnl_pct" not in t or t.get("pnl_pct") is None:
                    realized = t.get("realized_pnl", 0) or 0
                    margin = t.get("margin", 1) or 1
                    t["pnl_pct"] = round((realized / margin) * 100, 2)
                # Normalize exit_reason field
                if "exit_reason" not in t:
                    t["exit_reason"] = t.get("close_reason", "CLOSED")
                paper_closed.append(t)
    except Exception as e:
        logger.warning(f"Could not load paper closed trades: {e}")

    all_closed = v2_closed + paper_closed
    return {
        "closed_trades": all_closed,
        "total_closed": len(all_closed),
        "v2_closed": len(v2_closed),
        "paper_closed": len(paper_closed),
    }


@router.get("/trades/closed")
async def api_trades_closed():
    """Closed trades for Trade Analytics — v2 + paper trades from DB"""
    trades = []

    # v2 closed (in-memory)
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
            "style": t.get("style", "engine_v2"),
            "notes": t.get("notes", ""),
            "notes_updated_at": t.get("notes_updated_at", ""),
            "source": "autonomous_v2",
        })

    # Paper trades from MongoDB
    try:
        if state.db is not None:
            raw = await state.db.paper_trades.find(
                {"status": "closed"},
                sort=[("closed_at", -1)]
            ).limit(2000).to_list(2000)
            for t in raw:
                pnl = t.get("pnl_pct") or t.get("realized_pnl_pct") or 0
                # Some records store realized_pnl in dollars, convert to pct via margin
                if not pnl and t.get("realized_pnl") and t.get("margin"):
                    pnl = round((t["realized_pnl"] / t["margin"]) * 100, 2)
                trades.append({
                    "id": t.get("id", ""),
                    "symbol": t.get("symbol", ""),
                    "direction": t.get("direction", ""),
                    "entry_price": t.get("entry_price", 0),
                    "exit_price": t.get("exit_price", 0),
                    "pnl_pct": float(pnl),
                    "closed_at": str(t.get("closed_at", t.get("exit_time", ""))),
                    "timestamp": str(t.get("closed_at", t.get("exit_time", ""))),
                    "exit_reason": t.get("close_reason", t.get("exit_reason", "")),
                    "style": t.get("strategy", t.get("account_id", "paper")),
                    "notes": t.get("notes", ""),
                    "notes_updated_at": t.get("notes_updated_at", ""),
                    "account": t.get("account_name", t.get("account_id", "")),
                    "leverage": t.get("leverage", 1),
                    "source": "paper_trading",
                    "engine": t.get("signal_data", {}).get("engine", ""),
                    "confidence": t.get("signal_data", {}).get("confidence"),
                })
    except Exception as e:
        logger.warning(f"Could not load paper closed trades for analytics: {e}")

    # Sort all by closed_at desc
    def sort_key(t):
        ts = t.get("closed_at") or ""
        return str(ts)

    trades.sort(key=sort_key, reverse=True)
    return {"trades": trades, "total": len(trades)}


@router.get("/trades/export")
async def api_trades_export():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Symbol", "Direction", "Entry", "Exit", "PnL%", "Exit Reason", "Style", "Account", "Leverage", "Source"])

    # v2 trades
    for t in state.autonomous_trader_v2.closed_trades:
        ts = t.get("exit_time", t.get("closed_at", ""))
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        writer.writerow([
            str(ts), t.get("symbol", ""), t.get("direction", ""),
            t.get("entry_price", 0), t.get("exit_price", 0),
            round(t.get("pnl_pct", 0), 2), t.get("exit_reason", ""), t.get("style", ""),
            "", "", "autonomous_v2",
        ])

    # Paper trades from DB
    try:
        if state.db is not None:
            raw = await state.db.paper_trades.find({"status": "closed"}).to_list(500)
            for t in raw:
                pnl = t.get("pnl_pct") or 0
                if not pnl and t.get("realized_pnl") and t.get("margin"):
                    pnl = round((t["realized_pnl"] / t["margin"]) * 100, 2)
                writer.writerow([
                    str(t.get("closed_at", "")), t.get("symbol", ""), t.get("direction", ""),
                    t.get("entry_price", 0), t.get("exit_price", 0),
                    round(float(pnl), 2), t.get("close_reason", ""),
                    t.get("strategy", ""), t.get("account_name", ""), t.get("leverage", 1),
                    "paper_trading",
                ])
    except Exception as e:
        logger.warning(f"Could not export paper trades: {e}")

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

    # Read from MongoDB paper_trades (survives restarts)
    try:
        if state.db is not None:
            closed = await state.db.paper_trades.find(
                {"status": "closed", "realized_pnl": {"$exists": True, "$ne": None}},
                {"symbol": 1, "direction": 1, "realized_pnl": 1, "closed_at": 1, "close_reason": 1}
            ).sort("closed_at", 1).limit(200).to_list(200)
            for trade in closed:
                pnl = trade.get("realized_pnl", 0) or 0
                cumulative_pnl += pnl
                history.append({
                    "timestamp": str(trade.get("closed_at", "")),
                    "symbol": trade.get("symbol", ""),
                    "pnl": round(pnl, 2),
                    "cumulative_pnl": round(cumulative_pnl, 2),
                    "direction": trade.get("direction", ""),
                    "result": "WIN" if pnl > 0 else "LOSS"
                })
    except Exception as e:
        logger.warning(f"pnl-history DB read failed: {e}")

    # Fall back to in-memory if DB empty
    if not history:
        for trade in state.autonomous_trader_v2.closed_trades:
            pnl = trade.get("pnl_pct", 0) or 0
            cumulative_pnl += pnl
            history.append({
                "timestamp": trade.get("exit_time", trade.get("closed_at", datetime.now(timezone.utc))).isoformat() if isinstance(trade.get("exit_time"), datetime) else str(trade.get("exit_time", "")),
                "symbol": trade.get("symbol", ""),
                "pnl": pnl,
                "cumulative_pnl": round(cumulative_pnl, 2),
                "direction": trade.get("direction", ""),
                "result": "WIN" if pnl > 0 else "LOSS"
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

    # 1) In-memory v2 engine trades
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

    # 2) Paper trades from MongoDB (PRO/STARTER accounts) — same source as /paper/positions
    try:
        if state.db is not None:
            raw = await state.db.paper_trades.find({"status": "open"}).to_list(200)
            for t in raw:
                # Save _id before popping — used as stable position ID
                mongo_id = str(t.pop("_id", ""))
                symbol = t.get("symbol", "")
                entry = t.get("entry_price", 0)
                direction = t.get("direction", "")
                account_id = t.get("account_id", "")
                # Use mongo_id as primary — unique even when same symbol has multiple open records
                stable_id = mongo_id or f"{account_id}_{symbol}"
                # Fetch live price for accurate PnL
                try:
                    ticker = await state.market_intel.get_ticker(symbol)
                    current_price = ticker.get("price", 0) if ticker and "error" not in ticker else (t.get("current_price") or entry)
                except Exception:
                    current_price = t.get("current_price") or entry
                if entry and current_price:
                    pnl_pct = ((current_price - entry) / entry) * 100 if direction == "LONG" else ((entry - current_price) / entry) * 100
                else:
                    pnl_pct = t.get("unrealized_pnl_pct", 0) or 0
                total_pnl += pnl_pct
                stop_price = t.get("stop_loss") or t.get("stop_price")
                liq_price = t.get("liquidation_price")
                margin = t.get("margin", 0)
                leverage = t.get("leverage", 1)
                position_size = t.get("position_size_usd") or t.get("position_size") or (margin * leverage)
                unrealized_pnl = round(margin * (pnl_pct / 100), 2) if margin else 0
                # SL-to-liq gap: for LONG, gap = (stop - liq) / liq * 100; for SHORT, gap = (liq - stop) / stop * 100
                sl_liq_gap_pct = None
                if stop_price and liq_price and liq_price > 0 and stop_price > 0:
                    if direction == "LONG":
                        sl_liq_gap_pct = round((stop_price - liq_price) / liq_price * 100, 2)
                    else:
                        sl_liq_gap_pct = round((liq_price - stop_price) / stop_price * 100, 2)
                positions.append({
                    "id": stable_id,
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry,
                    "current_price": current_price,
                    "stop_price": stop_price,
                    "target_price": t.get("take_profit") or t.get("target_price"),
                    "liquidation_price": liq_price,  # normalized field name
                    "liq_price": liq_price,           # kept for backward compat
                    "sl_liq_gap_pct": sl_liq_gap_pct,
                    "trail_stop": t.get("trail_stop"),
                    "pnl_pct": round(pnl_pct, 2),
                    "unrealized_pnl": unrealized_pnl,
                    "confidence": t.get("confidence"),
                    "timeframe": t.get("timeframe"),
                    "trade_type": t.get("trade_type", "SWING"),
                    "leverage": leverage,
                    "margin": margin,
                    "position_size": position_size,
                    "entry_time": t.get("opened_at") or t.get("entry_time", ""),
                    "opened_at": t.get("opened_at") or t.get("entry_time", ""),
                    "confirmations": t.get("confirmations", [])[:3],
                    "strategy": t.get("strategy"),
                    "account_id": account_id,
                })
    except Exception as e:
        logger.warning(f"Could not load paper open trades for live-positions: {e}")

    return {"positions": positions, "total_positions": len(positions), "total_pnl_pct": round(total_pnl, 2), "data_source": "MEXC Live"}


@router.get("/positions")
async def api_positions():
    """
    Unified positions endpoint — all open paper positions, normalized shape.
    Source of truth: paper_accounts.positions (embedded array, status=open).
    This matches what close_position() operates on — no stale orphan records.
    Prices fetched in ONE MEXC public REST request (~2s, no auth required).
    """
    from datetime import datetime, timezone as tz

    positions = []
    if state.db is None:
        return {"positions": [], "total": 0, "total_pnl": 0}

    # ── Read from paper_accounts (the real source of truth) ──────────────────
    try:
        accounts = await state.db.paper_accounts.find({}).to_list(50)
    except Exception as e:
        logger.warning(f"[/positions] DB error: {e}")
        return {"positions": [], "total": 0, "total_pnl": 0}

    # Collect all open embedded positions, tagged with their account_id
    raw = []
    for acc in accounts:
        account_id = acc.get("_id", "")
        for pos in acc.get("positions", []):
            if pos.get("status") == "open":
                pos["_account_id"] = account_id
                raw.append(pos)

    if not raw:
        return {"positions": [], "total": 0, "total_pnl": 0}

    # ── Fetch all prices in ONE MEXC public REST request ─────────────────────
    live_prices: dict = {}
    try:
        import httpx
        unique_symbols = list({t.get("symbol", "") for t in raw if t.get("symbol")})
        mexc_to_internal: dict = {}
        for sym in unique_symbols:
            mexc_to_internal[sym.replace("/", "")] = sym
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get("https://api.mexc.com/api/v3/ticker/price")
            if resp.status_code == 200:
                for item in resp.json():
                    mexc_sym = item.get("symbol", "")
                    if mexc_sym in mexc_to_internal:
                        try:
                            live_prices[mexc_to_internal[mexc_sym]] = float(item["price"])
                        except (KeyError, ValueError):
                            pass
    except Exception:
        pass

    now = datetime.now(tz.utc)

    for t in raw:
        # Stable ID: use the embedded position's own `id` field (timestamp-based,
        # guaranteed unique per account). Falls back to account+symbol.
        pos_id = t.get("id") or f"{t['_account_id']}_{t.get('symbol', '')}"
        symbol = t.get("symbol", "")
        account_id = t["_account_id"]
        direction = t.get("direction", "")
        entry = t.get("entry_price", 0)
        leverage = t.get("leverage", 1)
        margin = t.get("margin", 0)
        position_size = t.get("position_size_usd") or t.get("position_size") or (margin * leverage)

        live_price = live_prices.get(symbol, 0)
        current_price = live_price if live_price else (t.get("current_price") or entry)
        price_is_live = bool(live_price and live_price != entry)

        if entry and current_price:
            raw_pnl_pct = ((current_price - entry) / entry * 100) if direction == "LONG" else ((entry - current_price) / entry * 100)
        else:
            raw_pnl_pct = t.get("unrealized_pnl_pct", 0) or 0
        leveraged_pnl = round(raw_pnl_pct * leverage, 2)
        unrealized_pnl = round(margin * (raw_pnl_pct / 100), 2) if margin else 0

        opened_at = t.get("opened_at") or t.get("entry_time", "")
        duration_min = 0
        try:
            open_dt = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00")) if opened_at else None
            if open_dt and open_dt.tzinfo is None:
                open_dt = open_dt.replace(tzinfo=tz.utc)
            if open_dt:
                duration_min = max(0, int((now - open_dt).total_seconds() / 60))
        except Exception:
            pass

        positions.append({
            "id": pos_id,
            "symbol": symbol,
            "base": symbol.replace("/USDT", ""),
            "direction": direction,
            "entry_price": entry,
            "current_price": current_price,
            "leverage": leverage,
            "margin": margin,
            "position_size": position_size,
            "unrealized_pnl": unrealized_pnl,
            "pnl_pct": leveraged_pnl,
            "roe_pct": leveraged_pnl,
            "liquidation_price": t.get("liquidation_price") or t.get("liq_price"),
            "stop_price": t.get("stop_loss") or t.get("stop_price"),
            "target_price": t.get("take_profit") or t.get("target_price"),
            "engine": t.get("strategy") or "AEON",
            "account_id": account_id,
            "opened_at": str(opened_at),
            "duration_min": duration_min,
            "timeframe": t.get("timeframe"),
            "trade_type": t.get("trade_type", "SWING"),
            "price_is_live": price_is_live,
        })

    total_pnl = round(sum(p["pnl_pct"] for p in positions), 2)
    return {"positions": positions, "total": len(positions), "total_pnl": total_pnl}


@router.post("/positions/close")
async def api_positions_close(request: Request):
    """
    Close a single open position.
    Body: { "symbol": "BTC/USDT", "account_id": "PRO" }
    """
    body = await request.json()
    symbol = body.get("symbol", "")
    account_id = body.get("account_id", "")
    if not symbol or not account_id:
        return {"error": "symbol and account_id are required"}
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    clean_symbol = symbol if "/" in symbol else f"{symbol}/USDT"
    # Fetch price via MEXC public REST (no API key required — avoids ccxt executor timeout)
    current_price = 0.0
    try:
        import httpx
        mexc_sym = clean_symbol.replace("/", "")
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://api.mexc.com/api/v3/ticker/price",
                params={"symbol": mexc_sym},
            )
            if resp.status_code == 200:
                current_price = float(resp.json().get("price", 0) or 0)
    except Exception:
        pass
    if not current_price:
        return {"error": f"Could not fetch live price for {clean_symbol}"}
    result = await state.paper_trading.close_position(account_id.upper(), clean_symbol, current_price)
    return result


@router.post("/trading/v2/confidence")
async def api_trading_v2_confidence(min_conf: int = 85):
    state.autonomous_trader_v2.min_confidence = max(70, min(98, min_conf))
    await state.autonomous_trader_v2.save_settings()
    return {"min_confidence": state.autonomous_trader_v2.min_confidence}


@router.post("/trading/v2/close/{symbol}")
async def api_trading_v2_close(symbol: str):
    symbol_full = symbol.upper() + "/USDT"

    # Find index first (never mutate a list while iterating it)
    trade_index = None
    for i, trade in enumerate(state.autonomous_trader_v2.open_trades):
        if trade.get("symbol") == symbol_full:
            trade_index = i
            break  # stop — only close the first match

    if trade_index is None:
        return {"error": f"No open trade found for {symbol_full}"}

    # Fetch price before mutating state
    ticker = await state.market_intel.get_ticker(symbol_full)
    current_price = ticker.get("price", 0) if ticker and "error" not in ticker else 0

    # Guard: index may be stale if a concurrent evaluate_trades() ran
    try:
        closed_trade = state.autonomous_trader_v2.open_trades.pop(trade_index)
    except IndexError:
        return {"error": f"Trade for {symbol_full} was already closed"}

    entry = closed_trade.get("entry_price", 0)
    direction = closed_trade.get("direction", "")
    pnl = 0
    if entry and current_price:
        pnl = ((current_price - entry) / entry) * 100 if direction == "LONG" else ((entry - current_price) / entry) * 100

    closed_trade["exit_price"] = current_price
    closed_trade["pnl_pct"] = pnl
    closed_trade["exit_reason"] = "API_MANUAL_CLOSE"
    closed_trade["closed_at"] = datetime.now(timezone.utc).isoformat()
    state.autonomous_trader_v2.closed_trades.append(closed_trade)
    return {"status": "closed", "trade": closed_trade}


@router.get("/trading/exposure")
async def api_trading_exposure():
    """Open exposure summary from memory engine — pair concentration, LONG/SHORT bias."""
    from memory_engine import get_memory_engine
    mem = get_memory_engine()
    if mem is None:
        return {"error": "Memory engine not initialized", "total_open": 0}
    return await mem.get_open_exposure()


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


@router.post("/freewill/confirmations")
async def api_freewill_confirmations(min_confirms: int = 3):
    """Set Free Will minimum confirmations (1-5)"""
    state.free_will_v2.min_confirmations = max(1, min(5, min_confirms))
    return {"min_confirmations": state.free_will_v2.min_confirmations}


@router.post("/freewill/settings")
async def api_freewill_settings(request: Request):
    """Update all Free Will settings at once"""
    try:
        data = await request.json()
        fw = state.free_will_v2
        
        if "min_confidence" in data:
            fw.min_confidence = max(60, min(95, data["min_confidence"]))
        if "min_confirmations" in data:
            fw.min_confirmations = max(1, min(5, data["min_confirmations"]))
        if "active" in data:
            fw.active = data["active"]
        
        return {
            "success": True,
            "settings": {
                "min_confidence": fw.min_confidence,
                "min_confirmations": fw.min_confirmations,
                "active": fw.active
            }
        }
    except Exception as e:
        return {"error": str(e)}


# Strategy Health
@router.get("/strategy-health/status")
async def api_strategy_health():
    return state.strategy_health.get_status()


# VWAP Scalper Routes
@router.get("/vwap-scalper/stats")
async def api_vwap_scalper_stats():
    """Get VWAP Scalper statistics"""
    if not state.vwap_scalper:
        return {"error": "VWAP Scalper not initialized"}
    return state.vwap_scalper.get_stats()


@router.get("/vwap-scalper/scan")
async def api_vwap_scalper_scan():
    """Run immediate scan for VWAP signals"""
    if not state.vwap_scalper:
        return {"error": "VWAP Scalper not initialized"}
    signals = await state.vwap_scalper.scan_all_symbols()
    return {"signals": signals, "count": len(signals)}


@router.get("/vwap-scalper/analyze/{symbol}")
async def api_vwap_scalper_analyze(symbol: str):
    """Analyze a specific symbol for VWAP signals"""
    if not state.vwap_scalper:
        return {"error": "VWAP Scalper not initialized"}
    signal = await state.vwap_scalper.analyze_symbol(symbol.upper() + "/USDT")
    return signal or {"message": "No signal for this symbol", "symbol": symbol.upper() + "/USDT"}


@router.post("/vwap-scalper/toggle")
async def api_vwap_scalper_toggle(active: bool = True):
    """Toggle VWAP Scalper on/off"""
    if not state.vwap_scalper:
        return {"error": "VWAP Scalper not initialized"}
    state.vwap_scalper.active = active
    return {"active": state.vwap_scalper.active, "message": f"VWAP Scalper {'activated' if active else 'paused'}"}


@router.post("/vwap-scalper/settings")
async def api_vwap_scalper_settings(request: Request):
    """Update VWAP Scalper settings"""
    if not state.vwap_scalper:
        return {"error": "VWAP Scalper not initialized"}
    
    data = await request.json()
    scalper = state.vwap_scalper
    
    if "ema_fast" in data:
        scalper.ema_fast = max(5, min(20, data["ema_fast"]))
    if "ema_slow" in data:
        scalper.ema_slow = max(15, min(50, data["ema_slow"]))
    if "rsi_period" in data:
        scalper.rsi_period = max(7, min(21, data["rsi_period"]))
    if "stop_loss_pct" in data:
        scalper.stop_loss_pct = max(0.001, min(0.01, data["stop_loss_pct"]))
    if "take_profit_pct" in data:
        scalper.take_profit_pct = max(0.002, min(0.02, data["take_profit_pct"]))
    
    return {
        "success": True,
        "settings": {
            "ema_fast": scalper.ema_fast,
            "ema_slow": scalper.ema_slow,
            "rsi_period": scalper.rsi_period,
            "stop_loss_pct": scalper.stop_loss_pct,
            "take_profit_pct": scalper.take_profit_pct
        }
    }



# YOLO Engine Routes
@router.get("/yolo/stats")
async def api_yolo_stats():
    """Get YOLO Engine statistics"""
    if not state.yolo_engine:
        return {"error": "YOLO Engine not initialized"}
    return state.yolo_engine.get_stats()


@router.get("/yolo/scan")
async def api_yolo_scan():
    """Run immediate YOLO scan"""
    if not state.yolo_engine:
        return {"error": "YOLO Engine not initialized"}
    signals = await state.yolo_engine.scan_markets()
    return {"signals": signals, "count": len(signals)}


@router.post("/yolo/toggle")
async def api_yolo_toggle(active: bool = True):
    """Toggle YOLO Engine on/off"""
    if not state.yolo_engine:
        return {"error": "YOLO Engine not initialized"}
    state.yolo_engine.active = active
    return {"active": state.yolo_engine.active, "message": f"YOLO Engine {'ACTIVATED 🚀' if active else 'PAUSED'}"}



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
        btc = await state.market_intel.get_technical_analysis("BTC/USDT", "1h")
        binance_ok = "error" not in btc
        return {"status": "success", "binance": binance_ok, "mexc": bool(os.environ.get('MEXC_API_KEY')), "telegram": bool(os.environ.get('TELEGRAM_TOKEN')), "users": len(state.chat_ids)}
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
        client = anthropic.AsyncAnthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        msg = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=150,
            system="You are Aeon, a confident trading buddy having a voice conversation. Keep responses SHORT (1-3 sentences). Be conversational. No bullet points or lists. No markdown. Speak like talking to a friend. Be direct and insightful.",
            messages=[{"role": "user", "content": user_text}]
        )
        aeon_text = msg.content[0].text
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


@router.post("/learning/trigger")
async def api_trigger_learning():
    """Manually trigger a learning cycle"""
    if not state.continuous_learner:
        return {"error": "Learning system not initialized"}
    
    try:
        await state.continuous_learner.run_pattern_learning()
        await state.continuous_learner.run_market_analysis()
        
        return {
            "success": True,
            "message": "Learning cycle triggered",
            "patterns_learned": len(state.continuous_learner.pattern_learner.pattern_stats),
            "coins_analyzed": len(state.continuous_learner.pattern_learner.coin_stats),
            "insights_count": len(state.continuous_learner.daily_insights)
        }
    except Exception as e:
        return {"error": str(e)}



# ═══════════════════════════════════════════════════════════════════════════════
# PAPER TRADING ROUTES - Position Monitor & Performance Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/paper/accounts")
async def api_paper_accounts():
    """Get all paper trading accounts with positions"""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    
    accounts = []
    for acc_id in ACCOUNTS:
        summary = await state.paper_trading.get_account_summary(acc_id)
        if summary and "error" not in summary:
            accounts.append(summary)

    return {"accounts": accounts}


@router.get("/paper/positions")
async def api_paper_positions():
    """Get all open positions across all accounts with live data"""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    
    positions = []
    for acc_id, acc_config in ACCOUNTS.items():
        account = await state.paper_trading.get_account(acc_id)
        if account:
            for pos in account.get("positions", []):
                if pos.get("status") == "open":
                    # Recompute unrealized PnL from current_price if stored value is stale/zero
                    current_price = pos.get("current_price") or pos.get("entry_price", 0)
                    if current_price and pos.get("entry_price") and pos.get("margin"):
                        entry = pos["entry_price"]
                        leverage = pos.get("leverage", 1)
                        margin = pos["margin"]
                        if pos.get("direction", "").upper() == "LONG":
                            pnl_pct = ((current_price - entry) / entry) * 100 * leverage
                        else:
                            pnl_pct = ((entry - current_price) / entry) * 100 * leverage
                        pos = {
                            **pos,
                            "unrealized_pnl": round(margin * (pnl_pct / 100), 2),
                            "unrealized_pnl_pct": round(pnl_pct, 2),
                            "current_price": current_price,
                        }
                    positions.append({
                        **pos,
                        "account_id": acc_id,
                        "account_emoji": acc_config.get("emoji", "📊"),
                    })
    
    # Sort by entry time (newest first)
    positions.sort(key=lambda x: x.get("opened_at", ""), reverse=True)
    
    return {
        "positions": positions,
        "total": len(positions),
        "by_strategy": _group_by_strategy(positions)
    }


def _group_by_strategy(positions):
    """Group positions by strategy for analytics"""
    strategies = {}
    for pos in positions:
        strategy = pos.get("strategy", "unknown")
        if strategy not in strategies:
            strategies[strategy] = {
                "count": 0,
                "total_margin": 0,
                "total_pnl": 0,
                "symbols": []
            }
        strategies[strategy]["count"] += 1
        strategies[strategy]["total_margin"] += pos.get("margin", 0)
        strategies[strategy]["total_pnl"] += pos.get("unrealized_pnl", 0)
        strategies[strategy]["symbols"].append(pos.get("symbol"))
    return strategies


@router.get("/paper/performance")
async def api_paper_performance():
    """Get paper trading performance metrics by strategy"""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    
    # Get trade history from DB
    trades = await state.db.paper_trades.find().sort("opened_at", -1).to_list(500)
    
    # Group by strategy
    strategy_stats = {}
    for trade in trades:
        strategy = trade.get("strategy", "unknown")
        if strategy not in strategy_stats:
            strategy_stats[strategy] = {
                "name": strategy,
                "total_trades": 0,
                "open_trades": 0,
                "closed_trades": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0,
                "total_margin_used": 0,
                "avg_leverage": 0,
                "leverages": []
            }
        
        stats = strategy_stats[strategy]
        stats["total_trades"] += 1
        stats["leverages"].append(trade.get("leverage", 1))
        
        status = trade.get("status", "open")
        if status == "open":
            stats["open_trades"] += 1
            stats["total_margin_used"] += trade.get("margin", 0)
        else:
            stats["closed_trades"] += 1
            pnl = trade.get("realized_pnl", 0)
            stats["total_pnl"] += pnl
            if pnl > 0:
                stats["wins"] += 1
            elif pnl < 0:
                stats["losses"] += 1
    
    # Calculate averages and win rates
    for strategy, stats in strategy_stats.items():
        if stats["leverages"]:
            stats["avg_leverage"] = round(sum(stats["leverages"]) / len(stats["leverages"]), 1)
        del stats["leverages"]  # Remove raw data
        
        closed = stats["closed_trades"]
        if closed > 0:
            stats["win_rate"] = round((stats["wins"] / closed) * 100, 1)
        else:
            stats["win_rate"] = 0
    
    # Get account summaries
    accounts = []
    for acc_id in ACCOUNTS:
        summary = await state.paper_trading.get_account_summary(acc_id)
        if summary and "error" not in summary:
            accounts.append(summary)
    
    return {
        "strategies": list(strategy_stats.values()),
        "accounts": accounts,
        "total_trades": len(trades),
        "unique_strategies": len(strategy_stats)
    }


@router.post("/paper/trade")
async def api_paper_manual_trade(data: dict):
    """
    Manually open a paper trade.
    Body: { account_id, symbol, direction, confidence?, leverage?, risk_pct? }
    Fetches live price from market intelligence and calculates SL/TP automatically.
    """
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}

    account_id = data.get("account_id", "PRO").upper()
    symbol     = data.get("symbol", "BTC/USDT").upper()
    if not symbol.endswith("/USDT"):
        symbol = symbol.replace("USDT", "") + "/USDT"
    direction  = data.get("direction", "LONG").upper()
    confidence = int(data.get("confidence", 75))
    risk_pct   = float(data.get("risk_pct", 2.0))

    # Fetch live price from MEXC (async wrapper)
    try:
        ticker = await state.market_intel.get_ticker(symbol)
        entry_price = float(ticker.get("last") or ticker.get("close") or ticker.get("price") or 0)
    except Exception:
        entry_price = 0.0

    if entry_price <= 0:
        return {"error": f"Could not fetch live price for {symbol}"}

    # Determine leverage from confidence
    from paper_trading import get_dynamic_leverage, calculate_smart_stops
    leverage = int(data.get("leverage", 0)) or get_dynamic_leverage(symbol, confidence, direction)
    stop_loss, take_profit = calculate_smart_stops(entry_price, leverage, direction)

    result = await state.paper_trading.open_position(
        account_id=account_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        leverage=leverage,
        risk_pct=risk_pct,
        confidence=confidence,
        strategy="manual",
    )
    return {
        "result": result,
        "trade_details": {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "leverage": leverage,
            "rr_ratio": round((abs(take_profit - entry_price) / abs(stop_loss - entry_price)), 2) if stop_loss != entry_price else 0,
        }
    }


@router.post("/paper/reset/{account_id}")
async def api_paper_reset(account_id: str):
    """Reset a paper trading account"""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    
    if account_id.upper() not in ACCOUNTS:
        return {"error": f"Invalid account. Use one of: {', '.join(ACCOUNTS.keys())}"}
    
    result = await state.paper_trading.reload_account(account_id.upper())
    return result


@router.post("/paper/close/{account_id}/{symbol}")
async def api_paper_close_position(account_id: str, symbol: str):
    """Manually close a paper trading position"""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    
    # Normalise symbol: BTC / BTCUSDT / BTC_USDT / BTC/USDT → BTC/USDT
    sym = symbol.upper().replace("_", "/")
    if "/" not in sym:
        sym = sym.replace("USDT", "") + "/USDT"

    # Get current price
    try:
        ticker = await state.market_intel.get_ticker(sym)
        current_price = float(ticker.get("last") or ticker.get("price") or ticker.get("close") or 0)
        if not current_price:
            return {"error": "Could not fetch current price"}
    except Exception as e:
        logger.warning(f"Price fetch error for {sym}: {e}")
        return {"error": "Could not fetch current price"}

    result = await state.paper_trading.close_position(
        account_id.upper(),
        sym,
        current_price
    )
    return result



@router.get("/paper/health")
async def api_paper_health():
    """Check paper trading account health and auto-reload status"""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    
    return await state.paper_trading.check_account_health()


@router.get("/paper/events")
async def api_paper_events(limit: int = 50):
    """Get paper trading events (reloads, liquidations, etc.)"""
    events = await state.db.paper_events.find().sort("timestamp", -1).limit(limit).to_list(limit)
    # Convert ObjectId to string for JSON serialization
    for event in events:
        event["_id"] = str(event["_id"])
    return {"events": events}


@router.get("/paper/equity-curves")
async def api_paper_equity_curves():
    """Get equity curves for all paper trading accounts (30 days)."""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    if not state.analytics_engine:
        return {"error": "Analytics engine not initialized"}

    curves = {}
    for acc_id in ACCOUNTS:
        curves[acc_id] = await state.analytics_engine.get_equity_curve(account_id=acc_id, days=90)

    return {"curves": curves}


@router.get("/paper/weekly-summary")
async def api_paper_weekly_summary():
    """Get weekly PnL summary for all accounts."""
    if not state.paper_trading:
        return {"error": "Paper trading not initialized"}
    return await state.paper_trading.get_weekly_summary()
