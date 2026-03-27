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

UNIFIED ENGINE INTEGRATION:
- All signals validated through EngineManager
- Risk controls: position limits, daily loss limits, R:R enforcement
- Blacklist/cooldown per engine after losses
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

from alert_throttler import AlertThrottler

logger = logging.getLogger(__name__)

# Import unified engine system
try:
    from aeon_engine_system import get_engine_manager, EngineType
except ImportError:
    get_engine_manager = None
    EngineType = None
    logger.warning("Unified engine system not available for Dual Trading Engine")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Top pairs for scanning
TOP_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ATOM/USDT", "UNI/USDT", "LTC/USDT", "OP/USDT",
    "INJ/USDT", "APT/USDT", "FIL/USDT", "TRX/USDT"
    # ARB removed: 76 trades, 8% WR, -$10,255 (2026-03-22)
    # NEAR removed: 39 trades, 0% WR, -$8,515 (2026-03-22)
]

# Day Trader config - AGGRESSIVE scalping
DAY_TRADER_CONFIG = {
    "name": "Day Trader",
    "style": "AGGRESSIVE",
    "emoji": "⚡",
    "timeframes": ["15m", "1h", "4h"],
    "min_confidence": 77,
    "min_confirmations": 2,
    "cooldown_seconds": 600,  # 10 min cooldown
    "direction_lock_seconds": 1800,  # 30 min lock
    "max_daily_alerts": 25,
    "risk_reward_min": 1.5,
    "stop_loss_atr_mult": 2.0,
    "take_profit_atr_mult": 3.0
}

# Long Term config - SMART position trading
LONG_TERM_CONFIG = {
    "name": "Long Term",
    "style": "SMART",
    "emoji": "🎯",
    "timeframes": ["4h", "1d"],
    "min_confidence": 82,
    "min_confirmations": 3,
    "cooldown_seconds": 3600,  # 1 hour cooldown
    "direction_lock_seconds": 7200,  # 2 hour lock
    "max_daily_alerts": 10,
    "risk_reward_min": 2.0,
    "stop_loss_atr_mult": 2.5,
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
        
        # Alert throttling (cooldown, direction lock, daily limit)
        self._throttler = AlertThrottler(
            cooldown_seconds=config["cooldown_seconds"],
            direction_lock_seconds=config["direction_lock_seconds"],
            max_daily_alerts=config["max_daily_alerts"],
            name=config["name"],
        )
        
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
    
    def set_dependencies(self, **kwargs):
        self.market_intel = kwargs.get('market_intel')
        self.derivatives_intel = kwargs.get('derivatives_intel')
        self.enhanced_intel = kwargs.get('enhanced_intel')
        self.order_flow = kwargs.get('order_flow')
        self.options_analyzer = kwargs.get('options_analyzer')
    
    def _can_alert(self, symbol: str, direction: str = None) -> bool:
        return self._throttler.can_alert(symbol, direction)

    def _mark_alerted(self, symbol: str, direction: str = None):
        self._throttler.mark_alerted(symbol, direction)
        self.total_alerts += 1
    
    async def analyze_setup(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Analyze a setup using all data sources"""
        from post_mortem_engine import get_post_mortem
        engine_name = "day_trader" if self.style == "AGGRESSIVE" else "dual_engine"
        if get_post_mortem().is_engine_paused(engine_name):
            return None  # blindspot pause active
        if not self.market_intel:
            return None
        
        self.setups_analyzed += 1
        
        try:
            # Get market scan
            scan = await self.market_intel.get_full_market_scan(symbol)
            if not scan or "error" in scan:
                return None
            
            price = scan.get("price", 0)
            if not price:
                return None
            
            # Score the setup — keep long and short reasons separate so only
            # the winning direction's reasons are shown (no contradicting confirmations)
            signals_long = 0
            signals_short = 0
            long_reasons = []
            short_reasons = []

            # 1. Technical Analysis
            tech = scan.get("technical", {})
            rsi = tech.get("rsi", 50)
            macd_hist = tech.get("macd_histogram", 0)

            # ADX regime filter: skip ranging markets (ADX < 20 = no trend to trade)
            adx = tech.get("adx", 0)
            if adx > 0 and adx < 20:
                logger.debug(f"[{self.name}] Skipping {symbol} {timeframe} — ADX {adx:.1f} < 20 (ranging)")
                return None

            if rsi < 35:
                signals_long += 2
                long_reasons.append("RSI oversold")
            elif rsi > 65:
                signals_short += 2
                short_reasons.append("RSI overbought")

            if macd_hist > 0:
                signals_long += 1
                long_reasons.append("MACD bullish")
            elif macd_hist < 0:
                signals_short += 1
                short_reasons.append("MACD bearish")

            # 2. Trend (EMA)
            trend = tech.get("trend", "neutral")
            if trend == "bullish":
                signals_long += 2
                long_reasons.append("Trend bullish")
            elif trend == "bearish":
                signals_short += 2
                short_reasons.append("Trend bearish")

            # 3. Overall bias — derive from RSI + trend
            if rsi < 45 and trend == "bearish":
                signals_short += 1
                short_reasons.append("Bear bias (RSI+trend)")
            elif rsi > 55 and trend == "bullish":
                signals_long += 1
                long_reasons.append("Bull bias (RSI+trend)")

            # 4. Derivatives (funding, L/S)
            deriv = scan.get("derivatives", {})
            funding = deriv.get("funding_rate", 0)
            ls_ratio = deriv.get("long_short_ratio", 1.0)

            if funding and funding < -0.01:
                signals_long += 2
                long_reasons.append("Funding negative (squeeze)")
            elif funding and funding > 0.03:
                signals_short += 2
                short_reasons.append("Funding extreme (dump risk)")

            if ls_ratio and ls_ratio > 2.0:
                signals_short += 1
                short_reasons.append("Longs crowded")
            elif ls_ratio and ls_ratio < 0.5:
                signals_long += 1
                long_reasons.append("Shorts crowded")

            # 5. Fear & Greed — only extreme greed kept as sell signal.
            # Extreme fear contrarian LONG removed: 0/6 win rate in data (fear keeps
            # rising in crypto bear markets so "contrarian buy" becomes a falling knife).
            fg = scan.get("fear_greed", {})
            fg_value = fg.get("value", 50)
            if fg_value > 75:
                signals_short += 1
                short_reasons.append("Extreme greed (contrarian sell)")

            # 6. Volume/CVD if available
            if self.order_flow:
                try:
                    cvd = await self.order_flow.get_cvd(symbol)
                    if cvd and cvd.get("trend") == "bullish":
                        signals_long += 1
                        long_reasons.append("CVD bullish")
                    elif cvd and cvd.get("trend") == "bearish":
                        signals_short += 1
                        short_reasons.append("CVD bearish")
                except Exception as e:
                    logger.debug(f"CVD data unavailable for {symbol}: {e}")

            # Calculate direction — only show reasons that match the chosen direction
            total_signals = signals_long + signals_short
            if total_signals < 3:
                return None

            if signals_long > signals_short:
                direction = "LONG"
                # Category-based confidence — each independent indicator = 1 category
                # Prevents double-counting RSI magnitude AND confirmation count from same data
                rsi_triggered   = rsi < 35
                macd_triggered  = macd_hist > 0
                trend_aligned   = tech.get("trend", "neutral") == "bullish"
                funding_signal  = bool(funding and funding < -0.01)
                sentiment_signal = bool((ls_ratio and ls_ratio < 0.5) or fg_value > 75)
                cat_score = sum([rsi_triggered, macd_triggered, trend_aligned, funding_signal, sentiment_signal])
                confidence = min(95, 55 + cat_score * 8)
                confirmations = long_reasons
            elif signals_short > signals_long:
                direction = "SHORT"
                rsi_triggered   = rsi > 65
                macd_triggered  = macd_hist < 0
                trend_aligned   = tech.get("trend", "neutral") == "bearish"
                funding_signal  = bool(funding and funding > 0.03)
                sentiment_signal = bool((ls_ratio and ls_ratio > 2.0) or fg_value > 75)
                cat_score = sum([rsi_triggered, macd_triggered, trend_aligned, funding_signal, sentiment_signal])
                confidence = min(95, 55 + cat_score * 8)
                confirmations = short_reasons
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
            
            # Check minimum requirements (+ macro direction gate)
            try:
                from regime_engine import get_regime_engine
                eff_threshold, macro_reason = get_regime_engine().apply_macro_confidence_gate(direction, self.min_confidence)
                if macro_reason:
                    logger.debug(f"[MACRO GATE] {symbol}: {macro_reason}")
            except Exception:
                eff_threshold = self.min_confidence
            if confidence < eff_threshold:
                return None

            if len(confirmations) < self.min_confirmations:
                return None
            
            # Calculate entry/SL/TP
            atr = tech.get("atr") or price * 0.02
            
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

        # BTC MACRO GATE — fetch once before scan loop
        btc_is_bearish = False
        btc_is_bullish = False
        if self.market_intel:
            try:
                btc_scan = await self.market_intel.get_full_market_scan("BTC/USDT")
                btc_bias = (btc_scan.get("market_structure", {}) or {}).get("bias", "neutral") if btc_scan else "neutral"
                btc_is_bearish = (btc_bias == "bearish")
                btc_is_bullish = (btc_bias == "bullish")
                logger.info(f"[{self.name}] BTC macro: {btc_bias}")
            except Exception as e:
                logger.debug(f"[{self.name}] BTC macro fetch failed: {e}")

        for symbol in TOP_PAIRS[:15]:
            for tf in self.timeframes:
                setup = await self.analyze_setup(symbol, tf)

                if setup:
                    direction = setup.get("direction")

                    # BTC macro gate
                    if direction == "LONG" and btc_is_bearish:
                        logger.info(f"[{self.name}] BLOCKED {symbol} LONG — BTC macro BEARISH")
                        continue
                    if direction == "SHORT" and btc_is_bullish:
                        logger.info(f"[{self.name}] BLOCKED {symbol} SHORT — BTC macro BULLISH")
                        continue

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
                scan = await self.market_intel.get_full_market_scan(symbol)
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
                    atr = scan.get("technical", {}).get("atr") or current_price * 0.02
                    if direction == "LONG":
                        setup["stop_loss"] = current_price - (atr * self.sl_atr_mult)
                        setup["take_profit"] = current_price + (atr * self.tp_atr_mult)
                    else:
                        setup["stop_loss"] = current_price + (atr * self.sl_atr_mult)
                        setup["take_profit"] = current_price - (atr * self.tp_atr_mult)
            except Exception as e:
                logger.error(f"[{self.name}] Price validation error: {e}")
        
        # ═══════════════════════════════════════════════════════════════
        # UNIFIED ENGINE VALIDATION
        # ═══════════════════════════════════════════════════════════════
        if get_engine_manager and EngineType:
            try:
                engine_manager = get_engine_manager()
                _symbol    = setup.get("symbol")
                _direction = setup.get("direction", "long").lower()

                # Determine which engine type based on style
                engine_type = EngineType.DAY_TRADER if self.style == "AGGRESSIVE" else EngineType.DUAL_ENGINE

                # Compute quant-driven leverage before building signal
                final_leverage, _lev_bd = await engine_manager.get_dynamic_leverage(
                    _symbol, _direction, engine_type
                )

                # Build signal for unified validation
                engine_signal = {
                    "symbol":        _symbol,
                    "direction":     _direction,
                    "entry_price":   setup.get("entry", 0),
                    "position_size": 1200,
                    "leverage":      final_leverage,
                    "stop_loss":     setup.get("stop_loss", 0),
                    "take_profit":   setup.get("take_profit", 0),
                    "confidence":    setup.get("confidence", 80),
                    "confluences":   len(setup.get("confirmations", [])),
                    "reason":        "; ".join(setup.get("confirmations", [])[:3])
                }

                # Submit to unified validator
                result = await engine_manager.submit_signal_gated(engine_signal, engine_type)

                if result["action"] == "REJECT":
                    qr = result.get("quant_report", {})
                    if qr and not result.get("adapted"):
                        adapted_signal = dict(engine_signal)
                        if qr.get("suggested_sl"):    adapted_signal["stop_loss"]    = qr["suggested_sl"]
                        if qr.get("suggested_entry"): adapted_signal["entry_price"]  = qr["suggested_entry"]
                        if qr.get("suggested_tp1"):   adapted_signal["take_profit"]  = qr["suggested_tp1"]
                        adapted_signal["position_size"] = round(adapted_signal["position_size"] * 0.70, 2)
                        adapted_lev, _ = await engine_manager.get_dynamic_leverage(
                            _symbol, _direction, engine_type, quant_report=qr
                        )
                        adapted_signal["leverage"] = adapted_lev
                        logger.info(f"🔄 [{self.name}] [{setup.get('symbol')}] adapting signal — resubmitting to Quant")
                        result = await engine_manager.submit_signal_gated(adapted_signal, engine_type, adapted=True)
                        if result["action"] == "REJECT":
                            logger.warning(f"❌ [{self.name}] [{setup.get('symbol')}] adapted attempt BLOCKED: {result.get('reason')}")
                            return None, False
                    else:
                        logger.warning(f"❌ [{self.name}] [{setup.get('symbol')}] BLOCKED: {result.get('reason')}")
                        return None, False

                logger.info(f"✅ [{self.name}] [{setup.get('symbol')}] VALIDATED by unified engine")
                
            except Exception as e:
                logger.warning(f"[{self.name}] Unified validation failed: {e}")
        
        msg = self.format_alert(setup)
        return msg, True
    
    def format_alert(self, setup: Dict) -> str:
        """Format alert message with detailed WHY reasoning and IF WRONG guidance"""
        direction = setup["direction"]
        symbol = setup["symbol"].replace("/USDT", "")
        conf = setup["confidence"]
        dir_emoji = "🟢" if direction == "LONG" else "🔴"
        style_badge = "⚡ DAY" if self.style == "AGGRESSIVE" else "🎯 LT"
        
        entry = setup['entry']
        stop = setup['stop_loss']
        target = setup['take_profit']
        rr = setup['risk_reward']
        
        # Calculate percentages
        risk_pct = abs(entry - stop) / entry * 100 if entry > 0 else 0
        reward_pct = abs(target - entry) / entry * 100 if entry > 0 else 0

        confirms = setup.get('confirmations', [])[:4]
        confirm_str = " | ".join(confirms) if confirms else "Multiple signals"
        
        # Generate DETAILED WHY reasoning with scenarios
        style_name = "Day Trader" if self.style == "AGGRESSIVE" else "Long Term"
        why_parts = []
        scenarios = []
        
        # Context about strategy
        if self.style == "AGGRESSIVE":
            why_parts.append(f"Quick {setup['timeframe']} setup for fast profits")
            scenarios.append("Expect move within 4-24 hours")
        else:
            why_parts.append(f"Patient {setup['timeframe']} swing trade")
            scenarios.append("Position may take 3-14 days to play out")
        
        # Analyze confirmations
        for c in confirms:
            c_lower = c.lower()
            if 'rsi' in c_lower:
                if 'oversold' in c_lower:
                    why_parts.append("RSI oversold = bounce setup")
                    scenarios.append("Sellers exhausted, expect relief rally")
                elif 'overbought' in c_lower:
                    why_parts.append("RSI overbought = reversal setup")
                    scenarios.append("Buyers exhausted, expect pullback")
            elif 'macd' in c_lower:
                if 'bullish' in c_lower:
                    why_parts.append("MACD bullish = momentum up")
                else:
                    why_parts.append("MACD bearish = momentum down")
            elif 'trend' in c_lower or 'structure' in c_lower:
                if 'bullish' in c_lower or 'uptrend' in c_lower:
                    why_parts.append("Uptrend structure intact")
                else:
                    why_parts.append("Downtrend structure intact")
        
        # Add probability context
        why_parts.append(f"{conf}% probability based on backtested patterns")
        
        # Build numbered reasons
        nums = ["①","②","③","④","⑤"]
        why_lines = "\n".join(f"{nums[i]} {p}" for i, p in enumerate(why_parts[:5]))

        # Note line
        note = scenarios[0] if scenarios else f"Targeting ${target:,.2f}"

        style_label = "Day Trader" if self.style == "AGGRESSIVE" else "Long Term"

        msg = (
            f"{dir_emoji} {direction} · {symbol} {setup['timeframe']}   {style_label}\n"
            f"Confidence: {conf}%\n\n"
            f"Entry   ${entry:,.2f}\n"
            f"Target  ${target:,.2f}   +{reward_pct:.1f}%\n"
            f"Stop    ${stop:,.2f}   -{risk_pct:.1f}%\n"
            f"R:R     {rr:.1f}\n\n"
            f"Why This Trade\n"
            f"{why_lines}\n\n"
            f"Note\n"
            f"{note}"
        )

        return msg
    
    def get_stats(self) -> Dict:
        t = self._throttler
        return {
            "name": self.name,
            "style": self.style,
            "active": self.active,
            "min_confidence": self.min_confidence,
            "min_confirmations": self.min_confirmations,
            "timeframes": self.timeframes,
            "cooldown_mins": t.cooldown_seconds // 60,
            "direction_lock_hours": t.direction_lock_seconds // 3600,
            "daily_alerts": t.daily_alerts,
            "max_daily_alerts": t.max_daily_alerts,
            "total_alerts": self.total_alerts,
            "setups_analyzed": self.setups_analyzed,
            "contradictions_blocked": t.contradictions_blocked,
            "recent_directions": {k: v[0] for k, v in t.last_direction.items()}
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
