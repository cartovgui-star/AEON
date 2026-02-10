"""
AEON MEMORY & JOURNALING SYSTEM
Persistent memory for learning from trades and conversations

Features:
1. Trade Journal - Record and analyze all trades
2. Pattern Memory - Remember what worked and what didn't
3. Conversation Context - Maintain chat context across sessions
4. Performance Analytics - Track win rate, best setups, etc.
5. Learning Insights - AI-generated insights from patterns
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class TradeJournal:
    """Trade journaling and analysis system"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.trade_journal
        self.patterns = db.trade_patterns
        self.insights = db.trading_insights
    
    async def log_trade(self, trade: Dict) -> Dict:
        """Log a trade to the journal"""
        trade_entry = {
            "symbol": trade.get("symbol"),
            "direction": trade.get("direction"),  # LONG/SHORT
            "entry_price": trade.get("entry_price"),
            "exit_price": trade.get("exit_price"),
            "size": trade.get("size"),
            "leverage": trade.get("leverage", 1),
            "pnl_usd": trade.get("pnl_usd", 0),
            "pnl_pct": trade.get("pnl_pct", 0),
            "strategy": trade.get("strategy"),
            "timeframe": trade.get("timeframe"),
            "setup_type": trade.get("setup_type"),  # e.g., "breakout", "pullback", "reversal"
            "market_condition": trade.get("market_condition"),  # volatile, trending, ranging
            "confidence_at_entry": trade.get("confidence", 0),
            "notes": trade.get("notes", ""),
            "tags": trade.get("tags", []),
            "entry_time": trade.get("entry_time") or datetime.now(timezone.utc),
            "exit_time": trade.get("exit_time") or datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "result": "WIN" if trade.get("pnl_pct", 0) > 0 else "LOSS"
        }
        
        result = await self.collection.insert_one(trade_entry)
        trade_entry["_id"] = str(result.inserted_id)
        
        # Update pattern statistics
        await self._update_patterns(trade_entry)
        
        return trade_entry
    
    async def _update_patterns(self, trade: Dict):
        """Update pattern statistics based on trade outcome"""
        pattern_key = f"{trade['strategy']}_{trade['setup_type']}_{trade['timeframe']}"
        
        update = {
            "$inc": {
                "total_trades": 1,
                "wins" if trade["result"] == "WIN" else "losses": 1,
                "total_pnl_pct": trade.get("pnl_pct", 0)
            },
            "$set": {
                "last_trade": datetime.now(timezone.utc),
                "strategy": trade["strategy"],
                "setup_type": trade["setup_type"],
                "timeframe": trade["timeframe"]
            }
        }
        
        await self.patterns.update_one(
            {"pattern_key": pattern_key},
            update,
            upsert=True
        )
    
    async def get_performance_stats(self, days: int = 30, symbol: str = None) -> Dict:
        """Get trading performance statistics"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = {"created_at": {"$gte": cutoff}}
        if symbol:
            query["symbol"] = symbol
        
        trades = await self.collection.find(query).to_list(1000)
        
        if not trades:
            return {
                "period_days": days,
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl_pct": 0,
                "average_win": 0,
                "average_loss": 0,
                "profit_factor": 0,
                "best_trade": None,
                "worst_trade": None
            }
        
        wins = [t for t in trades if t["result"] == "WIN"]
        losses = [t for t in trades if t["result"] == "LOSS"]
        
        total_wins = sum(t.get("pnl_pct", 0) for t in wins)
        total_losses = abs(sum(t.get("pnl_pct", 0) for t in losses))
        
        sorted_trades = sorted(trades, key=lambda x: x.get("pnl_pct", 0))
        
        return {
            "period_days": days,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round((len(wins) / len(trades)) * 100, 1) if trades else 0,
            "total_pnl_pct": round(sum(t.get("pnl_pct", 0) for t in trades), 2),
            "average_win": round(total_wins / len(wins), 2) if wins else 0,
            "average_loss": round(total_losses / len(losses), 2) if losses else 0,
            "profit_factor": round(total_wins / total_losses, 2) if total_losses > 0 else float('inf'),
            "best_trade": {
                "symbol": sorted_trades[-1]["symbol"],
                "pnl_pct": sorted_trades[-1].get("pnl_pct", 0),
                "strategy": sorted_trades[-1].get("strategy")
            } if trades else None,
            "worst_trade": {
                "symbol": sorted_trades[0]["symbol"],
                "pnl_pct": sorted_trades[0].get("pnl_pct", 0),
                "strategy": sorted_trades[0].get("strategy")
            } if trades else None
        }
    
    async def get_best_patterns(self, min_trades: int = 5) -> List[Dict]:
        """Get best performing trading patterns"""
        patterns = await self.patterns.find({
            "total_trades": {"$gte": min_trades}
        }).to_list(100)
        
        for p in patterns:
            p["_id"] = str(p["_id"])
            p["win_rate"] = round((p.get("wins", 0) / p["total_trades"]) * 100, 1) if p["total_trades"] > 0 else 0
            p["avg_pnl"] = round(p.get("total_pnl_pct", 0) / p["total_trades"], 2) if p["total_trades"] > 0 else 0
        
        # Sort by win rate * average pnl
        return sorted(patterns, key=lambda x: x["win_rate"] * max(x["avg_pnl"], 0.01), reverse=True)[:10]
    
    async def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """Get recent trades from journal"""
        trades = await self.collection.find().sort("created_at", -1).limit(limit).to_list(limit)
        for t in trades:
            t["_id"] = str(t["_id"])
        return trades


class ConversationMemory:
    """Conversation context and memory system"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.conversation_memory
        self.context = db.chat_context
    
    async def store_message(self, chat_id: int, role: str, content: str, 
                            context_type: str = "general") -> Dict:
        """Store a conversation message"""
        message = {
            "chat_id": chat_id,
            "role": role,  # "user" or "assistant"
            "content": content,
            "context_type": context_type,  # general, trading, analysis, etc.
            "timestamp": datetime.now(timezone.utc)
        }
        
        await self.collection.insert_one(message)
        return message
    
    async def get_conversation_history(self, chat_id: int, limit: int = 20, 
                                        context_type: str = None) -> List[Dict]:
        """Get conversation history for a chat"""
        query = {"chat_id": chat_id}
        if context_type:
            query["context_type"] = context_type
        
        messages = await self.collection.find(query).sort("timestamp", -1).limit(limit).to_list(limit)
        
        # Reverse to get chronological order
        messages.reverse()
        
        for m in messages:
            m["_id"] = str(m["_id"])
        
        return messages
    
    async def store_context(self, chat_id: int, context_key: str, context_data: Dict):
        """Store context data for a chat"""
        await self.context.update_one(
            {"chat_id": chat_id, "context_key": context_key},
            {
                "$set": {
                    "data": context_data,
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    
    async def get_context(self, chat_id: int, context_key: str) -> Optional[Dict]:
        """Get context data for a chat"""
        doc = await self.context.find_one({"chat_id": chat_id, "context_key": context_key})
        return doc.get("data") if doc else None
    
    async def clear_old_messages(self, days: int = 7):
        """Clear messages older than specified days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.collection.delete_many({"timestamp": {"$lt": cutoff}})
        return result.deleted_count


class TradingInsights:
    """AI-generated trading insights from patterns"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.trading_insights
        self.journal = TradeJournal(db)
    
    async def generate_insights(self) -> Dict:
        """Generate insights from trading patterns"""
        # Get stats
        stats = await self.journal.get_performance_stats(30)
        patterns = await self.journal.get_best_patterns(3)
        
        insights = []
        
        # Win rate insights
        if stats["win_rate"] >= 60:
            insights.append({
                "type": "POSITIVE",
                "category": "performance",
                "message": f"Strong win rate of {stats['win_rate']}% over the last 30 days!"
            })
        elif stats["win_rate"] < 40 and stats["total_trades"] >= 10:
            insights.append({
                "type": "WARNING",
                "category": "performance",
                "message": f"Win rate at {stats['win_rate']}%. Consider reviewing your strategy selection."
            })
        
        # Best pattern insights
        if patterns:
            best = patterns[0]
            insights.append({
                "type": "INSIGHT",
                "category": "patterns",
                "message": f"Best pattern: {best.get('setup_type', 'Unknown')} on {best.get('timeframe', 'Unknown')} with {best['win_rate']}% win rate"
            })
        
        # Profit factor insights
        if stats["profit_factor"] >= 2:
            insights.append({
                "type": "POSITIVE",
                "category": "risk_management",
                "message": f"Excellent risk/reward with {stats['profit_factor']}x profit factor!"
            })
        elif stats["profit_factor"] < 1 and stats["total_trades"] >= 5:
            insights.append({
                "type": "WARNING",
                "category": "risk_management",
                "message": "Profit factor below 1. Review position sizing and stop losses."
            })
        
        # Average win vs loss
        if stats["average_win"] > 0 and stats["average_loss"] > 0:
            win_loss_ratio = stats["average_win"] / stats["average_loss"]
            if win_loss_ratio >= 1.5:
                insights.append({
                    "type": "POSITIVE",
                    "category": "trade_management",
                    "message": f"Good risk/reward: avg win ({stats['average_win']}%) is {win_loss_ratio:.1f}x avg loss ({stats['average_loss']}%)"
                })
        
        insight_doc = {
            "generated_at": datetime.now(timezone.utc),
            "stats_summary": stats,
            "top_patterns": patterns[:3],
            "insights": insights
        }
        
        await self.collection.insert_one(insight_doc)
        insight_doc["_id"] = str(insight_doc["_id"])
        
        return insight_doc
    
    async def get_latest_insights(self) -> Optional[Dict]:
        """Get most recent insights"""
        doc = await self.collection.find_one(sort=[("generated_at", -1)])
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc


class AeonMemorySystem:
    """Main memory system combining all components"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.journal = TradeJournal(db)
        self.conversation = ConversationMemory(db)
        self.insights = TradingInsights(db)
    
    async def get_full_context(self, chat_id: int) -> Dict:
        """Get full context for a conversation"""
        # Recent messages
        messages = await self.conversation.get_conversation_history(chat_id, 10)
        
        # Trading context
        trading_context = await self.conversation.get_context(chat_id, "trading_preferences")
        
        # Recent performance
        stats = await self.journal.get_performance_stats(7)
        
        # Best patterns
        patterns = await self.journal.get_best_patterns(3)
        
        return {
            "recent_messages": messages,
            "trading_preferences": trading_context,
            "recent_performance": stats,
            "best_patterns": patterns[:3]
        }
    
    async def remember_preference(self, chat_id: int, key: str, value: Any):
        """Remember a user preference"""
        prefs = await self.conversation.get_context(chat_id, "preferences") or {}
        prefs[key] = value
        await self.conversation.store_context(chat_id, "preferences", prefs)
    
    async def get_preference(self, chat_id: int, key: str, default: Any = None) -> Any:
        """Get a user preference"""
        prefs = await self.conversation.get_context(chat_id, "preferences") or {}
        return prefs.get(key, default)
    
    async def get_system_stats(self) -> Dict:
        """Get overall system statistics"""
        total_trades = await self.journal.collection.count_documents({})
        total_messages = await self.conversation.collection.count_documents({})
        total_insights = await self.insights.collection.count_documents({})
        
        stats = await self.journal.get_performance_stats(30)
        
        return {
            "total_trades_logged": total_trades,
            "total_messages_stored": total_messages,
            "total_insights_generated": total_insights,
            "30_day_performance": stats,
            "memory_active": True
        }


# Factory function
def init_memory_system(db: AsyncIOMotorDatabase) -> AeonMemorySystem:
    """Initialize the memory system"""
    return AeonMemorySystem(db)
