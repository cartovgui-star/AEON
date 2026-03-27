"""
Order Flow API Routes
CVD, Absorption, Delta analysis
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/orderflow", tags=["orderflow"])


@router.get("/cvd/{symbol}")
async def api_cvd(symbol: str):
    """Calculate Cumulative Volume Delta"""
    return await state.order_flow.calculate_cvd(symbol.upper())


@router.get("/divergence/{symbol}")
async def api_cvd_divergence(symbol: str):
    """Detect CVD divergence"""
    return await state.order_flow.detect_cvd_divergence(symbol.upper())


@router.get("/absorption/{symbol}")
async def api_absorption(symbol: str):
    """Detect order absorption"""
    return await state.order_flow.detect_absorption(symbol.upper())


@router.get("/full/{symbol}")
async def api_orderflow_full(symbol: str):
    """Get full order flow analysis"""
    return await state.order_flow.get_full_order_flow(symbol.upper())
