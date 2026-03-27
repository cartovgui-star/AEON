"""
Weekly Performance Report API Routes
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import pytz

router = APIRouter(prefix="/report", tags=["Weekly Report"])

from weekly_report import weekly_report, AUSTIN_TZ


@router.get("/status")
async def get_report_status():
    """Get the status of the weekly report system"""
    try:
        return await weekly_report.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def send_test_report():
    """Send a test weekly report immediately (runs in background)"""
    try:
        import asyncio
        asyncio.create_task(weekly_report.send_test_report())
        return {"success": True, "message": "Test report started - check Telegram"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview")
async def preview_report():
    """Preview the current week's report without sending"""
    try:
        content = await weekly_report.get_preview()
        return {
            "preview": content,
            "length": len(content),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_report(enabled: bool = True):
    """Enable or disable the weekly report"""
    weekly_report.is_active = enabled
    return {
        "success": True,
        "enabled": weekly_report.is_active
    }


@router.get("/strategy-stats")
async def get_strategy_stats():
    """Get strategy statistics for the current week"""
    try:
        week_start, week_end = weekly_report._get_week_range()
        trades = await weekly_report.get_closed_trades(week_start, week_end)
        stats = await weekly_report.calculate_strategy_stats(trades)
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_trades": len(trades),
            "strategies": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coin-performance")
async def get_coin_performance():
    """Get coin performance for the current week"""
    try:
        week_start, week_end = weekly_report._get_week_range()
        trades = await weekly_report.get_closed_trades(week_start, week_end)
        performance = await weekly_report.get_coin_performance(trades)
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_trades": len(trades),
            **performance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
