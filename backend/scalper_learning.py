"""
AEON AUTO-LEARNING SCALPER
Self-optimizing scalping system with reversal pattern detection

Features:
1. Reversal Pattern Detection for Smart Exits
2. Auto-Learning Parameter Optimization
3. Integration with V2.1 Autonomous Trader
4. Continuous Performance Tracking
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import os

logger = logging.getLogger(__name__)

# MongoDB connection
try:
    from pymongo import MongoClient
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    mongo_client = MongoClient(mongo_url)
    db = mongo_client.test_database
    scalper_collection = db.scalper_learning
    scalper_trades_collection = db.scalper_trades
    scalper_params_collection = db.scalper_params
except Exception as e:
    logger.error(f"MongoDB connection error for scalper: {e}")
    scalper_collection = None
    scalper_trades_collection = None
    scalper_params_collection = None


# ===== REVERSAL PATTERN DETECTION =====

class ReversalPatternDetector:
    """
    Detects candlestick reversal patterns for intelligent exits
    
    Patterns detected:
    - Doji (indecision)
    - Engulfing (bullish/bearish)
    - Hammer/Shooting Star
    - Morning/Evening Star
    - RSI Divergence
    """
    
    @staticmethod
    def detect_doji(open_price: float, high: float, low: float, close: float) -> bool:
        """Detect doji pattern (small body, long wicks)"""
        body = abs(close - open_price)
        range_size = high - low
        
        if range_size == 0:
            return False
        
        body_ratio = body / range_size
        return body_ratio < 0.1  # Body is less than 10% of range
    
    @staticmethod
    def detect_hammer(open_price: float, high: float, low: float, close: float) -> str:
        """Detect hammer (bullish) or shooting star (bearish)"""
        body = abs(close - open_price)
        range_size = high - low
        
        if range_size == 0 or body == 0:
            return None
        
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        
        # Hammer: small body at top, long lower wick (bullish reversal)
        if lower_wick > body * 2 and upper_wick < body * 0.5:
            return "HAMMER"  # Bullish reversal signal
        
        # Shooting Star: small body at bottom, long upper wick (bearish reversal)
        if upper_wick > body * 2 and lower_wick < body * 0.5:
            return "SHOOTING_STAR"  # Bearish reversal signal
        
        return None
    
    @staticmethod
    def detect_engulfing(candles: List[Dict]) -> str:
        """Detect bullish or bearish engulfing pattern"""
        if len(candles) < 2:
            return None
        
        prev = candles[-2]
        curr = candles[-1]
        
        prev_body = prev['close'] - prev['open']
        curr_body = curr['close'] - curr['open']
        
        # Bullish engulfing: prev red, curr green engulfs prev
        if prev_body < 0 and curr_body > 0:
            if curr['open'] < prev['close'] and curr['close'] > prev['open']:
                return "BULLISH_ENGULFING"
        
        # Bearish engulfing: prev green, curr red engulfs prev
        if prev_body > 0 and curr_body < 0:
            if curr['open'] > prev['close'] and curr['close'] < prev['open']:
                return "BEARISH_ENGULFING"
        
        return None
    
    @staticmethod
    def detect_rsi_divergence(prices: List[float], rsi_values: List[float]) -> str:
        """
        Detect RSI divergence (price vs RSI disagreement)
        
        Bullish divergence: Price makes lower low, RSI makes higher low
        Bearish divergence: Price makes higher high, RSI makes lower high
        """
        if len(prices) < 10 or len(rsi_values) < 10:
            return None
        
        # Check last 10 candles
        recent_prices = prices[-10:]
        recent_rsi = rsi_values[-10:]
        
        # Find local extremes
        price_min_idx = np.argmin(recent_prices)
        price_max_idx = np.argmax(recent_prices)
        
        # Bullish divergence check (price lower low, RSI higher low)
        if price_min_idx > 5:  # Recent low
            prev_low_idx = np.argmin(recent_prices[:5])
            if recent_prices[price_min_idx] < recent_prices[prev_low_idx]:
                if recent_rsi[price_min_idx] > recent_rsi[prev_low_idx]:
                    return "BULLISH_DIVERGENCE"
        
        # Bearish divergence check (price higher high, RSI lower high)
        if price_max_idx > 5:  # Recent high
            prev_high_idx = np.argmax(recent_prices[:5])
            if recent_prices[price_max_idx] > recent_prices[prev_high_idx]:
                if recent_rsi[price_max_idx] < recent_rsi[prev_high_idx]:
                    return "BEARISH_DIVERGENCE"
        
        return None
    
    @staticmethod
    def analyze_exit_signals(candles: List[Dict], rsi_values: List[float], 
                            position_type: str) -> Dict:
        """
        Analyze all reversal patterns for exit signals
        
        Returns: {should_exit: bool, reason: str, confidence: float}
        """
        if len(candles) < 3:
            return {"should_exit": False, "reason": None, "confidence": 0}
        
        curr = candles[-1]
        prices = [c['close'] for c in candles]
        
        signals = []
        
        # Check doji
        if ReversalPatternDetector.detect_doji(
            curr['open'], curr['high'], curr['low'], curr['close']
        ):
            signals.append(("DOJI", 0.3))
        
        # Check hammer/shooting star
        hammer = ReversalPatternDetector.detect_hammer(
            curr['open'], curr['high'], curr['low'], curr['close']
        )
        if hammer == "HAMMER" and position_type == "SHORT":
            signals.append(("HAMMER_REVERSAL", 0.7))
        elif hammer == "SHOOTING_STAR" and position_type == "LONG":
            signals.append(("SHOOTING_STAR_REVERSAL", 0.7))
        
        # Check engulfing
        engulfing = ReversalPatternDetector.detect_engulfing(candles)
        if engulfing == "BULLISH_ENGULFING" and position_type == "SHORT":
            signals.append(("BULLISH_ENGULFING_EXIT", 0.8))
        elif engulfing == "BEARISH_ENGULFING" and position_type == "LONG":
            signals.append(("BEARISH_ENGULFING_EXIT", 0.8))
        
        # Check RSI divergence
        if len(rsi_values) >= 10:
            divergence = ReversalPatternDetector.detect_rsi_divergence(prices, rsi_values)
            if divergence == "BULLISH_DIVERGENCE" and position_type == "SHORT":
                signals.append(("BULLISH_DIVERGENCE_EXIT", 0.9))
            elif divergence == "BEARISH_DIVERGENCE" and position_type == "LONG":
                signals.append(("BEARISH_DIVERGENCE_EXIT", 0.9))
        
        if not signals:
            return {"should_exit": False, "reason": None, "confidence": 0}
        
        # Get highest confidence signal
        best_signal = max(signals, key=lambda x: x[1])
        
        return {
            "should_exit": best_signal[1] >= 0.6,
            "reason": best_signal[0],
            "confidence": best_signal[1],
            "all_signals": signals
        }


# ===== AUTO-LEARNING SYSTEM =====

class AutoLearningSystem:
    """
    Self-optimizing parameter system that continuously learns from trades
    
    Features:
    - Tracks performance of each parameter combination
    - Identifies winning parameter sets
    - Auto-adjusts settings based on rolling performance
    - Stores learning history in MongoDB
    """
    
    def __init__(self):
        self.learning_history = []
        self.current_params = None
        self.last_optimization = None
        self.optimization_interval = 3600  # 1 hour
        
    async def load_from_db(self):
        """Load learning history from database"""
        if scalper_params_collection is None:
            return
        
        try:
            doc = scalper_params_collection.find_one({"_id": "current_params"})
            if doc:
                self.current_params = {
                    k: v for k, v in doc.items() 
                    if k not in ['_id', 'updated_at', 'learning_history']
                }
                logger.info(f"Loaded learned params: {self.current_params}")
        except Exception as e:
            logger.error(f"Error loading learned params: {e}")
    
    async def save_to_db(self, params: Dict, performance: Dict):
        """Save learned parameters and performance to database"""
        if scalper_params_collection is None:
            return
        
        try:
            scalper_params_collection.update_one(
                {"_id": "current_params"},
                {
                    "$set": {
                        **params,
                        "performance": performance,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "learning_history": {
                            "params": params,
                            "performance": performance,
                            "timestamp": datetime.now(timezone.utc)
                        }
                    }
                },
                upsert=True
            )
            logger.info(f"Saved learned params: WR={performance.get('win_rate', 0)}%")
        except Exception as e:
            logger.error(f"Error saving learned params: {e}")
    
    async def record_trade(self, trade: Dict):
        """Record a trade for learning"""
        if not scalper_trades_collection:
            return
        
        try:
            trade['recorded_at'] = datetime.now(timezone.utc)
            scalper_trades_collection.insert_one(trade)
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    async def analyze_performance(self, lookback_hours: int = 24) -> Dict:
        """Analyze recent trading performance"""
        if not scalper_trades_collection:
            return {}
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
            
            trades = list(scalper_trades_collection.find({
                "recorded_at": {"$gte": cutoff}
            }))
            
            if not trades:
                return {"total_trades": 0}
            
            wins = sum(1 for t in trades if t.get('pnl_pct', 0) > 0)
            total_pnl = sum(t.get('pnl_pct', 0) for t in trades)
            
            # Analyze by parameter combinations
            param_performance = {}
            for trade in trades:
                params_key = f"{trade.get('profit_target', 1.5)}_{trade.get('stop_loss', 0.5)}"
                if params_key not in param_performance:
                    param_performance[params_key] = {'wins': 0, 'total': 0, 'pnl': 0}
                
                param_performance[params_key]['total'] += 1
                param_performance[params_key]['pnl'] += trade.get('pnl_pct', 0)
                if trade.get('pnl_pct', 0) > 0:
                    param_performance[params_key]['wins'] += 1
            
            return {
                "total_trades": len(trades),
                "wins": wins,
                "losses": len(trades) - wins,
                "win_rate": round((wins / len(trades)) * 100, 1) if trades else 0,
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(total_pnl / len(trades), 2) if trades else 0,
                "param_performance": param_performance,
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {}
    
    async def optimize_parameters(self, current_settings: Dict) -> Dict:
        """
        Auto-optimize parameters based on recent performance
        
        Optimization logic:
        1. If win rate < 30%: Tighten stops, reduce targets
        2. If win rate > 60%: Can afford wider stops, bigger targets
        3. Adjust volume threshold based on signal quality
        4. Tune RSI bounds based on successful trades
        """
        performance = await self.analyze_performance(24)
        
        if performance.get('total_trades', 0) < 10:
            logger.info("Not enough trades for optimization")
            return current_settings
        
        win_rate = performance.get('win_rate', 0)
        avg_pnl = performance.get('avg_pnl', 0)
        
        new_settings = current_settings.copy()
        changes = []
        
        # Optimize profit target
        if win_rate < 30:
            # Lower win rate = reduce targets (easier to hit)
            new_target = max(0.8, current_settings['profit_target_pct'] * 0.9)
            if new_target != current_settings['profit_target_pct']:
                new_settings['profit_target_pct'] = round(new_target, 2)
                changes.append(f"Target: {current_settings['profit_target_pct']}% → {new_target}%")
        elif win_rate > 60 and avg_pnl > 0:
            # High win rate = can afford bigger targets
            new_target = min(3.0, current_settings['profit_target_pct'] * 1.1)
            if new_target != current_settings['profit_target_pct']:
                new_settings['profit_target_pct'] = round(new_target, 2)
                changes.append(f"Target: {current_settings['profit_target_pct']}% → {new_target}%")
        
        # Optimize stop loss
        if win_rate < 25:
            # Tighten stops to reduce losses
            new_stop = max(0.3, current_settings['stop_loss_pct'] * 0.9)
            if new_stop != current_settings['stop_loss_pct']:
                new_settings['stop_loss_pct'] = round(new_stop, 2)
                changes.append(f"Stop: {current_settings['stop_loss_pct']}% → {new_stop}%")
        elif win_rate > 55:
            # Can afford slightly wider stops
            new_stop = min(1.0, current_settings['stop_loss_pct'] * 1.05)
            if new_stop != current_settings['stop_loss_pct']:
                new_settings['stop_loss_pct'] = round(new_stop, 2)
                changes.append(f"Stop: {current_settings['stop_loss_pct']}% → {new_stop}%")
        
        # Optimize volume threshold
        if win_rate < 35:
            # Increase volume requirement (more selective)
            new_vol = min(2.5, current_settings['volume_threshold'] * 1.1)
            if new_vol != current_settings['volume_threshold']:
                new_settings['volume_threshold'] = round(new_vol, 2)
                changes.append(f"Volume: {current_settings['volume_threshold']}x → {new_vol}x")
        elif win_rate > 55:
            # Can relax volume requirement
            new_vol = max(1.2, current_settings['volume_threshold'] * 0.95)
            if new_vol != current_settings['volume_threshold']:
                new_settings['volume_threshold'] = round(new_vol, 2)
                changes.append(f"Volume: {current_settings['volume_threshold']}x → {new_vol}x")
        
        # Optimize RSI bounds
        if win_rate < 30:
            # Make RSI more extreme (more selective)
            new_ob = min(80, current_settings['rsi_overbought'] + 2)
            new_os = max(20, current_settings['rsi_oversold'] - 2)
            if new_ob != current_settings['rsi_overbought']:
                new_settings['rsi_overbought'] = new_ob
                new_settings['rsi_oversold'] = new_os
                changes.append(f"RSI: {current_settings['rsi_oversold']}-{current_settings['rsi_overbought']} → {new_os}-{new_ob}")
        
        if changes:
            logger.info(f"Auto-optimization changes: {', '.join(changes)}")
            await self.save_to_db(new_settings, performance)
        
        self.current_params = new_settings
        self.last_optimization = datetime.now(timezone.utc)
        
        return new_settings
    
    async def should_optimize(self) -> bool:
        """Check if it's time to run optimization"""
        if not self.last_optimization:
            return True
        
        elapsed = (datetime.now(timezone.utc) - self.last_optimization).total_seconds()
        return elapsed >= self.optimization_interval
    
    def get_learning_summary(self) -> Dict:
        """Get summary of learning progress"""
        return {
            "current_params": self.current_params,
            "last_optimization": self.last_optimization.isoformat() if self.last_optimization else None,
            "optimization_interval_hours": self.optimization_interval / 3600,
            "next_optimization_in": max(0, self.optimization_interval - 
                (datetime.now(timezone.utc) - self.last_optimization).total_seconds()
                if self.last_optimization else 0)
        }


# ===== V2.1 INTEGRATION =====

class ScalperV2Integration:
    """
    Integrates scalper signals with V2.1 autonomous trader
    
    - Feeds high-confidence scalp signals to V2.1
    - Allows parallel operation
    - Provides unified signal stream
    """
    
    def __init__(self):
        self.enabled = True
        self.min_strength_for_v2 = 2  # Only send strength 2+ to V2.1
        self.signal_queue = []
        
    async def should_send_to_v2(self, signal: Dict) -> bool:
        """Determine if signal should be sent to V2.1"""
        if not self.enabled:
            return False
        
        if signal.get('strength', 0) < self.min_strength_for_v2:
            return False
        
        # Additional filters for V2.1
        if signal.get('volume_ratio', 0) < 1.3:
            return False
        
        return True
    
    async def format_for_v2(self, signal: Dict) -> Dict:
        """Format scalper signal for V2.1 consumption"""
        return {
            "source": "SCALPER",
            "symbol": signal.get('symbol'),
            "direction": "LONG" if signal.get('signal') == 1 else "SHORT",
            "entry_price": signal.get('price'),
            "stop_loss": signal.get('stop_loss'),
            "take_profit": signal.get('target'),
            "confidence": 70 + (signal.get('strength', 0) * 10),  # 80-100%
            "timeframe": signal.get('timeframe'),
            "reason": signal.get('reason'),
            "scalper_strength": signal.get('strength'),
            "volume_ratio": signal.get('volume_ratio'),
            "rsi": signal.get('rsi'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def queue_signal(self, signal: Dict):
        """Queue signal for V2.1 processing"""
        if await self.should_send_to_v2(signal):
            formatted = await self.format_for_v2(signal)
            self.signal_queue.append(formatted)
            logger.info(f"Scalper signal queued for V2.1: {signal.get('symbol')} {signal.get('signal')}")
    
    def get_queued_signals(self) -> List[Dict]:
        """Get and clear queued signals"""
        signals = self.signal_queue.copy()
        self.signal_queue = []
        return signals


# Global instances
reversal_detector = ReversalPatternDetector()
auto_learner = AutoLearningSystem()
v2_integration = ScalperV2Integration()
