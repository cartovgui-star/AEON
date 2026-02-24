"""
Aggressive Scalper API Routes
High-frequency scalping signals alongside V2.1 strategy
"""

from fastapi import APIRouter, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scalper", tags=["scalper"])


class ScalperSettingsUpdate(BaseModel):
    lookback_vol: Optional[int] = None
    momentum_period: Optional[int] = None
    profit_target_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    volume_threshold: Optional[float] = None
    rsi_overbought: Optional[int] = None
    rsi_oversold: Optional[int] = None
    roc_threshold: Optional[float] = None
    max_hold_bars: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/signals/{symbol}")
async def api_scalper_signals(symbol: str, timeframe: str = "5m"):
    """
    Get scalp signals for a specific symbol
    
    Timeframes: 5m, 15m, 30m
    Signal: 1=BUY, -1=SELL, 0=HOLD
    Strength: 1-3 (3 = highest confidence)
    """
    from aggressive_scalper import scalper
    
    # Format symbol
    if "/" not in symbol:
        symbol = symbol.upper() + "/USDT"
    else:
        symbol = symbol.upper()
    
    result = await scalper.analyze_symbol(symbol, timeframe)
    return result


@router.get("/scan")
async def api_scalper_scan(timeframe: str = "5m"):
    """
    Scan all 15 symbols for scalp signals on a specific timeframe
    Returns only symbols with active signals (sorted by strength)
    """
    from aggressive_scalper import scalper
    
    signals = await scalper.scan_all_symbols(timeframe)
    
    return {
        "timeframe": timeframe,
        "total_signals": len(signals),
        "signals": signals
    }


@router.get("/scan/all")
async def api_scalper_scan_all():
    """
    Scan all symbols across all timeframes (5m, 15m, 30m)
    """
    from aggressive_scalper import scalper
    
    results = await scalper.scan_all_timeframes()
    
    total = sum(len(sigs) for sigs in results.values())
    
    return {
        "total_signals": total,
        "by_timeframe": results
    }


@router.get("/opportunities")
async def api_scalper_opportunities(min_strength: int = 2):
    """
    Get best scalp opportunities across all timeframes
    Filtered by minimum strength (default: 2)
    """
    from aggressive_scalper import scalper
    
    opportunities = await scalper.get_best_opportunities(min_strength)
    
    return {
        "min_strength": min_strength,
        "count": len(opportunities),
        "opportunities": opportunities
    }


@router.get("/backtest/{symbol}")
async def api_scalper_backtest_symbol(symbol: str, timeframe: str = "5m", days: int = 7):
    """
    Backtest scalper strategy on a single symbol
    """
    from aggressive_scalper import scalper
    
    # Format symbol
    if "/" not in symbol:
        symbol = symbol.upper() + "/USDT"
    else:
        symbol = symbol.upper()
    
    result = await scalper.backtest_symbol(symbol, timeframe, days)
    return result


@router.get("/backtest/all/{timeframe}")
async def api_scalper_backtest_all(timeframe: str = "5m", days: int = 7):
    """
    Backtest scalper strategy on all 15 symbols
    """
    from aggressive_scalper import scalper
    
    result = await scalper.backtest_all(timeframe, days)
    return result


@router.get("/settings")
async def api_scalper_settings():
    """Get current scalper settings"""
    from aggressive_scalper import scalper
    
    return {
        "settings": scalper.get_settings(),
        "available_symbols": [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT',
            'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ARB/USDT', 'OP/USDT'
        ],
        "available_timeframes": ['5m', '15m', '30m']
    }


@router.post("/settings")
async def api_scalper_update_settings(settings: ScalperSettingsUpdate):
    """Update scalper settings"""
    from aggressive_scalper import scalper
    
    updates = settings.dict(exclude_none=True)
    new_settings = scalper.update_settings(updates)
    
    return {
        "success": True,
        "settings": new_settings
    }


@router.post("/toggle")
async def api_scalper_toggle(enabled: bool = True):
    """Enable or disable the scalper"""
    from aggressive_scalper import scalper
    
    scalper.settings['enabled'] = enabled
    
    return {
        "success": True,
        "enabled": enabled,
        "message": f"Scalper {'enabled' if enabled else 'disabled'}"
    }


@router.get("/status")
async def api_scalper_status():
    """Get scalper status and active signals"""
    from aggressive_scalper import scalper
    
    return {
        "enabled": scalper.settings['enabled'],
        "is_scanning": scalper.is_scanning,
        "active_signals": len(scalper.active_signals),
        "settings_summary": {
            "profit_target": f"{scalper.settings['profit_target_pct']}%",
            "stop_loss": f"{scalper.settings['stop_loss_pct']}%",
            "volume_threshold": f"{scalper.settings['volume_threshold']}x",
            "rsi_range": f"{scalper.settings['rsi_oversold']}-{scalper.settings['rsi_overbought']}",
        }
    }


@router.get("/compare-timeframes")
async def api_scalper_compare_timeframes(days: int = 7):
    """
    Compare scalper performance across all timeframes
    Runs backtest on 5m, 15m, 30m and compares results
    """
    from aggressive_scalper import scalper
    
    results = {}
    
    for tf in ['5m', '15m', '30m']:
        result = await scalper.backtest_all(tf, days)
        results[tf] = {
            'total_trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'total_pnl': result['total_pnl'],
        }
    
    # Find best timeframe
    best_tf = max(results.items(), key=lambda x: x[1]['total_pnl'])[0]
    
    return {
        "days": days,
        "by_timeframe": results,
        "best_timeframe": best_tf,
        "recommendation": f"Best performance on {best_tf} with {results[best_tf]['win_rate']}% win rate"
    }
