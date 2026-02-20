"""
Dual Trading Engine API Routes
Day Trader + Long Term engine controls
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/dual", tags=["dual"])


@router.get("/stats")
async def api_dual_stats():
    """Get Dual Trading Engine statistics (Day Trader + Long Term)"""
    return state.dual_engine.get_stats()


@router.post("/toggle")
async def api_dual_toggle(active: bool = True):
    """Toggle entire Dual Trading Engine on/off"""
    state.dual_engine.active = active
    return {"status": "ok", "active": active}


@router.post("/day-trader/toggle")
async def api_dual_day_trader_toggle(active: bool = True):
    """Toggle Day Trader engine on/off"""
    state.dual_engine.day_trader.active = active
    return {"status": "ok", "day_trader_active": active}


@router.post("/long-term/toggle")
async def api_dual_long_term_toggle(active: bool = True):
    """Toggle Long Term engine on/off"""
    state.dual_engine.long_term.active = active
    return {"status": "ok", "long_term_active": active}


@router.post("/day-trader/confidence")
async def api_dual_day_trader_confidence(min_conf: int = 75):
    """Set Day Trader minimum confidence (65-95)"""
    min_conf = max(65, min(95, min_conf))
    state.dual_engine.day_trader.min_confidence = min_conf
    return {"status": "ok", "day_trader_min_confidence": min_conf}


@router.post("/long-term/confidence")
async def api_dual_long_term_confidence(min_conf: int = 88):
    """Set Long Term minimum confidence (75-95)"""
    min_conf = max(75, min(95, min_conf))
    state.dual_engine.long_term.min_confidence = min_conf
    return {"status": "ok", "long_term_min_confidence": min_conf}
