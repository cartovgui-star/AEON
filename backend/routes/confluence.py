"""
Confluence Analysis API Routes
SMC + Strategy confluence analysis
"""

from fastapi import APIRouter
import sys
sys.path.append('..')

router = APIRouter(prefix="/confluence", tags=["confluence"])


@router.get("/{symbol}")
async def api_confluence(symbol: str, timeframe: str = "4h"):
    """
    Get SMC + Strategy confluence analysis
    Combines Smart Money Concepts with technical strategies for high-probability setups
    """
    from server import confluence_analyzer
    return await confluence_analyzer.analyze_confluence(symbol.upper() + "/USDT", timeframe)
