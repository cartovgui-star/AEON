"""
Quant Analyzer API Routes
Pure multi-factor technical analysis and ranking — no trading.
"""

from fastapi import APIRouter, Query
from quant_analyzer_engine import get_quant_engine

router = APIRouter(prefix="/quant", tags=["quant_analyzer"])

DEFAULT_SYMBOLS = "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,AVAX/USDT,DOGE/USDT,LINK/USDT,DOT/USDT,ADA/USDT"


@router.get("/analyze")
async def analyze_coins(
    symbols: str = Query(DEFAULT_SYMBOLS, description="Comma-separated symbols to analyze"),
):
    """
    Run full quant analysis on provided symbols.
    Returns ranked report cards + watchlist summary table.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    engine = get_quant_engine()
    return await engine.analyze_coins(symbol_list)


@router.get("/analyze/{symbol}")
async def analyze_single(symbol: str):
    """
    Full quant analysis for a single coin.
    """
    import asyncio
    from quant_analyzer_engine import CoinAnalyzer
    loop = asyncio.get_running_loop()
    analyzer = CoinAnalyzer()
    result = await loop.run_in_executor(None, analyzer.analyze, symbol.upper())
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    return result
