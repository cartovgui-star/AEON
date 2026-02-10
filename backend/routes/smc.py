"""
Smart Money Concepts (SMC) API Routes
Institutional trading analysis endpoints
"""

from fastapi import APIRouter
from smc_analyzer import smc_analyzer

router = APIRouter(prefix="/smc", tags=["smc"])


@router.get("/analysis/{symbol}")
async def api_smc_full_analysis(symbol: str, timeframe: str = "4h"):
    """
    Full SMC analysis including:
    - Market structure (HH/HL/LH/LL, BOS, CHoCH)
    - Order blocks (bullish/bearish)
    - Fair value gaps
    - Liquidity zones
    - Premium/discount zones
    """
    return await smc_analyzer.full_analysis(symbol.upper() + "/USDT", timeframe)


@router.get("/structure/{symbol}")
async def api_smc_structure(symbol: str, timeframe: str = "4h"):
    """Get market structure analysis"""
    ohlcv = await smc_analyzer.get_ohlcv(symbol.upper() + "/USDT", timeframe, 100)
    if not ohlcv:
        return {"error": "Failed to fetch data"}
    
    return smc_analyzer.analyze_market_structure(ohlcv)


@router.get("/orderblocks/{symbol}")
async def api_smc_order_blocks(symbol: str, timeframe: str = "4h"):
    """Get active order blocks"""
    ohlcv = await smc_analyzer.get_ohlcv(symbol.upper() + "/USDT", timeframe, 100)
    if not ohlcv:
        return {"error": "Failed to fetch data"}
    
    obs = smc_analyzer.find_order_blocks(ohlcv)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "bullish_obs": [ob for ob in obs if ob["type"] == "BULLISH_OB"],
        "bearish_obs": [ob for ob in obs if ob["type"] == "BEARISH_OB"],
        "total": len(obs)
    }


@router.get("/fvg/{symbol}")
async def api_smc_fvg(symbol: str, timeframe: str = "4h"):
    """Get fair value gaps"""
    ohlcv = await smc_analyzer.get_ohlcv(symbol.upper() + "/USDT", timeframe, 100)
    if not ohlcv:
        return {"error": "Failed to fetch data"}
    
    fvgs = smc_analyzer.find_fair_value_gaps(ohlcv)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "bullish_fvgs": [f for f in fvgs if f["type"] == "BULLISH_FVG"],
        "bearish_fvgs": [f for f in fvgs if f["type"] == "BEARISH_FVG"],
        "total": len(fvgs)
    }


@router.get("/liquidity/{symbol}")
async def api_smc_liquidity(symbol: str, timeframe: str = "4h"):
    """Get liquidity zones"""
    ohlcv = await smc_analyzer.get_ohlcv(symbol.upper() + "/USDT", timeframe, 100)
    if not ohlcv:
        return {"error": "Failed to fetch data"}
    
    return smc_analyzer.find_liquidity_zones(ohlcv)


@router.get("/zones/{symbol}")
async def api_smc_zones(symbol: str, timeframe: str = "4h", lookback: int = 50):
    """Get premium/discount zones with Fibonacci levels"""
    ohlcv = await smc_analyzer.get_ohlcv(symbol.upper() + "/USDT", timeframe, lookback + 10)
    if not ohlcv:
        return {"error": "Failed to fetch data"}
    
    return smc_analyzer.calculate_premium_discount(ohlcv, lookback)
