"""
Accuracy Tracking API Routes
Track alert outcomes and measure trading accuracy
"""

from fastapi import APIRouter, Request
import sys
sys.path.append('..')
from trade_outcome_tracker import trade_outcome_tracker

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("")
async def api_accuracy_stats():
    """Get alert accuracy statistics"""
    return trade_outcome_tracker.get_accuracy_report()


@router.get("/pending")
async def api_accuracy_pending():
    """Get pending alerts awaiting outcome"""
    return {"pending": trade_outcome_tracker.get_pending_alerts()}


@router.post("/record")
async def api_accuracy_record(request: Request):
    """Record outcome for an alert"""
    data = await request.json()
    alert_id = data.get("alert_id", "")
    outcome = data.get("outcome", "")  # WIN, LOSS, BREAKEVEN, EXPIRED
    exit_price = data.get("exit_price", 0)
    
    if not alert_id or not outcome:
        return {"error": "alert_id and outcome required"}
    
    result = trade_outcome_tracker.update_outcome(alert_id, outcome, exit_price)
    return result
