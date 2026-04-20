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

UNIFIED ENGINE INTEGRATION:
- All signals validated through EngineManager
- Risk controls: position limits, daily loss limits, R:R enforcement
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

from alert_throttler import AlertThrottler

logger = logging.getLogger(__name__)

# Import paper trading for signal routing
try:
    from paper_trading import route_engine_signal
except ImportError:
    route_engine_signal = None
    logger.warning("Paper trading not available for Free Will signal routing")

# Import unified engine system
try:
    from aeon_engine_system import get_engine_manager, EngineType
except ImportError:
    get_engine_manager = None
    EngineType = None
    logger.warning("Unified engine system not available for Free Will")

# Telegram message formatters
try:
    from telegram_sender import format_quant_block, format_leverage_block, format_atr_block
    _tg_formatters_ok = True
except ImportError:
    _tg_formatters_ok = False

# Priority timeframes (higher = better signals, less noise)
# NOTE: 1d removed - data shows 0/12 win rate on daily signals (exhausted moves)
PRIORITY_TIMEFRAMES = ["4h", "1h"]  # Only alert on these
SCAN_TIMEFRAMES = ["15m", "1h", "4h", "1d"]  # Scan these for confluence

# Top pairs for scanning
TOP_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ATOM/USDT", "UNI/USDT", "LTC/USDT", "OP/USDT",
    "INJ/USDT", "APT/USDT", "FIL/USDT", "TRX/USDT"
    # ARB removed: 76 trades, 8% WR, -$10,255 (2026-03-22)
    # NEAR removed: 39 trades, 0% WR, -$8,515 (2026-03-22)
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
        self.min_confidence = 75  # Free Will - moderate threshold
        self.min_confirmations = 2  # Need 2+ data sources agreeing
        
        # Alert throttling (cooldown, direction lock, daily limit)
        self._throttler = AlertThrottler(
            cooldown_seconds=600,
            direction_lock_seconds=3600,
            max_daily_alerts=30,
            name="FreeWillV2",
        )
        
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
    
    def _can_alert(self, symbol: str, direction: str = None) -> bool:
        return self._throttler.can_alert(symbol, direction)

    def _mark_alerted(self, symbol: str, direction: str = None):
        self._throttler.mark_alerted(symbol, direction)
        self.total_alerts_sent += 1
    
    async def analyze_setup_full(self, symbol: str, timeframe: str, btc_is_bearish: bool = False, btc_is_bullish: bool = False, market_wide_bearish: bool = False) -> Optional[Dict]:
        """
        Full multi-source analysis for a setup
        Returns setup only if confidence >= 80% AND 3+ confirmations

        IMPROVED: Collects bullish/bearish signals separately, then only shows
        confirmations that support the final direction. No contradictions.
        """
        from post_mortem_engine import get_post_mortem
        if get_post_mortem().is_engine_paused("free_will_v2"):
            return None  # blindspot pause active
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
                ta = await self.market_intel.get_technical_analysis(symbol, timeframe)
                indicators = ta.get("indicators", {})
                price = ta.get("price", 0)
                
                if not price:
                    return None
                
                rsi = indicators.get("rsi", 50)
                macd_signal = indicators.get("macd_signal", "")
                bb_signal = indicators.get("bb_position", "")
                ema_stack = indicators.get("ema_stack", "")
                macd_histogram = indicators.get("macd_histogram", 0)
                bb_upper_val = indicators.get("bb_upper", 0)
                bb_lower_val = indicators.get("bb_lower", 0)
                ema_trend = indicators.get("trend", "neutral")

                # ADX regime filter: skip ranging markets (ADX < 20 = no trend to trade)
                adx = indicators.get("adx", 0)
                if adx > 0 and adx < 20:
                    logger.debug(f"Free Will: Skipping {symbol} {timeframe} — ADX {adx:.1f} < 20 (ranging)")
                    return None
                
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
                
                # MACD - use histogram for reliable signal (macd_signal field is a float, not string)
                if macd_histogram > 0:
                    signals_buy += 1
                    bullish_reasons.append("MACD bullish momentum")
                elif macd_histogram < 0:
                    signals_sell += 1
                    bearish_reasons.append("MACD bearish momentum")

                # Bollinger Bands - compare price vs actual band values
                if bb_lower_val and price <= bb_lower_val:
                    signals_buy += 1
                    bullish_reasons.append("Price at BB lower band (support)")
                elif bb_upper_val and price >= bb_upper_val:
                    signals_sell += 1
                    bearish_reasons.append("Price at BB upper band (resistance)")

                # EMA Stack - use trend field (9>21>50 alignment)
                if ema_trend == "bullish":
                    signals_buy += 1
                    bullish_reasons.append("EMA stack bullish (9>21>50)")
                elif ema_trend == "bearish":
                    signals_sell += 1
                    bearish_reasons.append("EMA stack bearish (9<21<50)")
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
                except Exception as e:
                    logger.debug(f"Divergence data unavailable for {symbol}: {e}")
            
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
                except Exception as e:
                    logger.debug(f"Market structure unavailable for {symbol}: {e}")
            
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
                    elif vwap_bias == "STRONG_BEARISH" and distance < -4:
                        signals_sell += 1
                        bearish_reasons.append(f"Below VWAP ({distance:.1f}%)")
                except Exception as e:
                    logger.debug(f"VWAP data unavailable for {symbol}: {e}")
            
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
                except Exception as e:
                    logger.debug(f"CVD data unavailable for {symbol}: {e}")
            
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
                except Exception as e:
                    logger.debug(f"Options data unavailable for {symbol}: {e}")
            
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

                    # Funding MOMENTUM (velocity > level)
                    try:
                        if self.market_intel:
                            fm = await self.market_intel.get_funding_momentum(symbol)
                            fm_signal = fm.get("signal", "NEUTRAL")
                            fm_squeeze = fm.get("squeeze_risk", "LOW")
                            fm_trend = fm.get("trend", "flat")
                            if fm_signal == "BEARISH" and fm_squeeze in ("HIGH", "MEDIUM"):
                                signals_sell += 1
                                bearish_reasons.append(f"Funding momentum rising ({fm_trend}, squeeze {fm_squeeze})")
                            elif fm_signal == "BULLISH" and fm_squeeze in ("HIGH", "MEDIUM"):
                                signals_buy += 1
                                bullish_reasons.append(f"Funding momentum bullish ({fm_trend}, squeeze {fm_squeeze})")
                            elif fm_signal == "REVERSAL":
                                if avg_funding > 0:
                                    signals_buy += 1
                                    bullish_reasons.append("Long squeeze complete — reversal likely")
                                else:
                                    signals_sell += 1
                                    bearish_reasons.append("Short squeeze complete — reversal likely")
                    except Exception as e:
                        logger.debug(f"Funding momentum unavailable for {symbol}: {e}")

                    ls = deriv.get("long_short", {}).get("global", {})
                    long_pct = ls.get("long_pct", 50)
                    
                    if long_pct > 67:
                        signals_sell += 1
                        bearish_reasons.append(f"Longs crowded ({long_pct:.0f}%)")
                    elif long_pct < 35:
                        signals_buy += 1
                        bullish_reasons.append(f"Shorts crowded ({100-long_pct:.0f}%)")
                except Exception as e:
                    logger.debug(f"Derivatives data unavailable for {symbol}: {e}")
            
            # ═══════════════════════════════════════════════════════════════════
            # 8. FEAR & GREED
            # ═══════════════════════════════════════════════════════════════════
            if self.enhanced_intel:
                try:
                    fg = await self.enhanced_intel.get_fear_greed_index()
                    fg_value = fg.get("value", 50)

                    # NOTE: Extreme Fear contrarian buy removed - data shows 0/6 win rate.
                    # In crypto bear markets fear keeps rising so "contrarian buy" is a trap.
                    # Only Extreme Greed (sell signal) kept as it fires at market tops.
                    if fg_value > 80:
                        signals_sell += 1
                        bearish_reasons.append(f"Extreme Greed ({fg_value}) - contrarian sell")
                except Exception as e:
                    logger.debug(f"Fear & Greed data unavailable: {e}")
            
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

            # ═══════════════════════════════════════════════════════════════════
            # SHORT-SPECIFIC FILTERS (data-driven, based on 100% WR confirmations)
            # ═══════════════════════════════════════════════════════════════════
            if direction == "SHORT":
                # MOMENTUM FILTER: Block SHORTs when MACD histogram is positive
                # Exception: BTC macro bearish means macro trend overrides local momentum lag
                if macd_histogram > 0:
                    _btc_dir = "NEUTRAL"
                    try:
                        from regime_engine import get_regime_engine
                        _btc_dir = get_regime_engine().get_btc_macro_direction()
                    except Exception:
                        pass
                    if _btc_dir.upper() not in ("BEARISH", "BEAR") and not market_wide_bearish:
                        logger.info(f"BLOCKED {symbol} SHORT - MACD histogram positive ({macd_histogram:.4f}), fighting bullish momentum")
                        return None
                    logger.debug(f"[FW] {symbol} SHORT — MACD positive but macro bearish (btc={_btc_dir}, market_wide={market_wide_bearish}), allowing through")

                # QUALITY GATE: Require at least 1 high-conviction microstructure signal
                # Based on trade data: 100% WR only when selling pressure + longs crowded + below VWAP present
                # Exception: market-wide bearish macro counts as a key signal
                key_signals = [c for c in bearish_reasons if any(
                    x in c.lower() for x in ["selling pressure", "longs crowded", "below vwap"]
                )]
                if not key_signals and not market_wide_bearish:
                    logger.info(f"BLOCKED {symbol} SHORT - missing key confirmation (need selling pressure, longs crowded 67%+, or below VWAP -4%+)")
                    return None
                elif not key_signals and market_wide_bearish:
                    logger.debug(f"[FW] {symbol} SHORT — no microstructure key signal but market-wide bearish, allowing through")

            # HARD FILTER: Market structure must not contradict direction
            # Exception: when BTC macro aligns with direction, coin structure may lag —
            # allow the trade through so quant gate can make the final call.
            structure = {}
            if self.market_intel:
                try:
                    ms = await self.market_intel.get_full_market_scan(symbol)
                    structure = ms.get("market_structure", {}) if ms else {}
                except Exception:
                    pass
            structure_bias = structure.get("bias", "neutral")

            # Use BTC macro passed in from scan_all (same source as outer macro gate)
            macro_bearish = btc_is_bearish
            macro_bullish = btc_is_bullish

            if direction == "LONG" and structure_bias == "bearish":
                if macro_bullish:
                    logger.debug(f"[FW] {symbol} LONG — bearish structure but BTC macro bullish, deferring to quant gate")
                else:
                    logger.info(f"BLOCKED {symbol} LONG - bearish structure (LH/LL)")
                    return None
            # SHORT structure block removed — defers to quant gate
            
            # Boost confidence when structure aligns
            if direction == "LONG" and structure_bias == "bullish":
                confidence = min(95, confidence + 5)
            elif direction == "SHORT" and structure_bias == "bearish":
                confidence = min(95, confidence + 5)
            
            # Check minimum confidence (+ macro direction gate)
            try:
                from regime_engine import get_regime_engine
                eff_threshold, macro_reason = get_regime_engine().apply_macro_confidence_gate(direction, self.min_confidence)
                if macro_reason:
                    logger.debug(f"[MACRO GATE] {symbol}: {macro_reason}")
            except Exception:
                eff_threshold = self.min_confidence
            if confidence < eff_threshold:
                return None

            # Calculate entry, stop, target
            atr = indicators.get("atr") or price * 0.02  # fallback if ATR is 0 or None
            
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

        # ═══════════════════════════════════════════════════════════════
        # MACRO TREND GATE
        # BTC/USDT uses BTC-specific macro (EMA20 4H+1D).
        # All altcoins use market-wide macro (majority of BTC+ETH+SOL on 4H EMA).
        # ═══════════════════════════════════════════════════════════════
        btc_macro = "NEUTRAL"
        market_wide_macro = "NEUTRAL"
        if self.market_intel:
            try:
                from regime_engine import get_regime_engine
                re = get_regime_engine()
                btc_macro = await re.refresh_macro_direction(self.market_intel)
                market_wide_macro = await re.refresh_market_wide_macro(self.market_intel)
                logger.info(f"BTC macro: {btc_macro} | Market-wide macro: {market_wide_macro}")
            except Exception as e:
                logger.debug(f"Could not fetch macro trend: {e}")

        # Pass BTC-specific flags to analyze_setup_full for internal use
        btc_is_bearish = (btc_macro == "BEARISH")
        btc_is_bullish = (btc_macro == "BULLISH")

        for symbol in TOP_PAIRS[:15]:  # Top 15 for speed
            for tf in PRIORITY_TIMEFRAMES:
                setup = await self.analyze_setup_full(symbol, tf, btc_is_bearish=btc_is_bearish, btc_is_bullish=btc_is_bullish, market_wide_bearish=(market_wide_macro == "BEARISH"))

                if setup:
                    direction = setup.get("direction")

                    # Macro gate: BTC/USDT uses BTC macro, alts use market-wide macro
                    macro = btc_macro if symbol == "BTC/USDT" else market_wide_macro
                    if direction == "LONG" and macro == "BEARISH":
                        logger.info(f"BLOCKED {symbol} LONG - {'BTC' if symbol == 'BTC/USDT' else 'market'} macro is BEARISH")
                        continue
                    if direction == "SHORT" and macro == "BULLISH":
                        logger.info(f"BLOCKED {symbol} SHORT - {'BTC' if symbol == 'BTC/USDT' else 'market'} macro is BULLISH")
                        continue

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
                ta = await self.market_intel.get_technical_analysis(symbol, "1h")
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
                    _macro_bear = False
                    _macro_bull = False
                    if self.market_intel:
                        try:
                            _btc_scan = await self.market_intel.get_full_market_scan("BTC/USDT")
                            _btc_bias = _btc_scan.get("market_structure", {}).get("bias", "neutral") if _btc_scan else "neutral"
                            _macro_bear = (_btc_bias == "bearish")
                            _macro_bull = (_btc_bias == "bullish")
                        except Exception:
                            pass
                    if direction == "LONG" and fresh_bias == "bearish":
                        if not _macro_bull:
                            logger.info(f"Free Will BLOCKED at validation: {symbol} LONG vs bearish structure")
                            return None, False
                    if direction == "SHORT" and fresh_bias == "bullish":
                        if not _macro_bear:
                            logger.info(f"Free Will BLOCKED at validation: {symbol} SHORT vs bullish structure")
                            return None, False
                    
                    # Update entry to current price for more accurate alert
                    setup["entry"] = current_price
                    setup["structure"] = fresh_structure.get("pattern", "")
                    
                    # Recalculate SL/TP based on fresh price
                    indicators = ta.get("indicators", {})
                    atr = indicators.get("atr") or current_price * 0.02  # fallback if ATR is 0 or None
                    
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
        
        # ═══════════════════════════════════════════════════════════════
        # UNIFIED ENGINE VALIDATION - Validate before routing to paper
        # ═══════════════════════════════════════════════════════════════
        if get_engine_manager and EngineType:
            try:
                engine_manager = get_engine_manager()
                _symbol    = setup.get("symbol")
                _direction = setup.get("direction", "long").lower()

                # Compute quant-driven leverage before building signal
                final_leverage, lev_bd = await engine_manager.get_dynamic_leverage(
                    _symbol, _direction, EngineType.FREE_WILL_V2
                )

                # FIX: Leverage-aware SL compression.
                # At high leverage, ATR-based stops may sit beyond the liquidation price.
                # Cap stop distance to 75% of the liquidation margin (25% safety buffer).
                import math as _math
                _lev_safe   = max(float(final_leverage), 1.0)
                _entry_fw   = float(setup.get("entry", 0))
                _raw_stop_fw = float(setup.get("stop", 0))
                if _entry_fw > 0 and _raw_stop_fw > 0:
                    _max_stop_pct_fw = (1.0 / _lev_safe) * 0.75
                    _raw_stop_pct_fw = abs(_entry_fw - _raw_stop_fw) / _entry_fw
                    if _raw_stop_pct_fw > _max_stop_pct_fw:
                        _capped_dist_fw = _entry_fw * _max_stop_pct_fw
                        _adj_stop_fw = (
                            _entry_fw - _capped_dist_fw if _direction == "long"
                            else _entry_fw + _capped_dist_fw
                        )
                        logger.info(
                            f"⚠️ [LEV-SL/FW] [{_symbol}] {_direction.upper()} lev={final_leverage}x "
                            f"stop compressed: {_raw_stop_pct_fw:.2%} > max={_max_stop_pct_fw:.2%} "
                            f"→ ${_raw_stop_fw:.4f}→${_adj_stop_fw:.4f}"
                        )
                        setup["stop"] = round(_adj_stop_fw, 8)

                # Build signal for unified validation
                engine_signal = {
                    "symbol":        _symbol,
                    "direction":     _direction,
                    "entry_price":   setup.get("entry", 0),
                    "position_size": 1500,
                    "leverage":      final_leverage,
                    "stop_loss":     setup.get("stop", 0),
                    "take_profit":   setup.get("target", 0),
                    "confidence":    setup.get("confidence", 80),
                    "confluences":   len(setup.get("confirmations", [])),
                    "reason":        "; ".join(setup.get("confirmations", [])[:3])
                }

                # Submit to unified validator
                result = await engine_manager.submit_signal_gated(engine_signal, EngineType.FREE_WILL_V2)

                _setup_adapted = False
                if result["action"] == "REJECT":
                    qr = result.get("quant_report", {})
                    if qr and not result.get("adapted"):
                        # Adapt: tighten levels, cut size 30%, recompute leverage from report
                        adapted_signal = dict(engine_signal)
                        if qr.get("suggested_sl"):    adapted_signal["stop_loss"]    = qr["suggested_sl"]
                        if qr.get("suggested_entry"): adapted_signal["entry_price"]  = qr["suggested_entry"]
                        if qr.get("suggested_tp1"):   adapted_signal["take_profit"]  = qr["suggested_tp1"]
                        adapted_signal["position_size"] = round(adapted_signal["position_size"] * 0.70, 2)
                        adapted_lev, adapted_lev_bd = await engine_manager.get_dynamic_leverage(
                            _symbol, _direction, EngineType.FREE_WILL_V2, quant_report=qr
                        )
                        adapted_signal["leverage"] = adapted_lev
                        lev_bd = adapted_lev_bd  # use post-adaptation breakdown
                        logger.info(f"🔄 Free Will [{setup.get('symbol')}] adapting signal — resubmitting to Quant")
                        result = await engine_manager.submit_signal_gated(adapted_signal, EngineType.FREE_WILL_V2, adapted=True)
                        if result["action"] == "REJECT":
                            logger.warning(f"❌ Free Will [{setup.get('symbol')}] adapted attempt BLOCKED: {result.get('reason')}")
                            # Alert still goes out — user sees the setup, paper trade is skipped
                            setup["_quant_blocked"] = True
                            setup["_quant_reason"] = result.get("reason", "Quant gate")
                        else:
                            _setup_adapted = True
                    else:
                        logger.warning(f"❌ Free Will [{setup.get('symbol')}] BLOCKED: {result.get('reason')}")
                        # Alert still goes out — user sees the setup, paper trade is skipped
                        setup["_quant_blocked"] = True
                        setup["_quant_reason"] = result.get("reason", "Quant gate")

                # Attach quant/leverage data to setup for Telegram formatting
                setup["_lev_bd"]  = lev_bd
                setup["_adapted"] = _setup_adapted

                logger.info(f"✅ Free Will [{setup.get('symbol')}] VALIDATED by unified system")
                
            except Exception as e:
                logger.warning(f"Unified validation failed for Free Will: {e}")
        
        # Append analysis-only note if quant gate blocked paper trade
        if setup.get("_quant_blocked") and msg:
            msg += "\n\n⚠️ Analysis alert — quant gate blocked paper trade (ranging market conditions)"

        # Route to paper trading accounts (only if quant approved)
        if route_engine_signal and msg and not setup.get("_quant_blocked"):
            try:
                # Regime-adaptive sizing: reduce position size by 50% in RANGING markets
                # (paired with the lowered QUANT gate threshold for free_will_v2)
                _risk_pct = 1.5
                _current_regime = "TRENDING"
                try:
                    from quant_analyzer_v2 import QuantGatekeeperV2
                    _bl = await QuantGatekeeperV2._load_baseline(None, setup.get("symbol", ""))
                    _current_regime = _bl.get("last_regime", "TRENDING") if _bl else "TRENDING"
                except Exception:
                    pass
                if _current_regime == "RANGING":
                    _risk_pct = 0.75  # 50% of normal 1.5% risk in ranging markets
                    logger.info(
                        f"QUANT GATE: Free Will [{setup.get('symbol')}] regime=RANGING "
                        f"— threshold lowered, position size halved (risk {_risk_pct}%)"
                    )

                paper_signal = {
                    "symbol": setup.get("symbol"),
                    "direction": setup.get("direction"),
                    "entry_price": setup.get("entry"),
                    "stop_loss": setup.get("stop"),
                    "take_profit": setup.get("target"),
                    "confidence": setup.get("confidence", 80),
                    "confirmations": setup.get("confirmations", []),
                    "timeframe": setup.get("timeframe", "4h"),
                    "risk_pct": _risk_pct
                }
                await route_engine_signal(paper_signal, "FREE_WILL_V2")
                logger.info(f"📊 Free Will alert routed to paper accounts: {setup.get('symbol')} {setup.get('direction')}")
            except Exception as e:
                logger.warning(f"Failed to route Free Will to paper trading: {e}")

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
        
        # Build numbered reasons
        nums = ["①","②","③","④","⑤"]
        why_lines = "\n".join(f"{nums[i]} {p}" for i, p in enumerate(why_parts[:5]))

        # Note line
        note = scenarios[0] if scenarios else f"Price should move toward ${target:,.2f} as signals play out"

        alert = (
            f"{emoji} {direction} · {symbol} {timeframe}\n"
            f"Confidence: {confidence}%\n\n"
            f"Entry   ${entry:,.2f}\n"
            f"Target  ${target:,.2f}   +{reward_pct:.1f}%\n"
            f"Stop    ${stop:,.2f}   -{risk_pct:.1f}%\n"
            f"R:R     1:{rr}\n\n"
            f"Why This Trade\n"
            f"{why_lines}\n\n"
            f"Note\n"
            f"{note}"
        )

        # Append Quant Gate / Leverage Engine / ATR Stop blocks if data available
        lev_bd = setup.get("_lev_bd", {})
        if lev_bd and _tg_formatters_ok:
            adapted = setup.get("_adapted", False)
            alert += "\n\n" + format_quant_block(lev_bd, adapted)
            alert += "\n\n" + format_leverage_block(lev_bd)
            alert += "\n\n" + format_atr_block(setup)

        return alert
    
    async def get_stats(self) -> Dict:
        """Get engine statistics"""
        t = self._throttler
        return {
            "active": self.active,
            "min_confidence": self.min_confidence,
            "min_confirmations": self.min_confirmations,
            "alert_cooldown_mins": t.cooldown_seconds // 60,
            "direction_lock_hours": t.direction_lock_seconds // 3600,
            "total_alerts_sent": self.total_alerts_sent,
            "daily_alerts": t.daily_alerts,
            "max_daily_alerts": t.max_daily_alerts,
            "setups_analyzed": self.setups_analyzed,
            "contradictions_blocked": t.contradictions_blocked,
            "recent_directions": {k: v[0] for k, v in t.last_direction.items()},
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
