"""
ORACLE Entropy Gate API Routes — routes/oracle_entropy.py
==========================================================
Endpoints:
  GET /api/oracle-entropy/status   — live H_market, regime, per-asset data
  GET /api/oracle-entropy/history  — last 7 days of hourly snapshots
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/oracle-entropy", tags=["oracle-entropy"])


def _get_gate():
    try:
        from oracle_entropy_gate import get_oracle_entropy_gate
        gate = get_oracle_entropy_gate()
        if gate is None:
            raise HTTPException(status_code=503, detail="ORACLE entropy gate not initialised")
        return gate
    except ImportError:
        raise HTTPException(status_code=503, detail="oracle_entropy_gate module not found")


@router.get("/status")
async def oracle_entropy_status():
    """Live H_market, regime classification, per-asset entropy breakdown."""
    gate = _get_gate()
    return gate.get_status()


@router.get("/history")
async def oracle_entropy_history(days: int = 7):
    """
    Last `days` days of hourly H_market snapshots from MongoDB.
    Returns list sorted oldest→newest.
    """
    gate = _get_gate()
    if gate.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        cursor = gate.db["market_entropy_history"].find(
            {"timestamp": {"$gte": since}},
            {"_id": 0, "timestamp": 1, "H_market": 1, "H_combined": 1, "regime": 1},
        ).sort("timestamp", 1)

        docs = []
        async for doc in cursor:
            doc["timestamp"] = doc["timestamp"].isoformat()
            docs.append(doc)

        return {"days": days, "count": len(docs), "history": docs}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
