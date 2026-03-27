"""
Database helper functions for user settings and state management
"""
from typing import Dict, Any, List
from datetime import datetime, timezone


class DatabaseHelpers:
    """Helper class for common database operations"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_user_settings(self, chat_id: int) -> Dict[str, Any]:
        """Get or create user settings"""
        settings = await self.db.user_settings.find_one({"chat_id": chat_id})
        if not settings:
            default = {
                "chat_id": chat_id,
                "free_will": True,
                "goals": [],
                "trading_style": "swing",
                "bot_mode": "casual",
                "created_at": datetime.now(timezone.utc)
            }
            await self.db.user_settings.insert_one(default)
            return default
        return settings
    
    async def update_user_settings(self, chat_id: int, updates: Dict[str, Any]):
        """Update user settings"""
        await self.db.user_settings.update_one(
            {"chat_id": chat_id}, {"$set": updates}, upsert=True
        )
    
    async def get_user_probe_state(self, chat_id: int) -> Dict[str, Any]:
        """Get user's Quantum Mason probe state"""
        state = await self.db.probe_states.find_one({"chat_id": chat_id})
        if not state:
            return {"intensity": "INITIATE", "questions_asked": 0, "insights_gathered": []}
        return state
    
    async def update_probe_state(self, chat_id: int, updates: Dict[str, Any]):
        """Update probe state"""
        await self.db.probe_states.update_one(
            {"chat_id": chat_id}, {"$set": updates}, upsert=True
        )
    
    async def store_user_insight(self, chat_id: int, insight: str, category: str = "general"):
        """Store an insight learned about the user"""
        await self.db.user_insights.insert_one({
            "chat_id": chat_id,
            "insight": insight,
            "category": category,
            "timestamp": datetime.now(timezone.utc)
        })
    
    async def get_user_insights(self, chat_id: int, limit: int = 10) -> List[Dict]:
        """Get recent insights about a user"""
        cursor = self.db.user_insights.find({"chat_id": chat_id}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
