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



class MultiConfidenceRequest(BaseModel):
    symbols: Optional[List[str]] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    days: Optional[int] = 30
    confidence_levels: Optional[List[int]] = [65, 70, 75, 80, 85, 90]


class MultiTimeframeRequest(BaseModel):
    symbols: Optional[List[str]] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    days: Optional[int] = 30
    timeframes: Optional[List[str]] = ["15m", "1h", "4h"]
    min_confidence: Optional[int] = 75


@router.post("/multi-confidence")
async def api_multi_confidence_backtest(request: MultiConfidenceRequest):
    """
    Run backtest across multiple confidence levels (65-90%)
    to find the optimal confidence threshold.
    
    This helps answer: "What confidence % gives the best balance 
    of win rate and trade frequency?"
    """
    try:
        from backtest_v21 import run_multi_confidence_backtest
        
        result = await run_multi_confidence_backtest(
            symbols=request.symbols,
            days=request.days,
            confidence_levels=request.confidence_levels
        )
        
        return {
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Multi-confidence backtest error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/multi-timeframe")
async def api_multi_timeframe_backtest(request: MultiTimeframeRequest):
    """
    Run backtest across multiple timeframes (15m, 1h, 4h)
    to find which timeframe works best with V2.1 strategy.
    
    This helps answer: "Which timeframe gives the best signals?"
    """
    try:
        from backtest_v21 import run_multi_timeframe_backtest
        
        result = await run_multi_timeframe_backtest(
            symbols=request.symbols,
            days=request.days,
            timeframes=request.timeframes,
            min_confidence=request.min_confidence
        )
        
        return {
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Multi-timeframe backtest error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/comprehensive")
async def api_comprehensive_backtest(
    symbols: Optional[List[str]] = None,
    days: int = 30
):
    """
    Run comprehensive backtest testing:
    1. Multiple confidence levels (65-90%)
    2. Multiple timeframes (15m, 1h, 4h)
    3. Find optimal combination
    
    This is the full analysis to find the best strategy settings.
    Takes longer but provides complete insights.
    """
    try:
        from backtest_v21 import run_comprehensive_backtest
        
        if symbols is None:
            symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        result = await run_comprehensive_backtest(
            symbols=symbols,
            days=days
        )
        
        return {
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Comprehensive backtest error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/confidence-range")
async def api_quick_confidence_range(days: int = 30):
    """
    Quick test of confidence levels 65%, 75%, 85%, 90%
    Returns win rate at each level for comparison
    """
    try:
        from backtest_v21 import run_multi_confidence_backtest
        
        result = await run_multi_confidence_backtest(
            symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            days=days,
            confidence_levels=[65, 75, 85, 90]
        )
        
        return {
            "status": "success",
            "data_source": "MEXC",
            "days": days,
            "results": result.get("results_by_confidence", []),
            "optimal": result.get("optimal_confidence"),
            "recommendation": result.get("recommendation"),
            "timestamp": result.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"Confidence range test error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/analyze-trades")
async def api_analyze_trades():
    """
    Mine all 841 closed paper_trades for patterns.
    Returns: engine×tf heat map, confirmation rankings, R:R simulation,
    symbol breakdown, close-reason analysis, and quantum weight recommendations.
    """
    try:
        import app_state
        if app_state.db is None:
            return {"error": "DB not ready"}

        from collections import defaultdict

        trades = await app_state.db.paper_trades.find(
            {"status": "closed", "realized_pnl": {"$exists": True}},
            {"_id": 0}
        ).to_list(5000)

        if not trades:
            return {"error": "No closed trades found"}

        # ── helpers ───────────────────────────────────────────────────────────
        def eng(t):
            return (t.get("strategy") or t.get("engine")
                    or (t.get("signal_data") or {}).get("engine", "unknown")).upper()

        def tf(t):
            return (t.get("signal_data") or {}).get("timeframe", "?")

        def pnl(t):
            return t.get("realized_pnl", 0) or 0

        def is_win(t):
            return pnl(t) > 0

        def rr_bucket(t):
            entry  = t.get("entry_price", 0)
            sl     = t.get("stop_loss", 0)
            tp     = t.get("take_profit", 0)
            if not (entry and sl and tp and entry != sl):
                return None
            risk   = abs(entry - sl)
            reward = abs(tp - entry)
            return round(reward / risk, 2) if risk else None

        # ── 1. By engine × timeframe ──────────────────────────────────────────
        etf = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
        for t in trades:
            key = (eng(t), tf(t))
            etf[key]["wins" if is_win(t) else "losses"] += 1
            etf[key]["pnl"] += pnl(t)

        heat_map = []
        for (engine_name, timeframe), s in sorted(etf.items()):
            total = s["wins"] + s["losses"]
            heat_map.append({
                "engine":    engine_name,
                "timeframe": timeframe,
                "trades":    total,
                "wins":      s["wins"],
                "losses":    s["losses"],
                "win_rate":  round(s["wins"] / total * 100, 1) if total else 0,
                "pnl":       round(s["pnl"], 2),
            })
        heat_map.sort(key=lambda x: x["win_rate"], reverse=True)

        # ── 2. Confirmation tag rankings ──────────────────────────────────────
        tag_stats = defaultdict(lambda: {"wins": 0, "total": 0, "pnl": 0.0})
        for t in trades:
            tags = (t.get("signal_data") or {}).get("confirmations", [])
            for tag in tags:
                tag_stats[tag]["total"] += 1
                tag_stats[tag]["pnl"] += pnl(t)
                if is_win(t):
                    tag_stats[tag]["wins"] += 1

        confirmation_ranks = []
        for tag, s in tag_stats.items():
            if s["total"] >= 5:   # min 5 occurrences
                confirmation_ranks.append({
                    "tag":       tag,
                    "total":     s["total"],
                    "wins":      s["wins"],
                    "win_rate":  round(s["wins"] / s["total"] * 100, 1),
                    "avg_pnl":   round(s["pnl"] / s["total"], 2),
                })
        confirmation_ranks.sort(key=lambda x: x["win_rate"], reverse=True)

        # ── 3. R:R simulation ─────────────────────────────────────────────────
        # A trade "wins" at test_rr if it closed via take_profit/trailing_stop
        # AND its actual rr_ratio >= test_rr (meaning TP was set at least that far).
        # Stop_loss / liquidation are always losses regardless of RR target.
        rr_eligible = [t for t in trades if t.get("rr_ratio") and t.get("close_reason")]
        rr_sim = {}
        for test_rr in [1.0, 1.5, 2.0, 2.5, 3.0]:
            wins_at_rr = sum(
                1 for t in rr_eligible
                if t.get("close_reason") in ("take_profit", "trailing_stop")
                and (t.get("rr_ratio") or 0) >= test_rr
            )
            rr_sim[str(test_rr)] = {
                "rr":       test_rr,
                "wins":     wins_at_rr,
                "total":    len(rr_eligible),
                "win_rate": round(wins_at_rr / len(rr_eligible) * 100, 1) if rr_eligible else 0,
            }

        # ── 4. Symbol breakdown ───────────────────────────────────────────────
        sym_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
        for t in trades:
            s = t.get("symbol", "?")
            sym_stats[s]["wins" if is_win(t) else "losses"] += 1
            sym_stats[s]["pnl"] += pnl(t)

        by_symbol = []
        for sym, s in sorted(sym_stats.items()):
            total = s["wins"] + s["losses"]
            by_symbol.append({
                "symbol":   sym,
                "trades":   total,
                "wins":     s["wins"],
                "win_rate": round(s["wins"] / total * 100, 1) if total else 0,
                "pnl":      round(s["pnl"], 2),
            })
        by_symbol.sort(key=lambda x: x["win_rate"], reverse=True)

        # ── 5. Close-reason breakdown ─────────────────────────────────────────
        reason_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
        for t in trades:
            r = t.get("close_reason", "unknown")
            reason_stats[r]["count"] += 1
            reason_stats[r]["pnl"] += pnl(t)

        close_reasons = [
            {"reason": r, "count": s["count"], "total_pnl": round(s["pnl"], 2)}
            for r, s in sorted(reason_stats.items(), key=lambda x: -x[1]["count"])
        ]

        # ── 6. Quantum weight recommendations ────────────────────────────────
        # Score each engine: EV = avg_pnl × win_rate / 100
        engine_scores = defaultdict(lambda: {"wins": 0, "total": 0, "pnl": 0.0})
        for t in trades:
            e = eng(t)
            engine_scores[e]["total"] += 1
            engine_scores[e]["pnl"] += pnl(t)
            if is_win(t):
                engine_scores[e]["wins"] += 1

        recommendations = []
        for e, s in sorted(engine_scores.items()):
            if s["total"] < 10:
                continue
            wr   = s["wins"] / s["total"]
            avg  = s["pnl"] / s["total"]
            ev   = wr * avg
            rec  = "INCREASE_WEIGHT" if ev > 0 else ("DECREASE_WEIGHT" if ev < -50 else "HOLD")
            if e == "VOLUME_PROFILE":
                rec = "DISABLE"   # 5% WR override
            recommendations.append({
                "engine":        e,
                "trades":        s["total"],
                "win_rate":      round(wr * 100, 1),
                "avg_pnl":       round(avg, 2),
                "expected_value": round(ev, 2),
                "recommendation": rec,
            })
        recommendations.sort(key=lambda x: x["expected_value"], reverse=True)

        # ── summary ───────────────────────────────────────────────────────────
        total  = len(trades)
        wins   = sum(1 for t in trades if is_win(t))
        total_pnl = sum(pnl(t) for t in trades)

        return {
            "summary": {
                "total_trades":  total,
                "wins":          wins,
                "losses":        total - wins,
                "win_rate":      round(wins / total * 100, 1) if total else 0,
                "total_pnl":     round(total_pnl, 2),
            },
            "heat_map":           heat_map,
            "confirmation_ranks": confirmation_ranks[:20],
            "rr_simulation":      list(rr_sim.values()),
            "by_symbol":          by_symbol[:20],
            "close_reasons":      close_reasons,
            "recommendations":    recommendations,
        }

    except Exception as e:
        logger.error(f"analyze-trades error: {e}", exc_info=True)
        return {"error": str(e)}


class ReplayRequest(BaseModel):
    engine:    Optional[str]  = None   # filter by engine
    timeframe: Optional[str]  = None   # filter by timeframe
    direction: Optional[str]  = None   # LONG / SHORT
    rr_test:   Optional[float] = 2.5   # RR to simulate
    limit:     Optional[int]  = 200    # max trades to replay


@router.post("/replay")
async def api_replay_trades(req: ReplayRequest):
    """
    Replay a filtered slice of closed trades through the simulator
    with an alternative R:R ratio and return per-trade outcomes.
    Uses actual close_price as proxy (no live kline fetch needed).
    """
    try:
        import app_state
        if app_state.db is None:
            return {"error": "DB not ready"}

        query: dict = {"status": "closed", "realized_pnl": {"$exists": True}}
        if req.engine:
            eng_upper = req.engine.upper()
            query["$or"] = [
                {"strategy": {"$regex": req.engine, "$options": "i"}},
                {"engine":   {"$regex": req.engine, "$options": "i"}},
                {"signal_data.engine": {"$regex": req.engine, "$options": "i"}},
            ]
        if req.timeframe:
            query["signal_data.timeframe"] = req.timeframe
        if req.direction:
            query["direction"] = req.direction.upper()

        trades = await app_state.db.paper_trades.find(
            query, {"_id": 0}
        ).sort("opened_at", -1).limit(req.limit).to_list(req.limit)

        if not trades:
            return {"replayed": [], "summary": {}}

        replayed = []
        wins = losses = skipped = 0

        for t in trades:
            entry     = t.get("entry_price", 0)
            sl        = t.get("stop_loss", 0)
            cp        = t.get("close_price") or t.get("exit_price", 0)
            direction = t.get("direction", "LONG")
            actual_pnl = t.get("realized_pnl", 0) or 0

            if not (entry and sl and cp and entry != sl):
                skipped += 1
                continue

            risk   = abs(entry - sl)
            alt_tp = (entry + risk * req.rr_test) if direction == "LONG" else (entry - risk * req.rr_test)

            if direction == "LONG":
                sim_win = cp >= alt_tp
            else:
                sim_win = cp <= alt_tp

            actual_win = actual_pnl > 0
            flip = "was_loss_now_win" if (sim_win and not actual_win) else (
                   "was_win_now_loss" if (not sim_win and actual_win) else
                   "same_win" if sim_win else "same_loss")

            sim_pnl = abs(actual_pnl) if sim_win else -abs(actual_pnl)

            if sim_win:
                wins += 1
            else:
                losses += 1

            replayed.append({
                "symbol":     t.get("symbol"),
                "direction":  direction,
                "engine":     t.get("strategy") or t.get("engine") or
                              (t.get("signal_data") or {}).get("engine"),
                "timeframe":  (t.get("signal_data") or {}).get("timeframe"),
                "entry":      entry,
                "sl":         sl,
                "actual_tp":  t.get("take_profit"),
                "alt_tp":     round(alt_tp, 6),
                "close_price": cp,
                "actual_pnl": round(actual_pnl, 2),
                "sim_pnl":    round(sim_pnl, 2),
                "actual_win": actual_win,
                "sim_win":    sim_win,
                "flip":       flip,
                "close_reason": t.get("close_reason"),
                "opened_at":  str(t.get("opened_at", "")),
            })

        total_sim_pnl  = sum(r["sim_pnl"] for r in replayed)
        total_real_pnl = sum(r["actual_pnl"] for r in replayed)
        total = wins + losses

        return {
            "rr_tested":  req.rr_test,
            "filter":     {"engine": req.engine, "timeframe": req.timeframe, "direction": req.direction},
            "summary": {
                "total":       total,
                "skipped":     skipped,
                "wins":        wins,
                "losses":      losses,
                "win_rate":    round(wins / total * 100, 1) if total else 0,
                "sim_pnl":     round(total_sim_pnl, 2),
                "real_pnl":    round(total_real_pnl, 2),
                "pnl_delta":   round(total_sim_pnl - total_real_pnl, 2),
                "flipped_wins":  sum(1 for r in replayed if r["flip"] == "was_loss_now_win"),
                "flipped_losses": sum(1 for r in replayed if r["flip"] == "was_win_now_loss"),
            },
            "replayed": replayed,
        }

    except Exception as e:
        logger.error(f"replay error: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/monte-carlo")
async def api_monte_carlo(
    simulations: int = 1000,
    sample_size: int = 200,
    engine: Optional[str] = None,
    timeframe: Optional[str] = None,
):
    """
    Monte Carlo simulation on real closed trades.
    Randomly resamples `sample_size` trades with replacement `simulations` times.
    Returns percentile equity curves + drawdown/final-PnL distributions.
    """
    import app_state, random, math
    if app_state.db is None:
        return {"error": "DB not ready"}

    try:
        query: dict = {"status": "closed", "realized_pnl": {"$exists": True}}
        if engine:
            query["$or"] = [
                {"strategy": {"$regex": engine, "$options": "i"}},
                {"engine":   {"$regex": engine, "$options": "i"}},
            ]
        if timeframe:
            query["signal_data.timeframe"] = timeframe

        raw = await app_state.db.paper_trades.find(
            query, {"realized_pnl": 1, "_id": 0}
        ).to_list(2000)

        pnls = [float(t.get("realized_pnl") or 0) for t in raw if t.get("realized_pnl") is not None]

        if len(pnls) < 10:
            return {"error": "Not enough closed trades"}

        simulations = min(simulations, 2000)
        sample_size = min(sample_size, len(pnls))

        # Run simulations
        all_curves = []   # list of cumulative PnL arrays
        final_pnls = []
        max_dds    = []

        for _ in range(simulations):
            sample = random.choices(pnls, k=sample_size)
            curve  = []
            peak   = 0.0
            max_dd = 0.0
            cum    = 0.0
            for p in sample:
                cum   += p
                curve.append(round(cum, 2))
                if cum > peak:
                    peak = cum
                dd = peak - cum
                if dd > max_dd:
                    max_dd = dd
            all_curves.append(curve)
            final_pnls.append(round(cum, 2))
            max_dds.append(round(max_dd, 2))

        # Build percentile bands at each trade step
        percentiles_wanted = [5, 25, 50, 75, 95]
        curve_bands = []
        for i in range(sample_size):
            vals = sorted(c[i] for c in all_curves)
            n    = len(vals)
            def pct(p):
                idx = max(0, min(n - 1, int(p / 100 * n)))
                return vals[idx]
            curve_bands.append({
                "trade": i + 1,
                "p5":  pct(5),
                "p25": pct(25),
                "p50": pct(50),
                "p75": pct(75),
                "p95": pct(95),
            })

        # Distribution stats
        final_pnls_s = sorted(final_pnls)
        max_dds_s    = sorted(max_dds)
        n = len(final_pnls_s)
        def pct(arr, p):
            idx = max(0, min(len(arr) - 1, int(p / 100 * len(arr))))
            return arr[idx]

        wins_rate = sum(1 for p in final_pnls if p > 0) / n * 100

        return {
            "simulations":  simulations,
            "sample_size":  sample_size,
            "source_trades": len(pnls),
            "engine_filter": engine,
            "tf_filter":     timeframe,
            "curve_bands":   curve_bands,
            "final_pnl_dist": {
                "p5":    pct(final_pnls_s, 5),
                "p25":   pct(final_pnls_s, 25),
                "p50":   pct(final_pnls_s, 50),
                "p75":   pct(final_pnls_s, 75),
                "p95":   pct(final_pnls_s, 95),
                "mean":  round(sum(final_pnls) / n, 2),
                "profitable_pct": round(wins_rate, 1),
            },
            "max_drawdown_dist": {
                "p5":   pct(max_dds_s, 5),
                "p25":  pct(max_dds_s, 25),
                "p50":  pct(max_dds_s, 50),
                "p75":  pct(max_dds_s, 75),
                "p95":  pct(max_dds_s, 95),
                "mean": round(sum(max_dds) / n, 2),
            },
        }

    except Exception as e:
        logger.error(f"monte-carlo error: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/timeframe-comparison")
async def api_timeframe_comparison(days: int = 30, confidence: int = 75):
    """
    Compare strategy performance across timeframes
    using specified confidence level
    """
    try:
        from backtest_v21 import run_multi_timeframe_backtest
        
        result = await run_multi_timeframe_backtest(
            symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            days=days,
            timeframes=["15m", "1h", "4h"],
            min_confidence=confidence
        )
        
        return {
            "status": "success",
            "data_source": "MEXC",
            "days": days,
            "confidence_used": confidence,
            "results": result.get("results_by_timeframe", []),
            "best_timeframe": result.get("best_timeframe"),
            "recommendation": result.get("recommendation"),
            "timestamp": result.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"Timeframe comparison error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
