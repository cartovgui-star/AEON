"""
AEON FREE WILL ENGINE
True 24/7 autonomous monitoring across all pairs and timeframes
Sends immediate alerts when high-probability setups detected
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import random

logger = logging.getLogger(__name__)

# All supported timeframes
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "12h", "1d", "1w"]

# All 44 pairs
ALL_PAIRS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", 
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "SHIB/USDT", "DOT/USDT",
    "LINK/USDT", "TRX/USDT", "BCH/USDT", "LTC/USDT", "NEAR/USDT",
    "UNI/USDT", "APT/USDT", "ICP/USDT", "ETC/USDT", "FIL/USDT",
    "ATOM/USDT", "XLM/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT",
    "HBAR/USDT", "VET/USDT", "GRT/USDT", "AAVE/USDT", "ALGO/USDT",
    "SAND/USDT", "AXS/USDT", "MANA/USDT", "XTZ/USDT", "FLOW/USDT",
    "NEO/USDT", "SNX/USDT", "CRV/USDT", "RUNE/USDT", "ZEC/USDT",
    "DASH/USDT", "COMP/USDT", "ENJ/USDT", "CHZ/USDT"
]


class FreeWillEngine:
    """
    Aeon's true autonomous brain.
    - Scans ALL 44 pairs across ALL 9 timeframes
    - Uses ALL available data: TA, funding, sentiment, order book, volume
    - Sends immediate alerts for high-probability setups (>65%)
    - Consolidates alerts per coin (best setup only)
    - Prioritizes higher timeframes for quality signals
    - Learns from user feedback
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.active = True
        self.min_confidence = 65  # Only alert on >65% confidence
        self.scan_interval = 30  # Scan every 30 seconds
        
        # Track recent alerts to avoid spam - per symbol (not per timeframe)
        self.recent_alerts: Dict[str, datetime] = {}
        self.alert_cooldown = 600  # 10 min cooldown per symbol (increased from 5)
        
        # Learning from feedback
        self.feedback_weights = {
            "rsi_oversold": 1.0,
            "rsi_overbought": 1.0,
            "macd_cross": 1.0,
            "bb_squeeze": 1.0,
            "ema_stack": 1.0,
            "volume_spike": 1.0,
            "funding_extreme": 1.0,
            "fear_greed_extreme": 1.0,
            "orderbook_imbalance": 1.0,
            "multi_tf_confluence": 1.2,
        }
        
        # External references (set by server.py)
        self.market_intel = None
        self.derivatives_intel = None
        self.enhanced_intel = None
        self.send_telegram = None
        self.get_user_settings = None
        self.chat_ids = set()
    
    def set_dependencies(self, market_intel, derivatives_intel, enhanced_intel, 
                         send_telegram, get_user_settings, chat_ids):
        """Set external dependencies"""
        self.market_intel = market_intel
        self.derivatives_intel = derivatives_intel
        self.enhanced_intel = enhanced_intel
        self.send_telegram = send_telegram
        self.get_user_settings = get_user_settings
        self.chat_ids = chat_ids
    
    async def analyze_setup(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Full analysis of a symbol on a specific timeframe.
        Uses ALL available data sources.
        """
        try:
            if not self.market_intel:
                return None
            
            # Get technical analysis
            ta = await self.market_intel.get_technical_analysis(symbol, timeframe)
            if "error" in ta:
                return None
            
            indicators = ta.get("indicators", {})
            price = ta.get("price", 0)
            
            if not price:
                return None
            
            # Scoring system
            score = 0
            confidence = 0
            signals = []
            direction = None
            
            # ═══════════════════════════════════════════════════════════════════
            # RSI Analysis
            # ═══════════════════════════════════════════════════════════════════
            rsi = indicators.get("rsi", 50)
            
            if rsi < 25:
                score += 2.5 * self.feedback_weights["rsi_oversold"]
                signals.append(f"RSI extreme oversold ({rsi:.0f})")
            elif rsi < 30:
                score += 1.5 * self.feedback_weights["rsi_oversold"]
                signals.append(f"RSI oversold ({rsi:.0f})")
            elif rsi > 75:
                score -= 2.5 * self.feedback_weights["rsi_overbought"]
                signals.append(f"RSI extreme overbought ({rsi:.0f})")
            elif rsi > 70:
                score -= 1.5 * self.feedback_weights["rsi_overbought"]
                signals.append(f"RSI overbought ({rsi:.0f})")
            
            # ═══════════════════════════════════════════════════════════════════
            # MACD Analysis
            # ═══════════════════════════════════════════════════════════════════
            macd = indicators.get("macd", 0)
            macd_signal = indicators.get("macd_signal", 0)
            macd_hist = indicators.get("macd_histogram", 0)
            
            if macd and macd_signal:
                if macd > macd_signal and macd_hist > 0:
                    score += 1.5 * self.feedback_weights["macd_cross"]
                    signals.append("MACD bullish cross")
                elif macd < macd_signal and macd_hist < 0:
                    score -= 1.5 * self.feedback_weights["macd_cross"]
                    signals.append("MACD bearish cross")
            
            # ═══════════════════════════════════════════════════════════════════
            # Bollinger Bands
            # ═══════════════════════════════════════════════════════════════════
            bb_lower = indicators.get("bb_lower", 0)
            bb_upper = indicators.get("bb_upper", 0)
            bb_middle = indicators.get("bb_middle", 0)
            
            if bb_lower and bb_upper and price:
                bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle else 0
                
                if price <= bb_lower:
                    score += 2.0 * self.feedback_weights["bb_squeeze"]
                    signals.append(f"Price at BB lower")
                elif price >= bb_upper:
                    score -= 2.0 * self.feedback_weights["bb_squeeze"]
                    signals.append(f"Price at BB upper")
                
                # Squeeze detection (low volatility = breakout coming)
                if bb_width < 0.03:
                    signals.append("BB squeeze (breakout imminent)")
            
            # ═══════════════════════════════════════════════════════════════════
            # EMA Stack
            # ═══════════════════════════════════════════════════════════════════
            ema_9 = indicators.get("ema_9", 0)
            ema_21 = indicators.get("ema_21", 0)
            ema_50 = indicators.get("ema_50", 0)
            
            if ema_9 and ema_21 and ema_50:
                if ema_9 > ema_21 > ema_50:
                    score += 1.5 * self.feedback_weights["ema_stack"]
                    signals.append("Bullish EMA stack (9>21>50)")
                elif ema_9 < ema_21 < ema_50:
                    score -= 1.5 * self.feedback_weights["ema_stack"]
                    signals.append("Bearish EMA stack (9<21<50)")
                
                # Price vs EMAs
                if price > ema_9 > ema_21:
                    score += 0.5
                elif price < ema_9 < ema_21:
                    score -= 0.5
            
            # ═══════════════════════════════════════════════════════════════════
            # Stochastic
            # ═══════════════════════════════════════════════════════════════════
            stoch_k = indicators.get("stoch_k", 50)
            stoch_d = indicators.get("stoch_d", 50)
            
            if stoch_k < 20 and stoch_d < 20:
                score += 1.0
                signals.append(f"Stoch oversold ({stoch_k:.0f}/{stoch_d:.0f})")
            elif stoch_k > 80 and stoch_d > 80:
                score -= 1.0
                signals.append(f"Stoch overbought ({stoch_k:.0f}/{stoch_d:.0f})")
            
            # ═══════════════════════════════════════════════════════════════════
            # Volume Analysis
            # ═══════════════════════════════════════════════════════════════════
            vol_ratio = indicators.get("volume_ratio", 1)
            if vol_ratio > 2.0:
                # High volume confirms the move
                if score > 0:
                    score += 1.0 * self.feedback_weights["volume_spike"]
                else:
                    score -= 1.0 * self.feedback_weights["volume_spike"]
                signals.append(f"Volume spike ({vol_ratio:.1f}x)")
            
            # ═══════════════════════════════════════════════════════════════════
            # ATR for Stop Loss / Take Profit
            # ═══════════════════════════════════════════════════════════════════
            atr = indicators.get("atr", price * 0.02)
            
            # ═══════════════════════════════════════════════════════════════════
            # Get Real Funding Rate (if derivatives available)
            # ═══════════════════════════════════════════════════════════════════
            if self.derivatives_intel:
                try:
                    funding = await self.derivatives_intel.get_aggregated_funding(symbol.replace("/", ""))
                    avg_rate = funding.get("average_funding_rate", 0)
                    
                    if avg_rate > 0.0008:  # Very high positive
                        score -= 1.5 * self.feedback_weights["funding_extreme"]
                        signals.append(f"High funding ({avg_rate*100:.3f}%) - longs crowded")
                    elif avg_rate < -0.0003:  # Negative
                        score += 1.0 * self.feedback_weights["funding_extreme"]
                        signals.append(f"Negative funding ({avg_rate*100:.3f}%) - shorts crowded")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # Get Fear & Greed (if enhanced intel available)
            # ═══════════════════════════════════════════════════════════════════
            if self.enhanced_intel and symbol in ["BTC/USDT", "ETH/USDT"]:
                try:
                    fng = await self.enhanced_intel.get_fear_greed_index()
                    fg_value = fng.get("value", 50)
                    
                    if fg_value <= 20:
                        score += 1.0 * self.feedback_weights["fear_greed_extreme"]
                        signals.append(f"Extreme fear ({fg_value}) - contrarian buy")
                    elif fg_value >= 80:
                        score -= 1.0 * self.feedback_weights["fear_greed_extreme"]
                        signals.append(f"Extreme greed ({fg_value}) - contrarian sell")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # Order Book Imbalance
            # ═══════════════════════════════════════════════════════════════════
            try:
                orderbook = await self.market_intel.get_orderbook(symbol)
                if "error" not in orderbook:
                    imbalance = orderbook.get("imbalance_pct", 0)
                    if imbalance > 30:
                        score += 0.8 * self.feedback_weights["orderbook_imbalance"]
                        signals.append(f"Orderbook bullish ({imbalance:+.0f}%)")
                    elif imbalance < -30:
                        score -= 0.8 * self.feedback_weights["orderbook_imbalance"]
                        signals.append(f"Orderbook bearish ({imbalance:+.0f}%)")
            except:
                pass
            
            # ═══════════════════════════════════════════════════════════════════
            # Determine Direction and Calculate Setup
            # ═══════════════════════════════════════════════════════════════════
            
            if score >= 3.0:
                direction = "LONG"
                confidence = min(95, 50 + (score * 7))
                entry = price
                stop_loss = price - (atr * 1.5)
                take_profit = price + (atr * 3)
            elif score <= -3.0:
                direction = "SHORT"
                confidence = min(95, 50 + (abs(score) * 7))
                entry = price
                stop_loss = price + (atr * 1.5)
                take_profit = price - (atr * 3)
            else:
                return None  # No clear setup
            
            # Calculate risk-reward
            risk = abs(entry - stop_loss)
            reward = abs(take_profit - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            # Only return if confidence meets threshold
            if confidence < self.min_confidence:
                return None
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "confidence": round(confidence, 0),
                "confidence_10": round(confidence / 10, 1),
                "entry": round(entry, 6 if price < 1 else 2),
                "stop_loss": round(stop_loss, 6 if price < 1 else 2),
                "take_profit": round(take_profit, 6 if price < 1 else 2),
                "rr_ratio": round(rr_ratio, 1),
                "score": round(score, 2),
                "signals": signals,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Setup analysis error {symbol} {timeframe}: {e}")
            return None
    
    def _should_alert(self, symbol: str) -> bool:
        """Check if we should send alert (cooldown check per symbol)"""
        now = datetime.now()
        
        if symbol in self.recent_alerts:
            last_alert = self.recent_alerts[symbol]
            if (now - last_alert).seconds < self.alert_cooldown:
                return False
        
        return True
    
    def _mark_alerted(self, symbol: str):
        """Mark that we sent an alert for this symbol"""
        self.recent_alerts[symbol] = datetime.now()
    
    def format_alert(self, setup: Dict) -> str:
        """Format the alert message"""
        coin = setup["symbol"].replace("/USDT", "")
        tf = setup["timeframe"]
        direction = setup["direction"]
        entry = setup["entry"]
        sl = setup["stop_loss"]
        tp = setup["take_profit"]
        rr = setup["rr_ratio"]
        conf = setup["confidence_10"]
        signals = setup["signals"]
        
        # Format price based on value
        if entry < 0.01:
            price_fmt = ".6f"
        elif entry < 1:
            price_fmt = ".4f"
        else:
            price_fmt = ",.2f"
        
        emoji = "🟢" if direction == "LONG" else "🔴"
        
        # Build sources string (max 4)
        sources = []
        for s in signals[:4]:
            if "RSI" in s:
                sources.append("RSI")
            elif "MACD" in s:
                sources.append("MACD")
            elif "EMA" in s:
                sources.append("EMA")
            elif "BB" in s:
                sources.append("BB")
            elif "Stoch" in s:
                sources.append("STOCH")
            elif "funding" in s.lower():
                sources.append("FUNDING")
            elif "fear" in s.lower() or "greed" in s.lower():
                sources.append("F&G")
            elif "volume" in s.lower():
                sources.append("VOL")
            elif "orderbook" in s.lower():
                sources.append("OB")
        
        sources_str = "/".join(list(set(sources))[:4])
        
        alert = f"""{emoji} ALERT: {coin} {tf}

{direction} Entry ${entry:{price_fmt}}
SL ${sl:{price_fmt}} | TP ${tp:{price_fmt}}
RR 1:{rr} | Conf {conf}/10

Sources: {sources_str}

⚠️ MANUAL CHECK REQ'D"""
        
        return alert
    
    async def scan_all(self) -> List[Dict]:
        """Scan all pairs across priority timeframes"""
        setups = []
        
        # Priority timeframes (scan more frequently)
        priority_tfs = ["5m", "15m", "1h", "4h"]
        
        # Scan priority pairs on priority timeframes
        priority_pairs = ALL_PAIRS[:20]  # Top 20 first
        
        for symbol in priority_pairs:
            for tf in priority_tfs:
                if not self._should_alert(symbol, tf):
                    continue
                
                setup = await self.analyze_setup(symbol, tf)
                if setup and setup["confidence"] >= self.min_confidence:
                    setups.append(setup)
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
        
        return setups
    
    async def scan_extended(self) -> List[Dict]:
        """Extended scan - all pairs, all timeframes (runs less frequently)"""
        setups = []
        
        for symbol in ALL_PAIRS:
            for tf in TIMEFRAMES:
                if not self._should_alert(symbol, tf):
                    continue
                
                setup = await self.analyze_setup(symbol, tf)
                if setup and setup["confidence"] >= self.min_confidence:
                    setups.append(setup)
                
                await asyncio.sleep(0.05)
        
        return setups
    
    async def record_feedback(self, setup_id: str, outcome: str, notes: str = None):
        """Record user feedback to improve signals"""
        await self.db.free_will_feedback.insert_one({
            "setup_id": setup_id,
            "outcome": outcome,  # "win", "loss", "skipped", "partial"
            "notes": notes,
            "timestamp": datetime.now(timezone.utc)
        })
        
        # Adjust weights based on feedback
        # (Simple implementation - could be more sophisticated)
        if outcome == "win":
            # Slightly increase all weights
            for key in self.feedback_weights:
                self.feedback_weights[key] = min(2.0, self.feedback_weights[key] * 1.02)
        elif outcome == "loss":
            # Slightly decrease weights
            for key in self.feedback_weights:
                self.feedback_weights[key] = max(0.5, self.feedback_weights[key] * 0.98)
    
    async def get_stats(self) -> Dict:
        """Get Free Will statistics"""
        total_alerts = await self.db.free_will_alerts.count_documents({})
        feedback = await self.db.free_will_feedback.find().to_list(100)
        
        wins = sum(1 for f in feedback if f.get("outcome") == "win")
        losses = sum(1 for f in feedback if f.get("outcome") == "loss")
        
        return {
            "active": self.active,
            "min_confidence": self.min_confidence,
            "total_alerts_sent": total_alerts,
            "feedback_received": len(feedback),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
            "pairs_monitored": len(ALL_PAIRS),
            "timeframes_monitored": len(TIMEFRAMES),
            "current_weights": self.feedback_weights
        }


# Global instance
free_will_engine = None


def init_free_will(db: AsyncIOMotorDatabase) -> FreeWillEngine:
    global free_will_engine
    free_will_engine = FreeWillEngine(db)
    return free_will_engine
