"""
Price Alerts API Routes
Real-time price monitoring and alerts
"""

from fastapi import APIRouter, Request
from price_alerts import price_alert_system

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/stats")
async def api_alerts_stats():
    """Get price alert system statistics"""
    return price_alert_system.get_stats()


@router.get("/dashboard")
async def api_alerts_dashboard(limit: int = 20, unread_only: bool = False):
    """Get dashboard alerts"""
    return {
        "alerts": price_alert_system.get_dashboard_alerts(limit, unread_only),
        "total": len(price_alert_system.dashboard_alerts),
        "unread": len([a for a in price_alert_system.dashboard_alerts if not a.get("read")])
    }


@router.post("/mark-read/{dashboard_id}")
async def api_alerts_mark_read(dashboard_id: str):
    """Mark dashboard alert as read"""
    success = price_alert_system.mark_alert_read(dashboard_id)
    return {"success": success}


@router.post("/clear")
async def api_alerts_clear():
    """Clear all dashboard alerts"""
    price_alert_system.clear_all_dashboard_alerts()
    return {"success": True}


@router.post("/add")
async def api_alerts_add(request: Request):
    """Add custom price alert"""
    data = await request.json()
    symbol = data.get("symbol", "BTC") + "/USDT"
    target_price = data.get("target_price", 0)
    direction = data.get("direction", "above")  # "above" or "below"
    chat_id = data.get("chat_id")
    
    if not target_price:
        return {"error": "target_price required"}
    
    return price_alert_system.add_price_alert(symbol, target_price, direction, chat_id)


@router.delete("/{alert_id}")
async def api_alerts_remove(alert_id: str):
    """Remove custom price alert"""
    return price_alert_system.remove_alert(alert_id)


@router.get("/custom")
async def api_alerts_list(chat_id: int = None):
    """List custom price alerts"""
    return {"alerts": price_alert_system.list_alerts(chat_id)}


@router.post("/threshold")
async def api_alerts_threshold(request: Request):
    """Update auto-alert thresholds"""
    data = await request.json()
    for key, value in data.items():
        if key in price_alert_system.auto_alert_thresholds:
            price_alert_system.auto_alert_thresholds[key] = value
    return {"thresholds": price_alert_system.auto_alert_thresholds}
