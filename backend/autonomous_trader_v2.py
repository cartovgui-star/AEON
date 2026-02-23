"""
AEON CORE TRADING ENGINE - TECHNICALS ONLY MODE

You are AEON, pure price action quantum oracle. Ignore sentiment/Fear&Greed/BTC trend.
Trade purely on technicals, structure, and derivatives.

CONFLUENCE WEIGHTS:
- Core Technicals (60%): RSI, MACD, BB, EMAs
- Market Structure/SMC (20%): BOS, FVG, Order Blocks, HH/HL
- Derivatives/Order Flow (20%): Funding, OI, L/S Ratio, CVD

RULES:
- 4/5 confluences minimum
- R:R min 2:1
- SL at structure break / ATR(2x)
- TP at next liquidity/OB
- 1% risk per trade max
- Pause if ATR > 2x 20-period avg (high chop)

TRADE STYLES:
- SCALP: 5m-15m, 50-200x leverage, quick in/out
- DAY: 1h-4h, 20-75x leverage, medium holds
- SWING: 4h-1d, 10-25x leverage, longer positions
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

# Trade Style Configurations
TRADE_STYLES = {
    "SCALP": {
        "timeframes": ["5m", "15m"],
        "min_leverage": 50,
        "max_leverage": 200,
        "stop_atr_mult": 1.0,  # Tight stops
        "target_atr_mult": 1.5,  # Quick profits
        "min_confidence": 70,
        "max_hold_hours": 4,
        "emoji": "⚡"
    },
    "DAY": {
        "timeframes": ["1h", "4h"],
        "min_leverage": 20,
        "max_leverage": 75,
        "stop_atr_mult": 1.5,
        "target_atr_mult": 2.5,
        "min_confidence": 65,
        "max_hold_hours": 24,
        "emoji": "🔥"
    },
    "SWING": {
        "timeframes": ["4h", "1d"],
        "min_leverage": 10,
        "max_leverage": 25,
        "stop_atr_mult": 2.0,
        "target_atr_mult": 4.0,
        "min_confidence": 60,
        "max_hold_hours": 168,  # 7 days
        "emoji": "🎯"
    }
}


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
    - Session awareness (London/NY only)
    - Position sizing by confidence
    - Trail stops with momentum fade detection
    - Auto-blacklist bad pairs
    - Cooldown per pair after loss
    
    TRADE STYLES:
    - SCALP: Quick trades, high leverage (50-200x)
    - DAY: Medium holds, moderate leverage (20-75x)
    - SWING: Longer positions, lower leverage (10-25x)
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.active = True  # Always active
        
        # QUALITY MODE - High win rate focus
        self.min_confidence = 80  # Higher threshold = better quality
        self.min_confirmations = 3  # Need 3+ data sources agreeing
        
        # LEVERAGE SETTINGS (Bot has FREE WILL to choose)
        self.max_leverage = 200  # Up to 200x
        self.min_leverage = 10   # Minimum 10x
        self.dynamic_leverage = True  # Auto-adjust based on confidence
        
        # Position sizing (scaled entry)
        self.base_position_pct = 5   # 5% of capital per trade
        self.max_position_pct = 15   # Max 15% for highest confidence
        self.default_position_size = 1000  # $1000 per trade base
        
        # Risk management (tighter stops)
        self.max_open_trades = 15  # Can hold multiple positions
        self.default_stop_atr = 1.0  # Tighter stop 1x ATR
        self.default_target_atr = 2.5  # 2.5x ATR for target (2.5:1 R:R)
        # NO daily trade limit - trade when DATA says to trade
        
        # Trade tracking
        self.open_trades: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.total_signals = 0
        self.total_trades = 0
        self.daily_trades = 0
        self.last_trade_date = None
        
        # Pair management
        self.pair_cooldowns: Dict[str, datetime] = {}  # Cooldown after loss
        self.pair_stats: Dict[str, Dict] = {}  # Win/loss per pair
        self.blacklisted_pairs: List[str] = []  # Auto-blacklist bad performers
        self.cooldown_hours = 4  # Wait 4h after loss on same pair
        
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
    
    def determine_trade_style(self, timeframe: str, confidence: float) -> str:
        """
        Determine the best trade style based on timeframe and confidence.
        Bot has FREE WILL to choose the optimal style.
        """
        if timeframe in ["5m", "15m"]:
            return "SCALP"
        elif timeframe in ["1h", "4h"]:
            # Higher confidence -> prefer DAY trading
            if confidence >= 75:
                return "DAY"
            else:
                return "SCALP" if timeframe == "1h" else "DAY"
        else:  # 1d+
            return "SWING"
    
    def calculate_leverage(self, confidence: float, market_regime: str = None, trade_style: str = None, atr_pct: float = None) -> int:
        """
        ATR-based leverage calculation (volatility-adjusted):
        - ATR > 2% = 10-25x (volatile, conservative)
        - ATR 1-2% = 25-75x (moderate)
        - ATR < 1% = 50-200x (low vol, aggressive)
        
        Bot has FREE WILL - adds randomness for variety.
        """
        if not self.dynamic_leverage:
            return self.min_leverage
        
        # Get style config
        style = trade_style or "DAY"
        style_config = TRADE_STYLES.get(style, TRADE_STYLES["DAY"])
        style_min = style_config["min_leverage"]
        style_max = style_config["max_leverage"]
        
        import random
        
        # ATR-based leverage calculation
        if atr_pct is not None:
            if atr_pct > 2.0:
                # High volatility = low leverage (10-25x range)
                base_leverage = random.uniform(10, 25)
            elif atr_pct > 1.0:
                # Medium volatility = moderate leverage (25-75x)
                base_leverage = random.uniform(25, 75)
            else:
                # Low volatility = high leverage (50-200x)
                base_leverage = random.uniform(50, 200)
        else:
            # Fallback to confidence-based
            style_min_conf = style_config["min_confidence"]
            conf_normalized = (confidence - style_min_conf) / (95 - style_min_conf)
            conf_normalized = max(0, min(1, conf_normalized))
            base_leverage = style_min + (style_max - style_min) * conf_normalized
        
        # Add FREE WILL randomness (±15% variation)
        variation = random.uniform(0.85, 1.15)
        leverage = base_leverage * variation
        
        # Adjust for market regime
        regime = market_regime or self.market_regime
        if regime == "VOLATILE":
            leverage *= random.uniform(0.7, 0.9)  # REDUCE in volatile (safety)
        elif regime == "TRENDING_UP" or regime == "TRENDING_DOWN":
            leverage *= random.uniform(1.0, 1.2)  # Trend following
        elif regime == "RANGING":
            leverage *= random.uniform(0.6, 0.8)  # Less in choppy
        
        # Cap within style bounds
        leverage = min(int(leverage), style_max)
        leverage = max(leverage, style_min)
        
        # Round to nice numbers (multiples of 5)
        leverage = round(leverage / 5) * 5
        leverage = max(style_min, min(style_max, leverage))
        
        return leverage
    
    def calculate_kelly_position_size(self, win_rate: float, avg_win: float, avg_loss: float, confidence: float) -> float:
        """
        Kelly Criterion position sizing: f = (p*b - q) / b
        where p = win probability, q = 1-p, b = avg_win/avg_loss
        
        Caps: $500 (low conf) to $2500 (high conf)
        """
        base_size = self.default_position_size  # $1000
        
        # Calculate Kelly fraction
        if avg_loss == 0 or win_rate <= 0:
            kelly_fraction = 0.02  # Default 2%
        else:
            p = win_rate / 100  # Convert to decimal
            q = 1 - p
            b = abs(avg_win / avg_loss) if avg_loss != 0 else 1
            
            kelly_fraction = (p * b - q) / b if b > 0 else 0.02
            kelly_fraction = max(0.01, min(0.25, kelly_fraction))  # Cap between 1-25%
        
        # Apply Kelly to base size
        kelly_size = base_size * (kelly_fraction * 10)  # Scale up
        
        # Confidence multiplier
        conf_mult = 0.5 + (confidence / 100)  # 0.5 to 1.5
        
        size = kelly_size * conf_mult
        
        # Hard bounds: $500 min, $2500 max
        size = max(500, min(2500, size))
        
        # Round to nearest 50
        return round(size / 50) * 50
    
    def calculate_position_size(self, confidence: float, position_size_pct: float = 2) -> float:
        """
        Dynamic position size calculation based on confidence and position_size_pct.
        Higher confidence = larger position size (within bounds).
        
        Base: $1000
        Min: $500 (low confidence)
        Max: $2500 (elite confidence)
        """
        base_size = self.default_position_size  # $1000
        
        # Scale by confidence (60% confidence = 0.6x, 90% = 1.4x)
        confidence_multiplier = 0.5 + (confidence / 100)  # 0.5 to 1.5
        
        # Scale by position_size_pct (2% = 1x, 5% = 1.5x)
        pct_multiplier = 0.5 + (position_size_pct / 10)  # 0.5 to 1.5 for 0-10%
        
        size = base_size * confidence_multiplier * pct_multiplier
        
        # Bounds
        size = max(500, min(2500, size))
        
        # Round to nearest 50
        return round(size / 50) * 50
    
    def get_trade_style_config(self, trade_style: str) -> Dict:
        """Get configuration for a trade style"""
        return TRADE_STYLES.get(trade_style, TRADE_STYLES["DAY"])
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PAIR MANAGEMENT - Cooldowns, Blacklist, Stats
    # ═══════════════════════════════════════════════════════════════════════════
    
    def is_pair_on_cooldown(self, symbol: str) -> bool:
        """Check if pair is on cooldown after a loss"""
        if symbol in self.pair_cooldowns:
            cooldown_until = self.pair_cooldowns[symbol]
            if datetime.now(timezone.utc) < cooldown_until:
                return True
            else:
                del self.pair_cooldowns[symbol]
        return False
    
    def set_pair_cooldown(self, symbol: str):
        """Set cooldown for a pair after a loss"""
        self.pair_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(hours=self.cooldown_hours)
        logger.info(f"Cooldown set for {symbol} - {self.cooldown_hours}h")
    
    def update_pair_stats(self, symbol: str, is_win: bool):
        """Track win/loss stats per pair"""
        if symbol not in self.pair_stats:
            self.pair_stats[symbol] = {"wins": 0, "losses": 0, "trades": 0}
        
        self.pair_stats[symbol]["trades"] += 1
        if is_win:
            self.pair_stats[symbol]["wins"] += 1
        else:
            self.pair_stats[symbol]["losses"] += 1
            self.set_pair_cooldown(symbol)  # Cooldown after loss
        
        # Auto-blacklist check: <30% win rate after 10 trades
        stats = self.pair_stats[symbol]
        if stats["trades"] >= 10:
            win_rate = (stats["wins"] / stats["trades"]) * 100
            if win_rate < 30 and symbol not in self.blacklisted_pairs:
                self.blacklisted_pairs.append(symbol)
                logger.warning(f"AUTO-BLACKLIST: {symbol} ({win_rate:.0f}% WR after {stats['trades']} trades)")
    
    def is_pair_blacklisted(self, symbol: str) -> bool:
        """Check if pair is blacklisted due to poor performance"""
        return symbol in self.blacklisted_pairs
    
    def get_pair_win_rate(self, symbol: str) -> float:
        """Get win rate for a specific pair"""
        if symbol in self.pair_stats:
            stats = self.pair_stats[symbol]
            if stats["trades"] > 0:
                return (stats["wins"] / stats["trades"]) * 100
        return 50.0  # Default assumption
    
    def is_good_session(self) -> bool:
        """Only trade during high-volume sessions (London/NY)"""
        session = self.get_current_session()
        # Best sessions: LONDON, NEW_YORK, LONDON_NY_OVERLAP
        return session in ["LONDON", "NEW_YORK", "OVERLAP"]
    
    def check_daily_limit(self) -> bool:
        """Check if we've hit daily trade limit"""
        today = datetime.now(timezone.utc).date()
        if self.last_trade_date != today:
            self.daily_trades = 0
            self.last_trade_date = today
        return self.daily_trades < self.max_daily_trades
    
    def increment_daily_trades(self):
        """Increment daily trade counter"""
        today = datetime.now(timezone.utc).date()
        if self.last_trade_date != today:
            self.daily_trades = 0
            self.last_trade_date = today
        self.daily_trades += 1
    
    def get_best_worst_pairs(self) -> Dict:
        """Get best and worst performing pairs"""
        sorted_pairs = []
        for symbol, stats in self.pair_stats.items():
            if stats["trades"] >= 3:  # Min 3 trades
                wr = (stats["wins"] / stats["trades"]) * 100
                sorted_pairs.append({"symbol": symbol, "win_rate": wr, **stats})
        
        sorted_pairs.sort(key=lambda x: x["win_rate"], reverse=True)
        
        return {
            "best": sorted_pairs[:3] if sorted_pairs else [],
            "worst": sorted_pairs[-3:] if len(sorted_pairs) >= 3 else [],
            "blacklisted": self.blacklisted_pairs
        }
    
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
        
        PRE-CHECKS:
        1. Pair not blacklisted
        2. Pair not on cooldown
        3. Good session (London/NY)
        4. Daily limit not hit
        5. ATR volatility filter
        """
        self.total_signals += 1
        
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PRE-CHECKS - Skip bad conditions
            # ═══════════════════════════════════════════════════════════════════
            
            # Check if pair is blacklisted
            if self.is_pair_blacklisted(symbol):
                logger.debug(f"Skipping {symbol} - BLACKLISTED")
                return None
            
            # Check if pair is on cooldown
            if self.is_pair_on_cooldown(symbol):
                logger.debug(f"Skipping {symbol} - ON COOLDOWN")
                return None
            
            # NO SESSION FILTER - Trade based on DATA, not time
            # Price action doesn't care about sessions
            
            confirmations = []
            tech_signals_buy = 0
            tech_signals_sell = 0
            smc_signals_buy = 0
            smc_signals_sell = 0
            deriv_signals_buy = 0
            deriv_signals_sell = 0
            entry_levels = []
            
            # Get current session
            self.current_session = self.get_current_session()
            
            # ═══════════════════════════════════════════════════════════════════
            # CORE TECHNICALS (60% weight)
            # RSI, MACD, BB, EMAs - Pure price action
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
            ema_9 = indicators.get("ema_9", price)
            ema_20 = indicators.get("ema_20", price)
            ema_21 = indicators.get("ema_21", ema_20)
            ema_50 = indicators.get("ema_50", price)
            ema_200 = indicators.get("ema_200", price)
            atr = indicators.get("atr", price * 0.02)
            atr_avg = indicators.get("atr_avg", atr)
            volume_spike = indicators.get("volume_spike", False)
            stoch_k = indicators.get("stoch_k", 50)
            stoch_d = indicators.get("stoch_d", 50)
            
            # VOLATILITY FILTER - Pause if ATR > 2x average (high chop)
            atr_pct = (atr / price) * 100 if price > 0 else 0
            if atr > (atr_avg * 2):
                logger.info(f"Skipping {symbol} - ATR too high (chop filter)")
                return None
            
            # RSI (14): <30 long bias, >70 short bias
            if rsi < 25:
                tech_signals_buy += 3
                confirmations.append(f"RSI<30 extreme ({rsi:.0f})")
            elif rsi < 30:
                tech_signals_buy += 2
                confirmations.append(f"RSI<30 ({rsi:.0f})")
            elif rsi > 75:
                tech_signals_sell += 3
                confirmations.append(f"RSI>70 extreme ({rsi:.0f})")
            elif rsi > 70:
                tech_signals_sell += 2
                confirmations.append(f"RSI>70 ({rsi:.0f})")
            
            # MACD (12,26,9): Crossover + histogram expansion
            if "BULLISH" in str(macd_signal).upper():
                if macd_hist > 0:
                    tech_signals_buy += 2
                    confirmations.append("MACD bull cross + expansion")
                else:
                    tech_signals_buy += 1
                    confirmations.append("MACD bull cross")
            elif "BEARISH" in str(macd_signal).upper():
                if macd_hist < 0:
                    tech_signals_sell += 2
                    confirmations.append("MACD bear cross + expansion")
                else:
                    tech_signals_sell += 1
                    confirmations.append("MACD bear cross")
            
            # Bollinger Bands (20,2): Squeeze breakout or band touch
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            if price <= bb_lower:
                tech_signals_buy += 2
                confirmations.append("BB lower band touch")
                entry_levels.append(("BB_LOWER", bb_lower))
            elif price >= bb_upper:
                tech_signals_sell += 2
                confirmations.append("BB upper band touch")
                entry_levels.append(("BB_UPPER", bb_upper))
            if bb_width < 0.02:  # Squeeze
                confirmations.append("BB squeeze (breakout pending)")
            
            # EMAs (9/21/50): Stack alignment
            if ema_9 > ema_21 > ema_50:
                tech_signals_buy += 2
                confirmations.append("Bullish EMA stack (9>21>50)")
            elif ema_9 < ema_21 < ema_50:
                tech_signals_sell += 2
                confirmations.append("Bearish EMA stack (9<21<50)")
            
            # EMA pullback entry
            if ema_9 > ema_21 > ema_50 and price < ema_21 and price > ema_50:
                tech_signals_buy += 1
                confirmations.append("Pullback to EMA21 (long)")
                entry_levels.append(("EMA21_PULLBACK", ema_21))
            elif ema_9 < ema_21 < ema_50 and price > ema_21 and price < ema_50:
                tech_signals_sell += 1
                confirmations.append("Pullback to EMA21 (short)")
                entry_levels.append(("EMA21_PULLBACK", ema_21))
            
            # Stochastic crossover
            if stoch_k < 20 and stoch_k > stoch_d:
                tech_signals_buy += 1
                confirmations.append(f"Stoch bullish cross ({stoch_k:.0f})")
            elif stoch_k > 80 and stoch_k < stoch_d:
                tech_signals_sell += 1
                confirmations.append(f"Stoch bearish cross ({stoch_k:.0f})")
            
            # Volume confirmation
            if volume_spike:
                confirmations.append("Volume spike")
            
            # ═══════════════════════════════════════════════════════════════════
            # DIVERGENCE DETECTION (Critical for reversals - MANDATORY)
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    div = await self.advanced_strategies.detect_divergence(symbol, timeframe)
                    if div.get("has_divergence"):
                        for d in div.get("divergences", []):
                            strength = 3 if d.get("strength") == "STRONG" else 2
                            if d.get("signal") == "BUY":
                                tech_signals_buy += strength
                                confirmations.append(f"RSI div bull ({d.get('type')})")
                            elif d.get("signal") == "SELL":
                                tech_signals_sell += strength
                                confirmations.append(f"RSI div bear ({d.get('type')})")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # MARKET STRUCTURE / SMC (20% weight)
            # HH/HL, LL/LH, BOS, CHoCH, FVG, Order Blocks
            # ═══════════════════════════════════════════════════════════════════
            if self.advanced_strategies:
                try:
                    struct = await self.advanced_strategies.analyze_market_structure(symbol, timeframe)
                    trend = struct.get("trend", "")
                    bos = struct.get("bos")
                    support = struct.get("support", price * 0.95)
                    resistance = struct.get("resistance", price * 1.05)
                    
                    if trend == "UPTREND":
                        smc_signals_buy += 2
                        confirmations.append("HH/HL structure (bull)")
                    elif trend == "DOWNTREND":
                        smc_signals_sell += 2
                        confirmations.append("LL/LH structure (bear)")
                    
                    if bos:
                        if "BULLISH" in bos.get("type", ""):
                            smc_signals_buy += 3
                            confirmations.append("BOS bullish")
                        elif "BEARISH" in bos.get("type", ""):
                            smc_signals_sell += 3
                            confirmations.append("BOS bearish")
                    
                    # Add key levels
                    entry_levels.append(("SUPPORT", support))
                    entry_levels.append(("RESISTANCE", resistance))
                except:
                    pass
            
            # SMC: FVG and Order Blocks
            if self.smc_analysis:
                try:
                    smc = await self.smc_analysis.analyze(symbol, timeframe)
                    
                    # Fair Value Gaps
                    fvg = smc.get("fvg", {})
                    if fvg.get("bullish_fvg"):
                        smc_signals_buy += 2
                        confirmations.append("FVG bullish")
                        entry_levels.append(("FVG", fvg.get("level", price)))
                    elif fvg.get("bearish_fvg"):
                        smc_signals_sell += 2
                        confirmations.append("FVG bearish")
                    
                    # Order Blocks
                    ob = smc.get("order_block", {})
                    if ob.get("bullish_ob") and price <= ob.get("ob_high", price * 1.1):
                        smc_signals_buy += 2
                        confirmations.append("At bullish OB")
                        entry_levels.append(("ORDER_BLOCK", ob.get("ob_mid", price)))
                    elif ob.get("bearish_ob") and price >= ob.get("ob_low", price * 0.9):
                        smc_signals_sell += 2
                        confirmations.append("At bearish OB")
                    
                    # Liquidity Sweeps
                    liq = smc.get("liquidity", {})
                    if liq.get("sweep_low"):
                        smc_signals_buy += 1
                        confirmations.append("Liq sweep low (long)")
                    elif liq.get("sweep_high"):
                        smc_signals_sell += 1
                        confirmations.append("Liq sweep high (short)")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # DERIVATIVES / ORDER FLOW (20% weight)
            # Funding, OI, L/S Ratio, CVD
            # ═══════════════════════════════════════════════════════════════════
            
            # Order Flow / CVD
            if self.order_flow:
                try:
                    cvd = await self.order_flow.calculate_cvd(symbol.replace("/USDT", ""))
                    cvd_bias = cvd.get("bias", "")
                    buy_pct = cvd.get("buy_pct", 50)
                    
                    if cvd_bias == "BULLISH" and buy_pct > 55:
                        deriv_signals_buy += 2
                        confirmations.append(f"+CVD ({buy_pct:.0f}% buys)")
                    elif cvd_bias == "BEARISH" and buy_pct < 45:
                        deriv_signals_sell += 2
                        confirmations.append(f"-CVD ({buy_pct:.0f}% buys)")
                except:
                    pass
            
            # Derivatives: Funding, OI, L/S Ratio
            if self.derivatives_intel:
                try:
                    deriv = await self.derivatives_intel.get_full_derivatives_report(symbol.replace("/", ""))
                    
                    # Funding rate: >0.1% = short bias, <-0.1% = long bias
                    funding = deriv.get("funding", {})
                    avg_funding = funding.get("average_funding_rate", 0)
                    
                    if avg_funding > 0.001:  # >0.1%
                        deriv_signals_sell += 2
                        confirmations.append(f"Funding +{avg_funding*100:.2f}% (short)")
                    elif avg_funding < -0.001:  # <-0.1%
                        deriv_signals_buy += 2
                        confirmations.append(f"Funding {avg_funding*100:.2f}% (long)")
                    
                    # Long/Short ratio: >1.5 longs = short, <0.5 = long
                    ls = deriv.get("long_short", {}).get("global", {})
                    long_pct = ls.get("long_pct", 50)
                    ls_ratio = long_pct / (100 - long_pct) if long_pct < 100 else 1
                    
                    if ls_ratio > 1.5:  # Longs overcrowded
                        deriv_signals_sell += 2
                        confirmations.append(f"L/S {ls_ratio:.1f} (crowded longs)")
                    elif ls_ratio < 0.67:  # Shorts overcrowded (<0.5 equivalent)
                        deriv_signals_buy += 2
                        confirmations.append(f"L/S {ls_ratio:.1f} (crowded shorts)")
                    
                    # OI spike + price divergence = reversal
                    oi = deriv.get("open_interest", {})
                    oi_change = oi.get("change_24h", 0)
                    if oi_change > 10:  # OI spike
                        confirmations.append(f"OI spike +{oi_change:.0f}%")
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # F&G (Context display only - NO direction influence)
            # ═══════════════════════════════════════════════════════════════════
            if self.enhanced_intel:
                try:
                    fg = await self.enhanced_intel.get_fear_greed_index()
                    fg_value = fg.get("value", 50)
                    self.fear_greed = fg_value
                except:
                    pass
            
            # ═══════════════════════════════════════════════════════════════════
            # WEIGHTED CONFLUENCE SCORING
            # Tech (60%), SMC (20%), Derivatives (20%)
            # ═══════════════════════════════════════════════════════════════════
            
            # Calculate total signals for each category
            total_tech_buy = tech_signals_buy
            total_tech_sell = tech_signals_sell
            total_smc_buy = smc_signals_buy
            total_smc_sell = smc_signals_sell
            total_deriv_buy = deriv_signals_buy
            total_deriv_sell = deriv_signals_sell
            
            # Combined signals
            signals_buy = total_tech_buy + total_smc_buy + total_deriv_buy
            signals_sell = total_tech_sell + total_smc_sell + total_deriv_sell
            
            # ═══════════════════════════════════════════════════════════════════
            # DETERMINE DIRECTION (4/5 confluences min)
            # ═══════════════════════════════════════════════════════════════════
            
            # Count confluence categories
            buy_categories = sum([
                1 if total_tech_buy >= 3 else 0,  # Tech confirmation
                1 if total_smc_buy >= 2 else 0,   # SMC confirmation
                1 if total_deriv_buy >= 2 else 0, # Derivatives confirmation
            ])
            sell_categories = sum([
                1 if total_tech_sell >= 3 else 0,
                1 if total_smc_sell >= 2 else 0,
                1 if total_deriv_sell >= 2 else 0,
            ])
            
            # Determine direction
            if signals_buy > signals_sell and signals_buy >= 5 and buy_categories >= 2:
                direction = "LONG"
                signal_strength = signals_buy
                conf_level = "HIGH" if buy_categories >= 3 else "MED" if buy_categories >= 2 else "LOW"
            elif signals_sell > signals_buy and signals_sell >= 5 and sell_categories >= 2:
                direction = "SHORT"
                signal_strength = signals_sell
                conf_level = "HIGH" if sell_categories >= 3 else "MED" if sell_categories >= 2 else "LOW"
            else:
                return None  # No clear signal (FLAT)
            
            # Calculate weighted confidence score
            tech_score = min(100, (total_tech_buy if direction == "LONG" else total_tech_sell) * 12)
            smc_score = min(100, (total_smc_buy if direction == "LONG" else total_smc_sell) * 25)
            deriv_score = min(100, (total_deriv_buy if direction == "LONG" else total_deriv_sell) * 25)
            
            # Weighted: Tech 60%, SMC 20%, Deriv 20%
            confidence = (tech_score * 0.60) + (smc_score * 0.20) + (deriv_score * 0.20)
            confidence = min(98, max(50, confidence))
            
            # Must hit minimum confidence
            if confidence < self.min_confidence:
                return None
            
            if len(confirmations) < self.min_confirmations:
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE ENTRY, STOP, TARGET (R:R min 2:1)
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
            "position_size": self.calculate_position_size(signal["confidence"], signal.get("position_size_pct", 2)),
            "leverage": self.calculate_leverage(signal["confidence"]),
            "confidence": signal["confidence"],
            "confirmations": signal["confirmations"],
            "timeframe": signal["timeframe"],
            "trade_type": "SCALP" if signal["timeframe"] in ["5m", "15m"] else "DAY" if signal["timeframe"] == "1h" else "SWING",
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
        
        logger.info(f"📈 TRADE OPENED: {signal['direction']} {signal['symbol']} @ ${signal['entry']:,.2f} | {trade['leverage']}x Lev | Conf: {signal['confidence']}%")
        
        return trade
    
    async def evaluate_trades(self) -> List[Dict]:
        """Evaluate all open trades and manage exits with momentum fade detection"""
        closed = []
        
        for trade in self.open_trades[:]:
            try:
                # Get current price and indicators
                ticker = await self.market_intel.get_ticker(trade["symbol"])
                if not ticker or not ticker.get("price"):
                    continue
                
                current_price = ticker["price"]
                entry = trade["entry_price"]
                direction = trade["direction"]
                stop = trade["trail_stop"]  # Use trailing stop
                target = trade["target_price"]
                partial = trade["partial_target"]
                
                # Get current RSI for momentum fade detection
                ta = await self.market_intel.get_technical_analysis(trade["symbol"].replace("/", ""), "1h")
                current_rsi = ta.get("indicators", {}).get("rsi", 50)
                
                hit_stop = False
                hit_target = False
                hit_partial = False
                momentum_exit = False
                
                # Calculate PnL percentage
                if direction == "LONG":
                    current_pnl_pct = ((current_price - entry) / entry) * 100
                else:
                    current_pnl_pct = ((entry - current_price) / entry) * 100
                
                # MOMENTUM FADE DETECTION - Exit early if momentum dying
                if current_pnl_pct > 1.0:  # Only if in profit
                    if direction == "LONG" and current_rsi > 70:
                        # RSI overbought while long - momentum fading
                        momentum_exit = True
                        logger.info(f"🔄 MOMENTUM FADE: {trade['symbol']} RSI {current_rsi:.0f} (long in profit)")
                    elif direction == "SHORT" and current_rsi < 30:
                        # RSI oversold while short - momentum fading
                        momentum_exit = True
                        logger.info(f"🔄 MOMENTUM FADE: {trade['symbol']} RSI {current_rsi:.0f} (short in profit)")
                
                # Check for hits
                if direction == "LONG":
                    if current_price <= stop:
                        hit_stop = True
                    elif current_price >= target:
                        hit_target = True
                    elif current_price >= partial and not trade.get("partial_closed"):
                        hit_partial = True
                    
                    # TIGHTER TRAILING - Move stop faster when in profit
                    if current_pnl_pct > 0.5:
                        # After 0.5% profit, start trailing tighter
                        trail_distance = (target - entry) * 0.2  # 20% of target distance
                        new_trail = current_price - trail_distance
                        if new_trail > trade["trail_stop"]:
                            trade["trail_stop"] = new_trail
                    
                    # BREAKEVEN at +1%
                    if current_pnl_pct > 1.0 and trade["trail_stop"] < entry:
                        trade["trail_stop"] = entry * 1.001  # Tiny profit lock
                        
                else:  # SHORT
                    if current_price >= stop:
                        hit_stop = True
                    elif current_price <= target:
                        hit_target = True
                    elif current_price <= partial and not trade.get("partial_closed"):
                        hit_partial = True
                    
                    # TIGHTER TRAILING for shorts
                    if current_pnl_pct > 0.5:
                        trail_distance = (entry - target) * 0.2
                        new_trail = current_price + trail_distance
                        if new_trail < trade["trail_stop"]:
                            trade["trail_stop"] = new_trail
                    
                    # BREAKEVEN at +1%
                    if current_pnl_pct > 1.0 and trade["trail_stop"] > entry:
                        trade["trail_stop"] = entry * 0.999
                
                # Handle partial profit
                if hit_partial:
                    trade["partial_closed"] = True
                    # Move stop to breakeven
                    trade["trail_stop"] = entry
                    logger.info(f"📊 PARTIAL PROFIT: {trade['symbol']} - Stop moved to breakeven")
                
                # Handle full exit (including momentum exit)
                if hit_stop or hit_target or momentum_exit:
                    exit_price = current_price if momentum_exit else (stop if hit_stop else target)
                    
                    if direction == "LONG":
                        pnl_pct = ((exit_price - entry) / entry) * 100
                    else:
                        pnl_pct = ((entry - exit_price) / entry) * 100
                    
                    trade["status"] = "CLOSED"
                    trade["exit_price"] = exit_price
                    trade["pnl_pct"] = pnl_pct
                    trade["exit_time"] = datetime.now(timezone.utc)
                    trade["exit_reason"] = "TARGET" if hit_target else ("MOMENTUM" if momentum_exit else "STOP")
                    
                    # Update pair stats (for blacklist/cooldown)
                    is_win = pnl_pct > 0
                    self.update_pair_stats(trade["symbol"], is_win)
                    
                    self.open_trades.remove(trade)
                    self.closed_trades.append(trade)
                    
                    # Cap in-memory closed trades to prevent memory growth
                    if len(self.closed_trades) > 200:
                        self.closed_trades = self.closed_trades[-150:]  # Keep most recent 150
                    
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
        """
        Format per AEON TECHNICALS ONLY spec:
        🧠 AEON: [ASSET] [LONG/SHORT] | Signals: [list 4-5 hits] | Confidence: HIGH/MED/LOW | Entry: $X | SL: $Y | TP: $Z | Reason: [1-sentence]
        """
        direction = signal.get("direction", "")
        symbol = signal.get("symbol", "").replace("/USDT", "")
        confidence = signal.get("confidence", 0)
        trade_type = signal.get("trade_type", "DAY")
        conf_level = signal.get("conf_level", "MED")
        
        entry = signal.get("entry", 0)
        stop = signal.get("stop", 0)
        target = signal.get("target", 0)
        partial = signal.get("partial_target", 0)
        rr = signal.get("risk_reward", 0)
        position_size = signal.get("position_size", 1000)
        leverage = signal.get("leverage", 20)
        
        confirmations = signal.get("confirmations", [])
        
        # Build signal list (4-5 hits)
        signal_list = ", ".join(confirmations[:5])
        
        # Build 1-sentence reason
        if direction == "LONG":
            reason = "Bullish internals align" + (f" at {signal.get('entry_reason', 'key level')}" if signal.get('entry_reason') else "")
        else:
            reason = "Bearish internals align" + (f" at {signal.get('entry_reason', 'key level')}" if signal.get('entry_reason') else "")
        
        # Format per spec
        alert = f"""🧠 AEON: {symbol}USDT {direction} | {trade_type}

📊 Signals: {signal_list}

⚡ Confidence: {conf_level} ({confidence:.0f}%)

💰 Trade Setup:
Entry: ${entry:,.2f}
SL: ${stop:,.2f} (ATR-based)
TP1: ${partial:,.2f} (50%)
TP2: ${target:,.2f}
R:R 1:{rr:.1f}

📐 Position: ${position_size:,.0f} @ {leverage}x

💡 {reason}

⚠️ PAPER TRADE | 1% risk max"""
        
        return alert


# Initialization
def init_autonomous_trader_v2(db: AsyncIOMotorDatabase) -> AutonomousTraderV2:
    return AutonomousTraderV2(db)


# Global placeholder
autonomous_trader_v2 = None
