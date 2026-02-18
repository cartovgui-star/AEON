"""
AEON DUAL TRADING ENGINE v3
Two trading styles running simultaneously:

1. DAY TRADER (Aggressive)
   - Scalps & Swings
   - Timeframes: 15m, 1h, 4h
   - Faster entries, tighter stops
   - Min confidence: 75%
   - Quick profits, manage risk

2. LONG TERM (Smart/Cautious)  
   - Position trades
   - Timeframes: 4h, 1d, 1w
   - High conviction only
   - Min confidence: 88%
   - Larger moves, patient entries

Both run continuously - NEVER contradicting
Only the BEST setups get through
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Top pairs for scanning
TOP_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ATOM/USDT", "UNI/USDT", "LTC/USDT", "ARB/USDT", "OP/USDT",
    "INJ/USDT", "NEAR/USDT", "APT/USDT", "FIL/USDT", "TRX/USDT"
]

# Day Trader config
DAY_TRADER_CONFIG = {
    "name": "Day Trader",
    "style": "AGGRESSIVE",
    "emoji": "⚡",
    "timeframes": ["15m", "1h", "4h"],
    "min_confidence": 75,
    "min_confirmations": 3,
    "cooldown_seconds": 900,  # 15 min cooldown
    "direction_lock_seconds": 3600,  # 1 hour - faster flip allowed for day trading
    "max_daily_alerts": 20,
    "risk_reward_min": 1.5,
    "stop_loss_atr_mult": 1.5,
    "take_profit_atr_mult": 2.5
}

# Long Term config
LONG_TERM_CONFIG = {
    "name": "Long Term",
    "style": "SMART",
    "emoji": "🎯",
    "timeframes": ["4h", "1d"],
    "min_confidence": 88,
    "min_confirmations": 4,
    "cooldown_seconds": 7200,  # 2 hour cooldown
    "direction_lock_seconds": 14400,  # 4 hours - no flip-flopping
    "max_daily_alerts": 6,
    "risk_reward_min": 2.5,
    "stop_loss_atr_mult": 2.0,
    "take_profit_atr_mult": 5.0
}


class TradingStyleEngine:
    """Single trading style engine (Day Trader or Long Term)"""
    
    def __init__(self, config: Dict, db: AsyncIOMotorDatabase):
        self.config = config
        self.db = db
        self.name = config["name"]
        self.style = config["style"]
        self.emoji = config["emoji"]
        self.active = True
        
        self.min_confidence = config["min_confidence"]
        self.min_confirmations = config["min_confirmations"]
        self.timeframes = config["timeframes"]
        
        # Alert tracking
        self.recent_alerts: Dict[str, datetime] = {}
        self.alert_cooldown = config["cooldown_seconds"]
        
        # Anti-contradiction
        self.last_direction: Dict[str, tuple] = {}
        self.direction_lock_time = config["direction_lock_seconds"]
        
        # Daily limits
        self.daily_alerts = 0
        self.max_daily_alerts = config["max_daily_alerts"]
        self.last_reset = datetime.now(timezone.utc).date()
        
        # R:R config
        self.risk_reward_min = config["risk_reward_min"]
        self.sl_atr_mult = config["stop_loss_atr_mult"]
        self.tp_atr_mult = config["take_profit_atr_mult"]
        
        # External deps (set later)
        self.market_intel = None
        self.derivatives_intel = None
        self.enhanced_intel = None
        self.order_flow = None
        self.options_analyzer = None
        
        # Stats
        self.total_alerts = 0
        self.setups_analyzed = 0
        self.contradictions_blocked = 0
    
    def set_dependencies(self, **kwargs):
        self.market_intel = kwargs.get('market_intel')
        self.derivatives_intel = kwargs.get('derivatives_intel')
        self.enhanced_intel = kwargs.get('enhanced_intel')
        self.order_flow = kwargs.get('order_flow')
        self.options_analyzer = kwargs.get('options_analyzer')
    
    def _reset_daily(self):
        today = datetime.now(timezone.utc).date()
        if today > self.last_reset:
            self.daily_alerts = 0
            self.last_reset = today
            # Clean up old tracking data to prevent memory growth
            self._cleanup_old_tracking()
    
    def _cleanup_old_tracking(self):
        """Remove stale entries from tracking dictionaries"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)  # Remove entries older than 24h
        
        # Clean recent_alerts
        self.recent_alerts = {
            k: v for k, v in self.recent_alerts.items()
            if v > cutoff
        }
        
        # Clean last_direction
        self.last_direction = {
            k: v for k, v in self.last_direction.items()
            if v[1] > cutoff
        }
    
    def _can_alert(self, symbol: str, direction: str = None) -> bool:
        self._reset_daily()
        
        if self.daily_alerts >= self.max_daily_alerts:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Cooldown check
        if symbol in self.recent_alerts:
            elapsed = (now - self.recent_alerts[symbol]).total_seconds()
            if elapsed < self.alert_cooldown:
                return False
        
        # Anti-contradiction
        if direction and symbol in self.last_direction:
            last_dir, last_time = self.last_direction[symbol]
            elapsed = (now - last_time).total_seconds()
            
            if elapsed < self.direction_lock_time and last_dir != direction:
                logger.info(f"⚠️ [{self.name}] Blocked contradiction: {symbol} was {last_dir}, now {direction}")
                self.contradictions_blocked += 1
                return False
        
        return True
    
    def _mark_alerted(self, symbol: str, direction: str = None):
        now = datetime.now(timezone.utc)
        self.recent_alerts[symbol] = now
        self.daily_alerts += 1
        self.total_alerts += 1
        
        if direction:
            self.last_direction[symbol] = (direction, now)
    
    async def analyze_setup(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Analyze a setup using all data sources"""
        if not self.market_intel:
            return None
        
        self.setups_analyzed += 1
        
        try:
            # Get market scan
            scan = await self.market_intel.get_full_market_scan(symbol.replace("/", ""))
            if not scan or "error" in scan:
                return None
            
            price = scan.get("price", 0)
            if not price:
                return None
            
            # Score the setup
            signals_long = 0
            signals_short = 0
            confirmations = []
            
            # 1. Technical Analysis
            tech = scan.get("technical", {})
            rsi = tech.get("rsi", 50)
            macd_hist = tech.get("macd_histogram", 0)
            
            if rsi < 35:
                signals_long += 2
                confirmations.append("RSI oversold")
            elif rsi > 65:
                signals_short += 2
                confirmations.append("RSI overbought")
            
            if macd_hist > 0:
                signals_long += 1
                confirmations.append("MACD bullish")
            elif macd_hist < 0:
                signals_short += 1
                confirmations.append("MACD bearish")
            
            # 2. Trend (EMA)
            trend = tech.get("trend", "neutral")
            if trend == "bullish":
                signals_long += 2
                confirmations.append("Trend bullish")
            elif trend == "bearish":
                signals_short += 2
                confirmations.append("Trend bearish")
            
            # 3. Overall bias
            bias = scan.get("overall_bias", "neutral")
            if bias == "bullish":
                signals_long += 1
            elif bias == "bearish":
                signals_short += 1
            
            # 4. Derivatives (funding, L/S)
            deriv = scan.get("derivatives", {})
            funding = deriv.get("funding_rate", 0)
            ls_ratio = deriv.get("long_short_ratio", 1.0)
            
            # Extreme funding = reversal signal
            if funding and funding < -0.01:
                signals_long += 2
                confirmations.append("Funding negative (squeeze)")
            elif funding and funding > 0.03:
                signals_short += 2
                confirmations.append("Funding extreme (dump risk)")
            
            # Crowded trade = contrarian
            if ls_ratio and ls_ratio > 2.0:
                signals_short += 1
                confirmations.append("Longs crowded")
            elif ls_ratio and ls_ratio < 0.5:
                signals_long += 1
                confirmations.append("Shorts crowded")
            
            # 5. Fear & Greed
            fg = scan.get("fear_greed", {})
            fg_value = fg.get("value", 50)
            if fg_value < 25:
                signals_long += 1
                confirmations.append("Extreme fear")
            elif fg_value > 75:
                signals_short += 1
                confirmations.append("Extreme greed")
            
            # 6. Volume/CVD if available
            if self.order_flow:
                try:
                    cvd = await self.order_flow.get_cvd(symbol)
                    if cvd.get("trend") == "bullish":
                        signals_long += 1
                        confirmations.append("CVD bullish")
                    elif cvd.get("trend") == "bearish":
                        signals_short += 1
                        confirmations.append("CVD bearish")
                except:
                    pass
            
            # Calculate direction and confidence
            total_signals = signals_long + signals_short
            if total_signals < 3:
                return None
            
            if signals_long > signals_short:
                direction = "LONG"
                confidence = min(95, 50 + (signals_long - signals_short) * 8 + len(confirmations) * 3)
            elif signals_short > signals_long:
                direction = "SHORT"
                confidence = min(95, 50 + (signals_short - signals_long) * 8 + len(confirmations) * 3)
            else:
                return None
            
            # HARD FILTER: Market structure must not contradict direction
            # LONG requires non-bearish structure (HH/HL or neutral OK, LH/LL = blocked)
            # SHORT requires non-bullish structure (LH/LL or neutral OK, HH/HL = blocked)
            structure = scan.get("market_structure", {})
            structure_bias = structure.get("bias", "neutral")
            
            if direction == "LONG" and structure_bias == "bearish":
                logger.info(f"[{self.name}] BLOCKED {symbol} LONG - bearish structure (LH/LL)")
                return None
            if direction == "SHORT" and structure_bias == "bullish":
                logger.info(f"[{self.name}] BLOCKED {symbol} SHORT - bullish structure (HH/HL)")
                return None
            
            # Boost confidence when structure aligns with direction
            if direction == "LONG" and structure_bias == "bullish":
                confidence = min(95, confidence + 5)
                confirmations.append("Structure HH/HL")
            elif direction == "SHORT" and structure_bias == "bearish":
                confidence = min(95, confidence + 5)
                confirmations.append("Structure LH/LL")
            
            # Check minimum requirements
            if confidence < self.min_confidence:
                return None
            
            if len(confirmations) < self.min_confirmations:
                return None
            
            # Calculate entry/SL/TP
            atr = tech.get("atr", price * 0.02)
            
            if direction == "LONG":
                entry = price
                stop_loss = price - (atr * self.sl_atr_mult)
                take_profit = price + (atr * self.tp_atr_mult)
            else:
                entry = price
                stop_loss = price + (atr * self.sl_atr_mult)
                take_profit = price - (atr * self.tp_atr_mult)
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "confidence": confidence,
                "confirmations": confirmations,
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_reward": self.tp_atr_mult / self.sl_atr_mult,
                "style": self.name,
                "style_emoji": self.emoji,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[{self.name}] Analysis error for {symbol}: {e}")
            return None
    
    async def scan_all(self) -> List[Dict]:
        """Scan all pairs on configured timeframes"""
        best_setups = {}
        
        for symbol in TOP_PAIRS[:15]:
            for tf in self.timeframes:
                setup = await self.analyze_setup(symbol, tf)
                
                if setup:
                    direction = setup.get("direction")
                    
                    if not self._can_alert(symbol, direction):
                        continue
                    
                    # Keep best per symbol
                    if symbol not in best_setups or setup["confidence"] > best_setups[symbol]["confidence"]:
                        best_setups[symbol] = setup
                
                await asyncio.sleep(0.15)
        
        # Return top 3 by confidence
        setups = list(best_setups.values())
        setups.sort(key=lambda x: x["confidence"], reverse=True)
        return setups[:3]
    
    async def validate_and_format_alert(self, setup: Dict) -> tuple:
        """
        Validate setup price is still valid and format alert
        Returns (message, is_valid)
        """
        direction = setup["direction"]
        symbol = setup["symbol"]
        entry = setup["entry"]
        
        # Fetch fresh price to validate
        if self.market_intel:
            try:
                scan = await self.market_intel.get_full_market_scan(symbol.replace("/", ""))
                current_price = scan.get("price", 0)
                
                if current_price:
                    # Check if price has moved too far from entry (invalidates setup)
                    price_diff_pct = abs((current_price - entry) / entry * 100)
                    
                    if price_diff_pct > 2.0:  # Price moved more than 2%
                        logger.info(f"[{self.name}] Setup invalidated: {symbol} price moved {price_diff_pct:.1f}% from entry")
                        return None, False
                    
                    # Re-validate market structure with fresh data
                    fresh_structure = scan.get("market_structure", {})
                    fresh_bias = fresh_structure.get("bias", "neutral")
                    if direction == "LONG" and fresh_bias == "bearish":
                        logger.info(f"[{self.name}] BLOCKED at validation: {symbol} LONG vs bearish structure")
                        return None, False
                    if direction == "SHORT" and fresh_bias == "bullish":
                        logger.info(f"[{self.name}] BLOCKED at validation: {symbol} SHORT vs bullish structure")
                        return None, False
                    
                    # Update entry to current price for more accurate alert
                    setup["entry"] = current_price
                    setup["structure"] = fresh_structure.get("pattern", "")
                    
                    # Recalculate SL/TP based on fresh price
                    atr = scan.get("technical", {}).get("atr", current_price * 0.02)
                    if direction == "LONG":
                        setup["stop_loss"] = current_price - (atr * self.sl_atr_mult)
                        setup["take_profit"] = current_price + (atr * self.tp_atr_mult)
                    else:
                        setup["stop_loss"] = current_price + (atr * self.sl_atr_mult)
                        setup["take_profit"] = current_price - (atr * self.tp_atr_mult)
            except Exception as e:
                logger.error(f"[{self.name}] Price validation error: {e}")
        
        msg = self.format_alert(setup)
        return msg, True
    
    def format_alert(self, setup: Dict) -> str:
        """Format alert message with WHY reasoning"""
        direction = setup["direction"]
        symbol = setup["symbol"].replace("/USDT", "")
        conf = setup["confidence"]
        dir_emoji = "🟢" if direction == "LONG" else "🔴"
        style_badge = "⚡ DAY" if self.style == "AGGRESSIVE" else "🎯 LT"

        confirms = setup.get('confirmations', [])[:4]
        confirm_str = " | ".join(confirms) if confirms else "Multiple signals"
        
        # Generate WHY reasoning
        style_name = "Day Trader" if self.style == "AGGRESSIVE" else "Long Term"
        why_reason = f"WHY {direction}: {style_name} setup with {conf}% confidence and {len(setup.get('confirmations', []))} confirmations. R:R {setup['risk_reward']:.1f} on {setup['timeframe']}."

        msg = (
            f"{dir_emoji} {style_badge} {direction} {symbol} {setup['timeframe']} ({conf}%)\n"
            f"Entry ${setup['entry']:,.2f} | SL ${setup['stop_loss']:,.2f} | TP ${setup['take_profit']:,.2f} | RR {setup['risk_reward']:.1f}\n"
            f"{confirm_str}\n"
            f"{why_reason}"
        )
        return msg
    
    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "style": self.style,
            "active": self.active,
            "min_confidence": self.min_confidence,
            "min_confirmations": self.min_confirmations,
            "timeframes": self.timeframes,
            "cooldown_mins": self.alert_cooldown // 60,
            "direction_lock_hours": self.direction_lock_time // 3600,
            "daily_alerts": self.daily_alerts,
            "max_daily_alerts": self.max_daily_alerts,
            "total_alerts": self.total_alerts,
            "setups_analyzed": self.setups_analyzed,
            "contradictions_blocked": self.contradictions_blocked,
            "recent_directions": {k: v[0] for k, v in self.last_direction.items()}
        }


class DualTradingEngine:
    """
    Dual trading engine running Day Trader + Long Term simultaneously
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.day_trader = TradingStyleEngine(DAY_TRADER_CONFIG, db)
        self.long_term = TradingStyleEngine(LONG_TERM_CONFIG, db)
        
        self.active = True
        self.total_alerts_sent = 0
    
    def set_dependencies(self, **kwargs):
        """Set dependencies for both engines"""
        self.day_trader.set_dependencies(**kwargs)
        self.long_term.set_dependencies(**kwargs)
    
    async def scan_all_styles(self) -> Dict[str, List[Dict]]:
        """Run both trading styles simultaneously"""
        day_setups = []
        long_setups = []
        
        # Run both scans in parallel
        if self.day_trader.active:
            day_setups = await self.day_trader.scan_all()
        
        if self.long_term.active:
            long_setups = await self.long_term.scan_all()
        
        return {
            "day_trader": day_setups,
            "long_term": long_setups
        }
    
    def mark_alerted(self, style: str, symbol: str, direction: str):
        """Mark symbol as alerted for a specific style"""
        if style == "Day Trader":
            self.day_trader._mark_alerted(symbol, direction)
        else:
            self.long_term._mark_alerted(symbol, direction)
        self.total_alerts_sent += 1
    
    async def validate_and_format_alert(self, setup: Dict) -> tuple:
        """Validate and format alert with fresh price data"""
        if setup.get("style") == "Day Trader":
            return await self.day_trader.validate_and_format_alert(setup)
        else:
            return await self.long_term.validate_and_format_alert(setup)
    
    def format_alert(self, setup: Dict) -> str:
        """Format alert based on style (legacy - use validate_and_format_alert)"""
        if setup.get("style") == "Day Trader":
            return self.day_trader.format_alert(setup)
        else:
            return self.long_term.format_alert(setup)
    
    def get_stats(self) -> Dict:
        return {
            "active": self.active,
            "total_alerts_sent": self.total_alerts_sent,
            "day_trader": self.day_trader.get_stats(),
            "long_term": self.long_term.get_stats()
        }


# Global instance
dual_engine: DualTradingEngine = None

def init_dual_engine(db: AsyncIOMotorDatabase) -> DualTradingEngine:
    global dual_engine
    dual_engine = DualTradingEngine(db)
    return dual_engine
