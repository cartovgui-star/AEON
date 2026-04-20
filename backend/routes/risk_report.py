"""
Phase 2 — Risk policy advisory summary endpoint.

Surfaces trade candidate journal data so policy signals are observable
without querying MongoDB directly.

GET /api/risk/summary?hours=24
GET /api/risk/candidates?hours=6&limit=50
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

import app_state

router = APIRouter()


@router.get("/api/risk/summary")
async def risk_summary(hours: int = Query(default=24, ge=1, le=168)):
    """
    Aggregate summary of trade candidate policy outcomes over the last N hours.
    Default: 24 hours. Max: 7 days.
    """
    if app_state.db is None:
        return {"error": "db not ready"}

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    col = app_state.db["trade_candidates"]

    docs = await col.find(
        {"created_at": {"$gte": since}},
        {"_id": 0, "candidate_id": 1, "symbol": 1, "direction": 1, "engine": 1,
         "created_at": 1, "gate_passed": 1, "stress_level": 1, "stress_multiplier": 1,
         "account_decisions": 1, "route_results": 1}
    ).sort("created_at", -1).to_list(length=2000)

    total = len(docs)
    if total == 0:
        return {
            "window_hours": hours,
            "since": since.isoformat(),
            "total_candidates": 0,
            "message": "No candidates in window. Signals are recorded when route_signal_to_accounts fires.",
        }

    # ── Per-account outcome aggregation ───────────────────────────────────────
    account_stats: dict = {}
    rejection_reasons: Counter = Counter()
    advisory_notes_freq: Counter = Counter()
    outcome_types: Counter = Counter()
    engines: Counter = Counter()
    heat_snapshots: list = []

    for doc in docs:
        engines[doc.get("engine", "unknown")] += 1

        # Tally route_results outcome_type
        for r in doc.get("route_results", []):
            ot = r.get("outcome_type", "unknown")
            outcome_types[ot] += 1

        # Per-account decisions
        for acc_id, dec in doc.get("account_decisions", {}).items():
            if acc_id not in account_stats:
                account_stats[acc_id] = {
                    "approve": 0, "advisory": 0, "reject": 0,
                    "leverage_capped_count": 0,
                    "heat_samples": [],
                }
            v = dec.get("verdict", "APPROVE")
            if v == "APPROVE":
                account_stats[acc_id]["approve"] += 1
            elif v == "ADVISORY":
                account_stats[acc_id]["advisory"] += 1
            elif v == "REJECT":
                account_stats[acc_id]["reject"] += 1

            for note in dec.get("advisory_notes", []):
                advisory_notes_freq[note[:120]] += 1
                if "Leverage capped" in note:
                    account_stats[acc_id]["leverage_capped_count"] += 1

            for reason in dec.get("rejection_reasons", []):
                rejection_reasons[reason[:120]] += 1

            h = dec.get("heat_score")
            if h is not None:
                account_stats[acc_id]["heat_samples"].append(h)

        # Global heat trend (sample from PRO or first available)
        pro_dec = doc.get("account_decisions", {}).get("PRO")
        if pro_dec and pro_dec.get("heat_score") is not None:
            heat_snapshots.append(pro_dec["heat_score"])

    # Summarise per-account heat
    for acc_id, stats in account_stats.items():
        samples = stats.pop("heat_samples", [])
        if samples:
            stats["avg_heat"] = round(sum(samples) / len(samples), 4)
            stats["max_heat"] = round(max(samples), 4)
        else:
            stats["avg_heat"] = None
            stats["max_heat"] = None

    return {
        "window_hours": hours,
        "since": since.isoformat(),
        "total_candidates": total,
        "outcome_type_totals": dict(outcome_types.most_common()),
        "engines": dict(engines.most_common()),
        "per_account": account_stats,
        "top_rejection_reasons": [
            {"reason": r, "count": c} for r, c in rejection_reasons.most_common(10)
        ],
        "top_advisory_notes": [
            {"note": n, "count": c} for n, c in advisory_notes_freq.most_common(10)
        ],
        "heat_trend": {
            "samples": len(heat_snapshots),
            "avg": round(sum(heat_snapshots) / len(heat_snapshots), 4) if heat_snapshots else None,
            "max": round(max(heat_snapshots), 4) if heat_snapshots else None,
        },
    }


@router.get("/api/risk/candidates")
async def risk_candidates(
    hours: int = Query(default=6, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
    engine: str = Query(default=None),
    verdict: str = Query(default=None, description="Filter by verdict in any account_decision: APPROVE|ADVISORY|REJECT"),
):
    """
    Recent trade candidates with full per-account decision detail.
    Useful for inspecting individual advisory notes and rejection reasons.
    """
    if app_state.db is None:
        return {"error": "db not ready"}

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query: dict = {"created_at": {"$gte": since}}
    if engine:
        query["engine"] = engine

    docs = await app_state.db["trade_candidates"].find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)

    # Optional client-side filter by verdict (any account having that verdict)
    if verdict:
        v_upper = verdict.upper()
        docs = [
            d for d in docs
            if any(
                dec.get("verdict") == v_upper
                for dec in d.get("account_decisions", {}).values()
            )
        ]

    return {"candidates": docs, "count": len(docs), "window_hours": hours}
