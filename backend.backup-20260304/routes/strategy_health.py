"""
Strategy Health API Routes
Self-improving strategy tracking and performance
"""

from fastapi import APIRouter, Request
import app_state as state

router = APIRouter(prefix="/strategy-health", tags=["strategy-health"])


@router.get("/status")
async def api_strategy_health():
    """Get strategy health and performance status"""
    return state.strategy_health.get_status()


@router.get("/ranking")
async def api_strategy_health_ranking():
    """Get strategy ranking by performance score"""
    return {"ranking": state.strategy_health.get_ranking()}


@router.post("/record")
async def api_strategy_health_record(request: Request):
    """Record a trade result for strategy health tracking"""
    data = await request.json()
    strategy_id = data.get("strategy_id", "")
    pnl_pct = data.get("pnl_pct", 0)
    symbol = data.get("symbol", "")
    return state.strategy_health.record_trade(strategy_id, pnl_pct, symbol)


@router.post("/unbench/{strategy_id}")
async def api_strategy_unbench(strategy_id: str):
    """Manually un-bench a strategy"""
    return state.strategy_health.force_unbench(strategy_id)
