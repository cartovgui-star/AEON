"""
AEON LEARNING SYSTEM
Track predictions, learn from outcomes, improve over time
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class AeonLearningSystem:
    """Track Aeon's predictions and learn from outcomes"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def record_prediction(
        self,
        chat_id: int,
        symbol: str,
        prediction: str,  # "LONG", "SHORT", "NEUTRAL"
        confidence: float,  # 0-100
        reasoning: str,
        entry_price: float,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        timeframe: str = "1h",
        market_context: Dict[str, Any] = None
    ) -> str:
        """Record a new prediction"""
        prediction_id = f"{chat_id}-{symbol}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        doc = {
            "prediction_id": prediction_id,
            "chat_id": chat_id,
            "symbol": symbol,
            "prediction": prediction,
            "confidence": confidence,
            "reasoning": reasoning,
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "timeframe": timeframe,
            "market_context": market_context or {},
            "status": "OPEN",  # OPEN, WIN, LOSS, EXPIRED
            "outcome_price": None,
            "outcome_pnl_pct": None,
            "created_at": datetime.now(timezone.utc),
            "closed_at": None,
            "lessons_learned": None
        }
        
        await self.db.predictions.insert_one(doc)
        return prediction_id
    
    async def close_prediction(
        self,
        prediction_id: str,
        outcome_price: float,
        status: str,  # WIN, LOSS, EXPIRED
        lessons_learned: str = None
    ) -> Dict[str, Any]:
        """Close a prediction with outcome"""
        prediction = await self.db.predictions.find_one({"prediction_id": prediction_id})
        if not prediction:
            return {"error": "Prediction not found"}
        
        entry_price = prediction["entry_price"]
        direction = prediction["prediction"]
        
        # Calculate PnL
        if direction == "LONG":
            pnl_pct = ((outcome_price - entry_price) / entry_price) * 100
        elif direction == "SHORT":
            pnl_pct = ((entry_price - outcome_price) / entry_price) * 100
        else:
            pnl_pct = 0
        
        await self.db.predictions.update_one(
            {"prediction_id": prediction_id},
            {"$set": {
                "status": status,
                "outcome_price": outcome_price,
                "outcome_pnl_pct": round(pnl_pct, 2),
                "closed_at": datetime.now(timezone.utc),
                "lessons_learned": lessons_learned
            }}
        )
        
        return {
            "prediction_id": prediction_id,
            "status": status,
            "pnl_pct": round(pnl_pct, 2),
            "entry": entry_price,
            "exit": outcome_price
        }
    
    async def get_open_predictions(self, chat_id: int = None) -> List[Dict]:
        """Get all open predictions"""
        query = {"status": "OPEN"}
        if chat_id:
            query["chat_id"] = chat_id
        
        predictions = await self.db.predictions.find(query, {"_id": 0}).to_list(100)
        return predictions
    
    async def get_prediction_stats(self, chat_id: int = None) -> Dict[str, Any]:
        """Get prediction statistics"""
        query = {"status": {"$in": ["WIN", "LOSS"]}}
        if chat_id:
            query["chat_id"] = chat_id
        
        predictions = await self.db.predictions.find(query).to_list(1000)
        
        if not predictions:
            return {
                "total_predictions": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "avg_win_pct": 0,
                "avg_loss_pct": 0,
                "total_pnl_pct": 0,
                "best_trade": None,
                "worst_trade": None
            }
        
        wins = [p for p in predictions if p["status"] == "WIN"]
        losses = [p for p in predictions if p["status"] == "LOSS"]
        
        total = len(predictions)
        win_count = len(wins)
        loss_count = len(losses)
        
        avg_win = sum(p["outcome_pnl_pct"] for p in wins) / win_count if wins else 0
        avg_loss = sum(p["outcome_pnl_pct"] for p in losses) / loss_count if losses else 0
        total_pnl = sum(p["outcome_pnl_pct"] for p in predictions)
        
        best = max(predictions, key=lambda x: x["outcome_pnl_pct"]) if predictions else None
        worst = min(predictions, key=lambda x: x["outcome_pnl_pct"]) if predictions else None
        
        return {
            "total_predictions": total,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round((win_count / total) * 100, 1) if total > 0 else 0,
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "total_pnl_pct": round(total_pnl, 2),
            "best_trade": {
                "symbol": best["symbol"],
                "pnl": best["outcome_pnl_pct"],
                "prediction": best["prediction"]
            } if best else None,
            "worst_trade": {
                "symbol": worst["symbol"],
                "pnl": worst["outcome_pnl_pct"],
                "prediction": worst["prediction"]
            } if worst else None
        }
    
    async def get_symbol_performance(self, symbol: str) -> Dict[str, Any]:
        """Get performance for a specific symbol"""
        predictions = await self.db.predictions.find({
            "symbol": symbol,
            "status": {"$in": ["WIN", "LOSS"]}
        }).to_list(100)
        
        if not predictions:
            return {"symbol": symbol, "total": 0}
        
        wins = len([p for p in predictions if p["status"] == "WIN"])
        total = len(predictions)
        
        return {
            "symbol": symbol,
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round((wins / total) * 100, 1),
            "avg_pnl": round(sum(p["outcome_pnl_pct"] for p in predictions) / total, 2)
        }
    
    async def get_lessons_learned(self, limit: int = 10) -> List[Dict]:
        """Get recent lessons learned from closed predictions"""
        predictions = await self.db.predictions.find(
            {"lessons_learned": {"$ne": None}},
            {"_id": 0, "symbol": 1, "prediction": 1, "status": 1, 
             "outcome_pnl_pct": 1, "lessons_learned": 1, "closed_at": 1}
        ).sort("closed_at", -1).limit(limit).to_list(limit)
        
        return predictions
    
    async def generate_learning_summary(self) -> str:
        """Generate a summary of what Aeon has learned"""
        stats = await self.get_prediction_stats()
        lessons = await self.get_lessons_learned(5)
        
        summary = f"""📊 AEON TRADING PERFORMANCE

Total Predictions: {stats['total_predictions']}
Win Rate: {stats['win_rate']}%
Total PnL: {stats['total_pnl_pct']:+.2f}%

Wins: {stats['wins']} | Losses: {stats['losses']}
Avg Win: +{stats['avg_win_pct']:.2f}% | Avg Loss: {stats['avg_loss_pct']:.2f}%
"""
        
        if stats['best_trade']:
            summary += f"\nBest: {stats['best_trade']['symbol']} {stats['best_trade']['prediction']} +{stats['best_trade']['pnl']:.2f}%"
        
        if stats['worst_trade']:
            summary += f"\nWorst: {stats['worst_trade']['symbol']} {stats['worst_trade']['prediction']} {stats['worst_trade']['pnl']:.2f}%"
        
        if lessons:
            summary += "\n\n📝 RECENT LESSONS:"
            for l in lessons[:3]:
                summary += f"\n• {l['lessons_learned'][:100]}"
        
        return summary


class TradingSignalGenerator:
    """Generate trading signals from market data"""
    
    def __init__(self, market_intel, learning_system: AeonLearningSystem):
        self.market = market_intel
        self.learning = learning_system
    
    async def analyze_setup(self, symbol: str) -> Dict[str, Any]:
        """Analyze a potential trading setup"""
        scan = await self.market.get_full_market_scan(symbol)
        
        if not scan.get("price"):
            return {"error": "Failed to fetch market data"}
        
        # Score the setup
        score = 0
        reasons = []
        
        # Technical signals
        for signal in scan.get("signals", []):
            indicator, condition, bias = signal
            if bias == "bullish":
                score += 1
                reasons.append(f"✅ {indicator}: {condition}")
            elif bias == "bearish":
                score -= 1
                reasons.append(f"🔴 {indicator}: {condition}")
        
        # Funding rate analysis
        funding = scan.get("funding", {})
        if funding.get("rate"):
            rate = float(funding["rate"].replace("%", ""))
            if rate > 0.05:  # High positive = longs paying, potential squeeze
                score -= 0.5
                reasons.append(f"⚠️ High funding ({funding['rate']}) - long crowded")
            elif rate < -0.05:  # Negative = shorts paying
                score += 0.5
                reasons.append(f"✅ Negative funding ({funding['rate']}) - short crowded")
        
        # Long/short positioning
        positioning = scan.get("positioning", {})
        if positioning.get("long_short_ratio"):
            ratio = positioning["long_short_ratio"]
            if ratio > 1.5:
                score -= 0.5
                reasons.append(f"⚠️ L/S ratio {ratio:.2f} - crowded long")
            elif ratio < 0.7:
                score += 0.5
                reasons.append(f"✅ L/S ratio {ratio:.2f} - crowded short")
        
        # Whale positioning
        whale = scan.get("whale_positioning", {})
        if whale.get("long_short_ratio"):
            w_ratio = whale["long_short_ratio"]
            if w_ratio > 1.3:
                score += 0.5
                reasons.append(f"🐋 Whales long ({w_ratio:.2f})")
            elif w_ratio < 0.8:
                score -= 0.5
                reasons.append(f"🐋 Whales short ({w_ratio:.2f})")
        
        # Determine direction and confidence
        if score >= 2:
            direction = "LONG"
            confidence = min(90, 50 + (score * 10))
        elif score <= -2:
            direction = "SHORT"
            confidence = min(90, 50 + (abs(score) * 10))
        else:
            direction = "NEUTRAL"
            confidence = 30 + abs(score) * 10
        
        # Calculate targets
        price = scan["price"]
        atr = scan.get("technical", {}).get("atr", price * 0.02)
        
        if direction == "LONG":
            target = price + (atr * 2)
            stop = price - (atr * 1.5)
        elif direction == "SHORT":
            target = price - (atr * 2)
            stop = price + (atr * 1.5)
        else:
            target = None
            stop = None
        
        return {
            "symbol": symbol,
            "direction": direction,
            "confidence": round(confidence, 1),
            "score": round(score, 2),
            "price": price,
            "target": round(target, 2) if target else None,
            "stop_loss": round(stop, 2) if stop else None,
            "reasons": reasons,
            "market_data": scan,
            "timestamp": scan.get("timestamp")
        }
    
    async def generate_trade_idea(self, symbol: str, chat_id: int) -> str:
        """Generate a formatted trade idea"""
        analysis = await self.analyze_setup(symbol)
        
        if "error" in analysis:
            return f"⚠️ Unable to analyze {symbol}: {analysis['error']}"
        
        direction = analysis["direction"]
        confidence = analysis["confidence"]
        price = analysis["price"]
        
        if direction == "NEUTRAL":
            emoji = "⚖️"
            action = "WAIT"
        elif direction == "LONG":
            emoji = "🟢"
            action = "LONG BIAS"
        else:
            emoji = "🔴"
            action = "SHORT BIAS"
        
        report = f"""{emoji} **{symbol} ANALYSIS**

**Direction:** {action}
**Confidence:** {confidence}%
**Price:** ${price:,.2f}
"""
        
        if analysis["target"]:
            report += f"""
**Entry:** ${price:,.2f}
**Target:** ${analysis['target']:,.2f}
**Stop:** ${analysis['stop_loss']:,.2f}
**R:R:** 1.33:1
"""
        
        report += "\n**Signals:**\n"
        for reason in analysis["reasons"][:8]:
            report += f"{reason}\n"
        
        # Add market context
        md = analysis.get("market_data", {})
        tech = md.get("technical", {})
        
        report += f"""
**Technicals:**
RSI: {tech.get('rsi', 'N/A')} | MACD: {'Bullish' if tech.get('macd_histogram', 0) > 0 else 'Bearish'}
BB: ${tech.get('bb_lower', 0):,.0f} - ${tech.get('bb_upper', 0):,.0f}

**Positioning:**
L/S Ratio: {md.get('positioning', {}).get('long_short_ratio', 'N/A')}
Funding: {md.get('funding', {}).get('rate', 'N/A')}
"""
        
        report += "\n👁️ «The market speaks through confluence. Listen.»"
        
        return report
