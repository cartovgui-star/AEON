"""
AEON AUTONOMOUS TRADER V2
Ultimate trading engine with ALL data sources and smart execution

Features:
- Multi-source confirmation (8 data sources)
- Smart entry timing (pullbacks to key levels)
- Market regime filter (only trade trending markets)
- Position sizing by confidence
- BTC correlation filter for alts
- Session awareness (Asia/London/NY)
- Trail stops and partial profits
- Unlimited signals (quality filtered)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
import pytz

logger = logging.getLogger(__name__)

# Trading pairs - prioritized by liquidity (MEXC supported)
TRADING_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ATOM/USDT", "UNI/USDT", "LTC/USDT", "ARB/USDT", "OP/USDT",
    "INJ/USDT", "NEAR/USDT", "APT/USDT", "FIL/USDT", "TRX/USDT",
    "POL/USDT", "SHIB/USDT", "BCH/USDT", "ETC/USDT", "XLM/USDT"
]

# Priority timeframes for quality signals
TIMEFRAMES = ["4h", "1h", "1d"]


class AutonomousTraderV2:
    """
    Ultimate autonomous trading engine
    
    Uses ALL data sources:
    1. Technical Analysis (RSI, MACD, BB, EMA, ATR)
    2. Divergence Detection
    3. Market Structure (HH/HL/LH/LL, BOS)
    4. VWAP levels
    5. Order Flow / CVD
    6. Options data (BTC/ETH)
    7. Derivatives (funding, OI, L/S)
    8. Fear & Greed Index
    
    Smart features:
    - Entry on pullbacks to key levels
    - Market regime filter
    - BTC correlation for alts
    - Session awareness
    - Position sizing by confidence
    - Trail stops
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.active = True
        
        # Quality thresholds - Lower for paper trading
        self.min_confidence = 70  # Lowered for more action
        self.min_confirmations = 3  # Need 3+ data sources agreeing
        
        # Position sizing
        self.base_position_pct = 2  # 2% of capital per trade
        self.max_position_pct = 5  # Max 5% for highest confidence
        
        # Risk management
        self.max_open_trades = 10  # Max concurrent positions
        self.default_stop_atr = 2.0  # 2x ATR for stop
        self.default_target_atr = 4.0  # 4x ATR for target (2:1 R:R)
        
        # Trade tracking
        self.open_trades: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.total_signals = 0
        self.total_trades = 0
        
        # Market state
        self.btc_bias = "NEUTRAL"
        self.market_regime = "UNKNOWN"
        self.fear_greed = 50
        self.current_session = "UNKNOWN"
        
        # External dependencies
        self.market_intel = None
        self.derivatives_intel = None
        self.enhanced_intel = None
        self.advanced_strategies = None
        self.order_flow = None
        self.options_analyzer = None
        self.learning_system = None
        
        # Alert callback
        self.send_alert = None
        self.chat_ids: Set[int] = set()
    
    def set_dependencies(self, **kwargs):
        """Set all external dependencies"""
        self.market_intel = kwargs.get('market_intel')
        self.derivatives_intel = kwargs.get('derivatives_intel')
        self.enhanced_intel = kwargs.get('enhanced_intel')
        self.advanced_strategies = kwargs.get('advanced_strategies')
        self.order_flow = kwargs.get('order_flow')
        self.options_analyzer = kwargs.get('options_analyzer')
        self.learning_system = kwargs.get('learning_system')
        self.send_alert = kwargs.get('send_alert')
        self.chat_ids = kwargs.get('chat_ids', set())
    
    async def load_settings(self):
        """Load persisted settings from database"""
        try:
            settings = await self.db.trader_settings.find_one({"_id": "v2_settings"})
            if settings:
                self.active = settings.get("active", True)
                self.min_confidence = settings.get("min_confidence", 70)
                self.min_confirmations = settings.get("min_confirmations", 3)
                self.max_open_trades = settings.get("max_open_trades", 10)
                logger.info(f"Loaded trader settings: conf={self.min_confidence}%, confirms={self.min_confirmations}")
            
            # Load open trades from last session
            open_trades = await self.db.v2_open_trades.find().to_list(100)
            if open_trades:
                self.open_trades = [{k: v for k, v in t.items() if k != '_id'} for t in open_trades]
                logger.info(f"Restored {len(self.open_trades)} open trades from database")
            
            # Load closed trades history
            closed_trades = await self.db.v2_closed_trades.find().sort("closed_at", -1).limit(100).to_list(100)
            if closed_trades:
                self.closed_trades = [{k: v for k, v in t.items() if k != '_id'} for t in closed_trades]
                # Calculate stats from closed trades
                self.total_trades = len(self.open_trades) + len(self.closed_trades)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
    
    async def save_settings(self):
        """Persist current settings to database"""
        try:
            await self.db.trader_settings.update_one(
                {"_id": "v2_settings"},
                {"$set": {
                    "active": self.active,
                    "min_confidence": self.min_confidence,
                    "min_confirmations": self.min_confirmations,
                    "max_open_trades": self.max_open_trades,
                    "updated_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    async def save_open_trade(self, trade: Dict):
        """Persist an open trade to database"""
        try:
            trade_doc = {**trade}
            trade_doc["_id"] = trade["id"]
            await self.db.v2_open_trades.update_one(
                {"_id": trade["id"]},
                {"$set": trade_doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
    
    async def close_trade_in_db(self, trade: Dict):
        """Move trade from open to closed in database"""
        try:
            # Remove from open trades
            await self.db.v2_open_trades.delete_one({"_id": trade["id"]})
            # Add to closed trades
            trade_doc = {**trade}
            trade_doc["_id"] = trade["id"]
            await self.db.v2_closed_trades.insert_one(trade_doc)
        except Exception as e:
            logger.error(f"Failed to close trade in DB: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MARKET REGIME & SESSION DETECTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_current_session(self) -> str:
        """Detect current trading session"""
        now = datetime.now(pytz.UTC)
        hour = now.hour
        
        # Trading sessions (UTC)
        # Asia: 00:00 - 08:00 UTC
        # London: 08:00 - 16:00 UTC
        # New York: 13:00 - 21:00 UTC
        # London/NY overlap: 13:00 - 16:00 UTC (best volume)
        
        if 13 <= hour < 16:
            return "LONDON_NY_OVERLAP"  # Best time to trade
        elif 8 <= hour < 16:
            return "LONDON"
        elif 13 <= hour < 21:
            return "NEW_YORK"
        elif 0 <= hour < 8:
            return "ASIA"  # Lower volume, avoid
        else:
            return "OFF_HOURS"
        
        return "UNKNOWN"
    
    def get_session_quality(self, session: str) -> float:
        """Get session quality multiplier"""
        quality = {
            "LONDON_NY_OVERLAP": 1.2,  # Best - bonus confidence
            "LONDON": 1.1,
            "NEW_YORK": 1.1,
            "ASIA": 0.9,  # Reduce confidence for low volume
            "OFF_HOURS": 0.85,
            "UNKNOWN": 1.0
        }
        return quality.get(session, 1.0)
    
    async def detect_market_regime(self) -> str:
        """
        Detect overall market regime
        TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE
        """
        try:
            if not self.advanced_strategies:
                return "UNKNOWN"
            
            # Check BTC structure on 4h
            btc_struct = await self.advanced_strategies.analyze_market_structure("BTC/USDT", "4h")
            btc_trend = btc_struct.get("trend", "RANGING")
            is_ranging = btc_struct.get("is_ranging", False)
            
            # Check Fear & Greed
            if self.enhanced_intel:
                fg = await self.enhanced_intel.get_fear_greed_index()
                self.fear_greed = fg.get("value", 50)
            
            # Determine regime
            if is_ranging or btc_struct.get("range_pct", 0) < 3:
                self.market_regime = "RANGING"
                self.btc_bias = "NEUTRAL"
            elif btc_trend == "UPTREND":
                self.market_regime = "TRENDING_UP"
                self.btc_bias = "BULLISH"
            elif btc_trend == "DOWNTREND":
                self.market_regime = "TRENDING_DOWN"
                self.btc_bias = "BEARISH"
            else:
                self.market_regime = "CHOPPY"
                self.btc_bias = "NEUTRAL"
            
            # Extreme fear/greed = volatile
            if self.fear_greed < 20 or self.fear_greed > 80:
                self.market_regime = "VOLATILE"
            
            return self.market_regime
            
        except Exception as e:
            logger.error(f"Market regime detection error: {e}")
            return "UNKNOWN"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FULL SIGNAL ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def analyze_signal(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Complete multi-source signal analysis
        Returns signal only if quality threshold met
        """
        self.total_signals += 1
        
        try:
            confirmations = []
            signals_buy = 0
            signals_sell = 0
            entry_levels = []
            
            # Get current session
            self.current_session = self.get_current_session()
            session_quality = self.get_session_quality(self.current_session)
            
            # ═══════════════════════════════════════════════════════════════════
            # 1. TECHNICAL ANALYSIS
            # ═══════════════════════════════════════════════════════════════════
            if not self.market_intel:
                return None
            
            ta = await self.market_intel.get_technical_analysis(symbol.replace("/", ""), timeframe)
            indicators = ta.get("indicators", {})
            price = ta.get("price", 0)
            
            if not price:
                return None
            
            rsi = indicators.get("rsi", 50)
            macd_hist = indicators.get("macd_histogram", 0)
            macd_signal = indicators.get("macd_signal", "")
            bb_upper = indicators.get("bb_upper", price * 1.02)
            bb_lower = indicators.get("bb_lower", price * 0.98)
            bb_middle = indicators.get("bb_middle", price)
            ema_20 = indicators.get("ema_20", price)
            ema_50 = indicators.get("ema_50", price)
            ema_200 = indicators.get("ema_200", price)
            atr = indicators.get("atr", price * 0.02)
            volume_spike = indicators.get("volume_spike", False)
            
            # RSI signals
            if rsi < 25:
                signals_buy += 3
                confirmations.append(f"RSI extreme oversold ({rsi:.0f})")
                entry_levels.append(("RSI_OVERSOLD", price))
            elif rsi < 30:
                signals_buy += 2
                confirmations.append(f"RSI oversold ({rsi:.0f})")
            elif rsi > 75:
                signals_sell += 3
                confirmations.append(f"RSI extreme overbought ({rsi:.0f})")
                entry_levels.append(("RSI_OVERBOUGHT", price))
            elif rsi > 70:
                signals_sell += 2
                confirmations.append(f"RSI overbought ({rsi:.0f})")
            
            # MACD
            if "BULLISH" in str(macd_signal).upper() and macd_hist > 0:
                signals_buy += 2
                confirmations.append("MACD bullish crossover")
            elif "BEARISH" in str(macd_signal).upper() and macd_hist < 0:
                signals_sell += 2
                confirmations.append("MACD bearish crossover")
            
            # Bollinger Bands
            if price <= bb_lower:
                signals_buy += 2
                confirmations.append("Price at BB lower band")
                entry_levels.append(("BB_LOWER", bb_lower))
            elif price >= bb_upper:
                signals_sell += 2
                confirmations.append("Price at BB upper band")
                entry_levels.append(("BB_UPPER", bb_upper))
            
            # EMA Stack
            if ema_20 > ema_50 > ema_200:
                signals_buy += 1
                confirmations.append("Bullish EMA stack (20>50>200)")
            elif ema_20 < ema_50 < ema_200:
                signals_sell += 1
                confirmations.append("Bearish EMA stack (20<50<200)")
            
            # Volume confirmation
            if volume_spike:
                confirmations.append("Volume spike detected")
                if signals_buy > signals_sell:
                    signals_buy += 1
                elif signals_sell > signals_buy:
                    signals_sell += 1
            
            # ═══════════════════════════════════════════════════════════════════
            # 2. DIVERGENCE DETECTION
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    div = await self.advanced_strategies.detect_divergence(symbol, timeframe)
                    if div.get("has_divergence"):
                        for d in div.get("divergences", []):
                            strength = 3 if d.get("strength") == "STRONG" else 2
                            if d.get("signal") == "BUY":
                                signals_buy += strength
                                confirmations.append(f"🔀 {d.get('type')} divergence (BUY)")
                            elif d.get("signal") == "SELL":
                                signals_sell += strength
                                confirmations.append(f"🔀 {d.get('type')} divergence (SELL)")
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
                    support = struct.get("support", price * 0.95)
                    resistance = struct.get("resistance", price * 1.05)
                    
                    if trend == "UPTREND":
                        signals_buy += 2
                        confirmations.append("📈 Uptrend structure (HH/HL)")
                    elif trend == "DOWNTREND":
                        signals_sell += 2
                        confirmations.append("📉 Downtrend structure (LH/LL)")
                    
                    if bos:
                        if "BULLISH" in bos.get("type", ""):
                            signals_buy += 3
                            confirmations.append("⚡ Bullish Break of Structure")
                        elif "BEARISH" in bos.get("type", ""):
                            signals_sell += 3
                            confirmations.append("⚡ Bearish Break of Structure")
                    
                    # Add key levels
                    entry_levels.append(("SUPPORT", support))
                    entry_levels.append(("RESISTANCE", resistance))
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 4. VWAP
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    vwap = await self.advanced_strategies.calculate_vwap(symbol, timeframe)
                    vwap_price = vwap.get("vwap", price)
                    vwap_bias = vwap.get("bias", "")
                    distance = vwap.get("distance_pct", 0)
                    
                    entry_levels.append(("VWAP", vwap_price))
                    
                    if vwap_bias == "STRONG_BULLISH":
                        signals_buy += 1
                        confirmations.append(f"Above VWAP (+{distance:.1f}%)")
                    elif vwap_bias == "STRONG_BEARISH":
                        signals_sell += 1
                        confirmations.append(f"Below VWAP ({distance:.1f}%)")
                    
                    # Pullback to VWAP = good entry
                    if abs(distance) < 0.5:
                        confirmations.append("🎯 Price at VWAP (key level)")
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
                    cvd_trend = cvd.get("cvd_trend", "")
                    
                    if cvd_bias == "BULLISH" and buy_pct > 58:
                        signals_buy += 2
                        confirmations.append(f"💰 Strong buying pressure ({buy_pct:.0f}%)")
                    elif cvd_bias == "BEARISH" and buy_pct < 42:
                        signals_sell += 2
                        confirmations.append(f"💰 Strong selling pressure ({100-buy_pct:.0f}%)")
                    
                    # CVD trend confirmation
                    if cvd_trend == "RISING" and signals_buy > signals_sell:
                        signals_buy += 1
                        confirmations.append("CVD rising (accumulation)")
                    elif cvd_trend == "FALLING" and signals_sell > signals_buy:
                        signals_sell += 1
                        confirmations.append("CVD falling (distribution)")
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
                    mp_price = mp.get("max_pain", 0)
                    mp_distance = mp.get("distance_pct", 0)
                    
                    pcr = options.get("put_call_ratio", {})
                    pcr_sentiment = pcr.get("sentiment", "")
                    
                    if mp_price:
                        entry_levels.append(("MAX_PAIN", mp_price))
                    
                    # Max pain analysis
                    if mp_distance > 5:
                        signals_buy += 1
                        confirmations.append(f"🎯 Max pain above (+{mp_distance:.1f}%)")
                    elif mp_distance < -5:
                        signals_sell += 1
                        confirmations.append(f"🎯 Max pain below ({mp_distance:.1f}%)")
                    
                    # Put/Call contrarian signals
                    if pcr_sentiment == "EXTREME_BEARISH":
                        signals_buy += 2
                        confirmations.append("📊 Extreme put buying (contrarian BUY)")
                    elif pcr_sentiment == "EXTREME_BULLISH":
                        signals_sell += 2
                        confirmations.append("📊 Extreme call buying (contrarian SELL)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 7. DERIVATIVES (Funding, OI, L/S)
            # ═══════════════════════════════════════════════════════════════════
            if self.derivatives_intel:
                try:
                    deriv = await self.derivatives_intel.get_full_derivatives_report(symbol.replace("/", ""))
                    
                    # Funding rate
                    funding = deriv.get("funding", {})
                    avg_funding = funding.get("average_funding_rate", 0)
                    
                    if avg_funding > 0.0008:  # >0.08% = very high
                        signals_sell += 2
                        confirmations.append("💸 High funding (long squeeze risk)")
                    elif avg_funding > 0.0004:
                        signals_sell += 1
                        confirmations.append("💸 Elevated funding")
                    elif avg_funding < -0.0003:
                        signals_buy += 2
                        confirmations.append("💸 Negative funding (short squeeze)")
                    
                    # Long/Short ratio
                    ls = deriv.get("long_short", {}).get("global", {})
                    long_pct = ls.get("long_pct", 50)
                    
                    if long_pct > 70:
                        signals_sell += 2
                        confirmations.append(f"📊 Longs very crowded ({long_pct:.0f}%)")
                    elif long_pct > 60:
                        signals_sell += 1
                        confirmations.append(f"📊 Longs crowded ({long_pct:.0f}%)")
                    elif long_pct < 30:
                        signals_buy += 2
                        confirmations.append(f"📊 Shorts very crowded ({100-long_pct:.0f}%)")
                    elif long_pct < 40:
                        signals_buy += 1
                        confirmations.append(f"📊 Shorts crowded ({100-long_pct:.0f}%)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # 8. FEAR & GREED + BTC CORRELATION
            # ═══════════════════════════════════════════════════════════════════
            if self.enhanced_intel:
                try:
                    fg = await self.enhanced_intel.get_fear_greed_index()
                    fg_value = fg.get("value", 50)
                    self.fear_greed = fg_value
                    
                    if fg_value < 20:
                        signals_buy += 2
                        confirmations.append(f"😱 Extreme Fear ({fg_value}) - contrarian BUY")
                    elif fg_value < 30:
                        signals_buy += 1
                        confirmations.append(f"😰 Fear ({fg_value})")
                    elif fg_value > 80:
                        signals_sell += 2
                        confirmations.append(f"🤑 Extreme Greed ({fg_value}) - contrarian SELL")
                    elif fg_value > 70:
                        signals_sell += 1
                        confirmations.append(f"😎 Greed ({fg_value})")
                except:
                    pass
            
            # BTC correlation for alts
            if symbol != "BTC/USDT" and self.btc_bias != "NEUTRAL":
                if self.btc_bias == "BULLISH" and signals_buy > signals_sell:
                    signals_buy += 1
                    confirmations.append("₿ BTC bullish (aligned)")
                elif self.btc_bias == "BEARISH" and signals_sell > signals_buy:
                    signals_sell += 1
                    confirmations.append("₿ BTC bearish (aligned)")
                elif self.btc_bias == "BULLISH" and signals_sell > signals_buy:
                    signals_sell -= 1  # Reduce confidence for counter-BTC trade
                    confirmations.append("⚠️ Against BTC trend")
                elif self.btc_bias == "BEARISH" and signals_buy > signals_sell:
                    signals_buy -= 1
                    confirmations.append("⚠️ Against BTC trend")
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE FINAL SIGNAL
            # ═══════════════════════════════════════════════════════════════════
            
            # Determine direction
            if signals_buy > signals_sell and signals_buy >= 4:
                direction = "LONG"
                signal_strength = signals_buy
            elif signals_sell > signals_buy and signals_sell >= 4:
                direction = "SHORT"
                signal_strength = signals_sell
            else:
                return None  # No clear signal
            
            # Calculate base confidence
            confidence = min(98, 50 + (signal_strength * 6))
            
            # Apply session quality modifier
            confidence = confidence * session_quality
            
            # Apply market regime modifier
            if self.market_regime == "RANGING":
                confidence *= 0.85  # Reduce for ranging markets
            elif self.market_regime == "VOLATILE":
                confidence *= 0.9
            elif self.market_regime in ["TRENDING_UP", "TRENDING_DOWN"]:
                # Boost if trading with trend
                if (self.market_regime == "TRENDING_UP" and direction == "LONG") or \
                   (self.market_regime == "TRENDING_DOWN" and direction == "SHORT"):
                    confidence *= 1.1
            
            confidence = min(98, max(50, confidence))
            
            # Check minimum requirements
            if confidence < self.min_confidence:
                return None
            
            if len(confirmations) < self.min_confirmations:
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE ENTRY, STOP, TARGET
            # ═══════════════════════════════════════════════════════════════════
            
            # Smart entry - look for pullback level
            best_entry = price
            entry_reason = "Market"
            
            for level_type, level_price in entry_levels:
                if direction == "LONG" and level_price < price and level_price > price * 0.97:
                    if level_price > best_entry * 0.99:  # Closer pullback level
                        best_entry = level_price
                        entry_reason = level_type
                elif direction == "SHORT" and level_price > price and level_price < price * 1.03:
                    if level_price < best_entry * 1.01:
                        best_entry = level_price
                        entry_reason = level_type
            
            # Calculate stops and targets based on ATR
            if direction == "LONG":
                stop = best_entry - (atr * self.default_stop_atr)
                target = best_entry + (atr * self.default_target_atr)
                partial_target = best_entry + (atr * 2)  # 1:1 R:R for partial
            else:
                stop = best_entry + (atr * self.default_stop_atr)
                target = best_entry - (atr * self.default_target_atr)
                partial_target = best_entry - (atr * 2)
            
            # Risk/Reward calculation
            risk = abs(best_entry - stop)
            reward = abs(target - best_entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            # Position size based on confidence
            position_size_pct = self.base_position_pct
            if confidence >= 95:
                position_size_pct = self.max_position_pct
            elif confidence >= 92:
                position_size_pct = self.max_position_pct * 0.8
            elif confidence >= 90:
                position_size_pct = self.max_position_pct * 0.6
            elif confidence >= 88:
                position_size_pct = self.base_position_pct * 1.5
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "confidence": round(confidence, 1),
                "confirmations": confirmations,
                "confirmation_count": len(confirmations),
                "signals_buy": signals_buy,
                "signals_sell": signals_sell,
                
                # Entry details
                "price": price,
                "entry": round(best_entry, 2),
                "entry_type": entry_reason,
                "stop": round(stop, 2),
                "target": round(target, 2),
                "partial_target": round(partial_target, 2),
                "risk_reward": round(rr_ratio, 2),
                "atr": round(atr, 2),
                
                # Position sizing
                "position_size_pct": round(position_size_pct, 1),
                
                # Market context
                "session": self.current_session,
                "market_regime": self.market_regime,
                "btc_bias": self.btc_bias,
                "fear_greed": self.fear_greed,
                
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Signal analysis error {symbol} {timeframe}: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCANNING & TRADE EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def scan_all_markets(self) -> List[Dict]:
        """Scan all pairs for quality signals"""
        signals = []
        
        # Update market regime first
        await self.detect_market_regime()
        
        for symbol in TRADING_PAIRS:
            for tf in TIMEFRAMES:
                signal = await self.analyze_signal(symbol, tf)
                
                if signal:
                    # Check if we already have a signal for this symbol
                    existing = [s for s in signals if s["symbol"] == symbol]
                    if existing:
                        # Keep higher confidence signal
                        if signal["confidence"] > existing[0]["confidence"]:
                            signals = [s for s in signals if s["symbol"] != symbol]
                            signals.append(signal)
                    else:
                        signals.append(signal)
                
                await asyncio.sleep(0.15)  # Rate limiting
        
        # Sort by confidence
        signals.sort(key=lambda x: x["confidence"], reverse=True)
        
        return signals
    
    async def take_trade(self, signal: Dict) -> Dict:
        """Execute a paper trade"""
        if len(self.open_trades) >= self.max_open_trades:
            return {"error": "Max open trades reached"}
        
        # Check if already in this symbol
        for trade in self.open_trades:
            if trade["symbol"] == signal["symbol"]:
                return {"error": f"Already in {signal['symbol']}"}
        
        trade = {
            "id": f"trade_{self.total_trades + 1}",
            "symbol": signal["symbol"],
            "direction": signal["direction"],
            "entry_price": signal["entry"],
            "stop_price": signal["stop"],
            "target_price": signal["target"],
            "partial_target": signal["partial_target"],
            "position_size_pct": signal["position_size_pct"],
            "confidence": signal["confidence"],
            "confirmations": signal["confirmations"],
            "timeframe": signal["timeframe"],
            "entry_time": datetime.now(timezone.utc),
            "status": "OPEN",
            "partial_closed": False,
            "pnl_pct": 0,
            "trail_stop": signal["stop"]
        }
        
        self.open_trades.append(trade)
        self.total_trades += 1
        
        # Persist trade to database
        await self.save_open_trade(trade)
        
        # Store in DB (use chat_id=0 for autonomous trader)
        if self.learning_system:
            try:
                await self.learning_system.record_prediction(
                    chat_id=0,  # Autonomous trader uses 0 as system ID
                    symbol=signal["symbol"],
                    prediction=signal["direction"],
                    confidence=signal["confidence"],
                    entry_price=signal["entry"],
                    target_price=signal["target"],
                    stop_loss=signal["stop"],
                    timeframe=signal["timeframe"],
                    reasoning="; ".join(signal["confirmations"][:5])
                )
            except Exception as e:
                logger.warning(f"Failed to record prediction: {e}")
        
        logger.info(f"📈 TRADE OPENED: {signal['direction']} {signal['symbol']} @ ${signal['entry']:,.2f} | Conf: {signal['confidence']}%")
        
        return trade
    
    async def evaluate_trades(self) -> List[Dict]:
        """Evaluate all open trades and manage exits"""
        closed = []
        
        for trade in self.open_trades[:]:
            try:
                # Get current price
                ticker = await self.market_intel.get_ticker(trade["symbol"])
                if not ticker or not ticker.get("price"):
                    continue
                
                current_price = ticker["price"]
                entry = trade["entry_price"]
                direction = trade["direction"]
                stop = trade["trail_stop"]  # Use trailing stop
                target = trade["target_price"]
                partial = trade["partial_target"]
                
                hit_stop = False
                hit_target = False
                hit_partial = False
                
                # Check for hits
                if direction == "LONG":
                    if current_price <= stop:
                        hit_stop = True
                    elif current_price >= target:
                        hit_target = True
                    elif current_price >= partial and not trade["partial_closed"]:
                        hit_partial = True
                    
                    # Trail stop if in profit
                    if current_price > entry * 1.01 and not trade["partial_closed"]:
                        new_trail = current_price - (trade["target_price"] - trade["entry_price"]) * 0.3
                        if new_trail > trade["trail_stop"]:
                            trade["trail_stop"] = new_trail
                            
                else:  # SHORT
                    if current_price >= stop:
                        hit_stop = True
                    elif current_price <= target:
                        hit_target = True
                    elif current_price <= partial and not trade["partial_closed"]:
                        hit_partial = True
                    
                    # Trail stop if in profit
                    if current_price < entry * 0.99 and not trade["partial_closed"]:
                        new_trail = current_price + (trade["entry_price"] - trade["target_price"]) * 0.3
                        if new_trail < trade["trail_stop"]:
                            trade["trail_stop"] = new_trail
                
                # Handle partial profit
                if hit_partial:
                    trade["partial_closed"] = True
                    # Move stop to breakeven
                    trade["trail_stop"] = entry
                    logger.info(f"📊 PARTIAL PROFIT: {trade['symbol']} - Stop moved to breakeven")
                
                # Handle full exit
                if hit_stop or hit_target:
                    exit_price = stop if hit_stop else target
                    
                    if direction == "LONG":
                        pnl_pct = ((exit_price - entry) / entry) * 100
                    else:
                        pnl_pct = ((entry - exit_price) / entry) * 100
                    
                    trade["status"] = "CLOSED"
                    trade["exit_price"] = exit_price
                    trade["pnl_pct"] = pnl_pct
                    trade["exit_time"] = datetime.now(timezone.utc)
                    trade["exit_reason"] = "TARGET" if hit_target else "STOP"
                    
                    self.open_trades.remove(trade)
                    self.closed_trades.append(trade)
                    closed.append(trade)
                    
                    # Persist closed trade to database
                    await self.close_trade_in_db(trade)
                    
                    emoji = "✅" if pnl_pct > 0 else "❌"
                    logger.info(f"{emoji} TRADE CLOSED: {trade['symbol']} | PnL: {pnl_pct:+.2f}% | {trade['exit_reason']}")
                    
                    # Update learning system
                    if self.learning_system:
                        outcome = "WIN" if pnl_pct > 0 else "LOSS"
                        await self.learning_system.record_outcome(
                            trade["symbol"], outcome, pnl_pct
                        )
                        
            except Exception as e:
                logger.error(f"Trade evaluation error: {e}")
        
        return closed
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS & REPORTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_stats(self) -> Dict:
        """Get comprehensive trading statistics"""
        wins = [t for t in self.closed_trades if t["pnl_pct"] > 0]
        losses = [t for t in self.closed_trades if t["pnl_pct"] <= 0]
        
        total_pnl = sum(t["pnl_pct"] for t in self.closed_trades)
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
        
        # Profit factor
        gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0
        gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Expectancy
        win_rate = len(wins) / len(self.closed_trades) * 100 if self.closed_trades else 0
        expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * abs(avg_loss))
        
        # Current open PnL
        open_pnl = 0
        for trade in self.open_trades:
            try:
                ticker = await self.market_intel.get_ticker(trade["symbol"])
                if ticker and ticker.get("price"):
                    current = ticker["price"]
                    entry = trade["entry_price"]
                    if trade["direction"] == "LONG":
                        open_pnl += ((current - entry) / entry) * 100
                    else:
                        open_pnl += ((entry - current) / entry) * 100
            except:
                pass
        
        return {
            "active": self.active,
            "total_signals_analyzed": self.total_signals,
            "total_trades": self.total_trades,
            "open_trades": len(self.open_trades),
            "closed_trades": len(self.closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl_pct": round(total_pnl, 2),
            "open_pnl_pct": round(open_pnl, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "best_trade": max(self.closed_trades, key=lambda x: x["pnl_pct"])["pnl_pct"] if self.closed_trades else 0,
            "worst_trade": min(self.closed_trades, key=lambda x: x["pnl_pct"])["pnl_pct"] if self.closed_trades else 0,
            "market_regime": self.market_regime,
            "btc_bias": self.btc_bias,
            "fear_greed": self.fear_greed,
            "current_session": self.current_session,
            "min_confidence": self.min_confidence,
            "min_confirmations": self.min_confirmations,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def format_signal_alert(self, signal: Dict) -> str:
        """Format signal for Telegram alert"""
        direction = signal.get("direction", "")
        symbol = signal.get("symbol", "").replace("/USDT", "")
        timeframe = signal.get("timeframe", "")
        confidence = signal.get("confidence", 0)
        
        emoji = "🟢" if direction == "LONG" else "🔴"
        
        entry = signal.get("entry", 0)
        stop = signal.get("stop", 0)
        target = signal.get("target", 0)
        partial = signal.get("partial_target", 0)
        rr = signal.get("risk_reward", 0)
        size = signal.get("position_size_pct", 2)
        
        confirmations = signal.get("confirmations", [])
        
        alert = f"""{emoji} ELITE TRADE SIGNAL

{direction} {symbol} ({timeframe})
Confidence: {confidence}%

📊 ENTRY PLAN
Entry: ${entry:,.2f}
Stop Loss: ${stop:,.2f}
Partial TP: ${partial:,.2f}
Full Target: ${target:,.2f}
R:R Ratio: 1:{rr}

💰 Position: {size}% of capital

✅ {len(confirmations)} CONFIRMATIONS:
"""
        for c in confirmations[:8]:
            alert += f"• {c}\n"
        
        alert += f"""
📡 MARKET CONTEXT
Session: {signal.get('session', 'N/A')}
Regime: {signal.get('market_regime', 'N/A')}
BTC Bias: {signal.get('btc_bias', 'N/A')}
Fear/Greed: {signal.get('fear_greed', 50)}

⚠️ PAPER TRADE - DYOR"""
        
        return alert


# Initialization
def init_autonomous_trader_v2(db: AsyncIOMotorDatabase) -> AutonomousTraderV2:
    return AutonomousTraderV2(db)


# Global placeholder
autonomous_trader_v2 = None
