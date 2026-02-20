"""
Free Will Engine API Routes
24/7 autonomous monitoring and alerts
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/freewill", tags=["freewill"])


@router.get("/stats")
async def api_freewill_stats():
    """Get Free Will v2 engine statistics"""
    return await state.free_will_v2.get_stats()


@router.get("/scan/{symbol}")
async def api_freewill_scan_symbol(symbol: str, timeframe: str = "1h"):
    """Manually scan a specific symbol/timeframe with full analysis"""
    return await state.free_will_v2.analyze_setup_full(symbol.upper() + "/USDT", timeframe)


@router.post("/toggle")
async def api_freewill_toggle(active: bool = True):
    """Toggle Free Will v2 engine on/off"""
    state.free_will_v2.active = active
    return {"active": state.free_will_v2.active}


@router.post("/confidence")
async def api_freewill_confidence(min_conf: int = 80):
    """Set minimum confidence threshold (70-95)"""
    state.free_will_v2.min_confidence = max(70, min(95, min_conf))
    return {"min_confidence": state.free_will_v2.min_confidence}


@router.post("/feedback")
async def api_freewill_feedback(setup_id: str, outcome: str, notes: str = None):
    """Record feedback on a setup (win/loss/skipped/partial)"""
    await state.free_will_v2.record_feedback(setup_id, outcome, notes)
    return {"status": "recorded", "outcome": outcome}
