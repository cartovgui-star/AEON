"""
Coinglass API Routes
Real derivatives data from Coinglass
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/coinglass", tags=["coinglass"])


@router.get("/funding/{symbol}")
async def api_coinglass_funding(symbol: str = "BTC"):
    """Get funding rates from Coinglass (FREE - no API key)"""
    return await state.coinglass_intel.get_funding_rates(symbol.upper())


@router.get("/oi/{symbol}")
async def api_coinglass_oi(symbol: str = "BTC"):
    """Get open interest from Coinglass (FREE - no API key)"""
    return await state.coinglass_intel.get_open_interest(symbol.upper())


@router.get("/ls/{symbol}")
async def api_coinglass_ls(symbol: str = "BTC"):
    """Get long/short ratio from Coinglass (FREE - no API key)"""
    return await state.coinglass_intel.get_long_short_ratio(symbol.upper())


@router.get("/liquidations/{symbol}")
async def api_coinglass_liquidations(symbol: str = "BTC"):
    """Get liquidation heatmap from Coinglass (PAID - requires API key)"""
    return await state.coinglass_intel.get_liquidation_heatmap(symbol.upper())


@router.get("/full/{symbol}")
async def api_coinglass_full(symbol: str = "BTC"):
    """Get full Coinglass report (funding + OI + L/S)"""
    return await state.coinglass_intel.get_full_report(symbol.upper())
