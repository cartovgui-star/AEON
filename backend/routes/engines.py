"""
AEON Engine System API Routes
Routes for the unified 7-engine management system
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from aeon_engine_system import (
    EngineManager, EngineType, get_engine_manager, ENGINE_CONFIGS
)

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class SignalRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    position_size: float
    leverage: float
    stop_loss: float
    take_profit: float
    confidence: float
    confluences: int
    reason: str = ""
    engine: Optional[str] = "autonomous_trader_v2"


class TradeCloseRequest(BaseModel):
    trade_id: str
    exit_price: float
    pnl_usd: float


class BlacklistRequest(BaseModel):
    symbol: str
    hours: Optional[int] = 24


# ============================================================================
# SIGNAL ROUTES
# ============================================================================

@router.post("/signal")
async def submit_signal(signal: SignalRequest):
    """
    Submit a trade signal from any engine.
    The signal will be validated and either executed or rejected.
    """
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[signal.engine.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid engine type: {signal.engine}. Valid options: {[e.value for e in EngineType]}"
        )
    
    signal_dict = {
        "symbol": signal.symbol,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "position_size": signal.position_size,
        "leverage": signal.leverage,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "confidence": signal.confidence,
        "confluences": signal.confluences,
        "reason": signal.reason
    }
    
    result = manager.submit_signal(signal_dict, engine_type)

    # Persist to MongoDB if trade was executed
    if result["action"] == "EXECUTE":
        trade_dict = result.get("trade", {})
        trade_id = trade_dict.get("trade_id")
        if trade_id:
            for trade in manager.engine_trades[engine_type]:
                if trade.trade_id == trade_id:
                    await manager.save_trade_to_db(trade)
                    break

    return {
        "status": "success" if result["action"] == "EXECUTE" else "rejected",
        "result": result
    }


@router.post("/close-trade")
async def close_trade(request: TradeCloseRequest):
    """Close a trade by ID (searches across all engines)"""
    manager = get_engine_manager()
    
    success = manager.close_trade_by_id(
        request.trade_id,
        request.exit_price,
        request.pnl_usd
    )
    
    if success:
        return {
            "status": "success",
            "message": f"Trade {request.trade_id} closed",
            "pnl": request.pnl_usd
        }
    
    raise HTTPException(status_code=404, detail=f"Trade {request.trade_id} not found")


# ============================================================================
# STATUS ROUTES
# ============================================================================

@router.get("/status")
async def get_all_engines_status():
    """Get status of all 7 engines with stats"""
    manager = get_engine_manager()
    return manager.get_all_engine_status()


@router.get("/status/{engine_name}")
async def get_engine_status(engine_name: str):
    """Get detailed status for a specific engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid engine: {engine_name}. Valid options: {[e.value for e in EngineType]}"
        )
    
    return manager.get_engine_status(engine_type)


@router.get("/stats/global")
async def get_global_stats():
    """Get aggregated statistics across all engines"""
    manager = get_engine_manager()
    return manager.get_global_stats()


@router.get("/stats/{engine_name}")
async def get_engine_stats(engine_name: str):
    """Get statistics for a specific engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    return manager.engine_stats[engine_type].to_dict()


# ============================================================================
# TRADES ROUTES
# ============================================================================

@router.get("/trades/open")
async def get_all_open_trades():
    """Get all open trades across all engines"""
    manager = get_engine_manager()
    trades = manager.get_all_open_trades()
    return {
        "total": len(trades),
        "trades": trades
    }


@router.get("/trades/open/{engine_name}")
async def get_engine_open_trades(engine_name: str):
    """Get open trades for a specific engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    trades = [t.to_dict() for t in manager._get_open_trades(engine_type)]
    return {
        "engine": engine_name,
        "total": len(trades),
        "trades": trades
    }


# ============================================================================
# BLACKLIST / COOLDOWN ROUTES
# ============================================================================

@router.get("/blacklist/{engine_name}")
async def get_blacklist(engine_name: str):
    """Get blacklisted symbols for an engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    return {
        "engine": engine_name,
        "blacklisted": list(manager.engine_blacklists[engine_type].keys())
    }


@router.post("/blacklist/{engine_name}")
async def add_to_blacklist(engine_name: str, request: BlacklistRequest):
    """Manually blacklist a symbol for an engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    manager.add_to_blacklist(engine_type, request.symbol, request.hours)
    
    return {
        "status": "success",
        "message": f"{request.symbol} blacklisted for {engine_name} ({request.hours}h)"
    }


@router.delete("/blacklist/{engine_name}/{symbol}")
async def remove_from_blacklist(engine_name: str, symbol: str):
    """Remove a symbol from an engine's blacklist"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    if manager.remove_from_blacklist(engine_type, symbol):
        return {"status": "success", "message": f"{symbol} removed from blacklist"}
    
    return {"status": "not_found", "message": f"{symbol} was not blacklisted"}


@router.get("/cooldown/{engine_name}")
async def get_cooldown(engine_name: str):
    """Get symbols in cooldown for an engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    return {
        "engine": engine_name,
        "in_cooldown": list(manager.engine_cooldowns[engine_type].keys())
    }


# ============================================================================
# CONFIG ROUTES
# ============================================================================

@router.get("/config")
async def get_all_configs():
    """Get configuration for all engines"""
    manager = get_engine_manager()
    return manager.get_all_configs()


@router.get("/config/{engine_name}")
async def get_engine_config(engine_name: str):
    """Get configuration for a specific engine"""
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine_name}")
    
    return manager.get_engine_config(engine_type)


# ============================================================================
# VALIDATION ROUTES
# ============================================================================

@router.get("/validation/stats")
async def get_validation_stats():
    """Get entry validation statistics"""
    manager = get_engine_manager()
    return manager.validator.get_stats()


@router.post("/validation/test")
async def test_validation(signal: SignalRequest):
    """
    Test a signal against validation rules WITHOUT executing.
    Useful for understanding why signals get blocked.
    """
    manager = get_engine_manager()
    
    try:
        engine_type = EngineType[signal.engine.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {signal.engine}")
    
    signal_dict = {
        "symbol": signal.symbol,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "position_size": signal.position_size,
        "leverage": signal.leverage,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "confidence": signal.confidence,
        "confluences": signal.confluences,
        "reason": signal.reason
    }
    
    is_valid, trade, issues = manager.validator.validate_signal(signal_dict, engine_type)
    
    # Calculate R:R
    risk = abs(signal.entry_price - signal.stop_loss)
    reward = abs(signal.take_profit - signal.entry_price)
    rr_ratio = reward / risk if risk > 0 else 0
    
    return {
        "would_execute": is_valid,
        "engine": signal.engine,
        "symbol": signal.symbol,
        "issues": issues,
        "analysis": {
            "confidence_required": ENGINE_CONFIGS[engine_type].min_confidence,
            "confidence_provided": signal.confidence,
            "confluences_required": ENGINE_CONFIGS[engine_type].min_confluences,
            "confluences_provided": signal.confluences,
            "max_leverage": ENGINE_CONFIGS[engine_type].max_leverage,
            "leverage_used": signal.leverage,
            "rr_ratio": round(rr_ratio, 2),
            "rr_minimum": 1.5
        }
    }


# ============================================================================
# ENGINE TOGGLE — POST /api/engines/{name}/toggle
# Enables or disables an individual engine without restarting.
# The global kill switch overrides per-engine active state.
# ============================================================================

class ToggleRequest(BaseModel):
    active: bool


@router.post("/{engine_name}/toggle")
async def toggle_engine(engine_name: str, request: ToggleRequest):
    """Enable or disable a specific engine. Persists in memory until backend restarts."""
    manager = get_engine_manager()
    try:
        engine_type = EngineType[engine_name.upper().replace("-", "_")]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid engine: {engine_name}. Valid: {[e.value for e in EngineType]}"
        )
    manager.set_engine_active(engine_type, request.active)
    return {
        "name":   engine_type.value,
        "active": request.active,
        "status": "enabled" if request.active else "disabled",
    }
