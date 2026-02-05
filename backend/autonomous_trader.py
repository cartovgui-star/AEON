"""
AEON AUTONOMOUS TRADING ENGINE
Paper trading with learning feedback loop
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import random

from market_intelligence import market_intel
from learning_system import AeonLearningSystem

logger = logging.getLogger(__name__)


class AutonomousTrader:
    """
    Aeon's autonomous trading brain.
    - Monitors markets continuously
    - Generates trade signals based on confluence
    - Records predictions (paper trading)
    - Evaluates outcomes and learns
    """
    
    def __init__(self, db: AsyncIOMotorDatabase, learning_system: AeonLearningSystem):
        self.db = db
        self.learning = learning_system
        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        self.active = True
        self.min_confidence = 65  # Minimum confidence to take a trade
        self.max_open_positions = 3  # Max simultaneous predictions per symbol
        self.evaluation_interval = 300  # Check predictions every 5 minutes
        
        # Strategy weights (can be adjusted based on learning)
        self.strategy_weights = {
            "rsi_oversold": 1.0,
            "rsi_overbought": 1.0,
            "macd_bullish": 1.0,
            "macd_bearish": 1.0,
            "bb_lower": 1.0,
            "bb_upper": 1.0,
            "ema_stack_bull": 1.2,
            "ema_stack_bear": 1.2,
            "stoch_oversold": 0.8,
            "stoch_overbought": 0.8,
            "orderbook_imbalance": 0.7,
            "volume_spike": 0.5,
        }
        
        # Performance tracking for strategy adjustment
        self.strategy_performance = {}
    
    async def analyze_opportunity(self, symbol: str) -> Dict[str, Any]:
        """
        Comprehensive market analysis for trading opportunity.
        Returns signal with confidence score and reasoning.
        """
        try:
            # Get technical analysis
            ta = await market_intel.get_technical_analysis(symbol, "1h")
            if "error" in ta:
                return {"signal": "NONE", "confidence": 0, "error": ta["error"]}
            
            # Get orderbook
            orderbook = await market_intel.get_orderbook(symbol)
            
            # Scoring system
            score = 0.0
            reasons = []
            signals_used = []
            
            indicators = ta.get("indicators", {})
            price = ta.get("price", 0)
            
            # RSI Analysis
            rsi = indicators.get("rsi", 50)
            if rsi < 30:
                score += 1.5 * self.strategy_weights["rsi_oversold"]
                reasons.append(f"RSI oversold ({rsi:.1f})")
                signals_used.append("rsi_oversold")
            elif rsi < 40:
                score += 0.5 * self.strategy_weights["rsi_oversold"]
                reasons.append(f"RSI low ({rsi:.1f})")
                signals_used.append("rsi_oversold")
            elif rsi > 70:
                score -= 1.5 * self.strategy_weights["rsi_overbought"]
                reasons.append(f"RSI overbought ({rsi:.1f})")
                signals_used.append("rsi_overbought")
            elif rsi > 60:
                score -= 0.5 * self.strategy_weights["rsi_overbought"]
                reasons.append(f"RSI high ({rsi:.1f})")
                signals_used.append("rsi_overbought")
            
            # MACD Analysis
            macd = indicators.get("macd", 0)
            macd_signal = indicators.get("macd_signal", 0)
            macd_hist = indicators.get("macd_histogram", 0)
            
            if macd > macd_signal and macd_hist > 0:
                score += 1.0 * self.strategy_weights["macd_bullish"]
                reasons.append("MACD bullish crossover")
                signals_used.append("macd_bullish")
            elif macd < macd_signal and macd_hist < 0:
                score -= 1.0 * self.strategy_weights["macd_bearish"]
                reasons.append("MACD bearish crossover")
                signals_used.append("macd_bearish")
            
            # Bollinger Bands
            bb_lower = indicators.get("bb_lower", 0)
            bb_upper = indicators.get("bb_upper", 0)
            bb_middle = indicators.get("bb_middle", 0)
            
            if price and bb_lower and price < bb_lower:
                score += 1.2 * self.strategy_weights["bb_lower"]
                reasons.append(f"Price below BB lower (${price:,.0f} < ${bb_lower:,.0f})")
                signals_used.append("bb_lower")
            elif price and bb_upper and price > bb_upper:
                score -= 1.2 * self.strategy_weights["bb_upper"]
                reasons.append(f"Price above BB upper (${price:,.0f} > ${bb_upper:,.0f})")
                signals_used.append("bb_upper")
            
            # EMA Stack
            ema_9 = indicators.get("ema_9", 0)
            ema_21 = indicators.get("ema_21", 0)
            ema_50 = indicators.get("ema_50", 0)
            
            if ema_9 and ema_21 and ema_50:
                if ema_9 > ema_21 > ema_50:
                    score += 1.0 * self.strategy_weights["ema_stack_bull"]
                    reasons.append("Bullish EMA stack (9>21>50)")
                    signals_used.append("ema_stack_bull")
                elif ema_9 < ema_21 < ema_50:
                    score -= 1.0 * self.strategy_weights["ema_stack_bear"]
                    reasons.append("Bearish EMA stack (9<21<50)")
                    signals_used.append("ema_stack_bear")
            
            # Stochastic
            stoch_k = indicators.get("stoch_k", 50)
            stoch_d = indicators.get("stoch_d", 50)
            
            if stoch_k < 20 and stoch_d < 20:
                score += 0.8 * self.strategy_weights["stoch_oversold"]
                reasons.append(f"Stoch oversold (K={stoch_k:.0f}, D={stoch_d:.0f})")
                signals_used.append("stoch_oversold")
            elif stoch_k > 80 and stoch_d > 80:
                score -= 0.8 * self.strategy_weights["stoch_overbought"]
                reasons.append(f"Stoch overbought (K={stoch_k:.0f}, D={stoch_d:.0f})")
                signals_used.append("stoch_overbought")
            
            # Orderbook Imbalance
            if "error" not in orderbook:
                imbalance = orderbook.get("imbalance_pct", 0)
                if imbalance > 20:
                    score += 0.5 * self.strategy_weights["orderbook_imbalance"]
                    reasons.append(f"Orderbook bullish ({imbalance:+.1f}%)")
                    signals_used.append("orderbook_imbalance")
                elif imbalance < -20:
                    score -= 0.5 * self.strategy_weights["orderbook_imbalance"]
                    reasons.append(f"Orderbook bearish ({imbalance:+.1f}%)")
                    signals_used.append("orderbook_imbalance")
            
            # Volume Analysis
            vol_ratio = indicators.get("volume_ratio", 1)
            if vol_ratio > 1.5:
                # High volume confirms trend
                if score > 0:
                    score += 0.3 * self.strategy_weights["volume_spike"]
                elif score < 0:
                    score -= 0.3 * self.strategy_weights["volume_spike"]
                reasons.append(f"Volume spike ({vol_ratio:.1f}x avg)")
                signals_used.append("volume_spike")
            
            # Determine signal
            atr = indicators.get("atr", price * 0.02 if price else 0)
            
            if score >= 2.0:
                signal = "LONG"
                confidence = min(90, 50 + (score * 8))
                target = price + (atr * 2) if price else None
                stop = price - (atr * 1.5) if price else None
            elif score <= -2.0:
                signal = "SHORT"
                confidence = min(90, 50 + (abs(score) * 8))
                target = price - (atr * 2) if price else None
                stop = price + (atr * 1.5) if price else None
            else:
                signal = "NEUTRAL"
                confidence = 30 + abs(score) * 5
                target = None
                stop = None
            
            return {
                "symbol": symbol,
                "signal": signal,
                "confidence": round(confidence, 1),
                "score": round(score, 2),
                "price": price,
                "target": round(target, 2) if target else None,
                "stop_loss": round(stop, 2) if stop else None,
                "reasons": reasons,
                "signals_used": signals_used,
                "indicators": indicators,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")
            return {"signal": "NONE", "confidence": 0, "error": str(e)}
    
    async def should_take_trade(self, analysis: Dict[str, Any]) -> bool:
        """Determine if we should take this trade based on analysis and current positions."""
        if analysis.get("signal") == "NEUTRAL" or analysis.get("signal") == "NONE":
            return False
        
        if analysis.get("confidence", 0) < self.min_confidence:
            return False
        
        # Check open positions for this symbol
        symbol = analysis.get("symbol", "")
        open_predictions = await self.learning.get_open_predictions()
        symbol_positions = [p for p in open_predictions if p.get("symbol") == symbol]
        
        if len(symbol_positions) >= self.max_open_positions:
            return False
        
        # Don't take conflicting positions
        for pos in symbol_positions:
            if pos.get("prediction") != analysis.get("signal"):
                return False
        
        return True
    
    async def execute_paper_trade(self, analysis: Dict[str, Any], chat_id: int = 0) -> Optional[str]:
        """Record a paper trade (prediction) based on analysis."""
        try:
            if not await self.should_take_trade(analysis):
                return None
            
            # Record the prediction
            prediction_id = await self.learning.record_prediction(
                chat_id=chat_id,
                symbol=analysis["symbol"],
                prediction=analysis["signal"],
                confidence=analysis["confidence"],
                reasoning="; ".join(analysis.get("reasons", [])),
                entry_price=analysis["price"],
                target_price=analysis.get("target"),
                stop_loss=analysis.get("stop_loss"),
                timeframe="1h",
                market_context={
                    "score": analysis.get("score"),
                    "signals_used": analysis.get("signals_used", []),
                    "indicators": analysis.get("indicators", {})
                }
            )
            
            logger.info(f"📊 PAPER TRADE: {analysis['signal']} {analysis['symbol']} @ ${analysis['price']:,.2f} | Conf: {analysis['confidence']}%")
            
            return prediction_id
            
        except Exception as e:
            logger.error(f"Paper trade error: {e}")
            return None
    
    async def evaluate_predictions(self) -> List[Dict[str, Any]]:
        """
        Evaluate open predictions against current prices.
        Close predictions that hit target or stop loss.
        """
        results = []
        
        try:
            open_predictions = await self.learning.get_open_predictions()
            
            for pred in open_predictions:
                symbol = pred.get("symbol", "")
                if not symbol:
                    continue
                
                # Get current price
                ticker = await market_intel.get_ticker(symbol)
                if "error" in ticker or not ticker.get("price"):
                    continue
                
                current_price = ticker["price"]
                entry_price = pred.get("entry_price", 0)
                target = pred.get("target_price")
                stop = pred.get("stop_loss")
                direction = pred.get("prediction")
                prediction_id = pred.get("prediction_id")
                
                # Check if target or stop hit
                status = None
                lesson = None
                
                if direction == "LONG":
                    if target and current_price >= target:
                        status = "WIN"
                        pnl = ((current_price - entry_price) / entry_price) * 100
                        lesson = f"Target hit. Signals used: {pred.get('market_context', {}).get('signals_used', [])}"
                    elif stop and current_price <= stop:
                        status = "LOSS"
                        pnl = ((current_price - entry_price) / entry_price) * 100
                        lesson = f"Stop hit. Review: {pred.get('reasoning', '')[:100]}"
                        
                elif direction == "SHORT":
                    if target and current_price <= target:
                        status = "WIN"
                        pnl = ((entry_price - current_price) / entry_price) * 100
                        lesson = f"Target hit. Signals used: {pred.get('market_context', {}).get('signals_used', [])}"
                    elif stop and current_price >= stop:
                        status = "LOSS"
                        pnl = ((entry_price - current_price) / entry_price) * 100
                        lesson = f"Stop hit. Review: {pred.get('reasoning', '')[:100]}"
                
                # Check for time-based expiry (24 hours)
                created = pred.get("created_at")
                if created and not status:
                    if isinstance(created, str):
                        created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    age = datetime.now(timezone.utc) - created
                    if age > timedelta(hours=24):
                        pnl = 0
                        if direction == "LONG":
                            pnl = ((current_price - entry_price) / entry_price) * 100
                        elif direction == "SHORT":
                            pnl = ((entry_price - current_price) / entry_price) * 100
                        
                        status = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "EXPIRED"
                        lesson = f"Expired after 24h with {pnl:+.2f}% PnL"
                
                if status and prediction_id:
                    result = await self.learning.close_prediction(
                        prediction_id=prediction_id,
                        outcome_price=current_price,
                        status=status,
                        lessons_learned=lesson
                    )
                    
                    # Update strategy weights based on outcome
                    await self._update_strategy_weights(pred, status)
                    
                    results.append(result)
                    logger.info(f"📈 CLOSED: {prediction_id} | {status} | PnL: {result.get('pnl_pct', 0):+.2f}%")
            
            return results
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return results
    
    async def _update_strategy_weights(self, prediction: Dict, status: str):
        """
        Adjust strategy weights based on trade outcomes.
        This is the learning feedback loop.
        """
        signals_used = prediction.get("market_context", {}).get("signals_used", [])
        
        # Adjust weights: increase for wins, decrease for losses
        adjustment = 0.05 if status == "WIN" else -0.03 if status == "LOSS" else 0
        
        for signal in signals_used:
            if signal in self.strategy_weights:
                # Track performance
                if signal not in self.strategy_performance:
                    self.strategy_performance[signal] = {"wins": 0, "losses": 0, "total": 0}
                
                self.strategy_performance[signal]["total"] += 1
                if status == "WIN":
                    self.strategy_performance[signal]["wins"] += 1
                elif status == "LOSS":
                    self.strategy_performance[signal]["losses"] += 1
                
                # Adjust weight (keep within bounds)
                new_weight = self.strategy_weights[signal] + adjustment
                self.strategy_weights[signal] = max(0.3, min(2.0, new_weight))
        
        # Persist weights to database
        await self.db.strategy_weights.update_one(
            {"type": "current"},
            {"$set": {
                "weights": self.strategy_weights,
                "performance": self.strategy_performance,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
    
    async def load_strategy_weights(self):
        """Load strategy weights from database."""
        try:
            doc = await self.db.strategy_weights.find_one({"type": "current"})
            if doc:
                self.strategy_weights.update(doc.get("weights", {}))
                self.strategy_performance = doc.get("performance", {})
                logger.info("Loaded strategy weights from database")
        except Exception as e:
            logger.error(f"Error loading weights: {e}")
    
    async def get_strategy_report(self) -> str:
        """Generate a report on strategy performance."""
        report = "🧠 AEON STRATEGY PERFORMANCE\n\n"
        
        for signal, perf in self.strategy_performance.items():
            total = perf.get("total", 0)
            wins = perf.get("wins", 0)
            win_rate = (wins / total * 100) if total > 0 else 0
            weight = self.strategy_weights.get(signal, 1.0)
            
            emoji = "🟢" if win_rate >= 55 else "🟡" if win_rate >= 45 else "🔴"
            report += f"{emoji} {signal}: {win_rate:.0f}% ({wins}/{total}) | Weight: {weight:.2f}\n"
        
        return report
    
    async def scan_all_markets(self) -> List[Dict[str, Any]]:
        """Scan all monitored symbols for opportunities."""
        opportunities = []
        
        for symbol in self.symbols:
            analysis = await self.analyze_opportunity(symbol)
            if analysis.get("signal") != "NONE" and analysis.get("confidence", 0) >= 50:
                opportunities.append(analysis)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return opportunities
    
    async def get_trading_summary(self) -> Dict[str, Any]:
        """Get comprehensive trading summary."""
        stats = await self.learning.get_prediction_stats()
        open_preds = await self.learning.get_open_predictions()
        
        # Calculate current PnL on open positions
        open_pnl = 0
        for pred in open_preds:
            symbol = pred.get("symbol", "")
            if symbol:
                ticker = await market_intel.get_ticker(symbol)
                if ticker.get("price"):
                    entry = pred.get("entry_price", 0)
                    current = ticker["price"]
                    direction = pred.get("prediction")
                    
                    if direction == "LONG":
                        open_pnl += ((current - entry) / entry) * 100
                    elif direction == "SHORT":
                        open_pnl += ((entry - current) / entry) * 100
        
        return {
            "closed_stats": stats,
            "open_positions": len(open_preds),
            "open_pnl_pct": round(open_pnl, 2),
            "total_pnl_pct": round(stats.get("total_pnl_pct", 0) + open_pnl, 2),
            "strategy_weights": self.strategy_weights,
            "active": self.active
        }


# Global instance (initialized in server.py)
autonomous_trader = None


def init_autonomous_trader(db: AsyncIOMotorDatabase, learning: AeonLearningSystem):
    """Initialize the global autonomous trader instance."""
    global autonomous_trader
    autonomous_trader = AutonomousTrader(db, learning)
    return autonomous_trader
