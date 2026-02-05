"""
News & Intelligence API Routes
News, whales, on-chain, MTF analysis
"""

from fastapi import APIRouter
from news_intel import news_intel, futures_calc
from mtf_analysis import mtf_analysis

router = APIRouter(tags=["intelligence"])


# ═══════════════════════════════════════════════════════════════════════════════
# NEWS & SENTIMENT APIs
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/news/latest")
async def api_latest_news(limit: int = 10, coin: str = None):
    """Get latest crypto news"""
    return await news_intel.get_latest_news(limit, coin)


@router.get("/news/sentiment")
async def api_news_sentiment():
    """Get news sentiment summary"""
    return await news_intel.get_news_sentiment_summary()


@router.get("/onchain/btc")
async def api_btc_onchain():
    """Get Bitcoin on-chain stats"""
    return await news_intel.get_btc_onchain_stats()


@router.get("/onchain/flow")
async def api_exchange_flow():
    """Get exchange flow estimate"""
    return await news_intel.get_exchange_flow_estimate()


@router.get("/whales/activity")
async def api_whale_activity():
    """Get whale activity summary"""
    return await news_intel.get_whale_summary()


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME ANALYSIS APIs
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/mtf/{symbol}")
async def api_multi_timeframe(symbol: str):
    """Get multi-timeframe confluence analysis"""
    return await mtf_analysis.get_multi_timeframe_analysis(symbol.upper() + "USDT")


@router.get("/mtf/align/{symbol}")
async def api_trend_alignment(symbol: str):
    """Get trend alignment across timeframes"""
    return await mtf_analysis.get_trend_alignment(symbol.upper() + "USDT")


# ═══════════════════════════════════════════════════════════════════════════════
# FUTURES CALCULATOR APIs
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/calc/pnl")
async def api_calc_pnl(
    entry: float,
    exit: float,
    size: float,
    leverage: int = 1,
    direction: str = "LONG"
):
    """Calculate futures PnL"""
    return futures_calc.calculate_pnl(entry, exit, size, leverage, direction)


@router.get("/calc/position")
async def api_calc_position(
    balance: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: int = 1
):
    """Calculate recommended position size"""
    return futures_calc.calculate_position_size(balance, risk_pct, entry, stop, leverage)


@router.get("/calc/scenarios")
async def api_calc_scenarios(
    entry: float,
    size: float,
    leverage: int = 1,
    direction: str = "LONG"
):
    """Generate PnL scenarios at different price levels"""
    return futures_calc.generate_scenarios(entry, size, leverage, direction)
