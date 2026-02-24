"""
Morning Briefing API Routes
Test and manage the daily 6 AM market overview
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import pytz

router = APIRouter(prefix="/briefing", tags=["Morning Briefing"])

# Import the briefing system
from morning_briefing import morning_briefing, AUSTIN_TZ, BRIEFING_HOUR


@router.get("/status")
async def get_briefing_status():
    """Get the status of the morning briefing system"""
    austin_now = datetime.now(AUSTIN_TZ)
    
    # Calculate next briefing time
    if austin_now.hour >= BRIEFING_HOUR:
        # Next day
        next_briefing = austin_now.replace(
            hour=BRIEFING_HOUR, minute=0, second=0, microsecond=0
        ) + __import__('datetime').timedelta(days=1)
    else:
        # Today
        next_briefing = austin_now.replace(
            hour=BRIEFING_HOUR, minute=0, second=0, microsecond=0
        )
    
    return {
        "enabled": morning_briefing.is_active,
        "timezone": "America/Chicago (Central Time)",
        "scheduled_time": "6:00 AM CT",
        "current_time_ct": austin_now.strftime("%Y-%m-%d %H:%M:%S"),
        "next_briefing": next_briefing.strftime("%Y-%m-%d %H:%M:%S"),
        "last_sent": morning_briefing.last_briefing_date.isoformat() if morning_briefing.last_briefing_date else None,
        "active_users": len(morning_briefing.chat_ids)
    }


@router.post("/test")
async def send_test_briefing():
    """Send a test briefing immediately"""
    try:
        result = await morning_briefing.send_test_briefing()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview")
async def preview_briefing():
    """Preview the morning briefing content without sending"""
    try:
        content = await morning_briefing.generate_briefing()
        return {
            "preview": content,
            "length": len(content),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_briefing(enabled: bool = True):
    """Enable or disable the morning briefing"""
    morning_briefing.is_active = enabled
    return {
        "success": True,
        "enabled": morning_briefing.is_active
    }


@router.get("/movers")
async def get_overnight_movers():
    """Get the overnight movers data"""
    try:
        movers = await morning_briefing.get_overnight_movers()
        return movers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/structure")
async def get_market_structure():
    """Get market structure analysis"""
    try:
        structure = await morning_briefing.get_market_structure()
        return structure
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/setups")
async def get_setups_to_watch():
    """Get potential setups to watch"""
    try:
        setups = await morning_briefing.get_setups_to_watch()
        return {"setups": setups, "count": len(setups)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
