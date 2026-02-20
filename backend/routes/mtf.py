"""
Multi-Timeframe Analysis API Routes
MTF confluence and trend alignment
"""

from fastapi import APIRouter
import sys
sys.path.append('..')

router = APIRouter(prefix="/mtf", tags=["mtf"])


@router.get("/{symbol}")
async def api_multi_timeframe(symbol: str):
    """Get multi-timeframe confluence analysis"""
    from server import mtf_analysis
    return await mtf_analysis.get_multi_timeframe_analysis(symbol.upper() + "USDT")


@router.get("/align/{symbol}")
async def api_trend_alignment(symbol: str):
    """Get trend alignment across timeframes"""
    from server import mtf_analysis
    return await mtf_analysis.get_trend_alignment(symbol.upper() + "USDT")
