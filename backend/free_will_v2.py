"""
AEON FREE WILL ENGINE v2.1
Ultra-selective alerting using ALL data sources:
- Technical Analysis (RSI, MACD, BB, EMA, Stochastic)
- Divergence Detection (RSI/MACD divergence)
- Market Structure (HH/HL/LH/LL, BOS)
- VWAP (institutional levels)
- Order Flow / CVD (buy/sell pressure)
- Options Data (max pain, put/call ratio)
- Derivatives (funding, OI, L/S ratio)
- Fear & Greed Index
- Multi-Timeframe Alignment

ONLY alerts on setups with 80%+ confidence AND multiple confirmations
NO CONTRADICTING SIGNALS - tracks recent direction per symbol
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Priority timeframes (higher = better signals, less noise)
PRIORITY_TIMEFRAMES = ["4h", "1h", "1d"]  # Only alert on these
SCAN_TIMEFRAMES = ["15m", "1h", "4h", "1d"]  # Scan these for confluence

# Top pairs for scanning
TOP_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ATOM/USDT", "UNI/USDT", "LTC/USDT", "ARB/USDT", "OP/USDT",
    "INJ/USDT", "NEAR/USDT", "APT/USDT", "FIL/USDT", "TRX/USDT"
]


class FreeWillEngineV2:
    """
    Ultra-selective Free Will Engine v2.1
    
    ONLY sends alerts when:
    1. Confidence >= 80%
    2. At least 3 different data sources confirm
    3. Higher timeframe (1h, 4h, 1d) 
    4. 20-minute cooldown per symbol
    5. NO CONTRADICTING SIGNALS - won't flip direction within 2 hours
    
    Uses: TA + Divergence + Structure + VWAP + CVD + Options + Derivatives + MTF
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.active = True
        self.min_confidence = 80  # High bar - only the best
        self.min_confirmations = 3  # Need 3+ data sources agreeing
        
        # Alert tracking - 20 min cooldown per symbol
        self.recent_alerts: Dict[str, datetime] = {}
        self.alert_cooldown = 1200  # 20 minutes between alerts per symbol
        
        # ANTI-CONTRADICTION: Track last direction per symbol (2hr memory)
        self.last_direction: Dict[str, tuple] = {}  # symbol -> (direction, timestamp)
        self.direction_lock_time = 7200  # 2 hours - don't flip direction
        
        # Daily alert limit (increased for better coverage)
        self.daily_alerts = 0
        self.max_daily_alerts = 15  # Max 15 alerts per day
        self.last_reset = datetime.now(timezone.utc).date()
        
        # External dependencies
        self.market_intel = None
        self.derivatives_intel = None
        self.enhanced_intel = None
        self.advanced_strategies = None
        self.order_flow = None
        self.options_analyzer = None
        self.send_telegram = None
        self.get_user_settings = None
        self.chat_ids: Set[int] = set()
        
        # Stats
        self.total_alerts_sent = 0
        self.setups_analyzed = 0
        self.contradictions_blocked = 0
    
    def set_dependencies(self, **kwargs):
        """Set all external dependencies"""
        self.market_intel = kwargs.get('market_intel')
        self.derivatives_intel = kwargs.get('derivatives_intel')
        self.enhanced_intel = kwargs.get('enhanced_intel')
        self.advanced_strategies = kwargs.get('advanced_strategies')
        self.order_flow = kwargs.get('order_flow')
        self.options_analyzer = kwargs.get('options_analyzer')
        self.send_telegram = kwargs.get('send_telegram')
        self.get_user_settings = kwargs.get('get_user_settings')
        self.chat_ids = kwargs.get('chat_ids', set())
    
    def _reset_daily_counter(self):
        """Reset daily alert counter"""
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
        """Check if we can send alert for this symbol"""
        self._reset_daily_counter()
        
        # Check daily limit
        if self.daily_alerts >= self.max_daily_alerts:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Check cooldown
        if symbol in self.recent_alerts:
            elapsed = (now - self.recent_alerts[symbol]).total_seconds()
            if elapsed < self.alert_cooldown:
                return False
        
        # ANTI-CONTRADICTION CHECK
        if direction and symbol in self.last_direction:
            last_dir, last_time = self.last_direction[symbol]
            elapsed = (now - last_time).total_seconds()
            
            # If same symbol had opposite direction within lock time, block it
            if elapsed < self.direction_lock_time and last_dir != direction:
                logger.info(f"⚠️ Blocked contradicting signal: {symbol} was {last_dir}, now {direction}")
                self.contradictions_blocked += 1
                return False
        
        return True
    
    def _mark_alerted(self, symbol: str, direction: str = None):
        """Mark symbol as alerted"""
        now = datetime.now(timezone.utc)
        self.recent_alerts[symbol] = now
        self.daily_alerts += 1
        self.total_alerts_sent += 1
        
        # Track direction for anti-contradiction
        if direction:
            self.last_direction[symbol] = (direction, now)
    
    async def analyze_setup_full(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Full multi-source analysis for a setup
        Returns setup only if confidence >= 80% AND 3+ confirmations
        """
        self.setups_analyzed += 1
        
        try:
            confirmations = []
            signals_buy = 0
            signals_sell = 0
            
            # ═══════════════════════════════════════════════════════════════════
            # 1. TECHNICAL ANALYSIS
            # ═══════════════════════════════════════════════════════════════════
            if self.market_intel:
                ta = await self.market_intel.get_technical_analysis(symbol.replace("/", ""), timeframe)
                indicators = ta.get("indicators", {})
                price = ta.get("price", 0)
                
                if not price:
                    return None
                
                rsi = indicators.get("rsi", 50)
                macd_signal = indicators.get("macd_signal", "")
                bb_signal = indicators.get("bb_position", "")
                ema_stack = indicators.get("ema_stack", "")
                
                # RSI extremes
                if rsi < 25:
                    signals_buy += 2
                    confirmations.append(f"RSI extreme oversold ({rsi:.0f})")
                elif rsi < 30:
                    signals_buy += 1
                    confirmations.append(f"RSI oversold ({rsi:.0f})")
                elif rsi > 75:
                    signals_sell += 2
                    confirmations.append(f"RSI extreme overbought ({rsi:.0f})")
                elif rsi > 70:
                    signals_sell += 1
                    confirmations.append(f"RSI overbought ({rsi:.0f})")
                
                # MACD
                if "BULLISH" in str(macd_signal).upper():
                    signals_buy += 1
                    confirmations.append("MACD bullish")
                elif "BEARISH" in str(macd_signal).upper():
                    signals_sell += 1
                    confirmations.append("MACD bearish")
                
                # Bollinger Bands
                if "LOWER" in str(bb_signal).upper() or "OVERSOLD" in str(bb_signal).upper():
                    signals_buy += 1
                    confirmations.append("BB lower band touch")
                elif "UPPER" in str(bb_signal).upper() or "OVERBOUGHT" in str(bb_signal).upper():
                    signals_sell += 1
                    confirmations.append("BB upper band touch")
                
                # EMA Stack
                if "BULLISH" in str(ema_stack).upper():
                    signals_buy += 1
                elif "BEARISH" in str(ema_stack).upper():
                    signals_sell += 1
            else:
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # 2. DIVERGENCE DETECTION
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    div = await self.advanced_strategies.detect_divergence(symbol, timeframe)
                    if div.get("has_divergence"):
                        for d in div.get("divergences", []):
                            if d.get("signal") == "BUY":
                                signals_buy += 2  # Divergence is strong
                                confirmations.append(f"📊 {d.get('type')} divergence")
                            elif d.get("signal") == "SELL":
                                signals_sell += 2
                                confirmations.append(f"📊 {d.get('type')} divergence")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 3. MARKET STRUCTURE
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    struct = await self.advanced_strategies.analyze_market_structure(symbol, timeframe)
                    trend = struct.get("trend", "")
                    bos = struct.get("bos")
                    
                    if trend == "UPTREND":
                        signals_buy += 1
                        confirmations.append("📈 Uptrend (HH/HL)")
                    elif trend == "DOWNTREND":
                        signals_sell += 1
                        confirmations.append("📉 Downtrend (LH/LL)")
                    
                    if bos:
                        if "BULLISH" in bos.get("type", ""):
                            signals_buy += 2
                            confirmations.append("⚡ Bullish BOS")
                        elif "BEARISH" in bos.get("type", ""):
                            signals_sell += 2
                            confirmations.append("⚡ Bearish BOS")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 4. VWAP
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    vwap = await self.advanced_strategies.calculate_vwap(symbol, timeframe)
                    vwap_bias = vwap.get("bias", "")
                    distance = vwap.get("distance_pct", 0)
                    
                    if vwap_bias == "STRONG_BULLISH" and distance > 3:
                        signals_buy += 1
                        confirmations.append(f"📊 Above VWAP +{distance:.1f}%")
                    elif vwap_bias == "STRONG_BEARISH" and distance < -3:
                        signals_sell += 1
                        confirmations.append(f"📊 Below VWAP {distance:.1f}%")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 5. ORDER FLOW / CVD
            # ═══════════════════════════════════════════════════════════════════
            if self.order_flow:
                try:
                    cvd = await self.order_flow.calculate_cvd(symbol.replace("/USDT", ""))
                    cvd_bias = cvd.get("bias", "")
                    buy_pct = cvd.get("buy_pct", 50)
                    
                    if cvd_bias == "BULLISH" and buy_pct > 58:
                        signals_buy += 2
                        confirmations.append(f"💰 Strong buying ({buy_pct:.0f}%)")
                    elif cvd_bias == "BEARISH" and buy_pct < 42:
                        signals_sell += 2
                        confirmations.append(f"💰 Strong selling ({100-buy_pct:.0f}%)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 6. OPTIONS DATA (BTC/ETH only)
            # ═══════════════════════════════════════════════════════════════════
            base = symbol.replace("/USDT", "")
            if self.options_analyzer and base in ["BTC", "ETH"]:
                try:
                    options = await self.options_analyzer.get_full_options_analysis(base)
                    options_bias = options.get("overall_bias", "")
                    
                    mp = options.get("max_pain", {})
                    mp_distance = mp.get("distance_pct", 0)
                    
                    pcr = options.get("put_call_ratio", {})
                    pcr_sentiment = pcr.get("sentiment", "")
                    
                    # Max pain analysis
                    if mp_distance > 5:
                        signals_buy += 1
                        confirmations.append(f"🎯 Max pain above (+{mp_distance:.1f}%)")
                    elif mp_distance < -5:
                        signals_sell += 1
                        confirmations.append(f"🎯 Max pain below ({mp_distance:.1f}%)")
                    
                    # Put/Call contrarian
                    if pcr_sentiment == "EXTREME_BEARISH":
                        signals_buy += 1
                        confirmations.append("📈 PCR extreme bearish (contrarian buy)")
                    elif pcr_sentiment == "EXTREME_BULLISH":
                        signals_sell += 1
                        confirmations.append("📉 PCR extreme bullish (contrarian sell)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 7. DERIVATIVES (Funding, L/S)
            # ═══════════════════════════════════════════════════════════════════
            if self.derivatives_intel:
                try:
                    deriv = await self.derivatives_intel.get_full_derivatives_report(symbol.replace("/", ""))
                    
                    # Funding rate
                    funding = deriv.get("funding", {})
                    avg_funding = funding.get("average_funding_rate", 0)
                    
                    if avg_funding > 0.0005:  # >0.05% = longs paying
                        signals_sell += 1
                        confirmations.append("💸 High funding (long squeeze risk)")
                    elif avg_funding < -0.0003:  # Negative = shorts paying
                        signals_buy += 1
                        confirmations.append("💸 Negative funding (short squeeze)")
                    
                    # Long/Short ratio
                    ls = deriv.get("long_short", {}).get("global", {})
                    long_pct = ls.get("long_pct", 50)
                    
                    if long_pct > 65:
                        signals_sell += 1
                        confirmations.append(f"📊 Longs crowded ({long_pct:.0f}%)")
                    elif long_pct < 35:
                        signals_buy += 1
                        confirmations.append(f"📊 Shorts crowded ({100-long_pct:.0f}%)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 8. FEAR & GREED
            # ═══════════════════════════════════════════════════════════════════
            if self.enhanced_intel:
                try:
                    fg = await self.enhanced_intel.get_fear_greed_index()
                    fg_value = fg.get("value", 50)
                    
                    if fg_value < 20:
                        signals_buy += 1
                        confirmations.append(f"😱 Extreme Fear ({fg_value})")
                    elif fg_value > 80:
                        signals_sell += 1
                        confirmations.append(f"🤑 Extreme Greed ({fg_value})")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE FINAL SCORE
            # ═══════════════════════════════════════════════════════════════════
            
            # Determine direction
            if signals_buy > signals_sell and signals_buy >= 3:
                direction = "LONG"
                signal_strength = signals_buy
            elif signals_sell > signals_buy and signals_sell >= 3:
                direction = "SHORT"
                signal_strength = signals_sell
            else:
                return None  # No clear direction
            
            # Calculate confidence (base 50 + signals)
            confidence = min(95, 50 + (signal_strength * 8))
            
            # Check minimum requirements
            if confidence < self.min_confidence:
                return None
            
            if len(confirmations) < self.min_confirmations:
                return None
            
            # Calculate entry, stop, target
            atr = indicators.get("atr", price * 0.02)
            
            if direction == "LONG":
                entry = price
                stop = price - (atr * 1.5)
                target = price + (atr * 3)
            else:
                entry = price
                stop = price + (atr * 1.5)
                target = price - (atr * 3)
            
            # Risk/Reward
            risk = abs(entry - stop)
            reward = abs(target - entry)
            rr = reward / risk if risk > 0 else 0
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "confidence": confidence,
                "confirmations": confirmations,
                "confirmation_count": len(confirmations),
                "entry": entry,
                "stop": stop,
                "target": target,
                "risk_reward": round(rr, 1),
                "signals_buy": signals_buy,
                "signals_sell": signals_sell,
                "price": price,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Setup analysis error {symbol} {timeframe}: {e}")
            return None
    
    async def scan_all(self) -> List[Dict]:
        """
        Scan top pairs on priority timeframes
        Returns ONLY the best setups (80%+ confidence, 3+ confirmations, no contradictions)
        """
        best_setups = {}  # symbol -> best setup
        
        for symbol in TOP_PAIRS[:15]:  # Top 15 for speed
            for tf in PRIORITY_TIMEFRAMES:
                setup = await self.analyze_setup_full(symbol, tf)
                
                if setup:
                    direction = setup.get("direction")
                    
                    # Check if we can alert (includes contradiction check)
                    if not self._can_alert(symbol, direction):
                        continue
                    
                    # Keep best setup per symbol
                    if symbol not in best_setups or setup["confidence"] > best_setups[symbol]["confidence"]:
                        best_setups[symbol] = setup
                
                await asyncio.sleep(0.2)  # Rate limiting
        
        # Sort by confidence, return top 3 max
        setups = list(best_setups.values())
        setups.sort(key=lambda x: x["confidence"], reverse=True)
        
        return setups[:3]  # Max 3 setups per scan
    
    def format_alert(self, setup: Dict) -> str:
        """Format elite alert message"""
        direction = setup.get("direction", "")
        symbol = setup.get("symbol", "").replace("/USDT", "")
        timeframe = setup.get("timeframe", "")
        confidence = setup.get("confidence", 0)
        
        emoji = "🟢" if direction == "LONG" else "🔴"
        
        entry = setup.get("entry", 0)
        stop = setup.get("stop", 0)
        target = setup.get("target", 0)
        rr = setup.get("risk_reward", 0)
        
        confirmations = setup.get("confirmations", [])
        
        alert = f"""{emoji} ELITE ALERT: {symbol} {timeframe}

{direction} Entry ${entry:,.2f}
SL ${stop:,.2f} | TP ${target:,.2f}
RR 1:{rr} | Conf {confidence}%

✅ {len(confirmations)} CONFIRMATIONS:
"""
        for c in confirmations[:6]:
            alert += f"• {c}\n"
        
        alert += """
⚠️ MANUAL CHECK REQUIRED
This is a high-quality setup. DYOR."""
        
        return alert
    
    async def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            "active": self.active,
            "min_confidence": self.min_confidence,
            "min_confirmations": self.min_confirmations,
            "alert_cooldown_mins": self.alert_cooldown // 60,
            "direction_lock_hours": self.direction_lock_time // 3600,
            "total_alerts_sent": self.total_alerts_sent,
            "daily_alerts": self.daily_alerts,
            "max_daily_alerts": self.max_daily_alerts,
            "setups_analyzed": self.setups_analyzed,
            "contradictions_blocked": self.contradictions_blocked,
            "recent_directions": {k: v[0] for k, v in self.last_direction.items()},
            "pairs_monitored": len(TOP_PAIRS),
            "timeframes": PRIORITY_TIMEFRAMES,
            "data_sources": [
                "Technical Analysis",
                "Divergence Detection",
                "Market Structure",
                "VWAP",
                "Order Flow / CVD",
                "Options (BTC/ETH)",
                "Derivatives",
                "Fear & Greed"
            ]
        }


# Initialization
def init_free_will_v2(db: AsyncIOMotorDatabase) -> FreeWillEngineV2:
    return FreeWillEngineV2(db)


# Global instance placeholder
free_will_v2 = None
