"""
Volume Profile + Liquidation Heatmap + Orderbook API Routes
"""

from fastapi import APIRouter, Query
import app_state as state

router = APIRouter(prefix="/vp", tags=["volume_profile"])


@router.get("/profile/{symbol}")
async def api_volume_profile(
    symbol: str,
    timeframe: str = Query("1h", description="Candle timeframe (1h, 4h)"),
    limit: int = Query(96, description="Number of candles"),
):
    """
    Get Volume Session Profile for a symbol.
    Returns: POC, Value Area High/Low, HVN, LVN, bucket heatmap data.
    """
    from volume_profile_engine import vsp_analyzer
    import ccxt
    exchange = ccxt.okx({'enableRateLimit': True})
    return await vsp_analyzer.get_session_profile(symbol.upper(), exchange, timeframe, limit)


@router.get("/liquidations/{symbol}")
async def api_liq_heatmap(symbol: str):
    """
    Get Liquidation Heatmap for a symbol.
    Returns: long/short liq clusters, nearest clusters, approaching flag.
    """
    from volume_profile_engine import liq_heatmap
    import ccxt
    exchange = ccxt.okx({'enableRateLimit': True})
    loop = __import__("asyncio").get_running_loop()
    formatted = symbol.upper().replace("/", "")
    if not formatted.endswith("USDT"):
        formatted += "USDT"
    full_symbol = formatted.replace("USDT", "/USDT")
    ohlcv = await loop.run_in_executor(None, lambda: exchange.fetch_ohlcv(full_symbol, "4h", limit=60))
    return await liq_heatmap.analyze(symbol.upper(), ohlcv)


@router.get("/orderbook/{symbol}")
async def api_orderbook(symbol: str):
    """
    Get real-time orderbook analysis.
    Returns: bid/ask walls, imbalance ratio, sweep events.
    """
    from volume_profile_engine import ob_analyzer
    return await ob_analyzer.analyze(symbol.upper())


@router.get("/full/{symbol}")
async def api_vp_full(symbol: str):
    """
    Full VP Engine analysis: Profile + Liq Heatmap + Orderbook + Combined Signal.
    """
    if state.vp_engine is None:
        from volume_profile_engine import HyperAccuracyEngine
        eng = HyperAccuracyEngine()
        eng.set_dependencies(
            order_flow=state.order_flow,
            market_intel=state.market_intel,
        )
        return await eng.full_analysis(symbol.upper())
    return await state.vp_engine.full_analysis(symbol.upper())


@router.get("/scan")
async def api_vp_scan(
    symbols: str = Query("BTC/USDT,ETH/USDT,SOL/USDT", description="Comma-separated symbols")
):
    """
    Scan multiple symbols for VP setups. Returns only high-confidence signals.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if state.vp_engine is None:
        from volume_profile_engine import HyperAccuracyEngine
        eng = HyperAccuracyEngine()
        eng.set_dependencies(order_flow=state.order_flow)
    else:
        eng = state.vp_engine
    results = await eng.scan_all(symbol_list)
    return {
        "signals": results,
        "count": len(results),
        "symbols_scanned": len(symbol_list),
    }


@router.get("/stats")
async def api_vp_stats():
    """VP Engine runtime stats."""
    if state.vp_engine:
        return state.vp_engine.get_stats()
    return {"error": "VP engine not initialized"}
