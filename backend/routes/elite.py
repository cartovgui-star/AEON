"""
Elite Strategy v3 API Routes
Ultra-selective trading strategy with 60%+ target win rate
"""
from fastapi import APIRouter
from typing import Optional
import app_state

router = APIRouter(prefix="/elite", tags=["Elite Strategy v3"])


@router.get("/status")
async def api_elite_status():
    """Get Elite Strategy v3 status and statistics"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,  # smc_analyzer
        app_state.enhanced_intel
    )
    
    return strategy.get_stats()


@router.get("/scan")
async def api_elite_scan():
    """Scan all pairs for elite signals"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    signals = await strategy.scan_all_elite()
    
    return {
        "signals_found": len(signals),
        "signals": signals,
        "stats": strategy.get_stats()
    }


@router.get("/analyze/{symbol}")
async def api_elite_analyze(symbol: str, timeframe: str = "4h"):
    """Analyze a single symbol with Elite Strategy"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    if "/" not in symbol:
        symbol = symbol.upper() + "/USDT"
    
    signal = await strategy.analyze_elite_signal(symbol, timeframe)
    
    return {
        "symbol": symbol,
        "signal": signal,
        "has_signal": signal is not None,
        "stats": strategy.get_stats()
    }


@router.post("/toggle")
async def api_elite_toggle(enabled: bool = True):
    """Enable or disable Elite Strategy"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    strategy.enabled = enabled
    
    return {
        "success": True,
        "enabled": strategy.enabled,
        "message": f"Elite Strategy v3 {'enabled' if enabled else 'disabled'}"
    }


@router.post("/settings")
async def api_elite_settings(settings: dict):
    """Update Elite Strategy settings"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    strategy.update_settings(settings)
    
    return {
        "success": True,
        "new_settings": strategy.get_stats()["settings"]
    }


@router.post("/relaxed")
async def api_elite_relaxed(enabled: bool = True):
    """Toggle relaxed mode (70% conf, more signals)"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    result = strategy.set_relaxed_mode(enabled)
    
    return {
        "success": True,
        "relaxed_mode": result["relaxed_mode"],
        "mode": "RELAXED" if enabled else "STRICT",
        "settings": result["active_settings"]
    }


@router.get("/scan_unlimited")
async def api_elite_scan_unlimited():
    """Scan all pairs for elite signals WITHOUT daily limit (unlimited mode)"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    # Temporarily enable relaxed mode for unlimited signals
    original_mode = strategy.relaxed_mode
    original_daily_limit = strategy.max_daily_trades
    
    # Set unlimited scanning
    strategy.max_daily_trades = 999999
    strategy.daily_trades = 0  # Reset counter
    
    # Also use relaxed settings for more signals
    strategy.relaxed_mode = True
    
    signals = await strategy.scan_all_elite()
    
    # Restore original settings
    strategy.relaxed_mode = original_mode
    strategy.max_daily_trades = original_daily_limit
    
    return {
        "mode": "UNLIMITED",
        "signals_found": len(signals),
        "signals": signals,
        "message": f"Found {len(signals)} signals with unlimited scanning (no daily cap)"
    }


@router.get("/backtest")
async def api_elite_backtest(days: int = 30):
    """Backtest Elite Strategy against historical data"""
    from elite_strategy_v3 import get_elite_strategy
    
    strategy = get_elite_strategy(
        app_state.advanced_strategies,
        None,
        app_state.enhanced_intel
    )
    
    return await strategy.backtest(days)
