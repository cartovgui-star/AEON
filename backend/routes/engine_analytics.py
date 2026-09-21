"""
ENGINE ANALYTICS ROUTES
========================
Real engine performance vs simulation targets.

GET /api/paper/engine-stats    — per-engine live win rate, PF, expectancy, MaxDD
GET /api/paper/sim-comparison  — real vs 10,000-trade sim side-by-side
GET /api/paper/engine-signals  — open (unresolved) signal log
"""

from fastapi import APIRouter
import app_state

router = APIRouter()


@router.get("/paper/engine-stats")
async def api_engine_stats():
    """
    Per-engine live performance from real signal history.
    Aggregated from engine_trades MongoDB collection.
    """
    if not app_state.engine_paper_tracker:
        return {"error": "Engine paper tracker not initialized"}

    stats = await app_state.engine_paper_tracker.get_engine_stats()

    # Sort by win rate descending
    ranked = sorted(stats.values(), key=lambda x: x.get("win_rate", 0), reverse=True)

    return {
        "engines": ranked,
        "total_engines_tracked": len(ranked),
        "total_closed_trades": sum(e["total_trades"] for e in ranked),
        "note": "Stats computed from real engine signals logged to engine_trades collection"
    }


@router.get("/paper/sim-comparison")
async def api_sim_comparison():
    """
    Real live performance vs 10,000-trade simulation targets (post-fix run).
    Shows the optimism gap between sim and reality for each engine.
    Requires >= 30 closed trades per engine for reliable signal.
    """
    if not app_state.engine_paper_tracker:
        return {"error": "Engine paper tracker not initialized"}

    comparison = await app_state.engine_paper_tracker.get_sim_comparison()

    reliable = [e for e in comparison if e.get("is_reliable")]
    pending = [e for e in comparison if not e.get("is_reliable")]

    return {
        "comparison": comparison,
        "reliable_engines": len(reliable),
        "pending_engines": len(pending),
        "sim_run": "10,000 trades per engine, mixed market, all 8 fixes applied",
        "min_trades_for_reliable": 30,
        "note": (
            "win_rate_gap > 0 means beating sim. "
            "Sim numbers are optimistic (no slippage/fees/partial fills). "
            "Expect real win rates 5-15pts below sim targets."
        )
    }


@router.get("/paper/engine-signals")
async def api_engine_open_signals():
    """
    Currently open (unresolved) engine signals being tracked.
    """
    if not app_state.engine_paper_tracker:
        return {"error": "Engine paper tracker not initialized"}

    signals = await app_state.engine_paper_tracker.get_open_signals()

    return {
        "open_signals": signals,
        "total": len(signals)
    }
