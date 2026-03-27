"""
User settings and state helpers — thin wrappers around MongoDB collections.

All functions use app_state.db so they work after lifespan initialisation.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def get_user_settings(chat_id: int) -> Dict[str, Any]:
    import app_state

    settings = await app_state.db.user_settings.find_one({"chat_id": chat_id})
    if not settings:
        settings = {
            "chat_id": chat_id,
            "free_will": True,
            "created_at": datetime.now(timezone.utc),
            "alert_threshold": 25,
            "mode": "default",
        }
        await app_state.db.user_settings.insert_one(settings)
    if "mode" not in settings:
        settings["mode"] = "default"
    return settings


async def update_user_settings(chat_id: int, updates: Dict[str, Any]):
    import app_state

    await app_state.db.user_settings.update_one(
        {"chat_id": chat_id}, {"$set": updates}, upsert=True
    )


async def get_user_probe_state(chat_id: int) -> Dict[str, Any]:
    import app_state

    state = await app_state.db.probe_states.find_one({"chat_id": chat_id})
    if not state:
        state = {
            "chat_id": chat_id,
            "intensity_level": "INITIATE",
            "probes_completed": 0,
            "last_topics": [],
        }
        await app_state.db.probe_states.insert_one(state)
    return state


async def update_probe_state(chat_id: int, updates: Dict[str, Any]):
    import app_state

    await app_state.db.probe_states.update_one(
        {"chat_id": chat_id}, {"$set": updates}, upsert=True
    )


async def store_user_insight(chat_id: int, insight: str, category: str = "general"):
    import app_state

    await app_state.db.user_insights.insert_one(
        {
            "chat_id": chat_id,
            "insight": insight,
            "category": category,
            "timestamp": datetime.now(timezone.utc),
        }
    )


async def get_user_insights(chat_id: int, limit: int = 10) -> List[Dict]:
    import app_state

    return (
        await app_state.db.user_insights.find({"chat_id": chat_id})
        .sort("timestamp", -1)
        .limit(limit)
        .to_list(limit)
    )
