"""
Backtesting API Routes
RSI, Bollinger Band, EMA strategy backtests
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/rsi/{symbol}")
async def api_backtest_rsi(symbol: str, timeframe: str = "1h", 
                           oversold: int = 30, overbought: int = 70,
                           stop_pct: float = 2.0, target_pct: float = 4.0,
                           days: int = 30):
    """Backtest RSI mean reversion strategy"""
    return await state.backtest_engine.backtest_rsi_strategy(
        symbol.upper() + "/USDT", timeframe, oversold, overbought, stop_pct, target_pct, days
    )


@router.get("/bb/{symbol}")
async def api_backtest_bb(symbol: str, timeframe: str = "1h",
                          stop_pct: float = 2.0, target_pct: float = 4.0,
                          days: int = 30):
    """Backtest Bollinger Band strategy"""
    return await state.backtest_engine.backtest_bb_strategy(
        symbol.upper() + "/USDT", timeframe, stop_pct, target_pct, days
    )


@router.get("/ema/{symbol}")
async def api_backtest_ema(symbol: str, timeframe: str = "1h",
                           fast: int = 9, slow: int = 21,
                           stop_pct: float = 2.0, days: int = 30):
    """Backtest EMA crossover strategy"""
    return await state.backtest_engine.backtest_ema_cross_strategy(
        symbol.upper() + "/USDT", timeframe, fast, slow, stop_pct, days
    )


@router.get("/compare/{symbol}")
async def api_backtest_compare(symbol: str, timeframe: str = "1h", days: int = 30):
    """Compare all strategies on same data"""
    return await state.backtest_engine.compare_strategies(symbol.upper() + "/USDT", timeframe, days)
