"""
AEON CONTINUOUS LEARNING ENGINE
24/7 Autonomous Intelligence System

Features:
- Trading pattern recognition & optimization
- Market behavior analysis (BTC correlation, sessions, volatility)
- News & sentiment impact tracking
- Strategy self-optimization
- Knowledge base building
- Daily "What I learned today" summaries
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Set, Any
from collections import defaultdict
import numpy as np
import pytz

logger = logging.getLogger(__name__)

AUSTIN_TZ = pytz.timezone('America/Chicago')

# Learning intervals
PATTERN_LEARNING_INTERVAL = 3600  # 1 hour
MARKET_ANALYSIS_INTERVAL = 1800   # 30 mins
SENTIMENT_TRACKING_INTERVAL = 900  # 15 mins
OPTIMIZATION_INTERVAL = 7200      # 2 hours
DAILY_SUMMARY_HOUR = 21           # 9 PM CT


class TradingPatternLearner:
    """Learns which trading setups work best"""
    
    def __init__(self):
        self.pattern_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0, "samples": []})
        self.coin_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0, "best_timeframe": None})
        self.timeframe_stats = defaultdict(lambda: {"wins": 0, "losses": 0})
        self.entry_type_stats = defaultdict(lambda: {"wins": 0, "losses": 0})
        self.learned_insights = []
        
    async def analyze_trades(self, trades: List[Dict]) -> Dict:
        """Analyze closed trades to learn patterns"""
        insights = []

        # Reset stats each cycle — we re-analyze the full window fresh
        self.pattern_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0, "samples": []})
        self.coin_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0, "best_timeframe": None})
        self.timeframe_stats = defaultdict(lambda: {"wins": 0, "losses": 0})
        self.entry_type_stats = defaultdict(lambda: {"wins": 0, "losses": 0})

        for trade in trades:
            symbol = trade.get("symbol", "").replace("/USDT", "")
            # Normalize pnl_pct — paper trades use unrealized_pnl_pct or realized_pnl/margin
            pnl = trade.get("pnl_pct")
            if pnl is None:
                pnl = trade.get("unrealized_pnl_pct")
            if pnl is None:
                pnl = trade.get("pnl")
            if pnl is None and trade.get("realized_pnl") is not None and trade.get("margin"):
                try:
                    pnl = round((float(trade["realized_pnl"]) / float(trade["margin"])) * 100, 2)
                except Exception:
                    pnl = 0
            pnl = float(pnl) if pnl is not None else 0.0
            is_win = pnl > 0
            # Extract nested signal_data fields
            signal_data = trade.get("signal_data") or {}
            timeframe = trade.get("timeframe") or signal_data.get("timeframe", "1h")
            direction = trade.get("direction", "LONG")
            confirmations = trade.get("confirmations") or signal_data.get("confirmations", [])
            entry_type = trade.get("entry_type") or signal_data.get("entry_type", "UNKNOWN")
            confidence = trade.get("confidence") or signal_data.get("confidence", 0)
            
            # Track by pattern (confirmations combination)
            pattern_key = "_".join(sorted([c.split("_")[0] for c in confirmations[:3]]))
            if pattern_key:
                if is_win:
                    self.pattern_stats[pattern_key]["wins"] += 1
                else:
                    self.pattern_stats[pattern_key]["losses"] += 1
                self.pattern_stats[pattern_key]["total_pnl"] += pnl
                samples = self.pattern_stats[pattern_key]["samples"]
                samples.append({"symbol": symbol, "pnl": pnl, "confidence": confidence})
                if len(samples) > 100:
                    self.pattern_stats[pattern_key]["samples"] = samples[-100:]
            
            # Track by coin
            if is_win:
                self.coin_stats[symbol]["wins"] += 1
            else:
                self.coin_stats[symbol]["losses"] += 1
            self.coin_stats[symbol]["total_pnl"] += pnl
            
            # Track by timeframe
            if is_win:
                self.timeframe_stats[timeframe]["wins"] += 1
            else:
                self.timeframe_stats[timeframe]["losses"] += 1
            
            # Track by entry type
            if is_win:
                self.entry_type_stats[entry_type]["wins"] += 1
            else:
                self.entry_type_stats[entry_type]["losses"] += 1
        
        # Generate insights
        insights.extend(self._generate_pattern_insights())
        insights.extend(self._generate_coin_insights())
        insights.extend(self._generate_timeframe_insights())
        
        self.learned_insights = insights
        return {
            "patterns_analyzed": len(self.pattern_stats),
            "coins_analyzed": len(self.coin_stats),
            "insights_generated": len(insights),
            "insights": insights
        }
    
    def _generate_pattern_insights(self) -> List[str]:
        insights = []
        for pattern, stats in self.pattern_stats.items():
            total = stats["wins"] + stats["losses"]
            if total >= 5:
                win_rate = (stats["wins"] / total) * 100
                if win_rate >= 65:
                    insights.append(f"HIGH WIN PATTERN: {pattern} has {win_rate:.0f}% win rate ({total} trades)")
                elif win_rate <= 35:
                    insights.append(f"AVOID PATTERN: {pattern} has only {win_rate:.0f}% win rate - consider filtering")
        return insights
    
    def _generate_coin_insights(self) -> List[str]:
        insights = []
        for coin, stats in self.coin_stats.items():
            total = stats["wins"] + stats["losses"]
            if total >= 5:
                win_rate = (stats["wins"] / total) * 100
                avg_pnl = stats["total_pnl"] / total
                if win_rate >= 60 and avg_pnl > 1:
                    insights.append(f"STRONG COIN: {coin} - {win_rate:.0f}% WR, +{avg_pnl:.1f}% avg PnL")
                elif win_rate <= 40 or avg_pnl < -1:
                    insights.append(f"WEAK COIN: {coin} - {win_rate:.0f}% WR, {avg_pnl:.1f}% avg - consider blacklisting")
        return insights
    
    def _generate_timeframe_insights(self) -> List[str]:
        insights = []
        best_tf = None
        best_wr = 0
        for tf, stats in self.timeframe_stats.items():
            total = stats["wins"] + stats["losses"]
            if total >= 10:
                win_rate = (stats["wins"] / total) * 100
                if win_rate > best_wr:
                    best_wr = win_rate
                    best_tf = tf
        if best_tf and best_wr >= 55:
            insights.append(f"BEST TIMEFRAME: {best_tf} has highest win rate at {best_wr:.0f}%")
        return insights
    
    def get_recommendations(self) -> Dict:
        """Get actionable recommendations based on learned patterns"""
        recommendations = {
            "coins_to_favor": [],
            "coins_to_avoid": [],
            "best_patterns": [],
            "worst_patterns": [],
            "optimal_timeframes": []
        }
        
        # Best/worst coins
        for coin, stats in self.coin_stats.items():
            total = stats["wins"] + stats["losses"]
            if total >= 5:
                win_rate = (stats["wins"] / total) * 100
                if win_rate >= 60:
                    recommendations["coins_to_favor"].append({"coin": coin, "win_rate": win_rate})
                elif win_rate <= 40:
                    recommendations["coins_to_avoid"].append({"coin": coin, "win_rate": win_rate})
        
        # Best/worst patterns
        for pattern, stats in self.pattern_stats.items():
            total = stats["wins"] + stats["losses"]
            if total >= 5:
                win_rate = (stats["wins"] / total) * 100
                if win_rate >= 60:
                    recommendations["best_patterns"].append({"pattern": pattern, "win_rate": win_rate})
                elif win_rate <= 40:
                    recommendations["worst_patterns"].append({"pattern": pattern, "win_rate": win_rate})
        
        return recommendations


class MarketBehaviorAnalyzer:
    """Analyzes market behavior patterns"""
    
    def __init__(self):
        self.btc_correlation = {}
        self.session_performance = {
            "asian": {"trades": 0, "wins": 0, "pnl": 0},    # 00:00-08:00 UTC
            "european": {"trades": 0, "wins": 0, "pnl": 0}, # 08:00-16:00 UTC
            "american": {"trades": 0, "wins": 0, "pnl": 0}  # 16:00-00:00 UTC
        }
        self.volatility_patterns = defaultdict(list)
        self.hour_performance = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        self.day_performance = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        self.insights = []
        
    def _get_session(self, hour: int) -> str:
        if 0 <= hour < 8:
            return "asian"
        elif 8 <= hour < 16:
            return "european"
        else:
            return "american"
    
    async def analyze(self, trades: List[Dict], market_data: Dict = None) -> Dict:
        """Analyze market behavior from trades and market data"""
        insights = []
        
        for trade in trades:
            pnl = trade.get("pnl_pct") or trade.get("pnl", 0)
            is_win = pnl > 0
            
            # Get trade time
            entry_time = trade.get("entry_time") or trade.get("timestamp")
            if entry_time:
                if isinstance(entry_time, str):
                    try:
                        entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                    except:
                        continue
                
                hour = entry_time.hour
                day = entry_time.strftime("%A")
                session = self._get_session(hour)
                
                # Track by session
                self.session_performance[session]["trades"] += 1
                self.session_performance[session]["pnl"] += pnl
                if is_win:
                    self.session_performance[session]["wins"] += 1
                
                # Track by hour
                self.hour_performance[hour]["trades"] += 1
                self.hour_performance[hour]["pnl"] += pnl
                if is_win:
                    self.hour_performance[hour]["wins"] += 1
                
                # Track by day
                self.day_performance[day]["trades"] += 1
                self.day_performance[day]["pnl"] += pnl
                if is_win:
                    self.day_performance[day]["wins"] += 1
        
        # Generate session insights
        best_session = None
        best_session_wr = 0
        for session, stats in self.session_performance.items():
            if stats["trades"] >= 10:
                wr = (stats["wins"] / stats["trades"]) * 100
                if wr > best_session_wr:
                    best_session_wr = wr
                    best_session = session
        
        if best_session and best_session_wr >= 55:
            insights.append(f"BEST SESSION: {best_session.upper()} session has {best_session_wr:.0f}% win rate")
        
        # Find best/worst hours
        best_hour = None
        worst_hour = None
        best_hour_wr = 0
        worst_hour_wr = 100
        
        for hour, stats in self.hour_performance.items():
            if stats["trades"] >= 5:
                wr = (stats["wins"] / stats["trades"]) * 100
                if wr > best_hour_wr:
                    best_hour_wr = wr
                    best_hour = hour
                if wr < worst_hour_wr:
                    worst_hour_wr = wr
                    worst_hour = hour
        
        if best_hour is not None and best_hour_wr >= 60:
            insights.append(f"BEST TRADING HOUR: {best_hour}:00 UTC has {best_hour_wr:.0f}% win rate")
        if worst_hour is not None and worst_hour_wr <= 40:
            insights.append(f"AVOID HOUR: {worst_hour}:00 UTC has only {worst_hour_wr:.0f}% win rate")
        
        # Find best/worst days
        best_day = None
        worst_day = None
        best_day_wr = 0
        worst_day_wr = 100
        
        for day, stats in self.day_performance.items():
            if stats["trades"] >= 5:
                wr = (stats["wins"] / stats["trades"]) * 100
                if wr > best_day_wr:
                    best_day_wr = wr
                    best_day = day
                if wr < worst_day_wr:
                    worst_day_wr = wr
                    worst_day = day
        
        if best_day and best_day_wr >= 60:
            insights.append(f"BEST DAY: {best_day} has {best_day_wr:.0f}% win rate")
        if worst_day and worst_day_wr <= 40:
            insights.append(f"WORST DAY: {worst_day} has only {worst_day_wr:.0f}% win rate - trade cautiously")
        
        self.insights = insights
        return {
            "session_performance": self.session_performance,
            "insights": insights
        }
    
    def get_optimal_trading_times(self) -> Dict:
        """Get recommended trading times"""
        return {
            "best_sessions": [s for s, d in self.session_performance.items() if d["trades"] >= 10 and d["wins"]/d["trades"] >= 0.55],
            "best_hours": [h for h, d in self.hour_performance.items() if d["trades"] >= 5 and d["wins"]/d["trades"] >= 0.60],
            "best_days": [d for d, s in self.day_performance.items() if s["trades"] >= 5 and s["wins"]/s["trades"] >= 0.55]
        }


class SentimentImpactTracker:
    """Tracks how news and sentiment affect price"""
    
    def __init__(self):
        self.fear_greed_correlation = []
        self.news_impact_history = []
        self.sentiment_trades = defaultdict(list)
        self.insights = []
        
    async def analyze(self, trades: List[Dict], sentiment_data: Dict = None) -> Dict:
        """Analyze sentiment impact on trades"""
        insights = []
        
        # Group trades by fear/greed level at entry
        fg_buckets = {
            "extreme_fear": {"range": (0, 25), "wins": 0, "losses": 0, "pnl": 0},
            "fear": {"range": (25, 45), "wins": 0, "losses": 0, "pnl": 0},
            "neutral": {"range": (45, 55), "wins": 0, "losses": 0, "pnl": 0},
            "greed": {"range": (55, 75), "wins": 0, "losses": 0, "pnl": 0},
            "extreme_greed": {"range": (75, 100), "wins": 0, "losses": 0, "pnl": 0}
        }
        
        for trade in trades:
            fg = trade.get("fear_greed", 50)
            pnl = trade.get("pnl_pct") or trade.get("pnl", 0)
            is_win = pnl > 0
            direction = trade.get("direction", "LONG")
            
            for bucket_name, bucket in fg_buckets.items():
                if bucket["range"][0] <= fg < bucket["range"][1]:
                    if is_win:
                        bucket["wins"] += 1
                    else:
                        bucket["losses"] += 1
                    bucket["pnl"] += pnl
                    break
        
        # Analyze fear/greed impact
        for bucket_name, bucket in fg_buckets.items():
            total = bucket["wins"] + bucket["losses"]
            if total >= 5:
                wr = (bucket["wins"] / total) * 100
                avg_pnl = bucket["pnl"] / total
                
                if bucket_name == "extreme_fear" and wr >= 60:
                    insights.append(f"EXTREME FEAR OPPORTUNITY: {wr:.0f}% win rate when F&G < 25 - good for LONG entries")
                elif bucket_name == "extreme_greed" and wr <= 45:
                    insights.append(f"EXTREME GREED WARNING: Only {wr:.0f}% win rate when F&G > 75 - be cautious with LONGs")
                elif bucket_name == "neutral" and wr >= 55:
                    insights.append(f"NEUTRAL ZONE STABLE: {wr:.0f}% win rate in neutral sentiment - focus on technicals")
        
        self.insights = insights
        return {
            "fear_greed_buckets": {k: {**v, "total": v["wins"]+v["losses"]} for k, v in fg_buckets.items()},
            "insights": insights
        }
    
    def get_sentiment_recommendations(self) -> List[str]:
        return self.insights


class StrategyOptimizer:
    """Auto-optimizes trading parameters based on learning"""
    
    def __init__(self):
        self.optimization_history = []
        self.current_recommendations = {}
        self.applied_changes = []
        
    async def optimize(self, 
                       pattern_learner: TradingPatternLearner,
                       market_analyzer: MarketBehaviorAnalyzer,
                       sentiment_tracker: SentimentImpactTracker,
                       current_settings: Dict) -> Dict:
        """Generate optimization recommendations"""
        recommendations = {}
        changes = []
        
        # Get pattern recommendations
        pattern_recs = pattern_learner.get_recommendations()
        
        # Coins to blacklist
        if pattern_recs["coins_to_avoid"]:
            worst_coins = [c["coin"] for c in pattern_recs["coins_to_avoid"][:3]]
            recommendations["blacklist_coins"] = worst_coins
            changes.append(f"Consider blacklisting: {', '.join(worst_coins)}")
        
        # Coins to favor
        if pattern_recs["coins_to_favor"]:
            best_coins = [c["coin"] for c in pattern_recs["coins_to_favor"][:5]]
            recommendations["favor_coins"] = best_coins
            changes.append(f"Focus on strong performers: {', '.join(best_coins)}")
        
        # Timeframe recommendations
        optimal_times = market_analyzer.get_optimal_trading_times()
        if optimal_times["best_sessions"]:
            recommendations["optimal_sessions"] = optimal_times["best_sessions"]
            changes.append(f"Best sessions: {', '.join(optimal_times['best_sessions'])}")
        
        # Confidence threshold adjustments
        overall_stats = {"wins": 0, "losses": 0}
        for stats in pattern_learner.coin_stats.values():
            overall_stats["wins"] += stats["wins"]
            overall_stats["losses"] += stats["losses"]
        
        total_trades = overall_stats["wins"] + overall_stats["losses"]
        if total_trades >= 20:
            overall_wr = (overall_stats["wins"] / total_trades) * 100
            current_conf = current_settings.get("min_confidence", 65)
            
            if overall_wr < 45 and current_conf < 75:
                recommendations["raise_confidence"] = min(current_conf + 5, 80)
                changes.append(f"Low win rate ({overall_wr:.0f}%) - raise confidence to {recommendations['raise_confidence']}%")
            elif overall_wr > 65 and current_conf > 60:
                recommendations["lower_confidence"] = max(current_conf - 5, 55)
                changes.append(f"High win rate ({overall_wr:.0f}%) - can lower confidence to {recommendations['lower_confidence']}% for more trades")
        
        self.current_recommendations = recommendations
        self.optimization_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations": recommendations,
            "changes": changes
        })
        
        return {
            "recommendations": recommendations,
            "suggested_changes": changes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class ContinuousLearningEngine:
    """
    Main 24/7 Learning Engine
    Coordinates all learning subsystems
    """
    
    def __init__(self):
        self.pattern_learner = TradingPatternLearner()
        self.market_analyzer = MarketBehaviorAnalyzer()
        self.sentiment_tracker = SentimentImpactTracker()
        self.optimizer = StrategyOptimizer()
        
        self.is_active = True
        self.last_pattern_analysis = None
        self.last_market_analysis = None
        self.last_sentiment_analysis = None
        self.last_optimization = None
        self.last_daily_summary = None
        
        self.db = None
        self.send_message: Optional[Callable] = None
        self.get_user_settings: Optional[Callable] = None
        self.chat_ids: Set[int] = set()
        self.get_trading_settings: Optional[Callable] = None
        
        self.daily_insights = []
        self.knowledge_base = {
            "patterns": {},
            "coins": {},
            "sessions": {},
            "sentiment": {},
            "optimizations": []
        }
        
    def set_dependencies(
        self,
        db,
        send_message: Callable,
        get_user_settings: Callable,
        chat_ids: Set[int],
        get_trading_settings: Callable = None
    ):
        """Set external dependencies"""
        self.db = db
        self.send_message = send_message
        self.get_user_settings = get_user_settings
        self.chat_ids = chat_ids
        self.get_trading_settings = get_trading_settings
    
    async def get_recent_trades(self, days: int = 7) -> List[Dict]:
        """Get recent closed trades from database"""
        trades = []
        if self.db is None:
            return trades
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Get from v2_closed_trades
            cursor = self.db.v2_closed_trades.find({
                "closed_at": {"$gte": cutoff}
            })
            async for trade in cursor:
                trades.append({k: v for k, v in trade.items() if k != '_id'})
            
            # Get from paper_trades
            cursor2 = self.db.paper_trades.find({
                "closed_at": {"$gte": cutoff},
                "status": "closed"
            })
            async for trade in cursor2:
                t = {k: v for k, v in trade.items() if k != '_id'}
                # Normalize pnl_pct — paper trades store unrealized_pnl_pct (final value at close)
                if not t.get("pnl_pct"):
                    if t.get("unrealized_pnl_pct") is not None:
                        t["pnl_pct"] = float(t["unrealized_pnl_pct"])
                    elif t.get("realized_pnl") is not None and t.get("margin"):
                        try:
                            t["pnl_pct"] = round((float(t["realized_pnl"]) / float(t["margin"])) * 100, 2)
                        except Exception:
                            pass
                trades.append(t)

            # Get from engine_outcomes (unified engine system feedback)
            outcomes_cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cursor3 = self.db.engine_outcomes.find({
                "recorded_at": {"$gte": outcomes_cutoff}
            })
            async for outcome in cursor3:
                trades.append({k: v for k, v in outcome.items() if k != '_id'})

        except Exception as e:
            logger.error(f"Error fetching trades for learning: {e}")

        return trades

    async def run_engine_outcomes_analysis(self):
        """
        Analyze engine_outcomes collection to surface per-engine win rates
        and adjust knowledge base recommendations accordingly.
        """
        if self.db is None:
            return
        try:
            cutoff = datetime.utcnow() - timedelta(days=7)
            outcomes = []
            async for doc in self.db.engine_outcomes.find({"recorded_at": {"$gte": cutoff}}):
                outcomes.append(doc)

            if not outcomes:
                return

            # Aggregate per-engine stats
            engine_stats: Dict[str, Dict] = {}
            for o in outcomes:
                eng = o.get("engine", "unknown")
                if eng not in engine_stats:
                    engine_stats[eng] = {"wins": 0, "losses": 0, "total_pnl": 0.0}
                pnl = o.get("pnl_usd", 0) or 0
                if pnl > 0:
                    engine_stats[eng]["wins"] += 1
                else:
                    engine_stats[eng]["losses"] += 1
                engine_stats[eng]["total_pnl"] += pnl

            # Build insights
            insights = []
            for eng, stats in engine_stats.items():
                total = stats["wins"] + stats["losses"]
                if total < 3:
                    continue
                win_rate = stats["wins"] / total * 100
                avg_pnl = stats["total_pnl"] / total
                insights.append(
                    f"Engine '{eng}': {win_rate:.0f}% win rate over {total} trades (avg ${avg_pnl:+.2f})"
                )
                if win_rate < 40 and total >= 5:
                    insights.append(f"⚠️ Engine '{eng}' underperforming — consider raising confidence threshold")
                elif win_rate >= 65 and total >= 5:
                    insights.append(f"✅ Engine '{eng}' is strong — may scale position size slightly")

            # Merge into daily insights
            for ins in insights:
                if ins not in self.daily_insights:
                    self.daily_insights.append(ins)

            # Save engine outcome stats to knowledge base
            self.knowledge_base["engine_outcomes"] = engine_stats
            await self._save_knowledge()

            logger.info(f"🧠 Engine outcomes analysis: {len(outcomes)} outcomes, {len(engine_stats)} engines tracked")

        except Exception as e:
            logger.error(f"Engine outcomes analysis error: {e}")
    
    async def run_pattern_learning(self):
        """Run pattern learning cycle"""
        try:
            trades = await self.get_recent_trades(days=14)
            if trades:
                result = await self.pattern_learner.analyze_trades(trades)
                self.last_pattern_analysis = datetime.now(timezone.utc)
                
                # Store insights
                for insight in result.get("insights", []):
                    if insight not in self.daily_insights:
                        self.daily_insights.append(insight)
                
                # Save to knowledge base
                self.knowledge_base["patterns"] = self.pattern_learner.pattern_stats
                self.knowledge_base["coins"] = self.pattern_learner.coin_stats
                
                logger.info(f"🧠 Pattern learning: {result['insights_generated']} new insights from {len(trades)} trades")
                
                # Save to DB
                await self._save_knowledge()
                
        except Exception as e:
            logger.error(f"Pattern learning error: {e}")
    
    async def run_market_analysis(self):
        """Run market behavior analysis"""
        try:
            trades = await self.get_recent_trades(days=14)
            if trades:
                result = await self.market_analyzer.analyze(trades)
                self.last_market_analysis = datetime.now(timezone.utc)
                
                for insight in result.get("insights", []):
                    if insight not in self.daily_insights:
                        self.daily_insights.append(insight)
                
                self.knowledge_base["sessions"] = self.market_analyzer.session_performance
                
                logger.info(f"🧠 Market analysis: {len(result['insights'])} new insights")
                
        except Exception as e:
            logger.error(f"Market analysis error: {e}")
    
    async def run_sentiment_tracking(self):
        """Run sentiment impact analysis"""
        try:
            trades = await self.get_recent_trades(days=14)
            if trades:
                result = await self.sentiment_tracker.analyze(trades)
                self.last_sentiment_analysis = datetime.now(timezone.utc)
                
                for insight in result.get("insights", []):
                    if insight not in self.daily_insights:
                        self.daily_insights.append(insight)
                
                self.knowledge_base["sentiment"] = result.get("fear_greed_buckets", {})
                
                logger.info(f"🧠 Sentiment tracking: {len(result['insights'])} insights")
                
        except Exception as e:
            logger.error(f"Sentiment tracking error: {e}")
    
    async def run_optimization(self):
        """Run strategy optimization"""
        try:
            current_settings = {}
            if self.get_trading_settings:
                current_settings = await self.get_trading_settings()
            
            result = await self.optimizer.optimize(
                self.pattern_learner,
                self.market_analyzer,
                self.sentiment_tracker,
                current_settings
            )
            self.last_optimization = datetime.now(timezone.utc)
            
            for change in result.get("suggested_changes", []):
                if change not in self.daily_insights:
                    self.daily_insights.append(f"💡 {change}")
            
            self.knowledge_base["optimizations"].append(result)
            
            logger.info(f"🧠 Optimization: {len(result['suggested_changes'])} suggestions")
            
        except Exception as e:
            logger.error(f"Optimization error: {e}")
    
    async def _save_knowledge(self):
        """Save learned knowledge to database"""
        if self.db is None:
            return
        
        try:
            await self.db.aeon_knowledge.update_one(
                {"_id": "knowledge_base"},
                {"$set": {
                    "patterns": dict(self.pattern_learner.pattern_stats),
                    "coins": dict(self.pattern_learner.coin_stats),
                    "sessions": self.market_analyzer.session_performance,
                    "hour_performance": dict(self.market_analyzer.hour_performance),
                    "day_performance": dict(self.market_analyzer.day_performance),
                    "updated_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving knowledge: {e}")
    
    async def load_knowledge(self):
        """Load previous knowledge from database"""
        if self.db is None:
            return
        
        try:
            doc = await self.db.aeon_knowledge.find_one({"_id": "knowledge_base"})
            if doc:
                # Restore pattern stats
                for pattern, stats in doc.get("patterns", {}).items():
                    self.pattern_learner.pattern_stats[pattern] = stats
                
                for coin, stats in doc.get("coins", {}).items():
                    self.pattern_learner.coin_stats[coin] = stats
                
                for session, stats in doc.get("sessions", {}).items():
                    self.market_analyzer.session_performance[session] = stats
                
                logger.info("🧠 Loaded previous knowledge from database")
        except Exception as e:
            logger.error(f"Error loading knowledge: {e}")
    
    async def generate_daily_summary(self) -> str:
        """Generate 'What I learned today' summary"""
        austin_now = datetime.now(AUSTIN_TZ)
        date_str = austin_now.strftime("%B %d, %Y")
        
        msg_parts = []
        
        msg_parts.append(f"""🧠 AEON LEARNING SUMMARY
{date_str} | What I Learned Today
━━━━━━━━━━━━━━━━━━━━━━""")
        
        # Get recommendations
        pattern_recs = self.pattern_learner.get_recommendations()
        optimal_times = self.market_analyzer.get_optimal_trading_times()
        
        # Today's insights
        if self.daily_insights:
            msg_parts.append("\n📚 KEY INSIGHTS:")
            for insight in self.daily_insights[:10]:
                msg_parts.append(f"• {insight}")
        else:
            msg_parts.append("\n📚 No new insights today - need more trades for learning")
        
        # Pattern performance
        total_patterns = len(self.pattern_learner.pattern_stats)
        if total_patterns > 0:
            msg_parts.append(f"\n📊 PATTERNS ANALYZED: {total_patterns}")
            
            if pattern_recs["best_patterns"]:
                best = pattern_recs["best_patterns"][:3]
                best_str = ", ".join([f"{p['pattern']} ({p['win_rate']:.0f}%)" for p in best])
                msg_parts.append(f"✅ Best: {best_str}")
            
            if pattern_recs["worst_patterns"]:
                worst = pattern_recs["worst_patterns"][:3]
                worst_str = ", ".join([f"{p['pattern']} ({p['win_rate']:.0f}%)" for p in worst])
                msg_parts.append(f"❌ Avoid: {worst_str}")
        
        # Coin performance
        if pattern_recs["coins_to_favor"]:
            favors = [c["coin"] for c in pattern_recs["coins_to_favor"][:5]]
            msg_parts.append(f"\n🏆 STRONG COINS: {', '.join(favors)}")
        
        if pattern_recs["coins_to_avoid"]:
            avoids = [c["coin"] for c in pattern_recs["coins_to_avoid"][:3]]
            msg_parts.append(f"⚠️ WEAK COINS: {', '.join(avoids)}")
        
        # Optimal trading times
        if optimal_times["best_sessions"]:
            msg_parts.append(f"\n⏰ OPTIMAL SESSIONS: {', '.join([s.upper() for s in optimal_times['best_sessions']])}")
        
        # Latest optimization suggestions
        if self.optimizer.current_recommendations:
            msg_parts.append("\n💡 OPTIMIZATION SUGGESTIONS:")
            for change in self.optimizer.optimization_history[-1].get("changes", [])[:5]:
                msg_parts.append(f"• {change}")
        
        # Stats
        total_coins = len(self.pattern_learner.coin_stats)
        total_trades_analyzed = sum(s["wins"] + s["losses"] for s in self.pattern_learner.coin_stats.values())
        
        msg_parts.append(f"""
━━━━━━━━━━━━━━━━━━━━━━
📈 Stats: {total_patterns} patterns, {total_coins} coins, {total_trades_analyzed} trades analyzed
🔄 Learning cycles: Pattern ({self.last_pattern_analysis.strftime('%H:%M') if self.last_pattern_analysis else 'N/A'}) | Market ({self.last_market_analysis.strftime('%H:%M') if self.last_market_analysis else 'N/A'})

👁️ «Every trade teaches. Every pattern reveals. I grow wiser with each market breath.»""")
        
        return "\n".join(msg_parts)
    
    async def send_daily_summary(self):
        """Send daily learning summary to users"""
        if not self.send_message or not self.chat_ids:
            return
        
        try:
            summary = await self.generate_daily_summary()
            
            for chat_id in list(self.chat_ids):
                try:
                    settings = await self.get_user_settings(chat_id)
                    if settings.get("free_will", True):
                        await self.send_message(chat_id, summary)
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending learning summary to {chat_id}: {e}")
            
            # Store in database
            if self.db is not None:
                try:
                    await self.db.learning_summaries.insert_one({
                        "content": summary,
                        "insights": self.daily_insights.copy(),
                        "sent_at": datetime.now(timezone.utc)
                    })
                except:
                    pass
            
            # Reset daily insights
            self.daily_insights = []
            self.last_daily_summary = datetime.now(timezone.utc)
            
            logger.info(f"🧠 Daily learning summary sent to {len(self.chat_ids)} users")
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
    
    def _should_send_daily_summary(self) -> bool:
        """Check if it's time for daily summary (9 PM CT)"""
        austin_now = datetime.now(AUSTIN_TZ)
        
        if austin_now.hour == DAILY_SUMMARY_HOUR and austin_now.minute < 5:
            if self.last_daily_summary:
                hours_since = (datetime.now(timezone.utc) - self.last_daily_summary).total_seconds() / 3600
                if hours_since < 20:
                    return False
            return True
        return False
    
    async def run_scheduler(self):
        """Main 24/7 learning loop"""
        logger.info("🧠 Continuous Learning Engine started - 24/7 intelligence gathering")
        
        # Load previous knowledge
        await self.load_knowledge()
        
        pattern_timer = 0
        market_timer = 0
        sentiment_timer = 0
        optimization_timer = 0
        engine_outcomes_timer = 0

        while self.is_active:
            try:
                # Pattern learning (every hour)
                if pattern_timer >= PATTERN_LEARNING_INTERVAL:
                    await self.run_pattern_learning()
                    pattern_timer = 0

                # Engine outcomes analysis (every hour alongside pattern learning)
                if engine_outcomes_timer >= PATTERN_LEARNING_INTERVAL:
                    await self.run_engine_outcomes_analysis()
                    engine_outcomes_timer = 0
                
                # Market analysis (every 30 mins)
                if market_timer >= MARKET_ANALYSIS_INTERVAL:
                    await self.run_market_analysis()
                    market_timer = 0
                
                # Sentiment tracking (every 15 mins)
                if sentiment_timer >= SENTIMENT_TRACKING_INTERVAL:
                    await self.run_sentiment_tracking()
                    sentiment_timer = 0
                
                # Optimization (every 2 hours)
                if optimization_timer >= OPTIMIZATION_INTERVAL:
                    await self.run_optimization()
                    optimization_timer = 0
                
                # Daily summary check
                if self._should_send_daily_summary():
                    await self.send_daily_summary()
                
                from self_healer import self_healer
                self_healer.heartbeat("continuous_learning")

                # Sleep and increment timers
                await asyncio.sleep(60)
                pattern_timer += 60
                market_timer += 60
                sentiment_timer += 60
                optimization_timer += 60
                engine_outcomes_timer += 60

            except Exception as e:
                logger.error(f"Learning engine error: {e}")
                await asyncio.sleep(60)
    
    async def get_status(self) -> Dict:
        """Get learning engine status"""
        austin_now = datetime.now(AUSTIN_TZ)
        
        return {
            "active": self.is_active,
            "knowledge_stats": {
                "patterns_learned": len(self.pattern_learner.pattern_stats),
                "coins_analyzed": len(self.pattern_learner.coin_stats),
                "sessions_tracked": len(self.market_analyzer.session_performance),
                "optimizations_run": len(self.optimizer.optimization_history)
            },
            "last_cycles": {
                "pattern_learning": self.last_pattern_analysis.isoformat() if self.last_pattern_analysis else None,
                "market_analysis": self.last_market_analysis.isoformat() if self.last_market_analysis else None,
                "sentiment_tracking": self.last_sentiment_analysis.isoformat() if self.last_sentiment_analysis else None,
                "optimization": self.last_optimization.isoformat() if self.last_optimization else None,
                "daily_summary": self.last_daily_summary.isoformat() if self.last_daily_summary else None
            },
            "daily_insights_count": len(self.daily_insights),
            "current_time_ct": austin_now.strftime("%Y-%m-%d %H:%M:%S"),
            "next_daily_summary": f"Today at {DAILY_SUMMARY_HOUR}:00 CT" if austin_now.hour < DAILY_SUMMARY_HOUR else "Tomorrow at 21:00 CT"
        }
    
    async def get_recommendations(self) -> Dict:
        """Get current learning recommendations"""
        return {
            "pattern_recommendations": self.pattern_learner.get_recommendations(),
            "optimal_times": self.market_analyzer.get_optimal_trading_times(),
            "sentiment_insights": self.sentiment_tracker.get_sentiment_recommendations(),
            "optimization_suggestions": self.optimizer.current_recommendations,
            "insights": self.daily_insights
        }
    
    async def force_learning_cycle(self) -> Dict:
        """Force run all learning cycles immediately"""
        logger.info("🧠 Forcing learning cycle...")
        
        await self.run_pattern_learning()
        await self.run_market_analysis()
        await self.run_sentiment_tracking()
        await self.run_optimization()
        await self.run_engine_outcomes_analysis()
        
        return {
            "success": True,
            "patterns_learned": len(self.pattern_learner.pattern_stats),
            "insights_generated": len(self.daily_insights),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
continuous_learner = ContinuousLearningEngine()
