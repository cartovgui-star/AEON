"""
V2.1 Backtesting API Routes
Test the HIGH WIN RATE strategy against MEXC historical data
"""

from fastapi import APIRouter, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest/v21", tags=["backtest-v21"])

# Store backtest results and status
backtest_state = {
    "is_running": False,
    "progress": 0,
    "current_symbol": "",
    "last_result": None,
    "error": None,
}


class BacktestRequest(BaseModel):
    symbols: Optional[List[str]] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    interval: Optional[str] = "1h"
    days: Optional[int] = 30


class BacktestResult(BaseModel):
    data_source: str
    symbols: List[str]
    interval: str
    days: int
    win_rate: float
    old_win_rate: float
    improvement: float
    total_trades: int
    wins: int
    losses: int


async def run_backtest_task(symbols: List[str], interval: str, days: int):
    """Background task to run backtest"""
    global backtest_state
    
    try:
        from backtest_v21 import BacktestV21Engine
        
        backtest_state["is_running"] = True
        backtest_state["progress"] = 0
        backtest_state["error"] = None
        
        engine = BacktestV21Engine()
        result = await engine.run_full_backtest(symbols=symbols, interval=interval, days=days)
        
        backtest_state["last_result"] = result
        backtest_state["progress"] = 100
        
        logger.info(f"Backtest completed: {result.get('win_rate', 0)}% win rate")
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        backtest_state["error"] = str(e)
    finally:
        backtest_state["is_running"] = False


@router.post("/run")
async def api_run_backtest_v21(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    Run V2.1 backtest against MEXC historical data
    
    This tests the HIGH WIN RATE strategy filters:
    - 200 EMA Trend Filter
    - ADX > 25 (trending market)
    - Volume > 1.5x average
    - Session filter (London/NY)
    - 90% confidence, 5/5 confirmations, 3:1 R:R
    """
    global backtest_state
    
    if backtest_state["is_running"]:
        return {
            "status": "already_running",
            "message": "Backtest is already in progress",
            "progress": backtest_state["progress"],
            "current_symbol": backtest_state["current_symbol"]
        }
    
    # Start backtest in background
    background_tasks.add_task(
        run_backtest_task,
        request.symbols,
        request.interval,
        request.days
    )
    
    return {
        "status": "started",
        "message": f"Backtest started for {len(request.symbols)} symbols over {request.days} days",
        "symbols": request.symbols,
        "interval": request.interval,
        "days": request.days
    }


@router.get("/status")
async def api_backtest_v21_status():
    """Get current backtest status"""
    global backtest_state
    
    return {
        "is_running": backtest_state["is_running"],
        "progress": backtest_state["progress"],
        "current_symbol": backtest_state["current_symbol"],
        "has_result": backtest_state["last_result"] is not None,
        "error": backtest_state["error"]
    }


@router.get("/result")
async def api_backtest_v21_result():
    """Get the last backtest result"""
    global backtest_state
    
    if backtest_state["last_result"] is None:
        return {
            "status": "no_result",
            "message": "No backtest has been run yet. Use POST /api/backtest/v21/run to start one."
        }
    
    return {
        "status": "success",
        "result": backtest_state["last_result"]
    }


@router.get("/quick/{symbol}")
async def api_quick_backtest_v21(symbol: str, interval: str = "1h", days: int = 30):
    """
    Run a quick synchronous backtest for a single symbol
    Returns immediately with results (may take 10-30 seconds)
    """
    try:
        from backtest_v21 import BacktestV21Engine
        
        engine = BacktestV21Engine()
        
        # Format symbol correctly
        if "/" not in symbol:
            symbol = symbol.upper().replace("USDT", "/USDT")
        
        result = await engine.run_full_backtest(
            symbols=[symbol],
            interval=interval,
            days=days
        )
        
        return {
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick backtest error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/settings")
async def api_backtest_v21_settings():
    """Get V2.1 strategy settings used for backtesting"""
    from backtest_v21 import V21_SETTINGS
    
    return {
        "settings": V21_SETTINGS,
        "description": {
            "min_confidence": "Minimum confidence % required for trade (raised from 80% to 90%)",
            "min_confirmations": "Number of confirmations needed (raised from 3 to 5)",
            "min_rr_ratio": "Minimum risk:reward ratio (raised from 2:1 to 3:1)",
            "ema_no_trade_zone_pct": "Skip trades within this % of 200 EMA",
            "min_adx": "Minimum ADX for trending market filter",
            "min_volume_multiplier": "Required volume vs 20-period average",
            "session_filter": "Only trade during London/NY sessions for SCALP/DAY"
        }
    }


@router.get("/compare")
async def api_backtest_v21_compare(days: int = 30, interval: str = "1h"):
    """
    Compare V2.1 strategy performance across BTC, ETH, and SOL
    """
    try:
        from backtest_v21 import BacktestV21Engine
        
        engine = BacktestV21Engine()
        result = await engine.run_full_backtest(
            symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            interval=interval,
            days=days
        )
        
        # Build comparison table
        comparison = []
        for symbol_result in result.get("results_by_symbol", []):
            trades = symbol_result.get("trades", [])
            wins = sum(1 for t in trades if t.get("outcome") == "WIN")
            losses = sum(1 for t in trades if t.get("outcome") == "LOSS")
            total = wins + losses
            
            comparison.append({
                "symbol": symbol_result.get("symbol", "Unknown"),
                "candles_analyzed": symbol_result.get("total_candles", 0),
                "old_signals": symbol_result.get("old_signals", 0),
                "v21_signals": symbol_result.get("new_signals", 0),
                "trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / total * 100), 1) if total > 0 else 0,
                "filter_breakdown": symbol_result.get("filter_breakdown", {})
            })
        
        return {
            "status": "success",
            "data_source": "MEXC",
            "interval": interval,
            "days": days,
            "aggregate": {
                "total_trades": result.get("total_trades", 0),
                "wins": result.get("wins", 0),
                "losses": result.get("losses", 0),
                "win_rate": result.get("win_rate", 0),
                "old_win_rate": result.get("old_win_rate", 19),
                "improvement": result.get("improvement", 0),
                "signal_reduction_pct": result.get("signal_reduction_pct", 0)
            },
            "by_symbol": comparison,
            "filter_effectiveness": result.get("filter_breakdown", {}),
            "recommendations": result.get("recommendations", []),
            "timestamp": result.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"Compare backtest error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
