"""
Strategy Engine API Routes
Multi-strategy analysis endpoints
"""

from fastapi import APIRouter
from strategy_engine import strategy_engine

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/scan/{symbol}")
async def api_strategies_scan(symbol: str, timeframe: str = "4h"):
    """Scan all strategies for a symbol"""
    return await strategy_engine.scan_all_strategies(
        symbol.upper() + "/USDT",
        timeframe
    )


@router.get("/all/{symbol}")
async def api_strategies_all(symbol: str, timeframe: str = "4h"):
    """Run all strategies and get combined signal"""
    return await strategy_engine.scan_all_strategies(
        symbol.upper() + "/USDT",
        timeframe
    )


@router.get("/ma/{symbol}")
async def api_strategy_ma(symbol: str, timeframe: str = "1h", fast: int = 9, slow: int = 21):
    """MA Crossover strategy analysis"""
    return await strategy_engine.strategy_ma_crossover(
        symbol.upper() + "/USDT",
        timeframe,
        fast,
        slow
    )


@router.get("/rsi/{symbol}")
async def api_strategy_rsi(symbol: str, timeframe: str = "1h"):
    """RSI Momentum strategy analysis"""
    return await strategy_engine.strategy_rsi_momentum(
        symbol.upper() + "/USDT",
        timeframe
    )


@router.get("/breakout/{symbol}")
async def api_strategy_breakout(symbol: str, timeframe: str = "4h"):
    """Breakout strategy analysis"""
    return await strategy_engine.strategy_breakout(
        symbol.upper() + "/USDT",
        timeframe
    )


@router.get("/bb/{symbol}")
async def api_strategy_bb(symbol: str, timeframe: str = "4h"):
    """Bollinger Band Squeeze strategy analysis"""
    return await strategy_engine.strategy_bb_squeeze(
        symbol.upper() + "/USDT",
        timeframe
    )


@router.get("/macd/{symbol}")
async def api_strategy_macd(symbol: str, timeframe: str = "4h"):
    """MACD Reversal strategy analysis"""
    return await strategy_engine.strategy_macd_reversal(
        symbol.upper() + "/USDT",
        timeframe
    )


@router.get("/pullback/{symbol}")
async def api_strategy_pullback(symbol: str, timeframe: str = "4h"):
    """Trend Pullback strategy analysis"""
    return await strategy_engine.strategy_trend_pullback(
        symbol.upper() + "/USDT",
        timeframe
    )
