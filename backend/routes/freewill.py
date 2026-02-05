"""
Free Will Engine API Routes
24/7 autonomous monitoring and alerts
"""

from fastapi import APIRouter

router = APIRouter(prefix="/freewill", tags=["freewill"])

# Will be set from server.py
free_will = None

def set_free_will(fw):
    global free_will
    free_will = fw


@router.get("/stats")
async def api_freewill_stats():
    """Get Free Will engine statistics"""
    return await free_will.get_stats()


@router.get("/scan/{symbol}")
async def api_freewill_scan_symbol(symbol: str, timeframe: str = "1h"):
    """Manually scan a specific symbol/timeframe"""
    return await free_will.analyze_setup(symbol.upper() + "/USDT", timeframe)


@router.post("/toggle")
async def api_freewill_toggle(active: bool = True):
    """Toggle Free Will engine on/off"""
    free_will.active = active
    return {"active": free_will.active}


@router.post("/confidence")
async def api_freewill_confidence(min_conf: int = 65):
    """Set minimum confidence threshold (0-100)"""
    free_will.min_confidence = max(50, min(95, min_conf))
    return {"min_confidence": free_will.min_confidence}


@router.post("/feedback")
async def api_freewill_feedback(setup_id: str, outcome: str, notes: str = None):
    """Record feedback on a setup (win/loss/skipped/partial)"""
    await free_will.record_feedback(setup_id, outcome, notes)
    return {"status": "recorded", "outcome": outcome}
