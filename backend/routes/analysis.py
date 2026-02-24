"""
Analysis Routes - Consolidated
MTF, Calculators, Backtest strategies
(Advanced, OrderFlow, Options, Coinglass moved to dedicated routes)
"""
from fastapi import APIRouter
import app_state as state

router = APIRouter()  # Prefix added when mounting


# Multi-timeframe (unique - not in mtf.py which has different endpoints)
@router.get("/mtf/{symbol}")
async def api_multi_timeframe(symbol: str):
    return await state.mtf_analysis.get_multi_timeframe_analysis(symbol.upper() + "USDT")


@router.get("/mtf/align/{symbol}")
async def api_trend_alignment(symbol: str):
    return await state.mtf_analysis.get_trend_alignment(symbol.upper() + "USDT")


# Calculators (unique - calculators.py has same but with /calculators prefix)
@router.get("/calc/pnl")
async def api_calc_pnl(entry: float, exit: float, size: float, leverage: int = 1, direction: str = "LONG"):
    return state.futures_calc.calculate_pnl(entry, exit, size, leverage, direction)


@router.get("/calc/position")
async def api_calc_position(balance: float, risk_pct: float, entry: float, stop: float, leverage: int = 1):
    return state.futures_calc.calculate_position_size(balance, risk_pct, entry, stop, leverage)


@router.get("/calc/scenarios")
async def api_calc_scenarios(entry: float, size: float, leverage: int = 1, direction: str = "LONG"):
    return state.futures_calc.generate_scenarios(entry, size, leverage, direction)


# Backtest strategies (unique - different from backtest.py and backtest_v21.py)
@router.get("/backtest/rsi/{symbol}")
async def api_backtest_rsi(symbol: str, timeframe: str = "1h",
                           oversold: int = 30, overbought: int = 70,
                           stop_pct: float = 2.0, target_pct: float = 4.0, days: int = 30):
    return await state.backtest_engine.backtest_rsi_strategy(
        symbol.upper() + "/USDT", timeframe, oversold, overbought, stop_pct, target_pct, days)


@router.get("/backtest/bb/{symbol}")
async def api_backtest_bb(symbol: str, timeframe: str = "1h",
                          stop_pct: float = 2.0, target_pct: float = 4.0, days: int = 30):
    return await state.backtest_engine.backtest_bb_strategy(
        symbol.upper() + "/USDT", timeframe, stop_pct, target_pct, days)


@router.get("/backtest/ema/{symbol}")
async def api_backtest_ema(symbol: str, timeframe: str = "1h",
                           fast: int = 9, slow: int = 21, stop_pct: float = 2.0, days: int = 30):
    return await state.backtest_engine.backtest_ema_cross_strategy(
        symbol.upper() + "/USDT", timeframe, fast, slow, stop_pct, days)


@router.get("/backtest/compare/{symbol}")
async def api_backtest_compare(symbol: str, timeframe: str = "1h", days: int = 30):
    return await state.backtest_engine.compare_strategies(symbol.upper() + "/USDT", timeframe, days)


# Multi-strategy scans (unique - different interface than strategies.py)
@router.get("/strategies/scan/{symbol}")
async def api_strategies_scan(symbol: str, timeframe: str = "4h"):
    return await state.strategy_engine.analyze_all(
        symbol.upper() + "/USDT",
        await state.strategy_engine.get_ohlcv(symbol.upper() + "/USDT", timeframe, 100),
        {"price": 0}
    )


@router.get("/strategies/ma/{symbol}")
async def api_strategy_ma(symbol: str, timeframe: str = "1h", fast: int = 9, slow: int = 21):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_ma_crossover(symbol.upper() + "/USDT", timeframe, fast, slow)


@router.get("/strategies/rsi/{symbol}")
async def api_strategy_rsi(symbol: str, timeframe: str = "1h"):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_rsi_momentum(symbol.upper() + "/USDT", timeframe)


@router.get("/strategies/breakout/{symbol}")
async def api_strategy_breakout(symbol: str, timeframe: str = "4h"):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_breakout(symbol.upper() + "/USDT", timeframe)


@router.get("/strategies/bb/{symbol}")
async def api_strategy_bb(symbol: str, timeframe: str = "4h"):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_bb_squeeze(symbol.upper() + "/USDT", timeframe)


@router.get("/strategies/macd/{symbol}")
async def api_strategy_macd(symbol: str, timeframe: str = "4h"):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_macd_reversal(symbol.upper() + "/USDT", timeframe)


@router.get("/strategies/pullback/{symbol}")
async def api_strategy_pullback(symbol: str, timeframe: str = "4h"):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_trend_pullback(symbol.upper() + "/USDT", timeframe)


@router.get("/strategies/all/{symbol}")
async def api_strategies_all(symbol: str, timeframe: str = "4h"):
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.scan_all_strategies(symbol.upper() + "/USDT", timeframe)
