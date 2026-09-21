"""
Quant Analyzer Engine API Routes
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/quant", tags=["quant_analyzer"])


def _get_engine():
    try:
        from quant_analyzer_engine import get_quant_engine
        engine = get_quant_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Quant Analyzer Engine not initialized")
        return engine
    except ImportError:
        raise HTTPException(status_code=503, detail="Quant Analyzer Engine module not found")


@router.get("/status")
async def get_status():
    """Engine status, config and stats"""
    engine = _get_engine()
    return engine.get_status()


@router.get("/scan")
async def run_scan():
    """Trigger an immediate scan across all pairs and return qualifying setups"""
    engine = _get_engine()
    if not engine.market_intel:
        raise HTTPException(status_code=503, detail="market_intel dependency not wired in yet")
    setups = await engine.scan_all()
    return {
        "setups_found": len(setups),
        "setups": setups
    }


@router.get("/analyze/{symbol}")
async def analyze_symbol(symbol: str):
    """
    Analyze a single symbol.
    symbol: coin name, e.g. BTC, ETH, SOL (USDT pair appended automatically)
    """
    engine = _get_engine()
    if not engine.market_intel:
        raise HTTPException(status_code=503, detail="market_intel dependency not wired in yet")

    symbol_clean = symbol.upper()
    if not symbol_clean.endswith("/USDT"):
        symbol_clean = f"{symbol_clean}/USDT"

    result = await engine.analyze_symbol(symbol_clean)
    if not result:
        return {
            "symbol": symbol_clean,
            "signal": None,
            "message": "No qualifying signal — score below threshold or TF conflict"
        }
    return result


@router.post("/toggle")
async def toggle_engine(active: bool):
    """Enable or disable the engine"""
    engine = _get_engine()
    engine.active = active
    return {"active": engine.active, "message": f"Quant Analyzer {'enabled' if active else 'paused'}"}
