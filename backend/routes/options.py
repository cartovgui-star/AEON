"""
Options Analysis API Routes
Max Pain, Put/Call Ratio, Open Interest
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/maxpain/{currency}")
async def api_max_pain(currency: str = "BTC"):
    """Calculate options max pain"""
    return await state.options_analyzer.calculate_max_pain(currency.upper())


@router.get("/pcr/{currency}")
async def api_put_call_ratio(currency: str = "BTC"):
    """Get put/call ratio"""
    return await state.options_analyzer.calculate_put_call_ratio(currency.upper())


@router.get("/oi/{currency}")
async def api_options_oi(currency: str = "BTC"):
    """Get options open interest by strike"""
    return await state.options_analyzer.get_oi_by_strike(currency.upper())


@router.get("/full/{currency}")
async def api_options_full(currency: str = "BTC"):
    """Get full options analysis"""
    return await state.options_analyzer.get_full_options_analysis(currency.upper())
