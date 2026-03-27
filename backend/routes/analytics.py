from fastapi import APIRouter
import app_state

router = APIRouter()


@router.get("/api/analytics/report")
async def get_analytics_report():
    if app_state.analytics_engine is None:
        return {"error": "Analytics engine not initialized"}
    return await app_state.analytics_engine.get_full_report()


@router.get("/api/analytics/equity-curve")
async def get_equity_curve(account_id: str = None, days: int = 60):
    if app_state.analytics_engine is None:
        return []
    return await app_state.analytics_engine.get_equity_curve(account_id, days)


@router.get("/api/analytics/win-rates")
async def get_win_rates():
    if app_state.analytics_engine is None:
        return {}
    return await app_state.analytics_engine.get_win_rate_breakdown()


@router.get("/api/analytics/top-performers")
async def get_top_performers():
    if app_state.analytics_engine is None:
        return {}
    return await app_state.analytics_engine.get_top_performers()


@router.get("/api/analytics/drawdown")
async def get_drawdown():
    if app_state.analytics_engine is None:
        return {}
    return await app_state.analytics_engine.get_drawdown_analysis()


@router.get("/api/analytics/recent")
async def get_recent_trades(limit: int = 50):
    if app_state.analytics_engine is None:
        return []
    return await app_state.analytics_engine.get_recent_trades(limit)
