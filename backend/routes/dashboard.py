"""
Phase 3 — Engine intelligence & governance dashboard endpoints.

Routes:
  GET /api/engine/health                    — all engines, 7-day default
  GET /api/engine/health/{engine_name}      — single engine
  GET /api/engine/governance                — current governance states
  GET /api/engine/governance/log            — governance event log
  GET /api/engine/overlap                   — overlap-toxicity analytics
  GET /api/portfolio/summary                — open positions across all accounts
  GET /api/portfolio/regime-fit             — regime-sliced win rates
  GET /api/portfolio/account-fit            — per-engine per-account fit analysis
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query

import app_state
from engine_health import EngineHealthScorer, CANONICAL_ENGINE_NAMES
from engine_governance import EngineGovernance

router = APIRouter()
_scorer     = EngineHealthScorer()
_governance = EngineGovernance()


# ── Engine health ─────────────────────────────────────────────────────────────

@router.get("/api/engine/health")
async def engine_health_all(days: int = Query(default=7, ge=1, le=90)):
    if app_state.db is None:
        return {"error": "db not ready"}
    results = await _scorer.compute_all(app_state.db, days=days)
    return {
        "days": days,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "engines": {name: h.to_dict() for name, h in results.items()},
    }


@router.get("/api/engine/health/{engine_name}")
async def engine_health_one(
    engine_name: str,
    days: int = Query(default=7, ge=1, le=90),
):
    if app_state.db is None:
        return {"error": "db not ready"}
    name_upper = engine_name.upper()
    if name_upper not in CANONICAL_ENGINE_NAMES:
        return {
            "error": f"Unknown engine '{engine_name}'. "
                     f"Valid: {', '.join(CANONICAL_ENGINE_NAMES)}"
        }
    health = await _scorer.compute_one(app_state.db, name_upper, days=days)
    return health.to_dict()


# ── Governance ────────────────────────────────────────────────────────────────

@router.get("/api/engine/governance")
async def engine_governance_states():
    if app_state.db is None:
        return {"error": "db not ready"}
    states = await _governance.get_current_states(app_state.db)
    return {"count": len(states), "states": states}


@router.post("/api/engine/governance/refresh")
async def engine_governance_refresh():
    """Trigger an immediate governance evaluation for all engines. Returns updated states."""
    if app_state.db is None:
        return {"error": "db not ready"}
    states = await _governance.run_all(app_state.db)
    return {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "count": len(states),
        "states": {name: s.to_dict() for name, s in states.items()},
    }


@router.get("/api/engine/governance/log")
async def engine_governance_log(
    limit: int  = Query(default=50, ge=1, le=500),
    engine: str = Query(default=None),
):
    if app_state.db is None:
        return {"error": "db not ready"}
    events = await _governance.get_log(app_state.db, limit=limit, engine=engine)
    return {"count": len(events), "events": events}


# ── Overlap toxicity ──────────────────────────────────────────────────────────

@router.get("/api/engine/overlap")
async def engine_overlap(
    hours:                  int = Query(default=48, ge=1,  le=720),
    overlap_window_minutes: int = Query(default=240, ge=15, le=1440),
):
    """
    Compares win rates of trades that were open simultaneously (overlapping)
    vs trades that ran alone. A large gap suggests correlated heat rather than
    independent edge.
    """
    if app_state.db is None:
        return {"error": "db not ready"}

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    trades = await app_state.db.paper_trades.find(
        {"status": "closed", "opened_at": {"$gte": since}},
        {
            "strategy": 1, "account_id": 1, "symbol": 1,
            "opened_at": 1, "closed_at": 1, "close_reason": 1,
            "realized_pnl": 1,
        }
    ).to_list(length=50000)

    if not trades:
        return {"window_hours": hours, "overlap_window_minutes": overlap_window_minutes, "trades_analyzed": 0}

    WIN_REASONS = {"take_profit", "trailing_stop"}
    overlap_wins = 0
    overlap_losses = 0
    solo_wins = 0
    solo_losses = 0

    overlap_window = timedelta(minutes=overlap_window_minutes)

    def _is_win(t: dict) -> bool:
        return t.get("close_reason") in WIN_REASONS

    def _overlaps(a: dict, b: dict) -> bool:
        a_open  = a.get("opened_at")
        a_close = a.get("closed_at") or (a_open + timedelta(hours=24))
        b_open  = b.get("opened_at")
        b_close = b.get("closed_at") or (b_open + timedelta(hours=24))
        if a_open is None or b_open is None:
            return False
        latest_open  = max(a_open, b_open)
        earliest_close = min(a_close, b_close)
        return earliest_close - latest_open >= overlap_window

    for i, trade in enumerate(trades):
        had_overlap = any(
            _overlaps(trade, other)
            for j, other in enumerate(trades)
            if i != j and other.get("account_id") == trade.get("account_id")
        )
        win = _is_win(trade)
        if had_overlap:
            if win:
                overlap_wins += 1
            else:
                overlap_losses += 1
        else:
            if win:
                solo_wins += 1
            else:
                solo_losses += 1

    overlap_total = overlap_wins + overlap_losses
    solo_total    = solo_wins + solo_losses
    overlap_wr    = overlap_wins / overlap_total if overlap_total else None
    solo_wr       = solo_wins    / solo_total    if solo_total    else None
    wr_gap        = round(solo_wr - overlap_wr, 4) if (overlap_wr is not None and solo_wr is not None) else None

    # Per-engine overlap breakdown
    engine_overlap: dict = defaultdict(lambda: {"overlap_wins": 0, "overlap_losses": 0, "solo_wins": 0, "solo_losses": 0})
    for i, trade in enumerate(trades):
        eng = trade.get("strategy", "unknown")
        had_overlap = any(
            _overlaps(trade, other)
            for j, other in enumerate(trades)
            if i != j and other.get("account_id") == trade.get("account_id")
        )
        key = "overlap" if had_overlap else "solo"
        w   = "wins" if _is_win(trade) else "losses"
        engine_overlap[eng][f"{key}_{w}"] += 1

    engine_summary = {}
    for eng, counts in engine_overlap.items():
        ot = counts["overlap_wins"] + counts["overlap_losses"]
        st = counts["solo_wins"] + counts["solo_losses"]
        engine_summary[eng] = {
            **counts,
            "overlap_win_rate": round(counts["overlap_wins"] / ot, 4) if ot else None,
            "solo_win_rate":    round(counts["solo_wins"]    / st, 4) if st else None,
        }

    return {
        "window_hours": hours,
        "overlap_window_minutes": overlap_window_minutes,
        "trades_analyzed": len(trades),
        "global": {
            "overlap_trades": overlap_total,
            "solo_trades":    solo_total,
            "overlap_win_rate": round(overlap_wr, 4) if overlap_wr is not None else None,
            "solo_win_rate":    round(solo_wr, 4)    if solo_wr    is not None else None,
            "win_rate_gap_solo_minus_overlap": wr_gap,
            "toxicity_signal": wr_gap is not None and wr_gap > 0.05,
        },
        "by_engine": engine_summary,
    }


# ── Portfolio summary ─────────────────────────────────────────────────────────

@router.get("/api/portfolio/summary")
async def portfolio_summary():
    """Open positions across all paper accounts with heat metrics."""
    if app_state.db is None:
        return {"error": "db not ready"}
    if app_state.paper_trading is None:
        return {"error": "paper_trading not ready"}

    accounts_data = await app_state.paper_trading.get_all_accounts()
    summary: dict = {}
    total_open = 0

    for account_data in accounts_data:
        account_id = account_data.get("_id") or account_data.get("account_id") or "unknown"
        balance      = account_data.get("balance", 0)
        positions    = account_data.get("positions", [])
        open_pos     = [p for p in positions if p.get("status") == "open"]
        total_margin = sum(p.get("margin", 0) for p in open_pos)
        heat         = total_margin / balance if balance > 0 else 0.0
        total_open  += len(open_pos)

        summary[account_id] = {
            "balance": round(balance, 2),
            "open_count": len(open_pos),
            "total_margin_in_use": round(total_margin, 4),
            "portfolio_heat": round(heat, 4),
            "symbols": [p.get("symbol") for p in open_pos if p.get("symbol")],
        }

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_open_positions": total_open,
        "accounts": summary,
    }


# ── Regime fit ────────────────────────────────────────────────────────────────

@router.get("/api/portfolio/regime-fit")
async def portfolio_regime_fit(days: int = Query(default=30, ge=7, le=90)):
    """Win rates and expectancy sliced by regime_at_open. Pre-Phase-3 trades show as regime_unknown."""
    if app_state.db is None:
        return {"error": "db not ready"}

    since = datetime.now(timezone.utc) - timedelta(days=days)
    WIN_REASONS  = {"take_profit", "trailing_stop"}
    LOSS_REASONS = {"stop_loss", "liquidation"}

    trades = await app_state.db.paper_trades.find(
        {"status": "closed", "opened_at": {"$gte": since}},
        {"strategy": 1, "close_reason": 1, "realized_pnl": 1,
         "initial_margin": 1, "regime_at_open": 1}
    ).to_list(length=100000)

    regime_buckets: dict = defaultdict(lambda: {"wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0})

    for t in trades:
        regime = t.get("regime_at_open") or "regime_unknown"
        cr     = t.get("close_reason")
        pnl    = t.get("realized_pnl", 0) or 0
        if cr in WIN_REASONS:
            regime_buckets[regime]["wins"]   += 1
            regime_buckets[regime]["win_pnl"] += pnl
        elif cr in LOSS_REASONS:
            regime_buckets[regime]["losses"]   += 1
            regime_buckets[regime]["loss_pnl"] += pnl

    result: dict = {}
    for regime, b in regime_buckets.items():
        total = b["wins"] + b["losses"]
        wr    = b["wins"] / total if total else None
        avg_w = b["win_pnl"]  / b["wins"]   if b["wins"]   else 0.0
        avg_l = b["loss_pnl"] / b["losses"] if b["losses"] else 0.0
        exp   = (wr * avg_w + (1 - wr) * avg_l) if wr is not None else None
        result[regime] = {
            "wins": b["wins"],
            "losses": b["losses"],
            "total_clean": total,
            "win_rate": round(wr, 4) if wr is not None else None,
            "avg_win_pnl": round(avg_w, 4),
            "avg_loss_pnl": round(avg_l, 4),
            "expectancy_pnl": round(exp, 4) if exp is not None else None,
        }

    unknown_note = None
    if "regime_unknown" in result:
        unknown_note = (
            "regime_unknown trades were opened before Phase-3 regime tagging was active. "
            "These do not reflect a specific market regime."
        )

    return {
        "days": days,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "regime_unknown_note": unknown_note,
        "by_regime": result,
    }


# ── Account fit ───────────────────────────────────────────────────────────────

@router.get("/api/portfolio/account-fit")
async def portfolio_account_fit(
    engine:  Optional[str] = Query(default=None),
    account: Optional[str] = Query(default=None),
    days:    int           = Query(default=30, ge=7, le=90),
):
    """
    Per-engine per-account observed fit: win rate, expectancy, avg leverage used.
    Pass ?engine= to filter a single engine; ?account= to filter a single account.
    Includes projected sizing note based on account tier.
    """
    if app_state.db is None:
        return {"error": "db not ready"}

    since   = datetime.now(timezone.utc) - timedelta(days=days)
    WIN_R   = {"take_profit", "trailing_stop"}
    LOSS_R  = {"stop_loss", "liquidation"}

    query: dict = {"status": "closed", "opened_at": {"$gte": since}}
    if engine:
        query["strategy"] = engine.upper()
    if account:
        query["account_id"] = account

    trades = await app_state.db.paper_trades.find(
        query,
        {"strategy": 1, "account_id": 1, "close_reason": 1,
         "realized_pnl": 1, "initial_margin": 1, "leverage": 1}
    ).to_list(length=100000)

    # Nest: engine → account_id → {wins, losses, pnl, leverages}
    matrix: dict = defaultdict(lambda: defaultdict(
        lambda: {"wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0, "leverages": []}
    ))

    for t in trades:
        eng  = t.get("strategy", "unknown")
        acc  = t.get("account_id", "unknown")
        cr   = t.get("close_reason")
        pnl  = t.get("realized_pnl", 0) or 0
        lev  = t.get("leverage")
        if cr in WIN_R:
            matrix[eng][acc]["wins"]   += 1
            matrix[eng][acc]["win_pnl"] += pnl
        elif cr in LOSS_R:
            matrix[eng][acc]["losses"]   += 1
            matrix[eng][acc]["loss_pnl"] += pnl
        if lev:
            matrix[eng][acc]["leverages"].append(lev)

    # Account max_leverage caps from paper_trading module-level ACCOUNTS dict
    account_caps: dict = {}
    try:
        from paper_trading import ACCOUNTS as _PT_ACCOUNTS
        for acc_id, cfg in _PT_ACCOUNTS.items():
            account_caps[acc_id] = cfg.get("max_leverage", 20)
    except Exception:
        pass

    result: dict = {}
    for eng, acc_dict in matrix.items():
        result[eng] = {}
        for acc_id, b in acc_dict.items():
            total = b["wins"] + b["losses"]
            wr    = b["wins"] / total if total else None
            avg_w = b["win_pnl"]  / b["wins"]   if b["wins"]   else 0.0
            avg_l = b["loss_pnl"] / b["losses"] if b["losses"] else 0.0
            exp   = (wr * avg_w + (1 - wr) * avg_l) if wr is not None else None
            levs  = b["leverages"]
            avg_lev = round(sum(levs) / len(levs), 1) if levs else None
            cap   = account_caps.get(acc_id)

            label = _fit_label(wr, exp, total)
            result[eng][acc_id] = {
                "wins": b["wins"],
                "losses": b["losses"],
                "total_clean": total,
                "win_rate": round(wr, 4) if wr is not None else None,
                "expectancy_pnl": round(exp, 4) if exp is not None else None,
                "avg_leverage_used": avg_lev,
                "account_max_leverage": cap,
                "fit_label": label,
            }

    return {
        "days": days,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "filter_engine": engine,
        "filter_account": account,
        "matrix": result,
    }


def _fit_label(win_rate: Optional[float], expectancy: Optional[float], n: int) -> str:
    if n < 5:
        return "insufficient_data"
    if win_rate is None or expectancy is None:
        return "insufficient_data"
    if win_rate >= 0.60 and expectancy > 0:
        return "strong_fit"
    if win_rate >= 0.45 and expectancy > 0:
        return "adequate_fit"
    if expectancy <= 0:
        return "poor_fit"
    return "weak_fit"


# ── FREE_WILL_V2 operator report ──────────────────────────────────────────────

_FW_ENGINE = "FREE_WILL_V2"
_WIN_R     = {"take_profit", "trailing_stop"}
_LOSS_R    = {"stop_loss", "liquidation"}
_COHORT_WINDOW = 60  # seconds — same as engine_health.COHORT_WINDOW_SECONDS


@router.get("/api/engine/fw_v2/report")
async def fw_v2_operator_report():
    """
    Compact post-fix monitoring report for FREE_WILL_V2.
    All data is read-only; all trades are paper-only.
    """
    if app_state.db is None:
        return {"error": "db not ready"}

    db   = app_state.db
    now  = datetime.now(timezone.utc)

    # ── 1+2+3: Health (7d) + governance state ─────────────────────────────────
    health_7d = await _scorer.compute_one(db, _FW_ENGINE, days=7)
    gov_doc   = await db.engine_governance.find_one({"engine": _FW_ENGINE}, {"_id": 0})

    # ── 7d / 14d / 30d rolling stats ──────────────────────────────────────────
    rolling = {}
    for days in (7, 14, 30):
        since = now - timedelta(days=days)
        trades = await db.paper_trades.find(
            {"strategy": _FW_ENGINE, "opened_at": {"$gte": since},
             "close_reason": {"$in": list(_WIN_R | _LOSS_R)}},
            {"realized_pnl": 1, "initial_margin": 1, "close_reason": 1,
             "direction": 1, "symbol": 1, "opened_at": 1, "leverage": 1,
             "entry_price": 1, "stop_loss": 1}
        ).to_list(length=20000)
        rolling[f"{days}d"] = _rolling_stats(trades)

    # ── 4+7: Last 10 signal cohorts ───────────────────────────────────────────
    since_30 = now - timedelta(days=30)
    all_closed = await db.paper_trades.find(
        {"strategy": _FW_ENGINE, "opened_at": {"$gte": since_30}},
        {"realized_pnl": 1, "initial_margin": 1, "close_reason": 1,
         "direction": 1, "symbol": 1, "opened_at": 1, "closed_at": 1,
         "leverage": 1, "entry_price": 1, "stop_loss": 1, "account_id": 1}
    ).sort("opened_at", 1).to_list(length=20000)

    cohorts    = _build_cohorts(all_closed)
    last_10    = cohorts[-10:]

    # ── 5: Requested / approved / executed leverage from trade_candidates ──────
    recent_candidates = await db.trade_candidates.find(
        {"engine": _FW_ENGINE, "created_at": {"$gte": since_30}},
        {"symbol": 1, "direction": 1, "created_at": 1,
         "account_decisions": 1, "route_results": 1}
    ).sort("created_at", -1).to_list(length=50)

    leverage_audit = _leverage_audit(recent_candidates)

    # ── 6: Malformed stop rejects ─────────────────────────────────────────────
    malformed_rejects = await db.trade_candidates.count_documents({
        "engine": _FW_ENGINE,
        "route_results.outcome_type": "malformed_stop",
        "created_at": {"$gte": since_30},
    })

    # ── 9: Consecutive D-week count ───────────────────────────────────────────
    consecutive_d = gov_doc.get("consecutive_d_weeks", 0) if gov_doc else 0

    # ── 10: Status field ──────────────────────────────────────────────────────
    status = _derive_status(health_7d, consecutive_d)

    return {
        "engine":      _FW_ENGINE,
        "computed_at": now.isoformat(),
        "status":      status,

        "health_7d": {
            "score":            health_7d.score,
            "tier":             health_7d.tier,
            "n_clean":          health_7d.n_clean,
            "n_cohorts":        health_7d.n_cohorts,
            "shrinkage_factor": health_7d.shrinkage_factor,
            "malformed_trades": health_7d.malformed_trades,
            "win_rate":         health_7d.win_rate,
            "expectancy_pct":   health_7d.expectancy_pct,
            "profit_factor":    health_7d.profit_factor,
            "avg_win_pct":      health_7d.avg_win_pct,
            "avg_loss_pct":     health_7d.avg_loss_pct,
            "liquidation_rate": health_7d.liquidation_rate,
            "leverage_profile": health_7d.leverage_profile,
        },

        "governance": {
            "recommendation":      gov_doc.get("recommendation")      if gov_doc else None,
            "rationale":           gov_doc.get("rationale")           if gov_doc else None,
            "consecutive_d_weeks": consecutive_d,
            "last_change_at":      gov_doc.get("last_change_at")      if gov_doc else None,
            "prev_recommendation": gov_doc.get("prev_recommendation") if gov_doc else None,
        },

        "rolling_performance": rolling,

        "signal_cohorts": {
            "total_cohorts_30d": len(cohorts),
            "last_10":           last_10,
        },

        "leverage_pipeline": {
            "candidates_checked_30d": len(recent_candidates),
            "malformed_stop_rejects_30d": malformed_rejects,
            "per_cohort_leverage": leverage_audit,
        },
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rolling_stats(trades: list) -> dict:
    wins   = [t for t in trades if t.get("close_reason") in _WIN_R]
    losses = [t for t in trades if t.get("close_reason") in _LOSS_R]
    n      = len(wins) + len(losses)

    def _pct(t):
        im = t.get("initial_margin") or 0
        return (t.get("realized_pnl", 0) / im * 100) if im > 0 else None

    wp = [p for t in wins   for p in [_pct(t)] if p is not None]
    lp = [p for t in losses for p in [_pct(t)] if p is not None]
    wr = len(wins) / n if n > 0 else None
    aw = round(sum(wp) / len(wp), 2) if wp else None
    al = round(sum(lp) / len(lp), 2) if lp else None
    exp = round(wr * (aw or 0) + (1 - wr) * (al or 0), 2) if wr is not None else None

    gp = sum(t.get("realized_pnl", 0) for t in wins)
    gl = abs(sum(t.get("realized_pnl", 0) for t in losses))
    pf = round(gp / gl, 3) if gl > 0 else (5.0 if gp > 0 else None)

    dirs = defaultdict(int)
    for t in trades:
        dirs[(t.get("direction") or "unknown").upper()] += 1

    from engine_health import EngineHealthScorer as _EHS
    n_cohorts = _EHS._count_cohorts(wins + losses)

    return {
        "n_clean":    n,
        "n_cohorts":  n_cohorts,
        "wins":       len(wins),
        "losses":     len(losses),
        "win_rate":   round(wr, 4) if wr is not None else None,
        "expectancy_pct": exp,
        "profit_factor":  pf,
        "avg_win_pct":    aw,
        "avg_loss_pct":   al,
        "direction_mix":  dict(dirs),
    }


def _build_cohorts(trades: list) -> list:
    """
    Group trades into signal cohorts (same symbol+direction within 60s).
    Returns cohorts sorted oldest-first, each summarising the signal outcome.
    """
    if not trades:
        return []

    window  = timedelta(seconds=_COHORT_WINDOW)

    def _tz(dt):
        if isinstance(dt, datetime) and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # Sort by symbol, direction, then open time
    keyed = sorted(
        trades,
        key=lambda t: (
            t.get("symbol", ""),
            (t.get("direction") or "").upper(),
            _tz(t.get("opened_at")) if t.get("opened_at") else datetime.min.replace(tzinfo=timezone.utc),
        )
    )

    cohorts: list = []
    current: list = []

    def _flush(group):
        if not group:
            return
        rep      = group[0]
        sym      = rep.get("symbol", "?")
        direction = (rep.get("direction") or "?").upper()
        open_t   = _tz(rep.get("opened_at"))
        close_rs = list({t.get("close_reason") for t in group if t.get("close_reason")})
        leverages = [t.get("leverage") for t in group if t.get("leverage")]
        wins_g    = [t for t in group if t.get("close_reason") in _WIN_R]
        losses_g  = [t for t in group if t.get("close_reason") in _LOSS_R]

        # Per-trade PnL% (use any account's trade as representative)
        pnl_pcts = []
        for t in wins_g + losses_g:
            im = t.get("initial_margin") or 0
            if im > 0:
                pnl_pcts.append(round(t.get("realized_pnl", 0) / im * 100, 2))

        outcome = "win" if wins_g else ("loss" if losses_g else "open")

        # Malformed: LONG with SL >= entry, or SHORT with SL <= entry
        malformed = any(
            (direction == "LONG"  and (t.get("stop_loss") or 0) >= (t.get("entry_price") or 0) > 0)
            or
            (direction == "SHORT" and (t.get("stop_loss") or 1e18) <= (t.get("entry_price") or 0))
            for t in group
        )

        cohorts.append({
            "symbol":        sym,
            "direction":     direction,
            "open_time":     open_t.isoformat() if open_t else None,
            "account_count": len(group),
            "outcome":       outcome,
            "close_reasons": close_rs,
            "avg_pnl_pct":   round(sum(pnl_pcts) / len(pnl_pcts), 2) if pnl_pcts else None,
            "leverage_used": leverages[0] if leverages else None,
            "malformed_sl":  malformed,
        })

    for trade in keyed:
        sym  = trade.get("symbol", "")
        dirc = (trade.get("direction") or "").upper()
        ot   = _tz(trade.get("opened_at")) if trade.get("opened_at") else None

        if not current:
            current.append(trade)
            continue

        prev = current[-1]
        prev_sym  = prev.get("symbol", "")
        prev_dirc = (prev.get("direction") or "").upper()
        prev_ot   = _tz(prev.get("opened_at")) if prev.get("opened_at") else None

        same_group = (
            sym == prev_sym
            and dirc == prev_dirc
            and ot is not None
            and prev_ot is not None
            and (ot - prev_ot) <= window
        )

        if same_group:
            current.append(trade)
        else:
            _flush(current)
            current = [trade]

    _flush(current)
    # Re-sort by open_time so callers get chronological order
    cohorts.sort(key=lambda c: c.get("open_time") or "")
    return cohorts


def _leverage_audit(candidates: list) -> list:
    """
    For each recent trade_candidate, extract requested / approved / executed leverage
    from the first available account_decision.
    """
    rows = []
    for c in candidates[:10]:
        decisions = c.get("account_decisions") or {}
        # Pick first account that has a decision
        rep_acc, rep_dec = next(iter(decisions.items()), (None, {}))
        req  = rep_dec.get("requested_leverage")
        appr = rep_dec.get("approved_leverage")
        # executed leverage is not in trade_candidates — it lives in paper_trades
        # We surface requested vs approved here; executed visible in health leverage_profile
        rows.append({
            "symbol":             c.get("symbol"),
            "direction":          c.get("direction"),
            "created_at":         c.get("created_at").isoformat() if isinstance(c.get("created_at"), datetime) else c.get("created_at"),
            "sample_account":     rep_acc,
            "requested_leverage": req,
            "approved_leverage":  appr,
            "gate_passed":        c.get("gate_passed"),
            "route_outcomes":     [r.get("outcome_type") for r in (c.get("route_results") or [])],
        })
    return rows


def _derive_status(health, consecutive_d: int) -> str:
    """
    Four-level status reflecting current risk posture.
    disable_risk   : consecutive_d >= 5  (disable_candidate threshold)
    sandbox_risk   : consecutive_d >= 3  (sandbox_only threshold)
    watch_closely  : tier C/D, or malformed_trades > 0, or consecutive_d >= 1
    healthy_observing: tier A or B, no malformed, consecutive_d == 0
    """
    if consecutive_d >= 5:
        return "disable_risk"
    if consecutive_d >= 3:
        return "sandbox_risk"
    if (health.tier in ("C", "D", "insufficient_data")
            or health.malformed_trades > 0
            or consecutive_d >= 1):
        return "watch_closely"
    return "healthy_observing"
