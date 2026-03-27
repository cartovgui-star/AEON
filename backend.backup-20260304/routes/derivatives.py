"""
Derivatives API Routes
Real data from Binance, OKX, Bitget, KuCoin, Gate.io
"""

from fastapi import APIRouter
from derivatives_intel import derivatives_intel

router = APIRouter(prefix="/derivatives", tags=["derivatives"])


@router.get("/funding/{symbol}")
async def api_real_funding(symbol: str):
    """Get REAL aggregated funding rates from multiple exchanges"""
    return await derivatives_intel.get_aggregated_funding(symbol.upper() + "USDT")


@router.get("/oi/{symbol}")
async def api_real_oi(symbol: str):
    """Get REAL open interest from multiple exchanges"""
    return await derivatives_intel.get_aggregated_open_interest(symbol.upper() + "USDT")


@router.get("/ls/{symbol}")
async def api_real_ls(symbol: str):
    """Get REAL long/short ratio from Binance Futures"""
    return await derivatives_intel.get_aggregated_long_short(symbol.upper() + "USDT")


@router.get("/full/{symbol}")
async def api_full_derivatives(symbol: str):
    """Get full derivatives report from all exchanges"""
    return await derivatives_intel.get_full_derivatives_report(symbol.upper() + "USDT")


@router.get("/funding/exchange/{exchange}/{symbol}")
async def api_exchange_funding(exchange: str, symbol: str):
    """Get funding from specific exchange (okx, bitget, kucoin, gate)"""
    sym = symbol.upper() + "USDT"
    if exchange.lower() == "okx":
        return await derivatives_intel.get_funding_rate_okx(sym)
    elif exchange.lower() == "bitget":
        return await derivatives_intel.get_funding_rate_bitget(sym)
    elif exchange.lower() == "kucoin":
        return await derivatives_intel.get_funding_rate_kucoin(sym)
    elif exchange.lower() == "gate":
        return await derivatives_intel.get_funding_rate_gate(sym)
    elif exchange.lower() == "binance":
        return await derivatives_intel.get_long_short_ratio_binance(sym)
    return {"error": f"Unknown exchange: {exchange}"}
