"""
Signal History & Accuracy Tracker
Collects and tracks all trading signals for backtest validation and accuracy monitoring
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class SignalTracker:
    """
    Tracks all trading signals from all engines for:
    1. Historical backtest data collection
    2. Accuracy monitoring per strategy
    3. Win rate calculation
    4. Performance analytics
    """
    
    def __init__(self):
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collection_name = "signal_history"
        self.accuracy_collection = "signal_accuracy"
        
        # In-memory cache for quick stats
        self.cache = {
            "total_signals": 0,
            "total_wins": 0,
            "total_losses": 0,
            "by_strategy": {},
            "by_symbol": {},
            "by_direction": {"LONG": {"wins": 0, "total": 0}, "SHORT": {"wins": 0, "total": 0}}
        }
        
        logger.info("📊 Signal Tracker initialized")
    
    def set_db(self, db: AsyncIOMotorDatabase):
        """Set database connection"""
        self.db = db
    
    async def record_signal(self, signal: Dict, source: str = "UNKNOWN") -> Dict:
        """
        Record a trading signal to history.
        Called whenever any engine generates a signal.
        """
        if self.db is None:
            logger.warning("Signal tracker: No database connection")
            return {"success": False, "error": "No database"}
        
        try:
            record = {
                "signal_id": f"sig_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{signal.get('symbol', 'UNK')}",
                "symbol": signal.get("symbol", "UNKNOWN"),
                "direction": signal.get("direction", "UNKNOWN"),
                "entry_price": signal.get("entry_price", 0),
                "stop_price": signal.get("stop_price", 0),
                "target_price": signal.get("target_price", 0),
                "confidence": signal.get("confidence", 0),
                "strategy": source,
                "timeframe": signal.get("timeframe", "4h"),
                "confirmations": signal.get("confirmations", []),
                "mtf_confluence": signal.get("mtf_confluence", "0/3"),
                "btc_trend": signal.get("btc_trend", "NEUTRAL"),
                "rr_ratio": signal.get("rr_ratio", 0),
                "volume_ratio": signal.get("volume_ratio", 0),
                "adx": signal.get("adx", 0),
                "rsi": signal.get("rsi", 50),
                "created_at": datetime.now(timezone.utc),
                "status": "OPEN",  # OPEN, WIN, LOSS, CANCELLED
                "exit_price": None,
                "exit_time": None,
                "pnl_pct": None,
                "outcome_reason": None
            }
            
            await self.db[self.collection_name].insert_one(record)
            
            # Update cache
            self.cache["total_signals"] += 1
            if source not in self.cache["by_strategy"]:
                self.cache["by_strategy"][source] = {"signals": 0, "wins": 0}
            self.cache["by_strategy"][source]["signals"] += 1
            
            logger.info(f"📊 Signal recorded: {signal.get('symbol')} {signal.get('direction')} from {source}")
            
            return {"success": True, "signal_id": record["signal_id"]}
            
        except Exception as e:
            logger.error(f"Error recording signal: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_signal_outcome(
        self, 
        symbol: str, 
        direction: str, 
        outcome: str,  # "WIN" or "LOSS"
        exit_price: float,
        pnl_pct: float,
        reason: str = ""
    ) -> Dict:
        """
        Update a signal with its outcome (win/loss).
        Called when a trade closes.
        """
        if self.db is None:
            return {"success": False, "error": "No database"}
        
        try:
            # Find the most recent open signal for this symbol/direction
            signal = await self.db[self.collection_name].find_one(
                {
                    "symbol": symbol,
                    "direction": direction,
                    "status": "OPEN"
                },
                sort=[("created_at", -1)]
            )
            
            if not signal:
                logger.warning(f"No open signal found for {symbol} {direction}")
                return {"success": False, "error": "No matching open signal"}
            
            # Update the signal
            update_result = await self.db[self.collection_name].update_one(
                {"_id": signal["_id"]},
                {
                    "$set": {
                        "status": outcome,
                        "exit_price": exit_price,
                        "exit_time": datetime.now(timezone.utc),
                        "pnl_pct": pnl_pct,
                        "outcome_reason": reason
                    }
                }
            )
            
            # Update cache
            if outcome == "WIN":
                self.cache["total_wins"] += 1
                self.cache["by_direction"][direction]["wins"] += 1
            else:
                self.cache["total_losses"] += 1
            self.cache["by_direction"][direction]["total"] += 1
            
            strategy = signal.get("strategy", "UNKNOWN")
            if strategy in self.cache["by_strategy"]:
                if outcome == "WIN":
                    self.cache["by_strategy"][strategy]["wins"] += 1
            
            logger.info(f"📊 Signal outcome updated: {symbol} {direction} = {outcome} ({pnl_pct:+.2f}%)")
            
            return {"success": True, "updated": update_result.modified_count > 0}
            
        except Exception as e:
            logger.error(f"Error updating signal outcome: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_accuracy_stats(self, days: int = 30) -> Dict:
        """
        Get signal accuracy statistics for the past N days.
        """
        if self.db is None:
            return {"error": "No database"}
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Get all closed signals
            pipeline = [
                {
                    "$match": {
                        "created_at": {"$gte": cutoff},
                        "status": {"$in": ["WIN", "LOSS"]}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "wins": {"$sum": {"$cond": [{"$eq": ["$status", "WIN"]}, 1, 0]}},
                        "total_pnl": {"$sum": {"$ifNull": ["$pnl_pct", 0]}},
                        "avg_confidence": {"$avg": "$confidence"}
                    }
                }
            ]
            
            result = await self.db[self.collection_name].aggregate(pipeline).to_list(1)
            
            if not result:
                return {
                    "days_analyzed": days,
                    "total_signals": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0,
                    "total_pnl": 0
                }
            
            stats = result[0]
            total = stats.get("total", 0)
            wins = stats.get("wins", 0)
            
            return {
                "days_analyzed": days,
                "total_signals": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": round((wins / total * 100) if total > 0 else 0, 1),
                "total_pnl": round(stats.get("total_pnl", 0), 2),
                "avg_confidence": round(stats.get("avg_confidence", 0), 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting accuracy stats: {e}")
            return {"error": str(e)}
    
    async def get_strategy_performance(self, days: int = 30) -> Dict:
        """
        Get performance breakdown by strategy.
        """
        if self.db is None:
            return {"error": "No database"}
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            pipeline = [
                {
                    "$match": {
                        "created_at": {"$gte": cutoff},
                        "status": {"$in": ["WIN", "LOSS"]}
                    }
                },
                {
                    "$group": {
                        "_id": "$strategy",
                        "total": {"$sum": 1},
                        "wins": {"$sum": {"$cond": [{"$eq": ["$status", "WIN"]}, 1, 0]}},
                        "total_pnl": {"$sum": {"$ifNull": ["$pnl_pct", 0]}},
                        "avg_confidence": {"$avg": "$confidence"}
                    }
                },
                {"$sort": {"wins": -1}}
            ]
            
            results = await self.db[self.collection_name].aggregate(pipeline).to_list(20)
            
            strategies = {}
            for r in results:
                strategy = r["_id"] or "UNKNOWN"
                total = r.get("total", 0)
                wins = r.get("wins", 0)
                strategies[strategy] = {
                    "total_signals": total,
                    "wins": wins,
                    "losses": total - wins,
                    "win_rate": round((wins / total * 100) if total > 0 else 0, 1),
                    "total_pnl": round(r.get("total_pnl", 0), 2),
                    "avg_confidence": round(r.get("avg_confidence", 0), 1)
                }
            
            return {
                "days_analyzed": days,
                "strategies": strategies
            }
            
        except Exception as e:
            logger.error(f"Error getting strategy performance: {e}")
            return {"error": str(e)}
    
    async def get_recent_signals(self, limit: int = 20) -> List[Dict]:
        """
        Get most recent signals.
        """
        if self.db is None:
            return []
        
        try:
            signals = await self.db[self.collection_name].find(
                {},
                {"_id": 0}
            ).sort("created_at", -1).limit(limit).to_list(limit)
            
            # Convert datetime to string for JSON serialization
            for s in signals:
                if "created_at" in s:
                    s["created_at"] = s["created_at"].isoformat()
                if "exit_time" in s and s["exit_time"]:
                    s["exit_time"] = s["exit_time"].isoformat()
            
            return signals
            
        except Exception as e:
            logger.error(f"Error getting recent signals: {e}")
            return []
    
    def get_cache_stats(self) -> Dict:
        """Get quick stats from cache"""
        total = self.cache["total_wins"] + self.cache["total_losses"]
        return {
            "total_signals_recorded": self.cache["total_signals"],
            "closed_signals": total,
            "wins": self.cache["total_wins"],
            "losses": self.cache["total_losses"],
            "win_rate": round((self.cache["total_wins"] / total * 100) if total > 0 else 0, 1),
            "by_strategy": self.cache["by_strategy"],
            "by_direction": self.cache["by_direction"]
        }


# Global instance
signal_tracker = SignalTracker()


async def init_signal_tracker(db: AsyncIOMotorDatabase):
    """Initialize signal tracker with database"""
    signal_tracker.set_db(db)
    
    # Create indexes
    try:
        await db.signal_history.create_index("symbol")
        await db.signal_history.create_index("strategy")
        await db.signal_history.create_index("status")
        await db.signal_history.create_index("created_at")
        await db.signal_history.create_index([("symbol", 1), ("direction", 1), ("status", 1)])
        logger.info("📊 Signal history indexes created")
    except Exception as e:
        logger.error(f"Error creating signal history indexes: {e}")
    
    return signal_tracker
