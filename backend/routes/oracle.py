"""
ORACLE API Routes  ─  routes/oracle.py
=======================================
All ORACLE endpoints. Pure read-only — ORACLE never places trades.

Endpoints:
  GET /oracle/status                     — ORACLE status + score distribution
  GET /oracle/bias/{symbol}              — Full 5-layer analysis for one symbol
  GET /oracle/report                     — All pairs from last full scan
  GET /oracle/top?min_score=70           — Pairs above score threshold
  GET /oracle/opportunities?min_score=70&bias=BEARISH — Filtered pairs
  GET /oracle/scan/full                  — Trigger a full scan (background)
  GET /oracle/scan/status                — Live progress of current scan
  GET /oracle/scan/results               — Last full scan results sorted by score
  POST /oracle/toggle                    — Enable / disable ORACLE
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Optional

router = APIRouter(prefix="/oracle", tags=["oracle"])


def _get_oracle():
    try:
        from oracle_engine import get_oracle
        oracle = get_oracle()
        if not oracle:
            raise HTTPException(status_code=503, detail="ORACLE not initialized")
        return oracle
    except ImportError:
        raise HTTPException(status_code=503, detail="ORACLE module not found")


# ─── ORACLE ENGINE STEP 7: API ENDPOINTS ─────────────────────────────────────

@router.get("/status")
async def oracle_status():
    """ORACLE operational status, cache info, and score distribution from last scan."""
    oracle = _get_oracle()
    return oracle.get_status()


@router.get("/bias/{symbol}")
async def get_bias(symbol: str):
    """
    Full 5-layer ORACLE analysis for a single symbol.
    symbol: coin name (BTC, ETH, SOLUSDT, SOL/USDT all accepted)
    Fresh analysis — bypasses cache for instant accuracy.
    """
    oracle = _get_oracle()
    if not oracle.market_intel:
        raise HTTPException(status_code=503, detail="market_intel not wired in yet")

    result = await oracle.analyze(symbol, use_cache=False)
    if not result:
        raise HTTPException(status_code=500, detail=f"Analysis failed for {symbol}")
    return result


@router.get("/report")
async def get_report():
    """
    Current bias for all symbols analyzed in the last full scan.
    Sorted by score descending.
    """
    oracle = _get_oracle()
    results = oracle.get_report()
    return {
        "total":   len(results),
        "results": results,
        "last_scan": oracle._last_full_scan_time.isoformat() if oracle._last_full_scan_time else None,
    }


@router.get("/top")
async def get_top(
    min_score: int = Query(default=70, ge=0, le=100, description="Minimum ORACLE score"),
):
    """
    Returns all pairs from last scan with score >= min_score, sorted by score.
    """
    oracle = _get_oracle()
    results = oracle.get_top(min_score=min_score)
    return {
        "min_score": min_score,
        "count":     len(results),
        "results":   results,
    }


@router.get("/opportunities")
async def get_opportunities(
    min_score: int  = Query(default=70, ge=0, le=100, description="Minimum score"),
    bias:      Optional[str] = Query(default=None,  description="Filter by bias: BULLISH, BEARISH, NEUTRAL"),
):
    """
    Filter last full scan by minimum score and optional bias direction.
    Returns matching pairs sorted by score descending.
    """
    oracle = _get_oracle()
    results = oracle.get_top(min_score=min_score, bias=bias)
    return {
        "min_score": min_score,
        "bias":      bias,
        "count":     len(results),
        "results":   results,
    }


@router.get("/scan/full")
async def trigger_full_scan(background_tasks: BackgroundTasks):
    """
    Trigger a full scan of all available MEXC USDT perpetuals.
    Runs in the background — use /oracle/scan/status to track progress.
    Returns immediately with a scan_id.
    """
    oracle = _get_oracle()
    if not oracle.market_intel:
        raise HTTPException(status_code=503, detail="market_intel not wired in yet")

    if oracle._scan_in_progress:
        return {
            "message":  "Scan already in progress",
            "progress": oracle.get_scan_status(),
        }

    # Run scan in background
    background_tasks.add_task(oracle.scan_all)
    return {
        "message": "Full scan started in background",
        "estimated_pairs": len(oracle._all_pairs) if oracle._all_pairs else "unknown",
        "check_progress": "/api/oracle/scan/status",
    }


@router.get("/scan/status")
async def scan_status():
    """
    Live progress of the current scan (if running).
    Returns {in_progress, scanned, total, percent, scan_id}.
    """
    oracle = _get_oracle()
    return oracle.get_scan_status()


@router.get("/scan/results")
async def scan_results():
    """
    Last full scan results sorted by score descending.
    Includes all pairs regardless of score (NEUTRAL pairs included).
    """
    oracle = _get_oracle()
    results = oracle.get_report()
    return {
        "scan_time":   oracle._last_full_scan_time.isoformat() if oracle._last_full_scan_time else None,
        "total_pairs": len(results),
        "results":     results,
    }


@router.post("/toggle")
async def toggle_oracle(active: bool):
    """Enable or pause ORACLE."""
    oracle = _get_oracle()
    oracle.active = active
    return {
        "active":  oracle.active,
        "message": f"ORACLE {'activated' if active else 'paused'}",
    }
