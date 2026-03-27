"""
AEON USER PROFILING SYSTEM
Learns user preferences from conversations to personalize responses

Features:
- Tracks favorite coins (what they ask about most)
- Detects trading style (scalper, swing, hodler)
- Learns risk tolerance from language
- Adapts communication preferences
- Remembers key facts about the user
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class UserProfiler:
    """
    Builds and maintains user profiles from conversation history
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.profiles = db.user_profiles
        self.insights = db.user_insights
        
        # Coin detection
        self.coin_keywords = {
            'btc': 'BTC', 'bitcoin': 'BTC',
            'eth': 'ETH', 'ethereum': 'ETH',
            'sol': 'SOL', 'solana': 'SOL',
            'doge': 'DOGE', 'dogecoin': 'DOGE',
            'xrp': 'XRP', 'ripple': 'XRP',
            'bnb': 'BNB', 'binance': 'BNB',
            'ada': 'ADA', 'cardano': 'ADA',
            'avax': 'AVAX', 'avalanche': 'AVAX',
            'link': 'LINK', 'chainlink': 'LINK',
            'dot': 'DOT', 'polkadot': 'DOT',
            'atom': 'ATOM', 'cosmos': 'ATOM',
            'near': 'NEAR', 'apt': 'APT', 'aptos': 'APT',
            'arb': 'ARB', 'arbitrum': 'ARB',
            'op': 'OP', 'optimism': 'OP',
            'inj': 'INJ', 'injective': 'INJ'
        }
        
        # Risk indicators
        self.high_risk_words = {'yolo', 'ape', 'degen', 'leverage', '100x', '50x', '20x', 'moon', 'lambo', 'all in', 'full send'}
        self.low_risk_words = {'safe', 'careful', 'dca', 'hodl', 'hold', 'long term', 'cautious', 'slow', 'steady'}
        self.medium_risk_words = {'swing', 'trade', 'scalp', 'position', 'entry', 'stop loss', 'take profit'}
        
        # Trading style indicators
        self.scalper_words = {'scalp', 'quick', 'fast', 'minutes', '5m', '15m', 'in and out', 'small gains'}
        self.swing_words = {'swing', 'days', 'week', '4h', '1d', 'trend', 'setup', 'patience'}
        self.hodler_words = {'hodl', 'hold', 'long term', 'years', 'accumulate', 'dca', 'stack', 'sats'}
    
    async def get_or_create_profile(self, chat_id: int) -> Dict:
        """Get existing profile or create new one"""
        profile = await self.profiles.find_one({"chat_id": chat_id})
        
        if not profile:
            profile = {
                "chat_id": chat_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "coin_mentions": {},  # coin -> count
                "favorite_coins": [],
                "trading_style": None,  # scalper, swing, hodler
                "risk_tolerance": None,  # low, medium, high
                "style_indicators": {"scalper": 0, "swing": 0, "hodler": 0},
                "risk_indicators": {"low": 0, "medium": 0, "high": 0},
                "messages_analyzed": 0,
                "topics_discussed": [],  # recent topics
                "key_facts": [],  # things Aeon learned about user
                "communication_preference": "balanced",  # brief, balanced, detailed
                "last_active": datetime.now(timezone.utc)
            }
            await self.profiles.insert_one(profile)
        
        return profile
    
    async def analyze_message(self, chat_id: int, message: str) -> Dict:
        """Analyze a message and update user profile"""
        profile = await self.get_or_create_profile(chat_id)
        message_lower = message.lower()
        words = set(message_lower.split())
        
        updates = {"$set": {"updated_at": datetime.now(timezone.utc), "last_active": datetime.now(timezone.utc)}}
        increments = {}
        
        # Track coin mentions
        coins_mentioned = []
        for keyword, coin in self.coin_keywords.items():
            if keyword in message_lower:
                coins_mentioned.append(coin)
                increments[f"coin_mentions.{coin}"] = 1
        
        # Detect risk tolerance
        high_risk_count = len(words & self.high_risk_words)
        low_risk_count = len(words & self.low_risk_words)
        medium_risk_count = len(words & self.medium_risk_words)
        
        if high_risk_count:
            increments["risk_indicators.high"] = high_risk_count
        if low_risk_count:
            increments["risk_indicators.low"] = low_risk_count
        if medium_risk_count:
            increments["risk_indicators.medium"] = medium_risk_count
        
        # Detect trading style
        scalper_count = len(words & self.scalper_words)
        swing_count = len(words & self.swing_words)
        hodler_count = len(words & self.hodler_words)
        
        if scalper_count:
            increments["style_indicators.scalper"] = scalper_count
        if swing_count:
            increments["style_indicators.swing"] = swing_count
        if hodler_count:
            increments["style_indicators.hodler"] = hodler_count
        
        # Increment messages analyzed
        increments["messages_analyzed"] = 1
        
        # Apply updates
        if increments:
            updates["$inc"] = increments
        
        await self.profiles.update_one({"chat_id": chat_id}, updates)
        
        # Recalculate derived fields
        await self._recalculate_profile(chat_id)
        
        return {
            "coins_mentioned": coins_mentioned,
            "risk_signals": {"high": high_risk_count, "low": low_risk_count, "medium": medium_risk_count},
            "style_signals": {"scalper": scalper_count, "swing": swing_count, "hodler": hodler_count}
        }
    
    async def _recalculate_profile(self, chat_id: int):
        """Recalculate derived profile fields"""
        profile = await self.profiles.find_one({"chat_id": chat_id})
        if not profile:
            return
        
        updates = {}
        
        # Calculate favorite coins (top 3)
        coin_mentions = profile.get("coin_mentions", {})
        if coin_mentions:
            sorted_coins = sorted(coin_mentions.items(), key=lambda x: x[1], reverse=True)
            updates["favorite_coins"] = [c[0] for c in sorted_coins[:3]]
        
        # Determine trading style
        style_indicators = profile.get("style_indicators", {})
        if sum(style_indicators.values()) >= 3:  # Need enough data
            max_style = max(style_indicators, key=style_indicators.get)
            if style_indicators[max_style] >= 2:  # Confidence threshold
                updates["trading_style"] = max_style
        
        # Determine risk tolerance
        risk_indicators = profile.get("risk_indicators", {})
        if sum(risk_indicators.values()) >= 3:  # Need enough data
            max_risk = max(risk_indicators, key=risk_indicators.get)
            if risk_indicators[max_risk] >= 2:  # Confidence threshold
                updates["risk_tolerance"] = max_risk
        
        # Determine communication preference based on message lengths
        # This would need message length tracking - simplified for now
        
        if updates:
            await self.profiles.update_one({"chat_id": chat_id}, {"$set": updates})
    
    async def add_key_fact(self, chat_id: int, fact: str, category: str = "general"):
        """Add a key fact about the user"""
        await self.profiles.update_one(
            {"chat_id": chat_id},
            {
                "$push": {
                    "key_facts": {
                        "$each": [{"fact": fact, "category": category, "added": datetime.now(timezone.utc)}],
                        "$slice": -20  # Keep last 20 facts
                    }
                }
            }
        )
    
    async def get_profile_summary(self, chat_id: int) -> Dict:
        """Get a summary of user profile for API response"""
        profile = await self.get_or_create_profile(chat_id)
        
        return {
            "chat_id": chat_id,
            "trading_style": profile.get("trading_style"),
            "risk_tolerance": profile.get("risk_tolerance"),
            "favorite_coins": profile.get("favorite_coins", []),
            "messages_analyzed": profile.get("messages_analyzed", 0),
            "style_indicators": profile.get("style_indicators", {}),
            "risk_indicators": profile.get("risk_indicators", {}),
            "key_facts": [f.get("fact") for f in profile.get("key_facts", [])[-5:]],  # Last 5 facts
            "last_active": profile.get("last_active", datetime.now(timezone.utc)).isoformat() if profile.get("last_active") else None
        }
    
    async def get_profile_for_prompt(self, chat_id: int) -> str:
        """Get profile info formatted for LLM prompt injection"""
        profile = await self.get_or_create_profile(chat_id)
        
        parts = []
        
        # Trading style
        if profile.get("trading_style"):
            style_desc = {
                "scalper": "prefers quick trades and short timeframes",
                "swing": "likes swing trading over days/weeks",
                "hodler": "is a long-term holder, believes in accumulation"
            }
            parts.append(f"User {style_desc.get(profile['trading_style'], '')}")
        
        # Risk tolerance
        if profile.get("risk_tolerance"):
            risk_desc = {
                "high": "is comfortable with high risk/high reward plays",
                "medium": "balances risk and reward",
                "low": "prefers safer, more conservative approaches"
            }
            parts.append(f"User {risk_desc.get(profile['risk_tolerance'], '')}")
        
        # Favorite coins
        fav_coins = profile.get("favorite_coins", [])
        if fav_coins:
            parts.append(f"User frequently asks about: {', '.join(fav_coins)}")
        
        # Key facts
        key_facts = profile.get("key_facts", [])
        if key_facts:
            recent_facts = [f.get("fact") for f in key_facts[-3:]]
            parts.append(f"Things you know about them: {'; '.join(recent_facts)}")
        
        if parts:
            return "\n[USER CONTEXT: " + ". ".join(parts) + "]"
        return ""


# Global instance
user_profiler = None

def init_user_profiler(db: AsyncIOMotorDatabase) -> UserProfiler:
    global user_profiler
    user_profiler = UserProfiler(db)
    return user_profiler
