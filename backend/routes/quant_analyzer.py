"""
Quant Analyzer API Routes
Pure multi-factor technical analysis and ranking — no trading.
"""

import asyncio
import aiohttp
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from quant_analyzer_engine import get_quant_engine

router = APIRouter(prefix="/quant", tags=["quant_analyzer"])

DEFAULT_SYMBOLS = "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,AVAX/USDT,DOGE/USDT,LINK/USDT,DOT/USDT,ADA/USDT"

# In-memory scan cache so /status and /scan don't run fresh analysis on every poll
_scan_cache: dict = {}


@router.get("/status")
async def get_quant_status():
    """
    Returns current quant engine status — last scan summary, win stats, config.
    Frontend polls this every 30s to show the status bar.
    """
    cached = _scan_cache.get("last_result")
    if cached:
        reports = cached.get("ranked_reports", [])
        buys  = sum(1 for r in reports if r.get("signal") in ("Buy", "Strong Buy"))
        sells = sum(1 for r in reports if r.get("signal") in ("Sell", "Strong Sell"))
        high_score = [r for r in reports if r.get("score", 0) >= 50]
        return {
            "active": True,
            "total_analyzed": cached.get("total_analyzed", 0),
            "total_signals": len(high_score),
            "daily_signals": len(high_score),
            "wins":   buys,
            "losses": sells,
            "last_scan": cached.get("generated_at"),
            "last_signal": reports[0].get("signal") if reports else None,
            "config": {"symbols": DEFAULT_SYMBOLS, "threshold": 50},
        }
    return {
        "active": True,
        "total_analyzed": 0,
        "total_signals": 0,
        "daily_signals": 0,
        "wins": 0,
        "losses": 0,
        "last_scan": None,
        "last_signal": None,
        "config": {"symbols": DEFAULT_SYMBOLS, "threshold": 50},
    }


@router.get("/scan")
async def scan_coins():
    """
    Run full quant scan on DEFAULT_SYMBOLS and return ranked setups.
    Results cached for 5 minutes to avoid hammering external APIs.
    """
    now = datetime.now(timezone.utc)
    cached = _scan_cache.get("last_result")
    cached_ts = _scan_cache.get("cached_at")
    if cached and cached_ts and (now - cached_ts).total_seconds() < 300:
        reports = cached.get("ranked_reports", [])
        return {"setups": reports, "cached": True, "generated_at": cached.get("generated_at")}

    symbol_list = [s.strip().upper() for s in DEFAULT_SYMBOLS.split(",") if s.strip()]
    engine = get_quant_engine()
    result = await engine.analyze_coins(symbol_list)
    _scan_cache["last_result"] = result
    _scan_cache["cached_at"] = now
    return {"setups": result.get("ranked_reports", []), "cached": False, "generated_at": result.get("generated_at")}


@router.get("/analyze")
async def analyze_coins(
    symbols: str = Query(DEFAULT_SYMBOLS, description="Comma-separated symbols to analyze"),
):
    """
    Run full quant analysis on provided symbols.
    Returns ranked report cards + watchlist summary table.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    engine = get_quant_engine()
    return await engine.analyze_coins(symbol_list)


@router.get("/analyze/{symbol}")
async def analyze_single(symbol: str):
    """
    Full quant analysis for a single coin.
    """
    from quant_analyzer_engine import CoinAnalyzer
    loop = asyncio.get_running_loop()
    analyzer = CoinAnalyzer()
    result = await loop.run_in_executor(None, analyzer.analyze, symbol.upper())
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    return result


@router.get("/debug/{symbol}")
async def debug_scorers(symbol: str, direction: str = Query("long")):
    """
    Run each sub-scorer independently and return raw pts + breakdown.
    Use to diagnose why scores are low.
    """
    from quant_analyzer_v2 import OnChainScorer, SentimentScorer, OrderBookScorer, MarketStructureScorer
    from quant_analyzer_engine import CoinAnalyzer

    loop = asyncio.get_running_loop()
    # Normalize symbol: BTCUSDT → BTC/USDT, BTC → BTC/USDT
    raw = symbol.upper()
    if "/" not in raw:
        if raw.endswith("USDT"):
            raw = raw[:-4] + "/USDT"
        elif raw.endswith("BUSD"):
            raw = raw[:-4] + "/BUSD"
    sym = raw

    # Run CoinAnalyzer for market structure
    analyzer = CoinAnalyzer()
    analysis = await loop.run_in_executor(None, analyzer.analyze, sym)
    ms_pts, ms_bd = MarketStructureScorer.score_from_analysis(analysis, direction)

    on_chain_scorer = OnChainScorer(db=None)
    sentiment_scorer = SentimentScorer()
    ob_scorer = OrderBookScorer()

    async with aiohttp.ClientSession() as session:
        oc_result, ob_result, sent_result = await asyncio.gather(
            on_chain_scorer.score(sym, direction, session),
            ob_scorer.score(sym, direction, session),
            sentiment_scorer.score(sym, direction, session),
            return_exceptions=True,
        )

    oc_pts, oc_bd   = oc_result  if not isinstance(oc_result,   Exception) else (0, {"error": str(oc_result)})
    ob_pts, ob_bd   = ob_result  if not isinstance(ob_result,   Exception) else (0, {"error": str(ob_result)})
    sent_pts, s_bd  = sent_result if not isinstance(sent_result, Exception) else (0, {"error": str(sent_result)})

    total = oc_pts + ob_pts + ms_pts + sent_pts
    return {
        "symbol": sym,
        "direction": direction,
        "total_score": total,
        "scorers": {
            "on_chain":        {"pts": oc_pts,   "max": 30, "breakdown": oc_bd},
            "order_book":      {"pts": ob_pts,   "max": 25, "breakdown": ob_bd},
            "market_structure":{"pts": ms_pts,   "max": 25, "breakdown": ms_bd},
            "sentiment":       {"pts": sent_pts, "max": 20, "breakdown": s_bd},
        },
    }
