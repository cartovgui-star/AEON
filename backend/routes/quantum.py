"""
routes/quantum.py — Quantum State API

Exposes |Ψ⟩, engine amplitudes, H, C, entropy, memory summary,
Ω cycle history, and web intelligence LΦ queue.

All read-only. AEON computes. Carlos observes.

Prefix: /api/quantum  (registered in server.py)
"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()


def _qs():
    from aeon_quantum_state import get_quantum_state_engine
    return get_quantum_state_engine()


def _mem():
    from memory_engine import get_memory_engine
    return get_memory_engine()


def _omega():
    from omega_cycle import get_omega_cycle
    return get_omega_cycle()


def _web():
    from web_intelligence import get_web_intelligence
    return get_web_intelligence()


# ── Quantum state ─────────────────────────────────────────────────────────────

@router.get("/quantum/state")
async def get_quantum_state():
    """
    Current |Ψ⟩ snapshot.
    Returns H, C, S_norm, position_multiplier, per-engine αᵢ, regime, ADX.
    """
    qs = _qs()
    if qs is None:
        return {"error": "Quantum state engine not initialised"}
    state = qs.get_state()
    if state is None:
        return {"error": "State not yet computed — wait 60s after startup"}
    return state


@router.get("/quantum/history")
async def get_quantum_history(limit: int = Query(60, ge=1, le=500)):
    """
    Last `limit` state snapshots from MongoDB states collection.
    Used for H trend chart and C trend chart on the dashboard.
    """
    qs = _qs()
    if qs is None or qs.db is None:
        return {"error": "no db"}
    try:
        docs = await qs.db["states"].find(
            {}, {"_id": 0, "timestamp": 1, "H": 1, "C": 1,
                 "S_norm": 1, "position_multiplier": 1,
                 "n_active": 1, "adx": 1, "regime": 1},
            sort=[("timestamp", -1)],
            limit=limit,
        ).to_list(length=limit)
        docs.reverse()   # chronological order
        return {"history": docs, "count": len(docs)}
    except Exception as e:
        return {"error": str(e)}


# ── Memory ────────────────────────────────────────────────────────────────────

@router.get("/quantum/memory/summary")
async def memory_summary(
    symbol: Optional[str] = None,
    engine: Optional[str] = None,
    last_n: int = Query(100, ge=10, le=500),
):
    """
    Aggregate win rate, avg PnL, best/worst setups from (E,a,r) store.
    Optionally scoped to a symbol or engine.
    """
    mem = _mem()
    if mem is None:
        return {"error": "Memory engine not initialised"}
    return await mem.get_summary(symbol=symbol, engine=engine, last_n=last_n)


@router.get("/quantum/memory/retrieve")
async def memory_retrieve(
    direction:  str   = Query("LONG"),
    confidence: float = Query(80.0),
    leverage:   int   = Query(50),
    regime:     str   = Query("trending"),
    adx:        float = Query(30.0),
    rsi:        float = Query(60.0),
    vol_ratio:  float = Query(1.5),
    symbol:     Optional[str] = None,
    n:          int   = Query(10, ge=1, le=50),
):
    """
    Find the n most similar historical setups to the given pattern.
    Returns memories ranked by cosine similarity with outcome data.
    """
    mem = _mem()
    if mem is None:
        return {"error": "Memory engine not initialised"}
    pattern = {
        "direction":   direction,
        "confidence":  confidence,
        "leverage":    leverage,
        "regime":      regime,
        "adx":         adx,
        "rsi":         rsi,
        "vol_ratio":   vol_ratio,
        "symbol":      symbol or "",
        "hour_of_day": 12,   # neutral default
    }
    results = await mem.retrieve(pattern, n=n)
    return {"results": results, "count": len(results), "pattern": pattern}


@router.get("/quantum/memory/count")
async def memory_count():
    mem = _mem()
    if mem is None:
        return {"count": 0}
    return {"count": await mem.get_memory_count()}


# ── Omega cycle ───────────────────────────────────────────────────────────────

@router.get("/quantum/omega/history")
async def omega_history(limit: int = Query(20, ge=1, le=100)):
    """
    Last `limit` Ω cycle fix records from MongoDB fixes collection.
    """
    qs = _qs()
    if qs is None or qs.db is None:
        return {"error": "no db"}
    try:
        docs = await qs.db["fixes"].find(
            {}, {"_id": 0},
            sort=[("timestamp", -1)],
            limit=limit,
        ).to_list(length=limit)
        return {"fixes": docs, "count": len(docs)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/quantum/omega/status")
async def omega_status():
    """Current Ω cycle state: cycle count, last run, H history."""
    omega = _omega()
    if omega is None:
        return {"error": "Omega cycle not initialised"}
    return {
        "cycle_count":    omega._cycle_count,
        "last_cycle_at":  str(omega._last_cycle_at) if omega._last_cycle_at else None,
        "H_history":      [round(h, 4) for h in omega._H_history],
        "C_history":      [round(c, 4) for c in omega._C_history],
        "decline_count":  omega._decline_count,
        "low_C_count":    omega._low_C_count,
    }


# ── Web intelligence ──────────────────────────────────────────────────────────

@router.get("/quantum/web/lphi")
async def web_lphi_queue(
    n:           int = Query(10, ge=1, le=50),
    since_hours: int = Query(48, ge=1, le=168),
):
    """
    Top LΦ proposal candidates from web intelligence.
    Documents above relevance 0.50 from the last `since_hours` hours.
    """
    web = _web()
    if web is None:
        return {"error": "Web intelligence not initialised"}
    docs = await web.get_lphi_queue(n=n, since_hours=since_hours)
    return {"candidates": docs, "count": len(docs)}


@router.get("/quantum/web/sentiment")
async def web_sentiment():
    """Latest Fear & Greed document from web intelligence."""
    web = _web()
    if web is None:
        return {"error": "Web intelligence not initialised"}
    doc = await web.get_latest_sentiment()
    return doc or {"error": "No sentiment data yet — first crawl in 10 min"}


@router.get("/quantum/web/status")
async def web_status():
    web = _web()
    if web is None:
        return {"error": "Web intelligence not initialised"}
    return {
        "cycle_count":  web._cycle_count,
        "last_run_at":  str(web._last_run_at) if web._last_run_at else None,
        "sources":      list(web.SOURCES.keys()) if hasattr(web, "SOURCES") else [],
        "seen_hashes":  len(web._seen_hashes),
    }
