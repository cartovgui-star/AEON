"""
Advanced Analysis API Routes
Divergence, Market Structure, VWAP, Order Flow
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/advanced", tags=["advanced"])


@router.get("/divergence/{symbol}")
async def api_divergence(symbol: str, timeframe: str = "1h"):
    """Detect RSI and MACD divergences"""
    return await state.advanced_strategies.detect_divergence(symbol.upper() + "/USDT", timeframe)


@router.get("/structure/{symbol}")
async def api_market_structure(symbol: str, timeframe: str = "1h"):
    """Analyze market structure (HH/HL/LH/LL, BOS, trend)"""
    return await state.advanced_strategies.analyze_market_structure(symbol.upper() + "/USDT", timeframe)


@router.get("/vwap/{symbol}")
async def api_vwap(symbol: str, timeframe: str = "1h"):
    """Calculate VWAP with bands"""
    return await state.advanced_strategies.calculate_vwap(symbol.upper() + "/USDT", timeframe)


@router.get("/full/{symbol}")
async def api_advanced_full(symbol: str, timeframe: str = "1h"):
    """Get full advanced analysis (divergence + structure + VWAP)"""
    return await state.advanced_strategies.get_full_analysis(symbol.upper() + "/USDT", timeframe)
