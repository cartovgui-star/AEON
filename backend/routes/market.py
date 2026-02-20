"""Market, Intel, Derivatives, News, On-chain, Whales routes."""
from fastapi import APIRouter
import app_state as state

router = APIRouter()  # No prefix - added when mounting


@router.get("/market/scan/{symbol}")
async def api_market_scan(symbol: str):
    return await state.market_intel.get_full_market_scan(symbol.upper() + "USDT")


@router.get("/market/ta/{symbol}")
async def api_technical_analysis(symbol: str, interval: str = "1h"):
    return await state.market_intel.get_technical_analysis(symbol.upper() + "USDT", interval)


@router.get("/market/funding/{symbol}")
async def api_funding(symbol: str):
    return await state.enhanced_intel.get_funding_rate(symbol.upper() + "USDT")


@router.get("/market/positions/{symbol}")
async def api_positions(symbol: str):
    ls = await state.market_intel.get_long_short_ratio(symbol.upper() + "USDT", "1h", 5)
    whale = await state.market_intel.get_top_trader_long_short_ratio(symbol.upper() + "USDT", "1h", 5)
    taker = await state.market_intel.get_taker_long_short_ratio(symbol.upper() + "USDT", "1h", 5)
    return {"long_short": ls, "whale": whale, "taker_flow": taker}


@router.get("/intel/top100")
async def api_top_100():
    return await state.enhanced_intel.get_top_100_coins()


@router.get("/intel/fear-greed")
async def api_fear_greed(days: int = 1):
    return await state.enhanced_intel.get_fear_greed_index(days)


@router.get("/intel/global")
async def api_global_market():
    return await state.enhanced_intel.get_global_market_data()


@router.get("/intel/trending")
async def api_trending():
    return await state.enhanced_intel.get_trending_coins()


@router.get("/intel/movers")
async def api_top_movers():
    return await state.enhanced_intel.get_top_movers()


@router.get("/intel/summary")
async def api_market_summary():
    return {"summary": await state.enhanced_intel.get_market_summary()}


@router.get("/intel/sentiment/{symbol}")
async def api_sentiment(symbol: str):
    return await state.enhanced_intel.analyze_symbol_sentiment(symbol.upper() + "USDT")


@router.get("/intel/full/{symbol}")
async def api_full_intel(symbol: str):
    return await state.enhanced_intel.get_market_intelligence(symbol.upper() + "USDT")


@router.get("/intel/bybit/funding/{symbol}")
async def api_bybit_funding(symbol: str):
    return await state.enhanced_intel.get_funding_rate(symbol.upper() + "USDT")


@router.get("/intel/bybit/oi/{symbol}")
async def api_bybit_oi(symbol: str):
    return await state.enhanced_intel.get_open_interest_estimate(symbol.upper() + "USDT")


@router.get("/derivatives/funding/{symbol}")
async def api_real_funding(symbol: str):
    return await state.derivatives_intel.get_aggregated_funding(symbol.upper() + "USDT")


@router.get("/derivatives/oi/{symbol}")
async def api_real_oi(symbol: str):
    return await state.derivatives_intel.get_aggregated_open_interest(symbol.upper() + "USDT")


@router.get("/derivatives/ls/{symbol}")
async def api_real_ls(symbol: str):
    return await state.derivatives_intel.get_aggregated_long_short(symbol.upper() + "USDT")


@router.get("/derivatives/full/{symbol}")
async def api_full_derivatives(symbol: str):
    return await state.derivatives_intel.get_full_derivatives_report(symbol.upper() + "USDT")


@router.get("/derivatives/funding/exchange/{exchange}/{symbol}")
async def api_exchange_funding(exchange: str, symbol: str):
    sym = symbol.upper() + "USDT"
    handlers = {
        "okx": state.derivatives_intel.get_funding_rate_okx,
        "bitget": state.derivatives_intel.get_funding_rate_bitget,
        "kucoin": state.derivatives_intel.get_funding_rate_kucoin,
        "gate": state.derivatives_intel.get_funding_rate_gate,
    }
    handler = handlers.get(exchange.lower())
    if handler:
        return await handler(sym)
    return {"error": f"Unknown exchange: {exchange}"}


@router.get("/news/latest")
async def api_latest_news(limit: int = 10, coin: str = None):
    return await state.news_intel.get_latest_news(limit, coin)


@router.get("/news/sentiment")
async def api_news_sentiment():
    return await state.news_intel.get_news_sentiment_summary()


@router.get("/onchain/btc")
async def api_btc_onchain():
    return await state.news_intel.get_btc_onchain_stats()


@router.get("/onchain/flow")
async def api_exchange_flow():
    return await state.news_intel.get_exchange_flow_estimate()


@router.get("/whales/activity")
async def api_whale_activity():
    return await state.news_intel.get_whale_summary()


@router.get("/sentiment/composite")
async def api_sentiment_composite(symbol: str = "BTC"):
    return await state.sentiment_analyzer.get_composite_sentiment(symbol.upper())


@router.get("/sentiment/news")
async def api_sentiment_news():
    return await state.sentiment_analyzer.get_news_sentiment()


@router.get("/sentiment/fear-greed")
async def api_sentiment_fear_greed():
    return await state.sentiment_analyzer.get_fear_greed()


@router.get("/sentiment/history")
async def api_sentiment_history():
    return {"history": state.sentiment_analyzer.get_sentiment_history()}


@router.get("/arbitrage/scan")
async def api_arbitrage_scan():
    return await state.arbitrage_detector.scan_all()


@router.get("/arbitrage/scan/{symbol}")
async def api_arbitrage_scan_symbol(symbol: str):
    return await state.arbitrage_detector.scan_symbol(symbol.upper() + "/USDT")


@router.get("/arbitrage/recent")
async def api_arbitrage_recent(limit: int = 20):
    return {"opportunities": state.arbitrage_detector.get_recent_opportunities(limit)}
