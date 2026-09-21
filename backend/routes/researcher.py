"""
Researcher API routes — /api/researcher/*
Includes Omega Cycle status since Omega is the researcher's governance backbone.

Surfaces the quantum-researcher layer:
  - Hurst regime readings per symbol
  - Cross-engine ensemble consensus
  - TCN neural vote
  - Confidence calibration (win rate per decile from paper_trades)
  - Quantum strategy status from MongoDB
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/researcher", tags=["Researcher"])

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db(request: Request):
    import app_state
    return app_state.db


def _get_tcn():
    try:
        import app_state
        return getattr(app_state, "tcn_engine", None)
    except Exception:
        return None


# ── Status overview ───────────────────────────────────────────────────────────

@router.get("/status")
async def researcher_status(request: Request):
    """Overall researcher system summary — health, gate stats, connections."""
    try:
        from hurst_gate import get_hurst_cache_snapshot
        hurst_snap = get_hurst_cache_snapshot()
        hurst_ok = True
    except Exception:
        hurst_snap = {}
        hurst_ok = False

    try:
        from ensemble_voter import get_consensus_snapshot
        ensemble = get_consensus_snapshot()
        ensemble_ok = True
    except Exception:
        ensemble = []
        ensemble_ok = False

    tcn = _get_tcn()
    tcn_vote = tcn.get_vote("BTC/USDT") if tcn else {"vote": "NEUTRAL", "live": False}

    # Count strategies from MongoDB
    db = _get_db(request)
    strategies_count = 0
    backtested_count = 0
    try:
        if db is not None:
            strategies_count = await db["qr_strategies"].count_documents({})
            backtested_count = await db["qr_backtests"].count_documents({})
    except Exception:
        pass

    elevated_count = sum(1 for c in ensemble if c.get("elevated"))

    return {
        "status": "live",
        "components": {
            "hurst_gate": {"active": hurst_ok, "symbols_cached": len(hurst_snap)},
            "ensemble_voter": {"active": ensemble_ok, "consensus_events": len(ensemble), "elevated": elevated_count},
            "tcn_neural": {"active": tcn_vote.get("live", False), "vote": tcn_vote.get("vote", "NEUTRAL"), "confidence": tcn_vote.get("confidence", 0)},
            "quantum_strategies": {"total": strategies_count, "backtested": backtested_count},
        },
        "gate16_hurst": hurst_ok,
        "gate_pipeline_complete": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Hurst readings ────────────────────────────────────────────────────────────

@router.get("/hurst")
async def researcher_hurst():
    """Current Hurst exponent readings for all cached symbols."""
    try:
        from hurst_gate import get_hurst_cache_snapshot
        snap = get_hurst_cache_snapshot()
        symbols = []
        for sym, data in snap.items():
            regime = data["regime"]
            symbols.append({
                "symbol": sym,
                "hurst": data["hurst"],
                "regime": regime,
                "regime_color": "green" if regime == "MOMENTUM" else "blue" if regime == "MEAN_REVERSION" else "red" if regime == "RANDOM_WALK" else "amber",
                "age_seconds": data["age_seconds"],
            })
        symbols.sort(key=lambda x: x["symbol"])
        return {
            "symbols": symbols,
            "summary": {
                "momentum": sum(1 for s in symbols if s["regime"] == "MOMENTUM"),
                "mean_reversion": sum(1 for s in symbols if s["regime"] == "MEAN_REVERSION"),
                "random_walk": sum(1 for s in symbols if s["regime"] == "RANDOM_WALK"),
                "transitional": sum(1 for s in symbols if s["regime"] == "TRANSITIONAL"),
                "unknown": sum(1 for s in symbols if s["regime"] == "UNKNOWN"),
            },
        }
    except Exception as e:
        return {"symbols": [], "error": str(e)}


# ── Ensemble consensus ────────────────────────────────────────────────────────

@router.get("/ensemble")
async def researcher_ensemble():
    """Current cross-engine signal consensus snapshot."""
    try:
        from ensemble_voter import get_consensus_snapshot, CONSENSUS_THRESHOLD, CONSENSUS_WINDOW_SECONDS
        snap = get_consensus_snapshot()
        return {
            "consensus": snap,
            "threshold": CONSENSUS_THRESHOLD,
            "window_seconds": CONSENSUS_WINDOW_SECONDS,
            "elevated_count": sum(1 for c in snap if c.get("elevated")),
        }
    except Exception as e:
        return {"consensus": [], "error": str(e)}


# ── TCN Neural votes ──────────────────────────────────────────────────────────

@router.get("/tcn_votes")
async def researcher_tcn_votes():
    """TCN neural engine vote per symbol (BULLISH/BEARISH/NEUTRAL)."""
    tcn = _get_tcn()
    if tcn is None:
        return {"votes": {}, "live": False, "message": "TCN engine not initialised"}

    votes = tcn.get_all_votes()
    return {
        "votes": votes,
        "live": tcn.is_live(),
        "sharpe": round(tcn.get_sharpe(), 4),
        "alpha9": round(tcn.get_alpha9(), 4),
        "p_hat": round(tcn.get_p_hat(), 4),
    }


# ── Confidence calibration ────────────────────────────────────────────────────

@router.get("/calibration")
async def researcher_calibration(request: Request, days: int = 30):
    """
    Confidence calibration analysis: win rate per confidence decile from paper_trades.
    Answers: 'Are our 80%+ confidence signals actually winning 80% of the time?'
    """
    db = _get_db(request)
    if db is None:
        return {"deciles": [], "error": "DB not available"}

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cursor = db["paper_trades"].find(
            {"status": "closed", "created_at": {"$gte": cutoff}},
            projection={"confidence": 1, "pnl": 1, "engine": 1, "_id": 0},
        ).limit(5000)

        trades: List[Dict] = await cursor.to_list(length=5000)

        if not trades:
            return {"deciles": [], "total_trades": 0, "message": "No closed trades in window"}

        # Build decile buckets: 50-60, 60-70, 70-75, 75-80, 80-85, 85-90, 90-95, 95-100
        buckets = [
            (50, 60), (60, 70), (70, 75), (75, 80),
            (80, 85), (85, 90), (90, 95), (95, 101),
        ]
        deciles = []
        for lo, hi in buckets:
            bucket_trades = [
                t for t in trades
                if lo <= float(t.get("confidence") or 0) < hi
            ]
            if not bucket_trades:
                continue
            wins = sum(1 for t in bucket_trades if float(t.get("pnl") or 0) > 0)
            win_rate = round(wins / len(bucket_trades) * 100, 1)
            avg_pnl = round(sum(float(t.get("pnl") or 0) for t in bucket_trades) / len(bucket_trades), 2)
            deciles.append({
                "range": f"{lo}-{hi if hi < 101 else 100}%",
                "lo": lo,
                "hi": hi if hi < 101 else 100,
                "count": len(bucket_trades),
                "win_rate": win_rate,
                "avg_pnl": avg_pnl,
                "calibration_gap": round(win_rate - (lo + (hi - lo) / 2), 1),
            })

        total_wins = sum(1 for t in trades if float(t.get("pnl") or 0) > 0)
        overall_wr = round(total_wins / len(trades) * 100, 1) if trades else 0

        return {
            "deciles": deciles,
            "total_trades": len(trades),
            "overall_win_rate": overall_wr,
            "days": days,
            "note": "calibration_gap > 0 means model is over-confident; < 0 means under-confident",
        }

    except Exception as e:
        logger.error(f"[RESEARCHER] Calibration query failed: {e}")
        return {"deciles": [], "error": str(e)}


# ── Quantum strategy status ───────────────────────────────────────────────────

@router.get("/strategies")
async def researcher_strategies(request: Request):
    """Quantum strategy status from MongoDB (qr_strategies + qr_backtests)."""
    db = _get_db(request)

    # Fallback static list if DB is unavailable
    static_strategies = [
        {"name": "hurst_regime", "description": "Rolling Hurst exponent regime detection", "status": "active", "wired": True},
        {"name": "von_neumann_entropy", "description": "Correlation matrix eigenvalue entropy — wired as Gate 17", "status": "active", "wired": True},
        {"name": "qubo_position", "description": "QUBO-inspired position sizing via simulated annealing — wired into position_multiplier", "status": "active", "wired": True},
        {"name": "quantum_walk", "description": "Discrete quantum walk for fat-tail return modeling", "status": "pending", "wired": False},
        {"name": "pathintegral_nash", "description": "Path-integral Nash equilibrium for microstructure", "status": "pending", "wired": False},
        {"name": "adversarial_robust_nn", "description": "Adversarial robust NN controller synthesis", "status": "pending", "wired": False},
        {"name": "recursive_utility_ac", "description": "Recursive utility actor-critic portfolio optimization", "status": "pending", "wired": False},
        {"name": "skewsabr_vol", "description": "Skew-SABR implied volatility fitting", "status": "pending", "wired": False},
    ]

    if db is None:
        return {"strategies": static_strategies, "source": "static"}

    try:
        strat_docs = await db["qr_strategies"].find({}, {"_id": 0}).to_list(length=50)
        backtest_docs = await db["qr_backtests"].find({}, {"_id": 0}).to_list(length=50)
        backtest_map = {b.get("strategy_name"): b for b in backtest_docs}

        if strat_docs:
            # Always prepend the gates that are actually wired into the engine,
            # with their stored backtest (if any) attached.
            wired_gates = [
                ("hurst_regime", "Rolling Hurst exponent regime detection — wired as Gate 16"),
                ("von_neumann_entropy", "Correlation-matrix eigenvalue entropy — wired as Gate 17"),
                ("qubo_position", "QUBO simulated-annealing position sizing — wired into position_multiplier"),
            ]
            wired_names = {n for n, _ in wired_gates}
            result = [{
                "name": n,
                "description": d,
                "status": "active",
                "wired": True,
                "backtest": ({
                    "sharpe": backtest_map[n].get("sharpe_ratio"),
                    "win_rate": backtest_map[n].get("win_rate"),
                    "total_trades": backtest_map[n].get("total_trades"),
                    "max_drawdown": backtest_map[n].get("max_drawdown"),
                } if n in backtest_map else None),
                "last_updated": "",
            } for n, d in wired_gates]
            for s in strat_docs:
                name = s.get("name") or s.get("strategy_name", "")
                if name in wired_names:
                    continue  # already added above as a wired gate
                bt = backtest_map.get(name, {})
                result.append({
                    "name": name,
                    "description": s.get("description", ""),
                    "status": s.get("status", "pending"),
                    "wired": False,
                    "backtest": {
                        "sharpe": bt.get("sharpe_ratio"),
                        "win_rate": bt.get("win_rate"),
                        "total_trades": bt.get("total_trades"),
                        "max_drawdown": bt.get("max_drawdown"),
                    } if bt else None,
                    "last_updated": str(s.get("updated_at") or s.get("created_at", "")),
                })
            return {"strategies": result, "source": "mongodb"}

    except Exception as e:
        logger.error(f"[RESEARCHER] Strategy query failed: {e}")

    return {"strategies": static_strategies, "source": "static"}


# ── Strategy backtest ─────────────────────────────────────────────────────────

@router.post("/backtest/{name}")
async def researcher_backtest(name: str, request: Request, symbol: str = "BTC/USDT", bars: int = 300):
    """
    Backtest a named quantum strategy over real historical OHLCV and persist the
    result to qr_backtests. Returns genuine Sharpe / win-rate / drawdown metrics.

    POST /api/researcher/backtest/hurst_regime?symbol=BTC/USDT&bars=300
    """
    import app_state
    market_intel = getattr(app_state, "market_intel", None)

    try:
        from strategy_backtest import run_backtest
        result = await run_backtest(name, market_intel, symbol=symbol, bars=bars)
    except ValueError as ve:
        return {"ok": False, "strategy": name, "error": str(ve)}
    except Exception as e:
        logger.error(f"[RESEARCHER] Backtest {name} failed: {e}")
        return {"ok": False, "strategy": name, "error": str(e)}

    # Persist (upsert by strategy_name) so /strategies can surface the numbers.
    db = _get_db(request)
    if db is not None:
        try:
            doc = {**result, "ran_at": datetime.now(timezone.utc)}
            await db["qr_backtests"].update_one(
                {"strategy_name": name}, {"$set": doc}, upsert=True
            )
            # Mark the strategy as backtested in qr_strategies (best-effort).
            await db["qr_strategies"].update_one(
                {"name": name},
                {"$set": {"last_backtest": datetime.now(timezone.utc), "status": "backtested"}},
                upsert=False,
            )
        except Exception as e:
            logger.debug(f"[RESEARCHER] Backtest persist skipped: {e}")

    return {"ok": True, **result}


@router.get("/backtest/{name}")
async def researcher_backtest_get(name: str, request: Request):
    """Return the most recent stored backtest for a strategy (no recompute)."""
    db = _get_db(request)
    if db is None:
        return {"ok": False, "error": "DB not available"}
    try:
        doc = await db["qr_backtests"].find_one({"strategy_name": name}, {"_id": 0})
        if not doc:
            return {"ok": False, "strategy": name, "error": "no backtest stored — POST to run one"}
        if hasattr(doc.get("ran_at"), "isoformat"):
            doc["ran_at"] = doc["ran_at"].isoformat()
        return {"ok": True, **doc}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Gate snapshots (Lab surfacing) ────────────────────────────────────────────

@router.get("/gates")
async def researcher_gates():
    """Live snapshot of the researcher-owned gates: Hurst (16), Von Neumann (17), TCN."""
    out: Dict[str, Any] = {}
    try:
        from hurst_gate import get_hurst_cache_snapshot
        out["hurst"] = get_hurst_cache_snapshot()
    except Exception:
        out["hurst"] = {}
    try:
        from von_neumann_gate import get_vn_cache_snapshot
        out["von_neumann"] = get_vn_cache_snapshot()
    except Exception:
        out["von_neumann"] = {"available": False}
    tcn = _get_tcn()
    out["tcn"] = tcn.get_vote("BTC/USDT") if tcn else {"vote": "NEUTRAL", "live": False}
    return out


# ── Recent papers ─────────────────────────────────────────────────────────────

@router.get("/papers")
async def researcher_papers(request: Request, limit: int = 10):
    """Recent quantum finance papers discovered by the researcher agent."""
    db = _get_db(request)
    if db is None:
        return {"papers": []}

    try:
        docs = await db["qr_papers"].find(
            {}, {"_id": 0, "title": 1, "arxiv_id": 1, "relevance_score": 1, "discovered_at": 1, "abstract_summary": 1}
        ).sort("discovered_at", -1).limit(limit).to_list(length=limit)
        return {"papers": docs}
    except Exception as e:
        return {"papers": [], "error": str(e)}


# ── Omega Cycle status ────────────────────────────────────────────────────────

@router.get("/omega")
async def researcher_omega(request: Request):
    """Omega Cycle (Ω) status — last cycle, trigger reasons, applied fixes, ORIA connection."""
    try:
        from omega_cycle import get_omega_cycle
        omega = get_omega_cycle()
        if omega is None:
            return {"status": "not_initialized", "cycle_count": 0}
        status = omega.get_status()
        return {"status": "live", **status}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/omega/fixes")
async def researcher_omega_fixes(request: Request, limit: int = 20):
    """Recent Omega Cycle fix history from MongoDB."""
    db = _get_db(request)
    if db is None:
        return {"fixes": []}
    try:
        docs = await db["fixes"].find(
            {}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(length=limit)
        # Convert datetime to ISO string for JSON
        for doc in docs:
            if hasattr(doc.get("timestamp"), "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
        return {"fixes": docs, "total": len(docs)}
    except Exception as e:
        return {"fixes": [], "error": str(e)}
