"""
Signal Tracking API Routes
Endpoints for monitoring signal accuracy and historical data
"""
from fastapi import APIRouter
from typing import Optional
import app_state

router = APIRouter(prefix="/signals", tags=["Signal Tracking"])


@router.get("/recent")
async def api_recent_signals(limit: int = 20):
    """Get most recent signals from all strategies"""
    from signal_tracker import signal_tracker
    
    signals = await signal_tracker.get_recent_signals(limit)
    
    return {
        "count": len(signals),
        "signals": signals
    }


@router.get("/accuracy")
async def api_signal_accuracy(days: int = 30):
    """Get signal accuracy statistics for past N days"""
    from signal_tracker import signal_tracker
    
    return await signal_tracker.get_accuracy_stats(days)


@router.get("/performance")
async def api_strategy_performance(days: int = 30):
    """Get performance breakdown by strategy"""
    from signal_tracker import signal_tracker
    
    return await signal_tracker.get_strategy_performance(days)


@router.get("/stats")
async def api_signal_stats():
    """Get quick signal stats from cache"""
    from signal_tracker import signal_tracker
    
    return signal_tracker.get_cache_stats()


@router.post("/record")
async def api_record_signal(signal: dict, source: str = "MANUAL"):
    """Manually record a signal (for testing)"""
    from signal_tracker import signal_tracker
    
    return await signal_tracker.record_signal(signal, source)


@router.post("/outcome")
async def api_update_outcome(
    symbol: str,
    direction: str,
    outcome: str,
    exit_price: float,
    pnl_pct: float,
    reason: str = ""
):
    """Update a signal with its outcome"""
    from signal_tracker import signal_tracker
    
    return await signal_tracker.update_signal_outcome(
        symbol, direction, outcome, exit_price, pnl_pct, reason
    )
