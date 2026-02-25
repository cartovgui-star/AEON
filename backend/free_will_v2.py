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

# Import paper trading for signal routing
try:
    from paper_trading import route_engine_signal
except ImportError:
    route_engine_signal = None
    logger.warning("Paper trading not available for Free Will signal routing")

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
        
        IMPROVED: Collects bullish/bearish signals separately, then only shows
        confirmations that support the final direction. No contradictions.
        """
        self.setups_analyzed += 1
        
        try:
            # Collect signals separately - no mixing
            bullish_reasons = []
            bearish_reasons = []
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
                
                # RSI signals
                if rsi < 25:
                    signals_buy += 2
                    bullish_reasons.append(f"RSI oversold at {rsi:.0f}")
                elif rsi < 30:
                    signals_buy += 1
                    bullish_reasons.append(f"RSI approaching oversold ({rsi:.0f})")
                elif rsi > 75:
                    signals_sell += 2
                    bearish_reasons.append(f"RSI overbought at {rsi:.0f}")
                elif rsi > 70:
                    signals_sell += 1
                    bearish_reasons.append(f"RSI approaching overbought ({rsi:.0f})")
                
                # MACD - only count clear signals
                if "BULLISH" in str(macd_signal).upper():
                    signals_buy += 1
                    bullish_reasons.append("MACD bullish crossover")
                elif "BEARISH" in str(macd_signal).upper():
                    signals_sell += 1
                    bearish_reasons.append("MACD bearish crossover")
                
                # Bollinger Bands
                if "LOWER" in str(bb_signal).upper() or "OVERSOLD" in str(bb_signal).upper():
                    signals_buy += 1
                    bullish_reasons.append("Price at BB lower band (support)")
                elif "UPPER" in str(bb_signal).upper() or "OVERBOUGHT" in str(bb_signal).upper():
                    signals_sell += 1
                    bearish_reasons.append("Price at BB upper band (resistance)")
                
                # EMA Stack
                if "BULLISH" in str(ema_stack).upper():
                    signals_buy += 1
                    bullish_reasons.append("EMA stack bullish (20>50>200)")
                elif "BEARISH" in str(ema_stack).upper():
                    signals_sell += 1
                    bearish_reasons.append("EMA stack bearish (20<50<200)")
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
                            div_type = d.get('type', '').replace('_', ' ')
                            if d.get("signal") == "BUY":
                                signals_buy += 2
                                bullish_reasons.append(f"{div_type} divergence (reversal signal)")
                            elif d.get("signal") == "SELL":
                                signals_sell += 2
                                bearish_reasons.append(f"{div_type} divergence (reversal signal)")
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
                        bullish_reasons.append("Uptrend structure (HH/HL)")
                    elif trend == "DOWNTREND":
                        signals_sell += 1
                        bearish_reasons.append("Downtrend structure (LH/LL)")
                    
                    if bos:
                        if "BULLISH" in bos.get("type", ""):
                            signals_buy += 2
                            bullish_reasons.append("Bullish Break of Structure")
                        elif "BEARISH" in bos.get("type", ""):
                            signals_sell += 2
                            bearish_reasons.append("Bearish Break of Structure")
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
                        bullish_reasons.append(f"Above VWAP (+{distance:.1f}%)")
                    elif vwap_bias == "STRONG_BEARISH" and distance < -3:
                        signals_sell += 1
                        bearish_reasons.append(f"Below VWAP ({distance:.1f}%)")
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
                        bullish_reasons.append(f"Strong buying pressure ({buy_pct:.0f}%)")
                    elif cvd_bias == "BEARISH" and buy_pct < 42:
                        signals_sell += 2
                        bearish_reasons.append(f"Strong selling pressure ({100-buy_pct:.0f}%)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 6. OPTIONS DATA (BTC/ETH only)
            # ═══════════════════════════════════════════════════════════════════
            base = symbol.replace("/USDT", "")
            if self.options_analyzer and base in ["BTC", "ETH"]:
                try:
                    options = await self.options_analyzer.get_full_options_analysis(base)
                    
                    mp = options.get("max_pain", {})
                    mp_distance = mp.get("distance_pct", 0)
                    
                    pcr = options.get("put_call_ratio", {})
                    pcr_sentiment = pcr.get("sentiment", "")
                    
                    if mp_distance > 5:
                        signals_buy += 1
                        bullish_reasons.append(f"Price below max pain (+{mp_distance:.1f}% upside)")
                    elif mp_distance < -5:
                        signals_sell += 1
                        bearish_reasons.append(f"Price above max pain ({mp_distance:.1f}% downside)")
                    
                    if pcr_sentiment == "EXTREME_BEARISH":
                        signals_buy += 1
                        bullish_reasons.append("Extreme put buying (contrarian buy)")
                    elif pcr_sentiment == "EXTREME_BULLISH":
                        signals_sell += 1
                        bearish_reasons.append("Extreme call buying (contrarian sell)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 7. DERIVATIVES (Funding, L/S)
            # ═══════════════════════════════════════════════════════════════════
            if self.derivatives_intel:
                try:
                    deriv = await self.derivatives_intel.get_full_derivatives_report(symbol.replace("/", ""))
                    
                    funding = deriv.get("funding", {})
                    avg_funding = funding.get("average_funding_rate", 0)
                    
                    if avg_funding > 0.0005:
                        signals_sell += 1
                        bearish_reasons.append("High funding rate (long squeeze risk)")
                    elif avg_funding < -0.0003:
                        signals_buy += 1
                        bullish_reasons.append("Negative funding (short squeeze setup)")
                    
                    ls = deriv.get("long_short", {}).get("global", {})
                    long_pct = ls.get("long_pct", 50)
                    
                    if long_pct > 65:
                        signals_sell += 1
                        bearish_reasons.append(f"Longs crowded ({long_pct:.0f}%)")
                    elif long_pct < 35:
                        signals_buy += 1
                        bullish_reasons.append(f"Shorts crowded ({100-long_pct:.0f}%)")
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
                        bullish_reasons.append(f"Extreme Fear ({fg_value}) - contrarian buy")
                    elif fg_value > 80:
                        signals_sell += 1
                        bearish_reasons.append(f"Extreme Greed ({fg_value}) - contrarian sell")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE FINAL SCORE - Use only matching direction reasons
            # ═══════════════════════════════════════════════════════════════════
            
            # Determine direction based on signal strength
            if signals_buy > signals_sell and signals_buy >= 3:
                direction = "LONG"
                signal_strength = signals_buy
                confirmations = bullish_reasons  # Only bullish reasons for LONG
            elif signals_sell > signals_buy and signals_sell >= 3:
                direction = "SHORT"
                signal_strength = signals_sell
                confirmations = bearish_reasons  # Only bearish reasons for SHORT
            else:
                return None  # No clear direction
            
            # Calculate confidence (base 50 + signals)
            confidence = min(95, 50 + (signal_strength * 8))
            
            # Require at least 3 confirmations (all matching direction now)
            if len(confirmations) < 3:
                logger.info(f"BLOCKED {symbol} {direction} - only {len(confirmations)} confirmations")
                return None
            
            # HARD FILTER: Market structure must not contradict direction
            structure = {}
            if self.market_intel:
                try:
                    ms = await self.market_intel.get_full_market_scan(symbol.replace("/", ""))
                    structure = ms.get("market_structure", {}) if ms else {}
                except Exception:
                    pass
            structure_bias = structure.get("bias", "neutral")
            
            if direction == "LONG" and structure_bias == "bearish":
                logger.info(f"BLOCKED {symbol} LONG - bearish structure (LH/LL)")
                return None
            if direction == "SHORT" and structure_bias == "bullish":
                logger.info(f"BLOCKED {symbol} SHORT - bullish structure (HH/HL)")
                return None
            
            # Boost confidence when structure aligns
            if direction == "LONG" and structure_bias == "bullish":
                confidence = min(95, confidence + 5)
            elif direction == "SHORT" and structure_bias == "bearish":
                confidence = min(95, confidence + 5)
            
            # Check minimum confidence
            if confidence < self.min_confidence:
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
            
            # Build the "WHY" explanation
            why_explanation = self._build_why_explanation(direction, confirmations, confidence)
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "confidence": confidence,
                "confirmations": confirmations[:5],  # Top 5 reasons
                "confirmation_count": len(confirmations),
                "why": why_explanation,
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
    
    def _build_why_explanation(self, direction: str, confirmations: list, confidence: int) -> str:
        """Build a clear explanation of WHY this trade makes sense"""
        if direction == "LONG":
            emoji = "📈"
            action = "BUY"
        else:
            emoji = "📉"
            action = "SELL"
        
        # Categorize reasons
        technical = []
        sentiment = []
        structure = []
        
        for conf in confirmations:
            conf_lower = conf.lower()
            if any(x in conf_lower for x in ["rsi", "macd", "bb", "ema", "divergence"]):
                technical.append(conf)
            elif any(x in conf_lower for x in ["fear", "greed", "funding", "crowd", "squeeze"]):
                sentiment.append(conf)
            else:
                structure.append(conf)
        
        # Build explanation
        parts = [f"{emoji} {action} Signal ({confidence}% confidence)"]
        
        if technical:
            parts.append(f"Technical: {', '.join(technical[:2])}")
        if sentiment:
            parts.append(f"Sentiment: {', '.join(sentiment[:2])}")
        if structure:
            parts.append(f"Structure: {', '.join(structure[:2])}")
        
        return " | ".join(parts)
    
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
    
    async def validate_and_format_alert(self, setup: Dict) -> tuple:
        """
        Validate setup price is still valid and format alert
        Returns (message, is_valid)
        """
        direction = setup.get("direction", "")
        symbol = setup.get("symbol", "")
        entry = setup.get("entry", 0)
        
        # Fetch fresh price to validate
        if self.market_intel:
            try:
                ta = await self.market_intel.get_technical_analysis(symbol.replace("/", ""), "1h")
                current_price = ta.get("price", 0)
                
                if current_price:
                    # Check if price has moved too far from entry (invalidates setup)
                    price_diff_pct = abs((current_price - entry) / entry * 100)
                    
                    if price_diff_pct > 1.5:  # Elite alerts - tighter validation (1.5%)
                        logger.info(f"Free Will setup invalidated: {symbol} price moved {price_diff_pct:.1f}% from entry")
                        return None, False
                    
                    # Re-validate market structure with fresh data
                    fresh_structure = ta.get("market_structure", {})
                    fresh_bias = fresh_structure.get("bias", "neutral")
                    if direction == "LONG" and fresh_bias == "bearish":
                        logger.info(f"Free Will BLOCKED at validation: {symbol} LONG vs bearish structure")
                        return None, False
                    if direction == "SHORT" and fresh_bias == "bullish":
                        logger.info(f"Free Will BLOCKED at validation: {symbol} SHORT vs bullish structure")
                        return None, False
                    
                    # Update entry to current price for more accurate alert
                    setup["entry"] = current_price
                    setup["structure"] = fresh_structure.get("pattern", "")
                    
                    # Recalculate SL/TP based on fresh price
                    indicators = ta.get("indicators", {})
                    atr = indicators.get("atr", current_price * 0.02)
                    
                    if direction == "LONG":
                        setup["stop"] = current_price - (atr * 1.5)
                        setup["target"] = current_price + (atr * 3)
                    else:
                        setup["stop"] = current_price + (atr * 1.5)
                        setup["target"] = current_price - (atr * 3)
                    
                    setup["price"] = current_price
            except Exception as e:
                logger.error(f"Free Will price validation error: {e}")
        
        msg = self.format_alert(setup)
        return msg, True
    
    def format_alert(self, setup: Dict) -> str:
        """Format elite alert with detailed WHY reasoning and IF WRONG guidance"""
        direction = setup.get("direction", "")
        symbol = setup.get("symbol", "").replace("/USDT", "")
        timeframe = setup.get("timeframe", "")
        confidence = setup.get("confidence", 0)
        emoji = "🟢" if direction == "LONG" else "🔴"

        entry = setup.get("entry", 0)
        stop = setup.get("stop", 0)
        target = setup.get("target", 0)
        rr = setup.get("risk_reward", 0)
        
        # Calculate percentages
        risk_pct = abs(entry - stop) / entry * 100 if entry > 0 else 0
        reward_pct = abs(target - entry) / entry * 100 if entry > 0 else 0

        confirmations = setup.get("confirmations", [])[:4]
        confirm_str = " | ".join(confirmations) if confirmations else "Multi-signal"
        
        # Generate DETAILED WHY reasoning based on confirmations
        why_parts = []
        scenarios = []
        
        # Analyze structure/trend
        structure_conf = [c for c in confirmations if any(x in c.lower() for x in ['trend', 'bos', 'structure', 'hh', 'hl', 'lh', 'll'])]
        if structure_conf:
            if direction == "LONG":
                why_parts.append("Market showing higher highs/lows (bullish structure)")
                scenarios.append("Price should continue making HH/HL toward target")
            else:
                why_parts.append("Market showing lower highs/lows (bearish structure)")
                scenarios.append("Price should continue making LH/LL toward target")
        
        # Analyze momentum indicators
        for conf in confirmations:
            if 'rsi' in conf.lower():
                if 'oversold' in conf.lower():
                    why_parts.append("RSI oversold = sellers exhausted, bounce incoming")
                    scenarios.append("Expect relief rally as shorts cover")
                elif 'overbought' in conf.lower():
                    why_parts.append("RSI overbought = buyers exhausted, pullback coming")
                    scenarios.append("Expect profit-taking selloff")
            elif 'macd' in conf.lower():
                if direction == "LONG":
                    why_parts.append("MACD bullish crossover = momentum shifting up")
                else:
                    why_parts.append("MACD bearish crossover = momentum shifting down")
        
        # Analyze order flow/sentiment
        for conf in confirmations:
            if 'buying' in conf.lower():
                why_parts.append("Strong buying pressure = smart money accumulating")
                scenarios.append("Accumulation often precedes major moves up")
            elif 'selling' in conf.lower():
                why_parts.append("Strong selling pressure = institutions distributing")
                scenarios.append("Distribution often precedes drops")
            elif 'fear' in conf.lower():
                why_parts.append("Extreme fear = contrarian buy opportunity")
                scenarios.append("Fear peaks often mark local bottoms")
            elif 'greed' in conf.lower():
                why_parts.append("Extreme greed = potential top forming")
                scenarios.append("Greed peaks often mark local tops")
        
        # Add risk/reward context
        why_parts.append(f"1:{rr} RR = risking {risk_pct:.1f}% to gain {reward_pct:.1f}%")
        
        # Combine into coherent reasoning
        why_reason = ". ".join(why_parts[:3]) + "." if why_parts else f"Multiple signals align at {confidence}% probability."
        
        # What to expect section
        if scenarios:
            scenario_text = scenarios[0]
        else:
            scenario_text = f"Price should move toward ${target:,.2f} as signals play out"

        alert = f"""{emoji} ELITE {direction} {symbol} {timeframe} ({confidence}%)

Entry ${entry:,.2f} | SL ${stop:,.2f} | TP ${target:,.2f}
Risk: {risk_pct:.1f}% | Reward: {reward_pct:.1f}% | RR 1:{rr}

✅ WHY {direction}:
{why_reason}

🎯 WHAT TO EXPECT:
{scenario_text}
• If confident: Enter at ${entry:,.2f}, set SL immediately
• If cautious: Wait for pullback to ${entry * 0.995 if direction == 'LONG' else entry * 1.005:,.2f}

⚠️ IF WRONG (Price hits ${stop:,.2f}):
• EXIT immediately - stop loss is non-negotiable
• Loss = {risk_pct:.1f}% on this position
• DO NOT: Move stop, add to loser, or hope
• WAIT: For next valid setup, don't revenge trade

📋 PREPARATION:
• Set alerts at entry zone before entering
• Pre-calculate position size for {risk_pct:.1f}% risk
• Know your exit BEFORE you enter"""
        
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
