"""Analysis routes: MTF, Calculators, Advanced, Order Flow, Options, Backtest, Coinglass, Strategies."""
from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/api")


# Multi-timeframe
@router.get("/mtf/{symbol}")
async def api_multi_timeframe(symbol: str):
    return await state.mtf_analysis.get_multi_timeframe_analysis(symbol.upper() + "USDT")


@router.get("/mtf/align/{symbol}")
async def api_trend_alignment(symbol: str):
    return await state.mtf_analysis.get_trend_alignment(symbol.upper() + "USDT")


# Calculators
@router.get("/calc/pnl")
async def api_calc_pnl(entry: float, exit: float, size: float, leverage: int = 1, direction: str = "LONG"):
    return state.futures_calc.calculate_pnl(entry, exit, size, leverage, direction)


@router.get("/calc/position")
async def api_calc_position(balance: float, risk_pct: float, entry: float, stop: float, leverage: int = 1):
    return state.futures_calc.calculate_position_size(balance, risk_pct, entry, stop, leverage)


@router.get("/calc/scenarios")
async def api_calc_scenarios(entry: float, size: float, leverage: int = 1, direction: str = "LONG"):
    return state.futures_calc.generate_scenarios(entry, size, leverage, direction)


# Advanced strategies
@router.get("/advanced/divergence/{symbol}")
async def api_divergence(symbol: str, timeframe: str = "1h"):
    return await state.advanced_strategies.detect_divergence(symbol.upper() + "/USDT", timeframe)


@router.get("/advanced/structure/{symbol}")
async def api_market_structure(symbol: str, timeframe: str = "1h"):
    return await state.advanced_strategies.analyze_market_structure(symbol.upper() + "/USDT", timeframe)


@router.get("/advanced/vwap/{symbol}")
async def api_vwap(symbol: str, timeframe: str = "1h"):
    return await state.advanced_strategies.calculate_vwap(symbol.upper() + "/USDT", timeframe)


@router.get("/advanced/full/{symbol}")
async def api_advanced_full(symbol: str, timeframe: str = "1h"):
    return await state.advanced_strategies.get_full_analysis(symbol.upper() + "/USDT", timeframe)


# Order flow
@router.get("/orderflow/cvd/{symbol}")
async def api_cvd(symbol: str):
    return await state.order_flow.calculate_cvd(symbol.upper())


@router.get("/orderflow/divergence/{symbol}")
async def api_cvd_divergence(symbol: str):
    return await state.order_flow.detect_cvd_divergence(symbol.upper())


@router.get("/orderflow/absorption/{symbol}")
async def api_absorption(symbol: str):
    return await state.order_flow.detect_absorption(symbol.upper())


@router.get("/orderflow/full/{symbol}")
async def api_orderflow_full(symbol: str):
    return await state.order_flow.get_full_order_flow(symbol.upper())


# Options
@router.get("/options/maxpain/{currency}")
async def api_max_pain(currency: str = "BTC"):
    return await state.options_analyzer.calculate_max_pain(currency.upper())


@router.get("/options/pcr/{currency}")
async def api_put_call_ratio(currency: str = "BTC"):
    return await state.options_analyzer.calculate_put_call_ratio(currency.upper())


@router.get("/options/oi/{currency}")
async def api_options_oi(currency: str = "BTC"):
    return await state.options_analyzer.get_oi_by_strike(currency.upper())


@router.get("/options/full/{currency}")
async def api_options_full(currency: str = "BTC"):
    return await state.options_analyzer.get_full_options_analysis(currency.upper())


# Backtest
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


# Coinglass
@router.get("/coinglass/funding/{symbol}")
async def api_coinglass_funding(symbol: str = "BTC"):
    return await state.coinglass_intel.get_funding_rates(symbol.upper())


@router.get("/coinglass/oi/{symbol}")
async def api_coinglass_oi(symbol: str = "BTC"):
    return await state.coinglass_intel.get_open_interest(symbol.upper())


@router.get("/coinglass/ls/{symbol}")
async def api_coinglass_ls(symbol: str = "BTC"):
    return await state.coinglass_intel.get_long_short_ratio(symbol.upper())


@router.get("/coinglass/liquidations/{symbol}")
async def api_coinglass_liquidations(symbol: str = "BTC"):
    return await state.coinglass_intel.get_liquidation_heatmap(symbol.upper())


@router.get("/coinglass/full/{symbol}")
async def api_coinglass_full(symbol: str = "BTC"):
    return await state.coinglass_intel.get_full_report(symbol.upper())


# Multi-strategy
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


# Additional Data
@router.get("/data/social/{symbol}")
async def api_social_data(symbol: str = "BTC"):
    from additional_data import additional_data
    return await additional_data.get_crypto_compare_social(symbol.upper())


@router.get("/data/btc/onchain")
async def api_btc_onchain_data():
    from additional_data import additional_data
    return await additional_data.get_blockchain_btc_stats()


@router.get("/data/btc/fees")
async def api_btc_fees():
    from additional_data import additional_data
    return await additional_data.get_mempool_fees()


@router.get("/data/eth/gas")
async def api_eth_gas():
    from additional_data import additional_data
    return await additional_data.get_eth_gas()


@router.get("/data/defi/tvl")
async def api_defi_tvl(protocol: str = None):
    from additional_data import additional_data
    return await additional_data.get_defi_llama_tvl(protocol)


@router.get("/data/all/{symbol}")
async def api_all_additional_data(symbol: str = "BTC"):
    from additional_data import additional_data
    return await additional_data.get_full_additional_data(symbol.upper())
