"""
AEON CORE TRADING ENGINE - V2.1 HIGH WIN RATE MODE

Major improvements for higher win rate:
1. 200 EMA Trend Filter (MANDATORY first check)
2. Minimum 90% confidence, 5/5 confirmations, 3:1 R:R
3. RSI signals must agree with trend (no counter-trend)
4. Volume confirmation (1.5x average required)
5. Session filter for SCALP/DAY trades (London/NY only)
6. ADX trending filter (>25 required)
7. Smart stop loss at support/resistance levels

CONFLUENCE WEIGHTS:
- Core Technicals (60%): RSI, MACD, BB, EMAs
- Market Structure/SMC (20%): BOS, FVG, Order Blocks, HH/HL
- Derivatives/Order Flow (20%): Funding, OI, L/S Ratio, CVD

RULES:
- 200 EMA trend filter FIRST (skip if within 0.5%)
- 5/5 confluences minimum (ALL must agree)
- R:R min 3:1
- 90% minimum confidence
- Max 5 open positions
- ADX > 25 required (trending market)
- Volume > 1.5x 20-period average
- SL at support/resistance levels (1-2x ATR bounds)
- 1% risk per trade max

TRADE STYLES:
- SCALP: 5m-15m, 50-200x leverage, quick in/out (session filter ON)
- DAY: 1h-4h, 20-75x leverage, medium holds (session filter ON)
- SWING: 4h-1d, 10-25x leverage, longer positions (no session filter)

UNIFIED ENGINE INTEGRATION:
- All signals validated through EngineManager
- Risk controls: position limits, daily loss limits, R:R enforcement
- Blacklist/cooldown per engine after losses
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
import pytz

logger = logging.getLogger(__name__)

# Import paper trading for signal routing
try:
    from paper_trading import route_engine_signal
except ImportError:
    route_engine_signal = None
    logger.warning("Paper trading not available for signal routing")

# Import unified engine system
try:
    from aeon_engine_system import get_engine_manager, EngineType
except ImportError:
    get_engine_manager = None
    EngineType = None
    logger.warning("Unified engine system not available")

# Telegram message formatters (import lazily to avoid circular deps at module load)
try:
    from telegram_sender import format_quant_block, format_leverage_block, format_atr_block
    _tg_formatters_ok = True
except ImportError:
    _tg_formatters_ok = False

# Trading pairs - prioritized by liquidity (MEXC supported)
TRADING_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "MATIC/USDT"
    # ARB removed: 76 trades, 8% WR, -$10,255 (2026-03-22)
]

# Priority timeframes for quality signals
# NOTE: 1d removed - data shows 0/12 win rate on daily signals (moves already exhausted by the time signal fires)
TIMEFRAMES = ["4h", "1h"]

# Trade Style Configurations - EACH STYLE UNIQUE
# NOTE: Leverage caps reduced significantly after data showed 28/64 trades liquidated at avg 50x
TRADE_STYLES = {
    "SCALP": {
        "timeframes": ["5m", "15m"],
        "min_leverage": 5,
        "max_leverage": 20,
        "stop_atr_mult": 1.5,
        "target_atr_mult": 2.5,
        "min_confidence": 65,
        "max_hold_hours": 4,
        "emoji": "⚡"
    },
    "DAY": {
        "timeframes": ["1h", "4h"],
        "min_leverage": 3,
        "max_leverage": 15,
        "stop_atr_mult": 2.0,
        "target_atr_mult": 3.5,
        "min_confidence": 70,
        "max_hold_hours": 24,
        "emoji": "🔥"
    },
    "SWING": {
        "timeframes": ["4h", "1d"],
        "min_leverage": 2,
        "max_leverage": 10,
        "stop_atr_mult": 2.5,
        "target_atr_mult": 5.0,
        "min_confidence": 75,
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
        
        # V2.1 SETTINGS - balanced for active trading
        self.min_confidence = 80  # 80% minimum — spec requirement
        self.min_confirmations = 3  # 3/5 confirmations must agree
        self.min_rr_ratio = 2.0  # Default balanced R:R
        
        # LEVERAGE SETTINGS - reduced after data showed 44% liquidation rate at avg 50x
        self.max_leverage = 20   # Hard cap 20x (was 50x)
        self.min_leverage = 2    # Minimum 2x
        self.dynamic_leverage = True  # Auto-adjust based on confidence
        
        # Position sizing (scaled entry)
        self.base_position_pct = 5   # 5% of capital per trade
        self.max_position_pct = 15   # Max 15% for highest confidence
        self.default_position_size = 1000  # $1000 per trade base
        
        # Risk management
        self.max_open_trades = 10  # Balanced limit
        self.default_stop_atr = 2.0  # 2x ATR
        self.default_target_atr = 4.0  # 4x ATR for 2:1 R:R
        
        # NEW: 200 EMA Trend Filter
        self.ema_200_filter_enabled = True
        self.ema_no_trade_zone_pct = 0.5  # Skip if within 0.5% of 200 EMA
        
        # NEW: ADX Trending Filter
        self.adx_filter_enabled = True
        self.min_adx = 25  # Only trade when ADX > 25 (trending market)
        
        # NEW: Volume Confirmation
        self.volume_filter_enabled = True
        self.min_volume_multiplier = 1.5  # 1.5x 20-period average
        
        # NEW: Session Filter (for SCALP/DAY only)
        self.session_filter_enabled = True
        # London: 3:00 AM - 12:00 PM EST = 8:00 - 17:00 UTC
        # NY: 8:00 AM - 5:00 PM EST = 13:00 - 22:00 UTC
        # Avoid: 5:00 PM - 3:00 AM EST = 22:00 - 8:00 UTC
        
        # Trade tracking
        self.open_trades: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.total_signals = 0
        self.total_trades = 0
        self.daily_trades = 0
        self.max_daily_trades = 15  # Match EngineManager config (was 999999 — effectively unlimited)
        self.last_trade_date = None
        
        # Filter statistics (for reporting)
        self.filter_stats = {
            "ema_200_filtered": 0,
            "adx_filtered": 0,
            "volume_filtered": 0,
            "session_filtered": 0,
            "confidence_filtered": 0,
            "rr_filtered": 0,
            "rsi_trend_filtered": 0,
            "total_passed": 0
        }
        
        # Pair management
        self.pair_cooldowns: Dict[str, datetime] = {}  # Cooldown after loss
        self.pair_stats: Dict[str, Dict] = {}  # Win/loss per pair
        self.blacklisted_pairs: List[str] = []  # Auto-blacklist bad performers
        self.cooldown_hours = 4  # Wait 4h after loss on same pair
        
        # Position Scaling Settings (IMPROVED)
        self.position_scaling_enabled = True  # Enable scaled entries
        self.initial_entry_pct = 50  # 50% position on initial signal
        self.scale_in_pct = 50  # 50% on confirmation
        self.scale_in_min_profit_pct = 0.5  # Must be 0.5% profitable (raised from 0.3%)
        self.scale_in_max_hours = 2  # Cancel scale-in after 2 hours
        self.pending_scale_ins: Dict[str, Dict] = {}  # Tracks positions waiting for scale-in
        
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
        self.smc_analysis = None  # Smart Money Concepts
        
        # Alert callback
        self.send_alert = None
        self.chat_ids: Set[int] = set()
    
    def determine_trade_style(self, timeframe: str, confidence: float, atr_pct: float = None) -> str:
        """
        Determine the best trade style based on timeframe, confidence, AND volatility.
        Bot has FREE WILL to choose the optimal style.
        
        Logic:
        - 5m/15m -> SCALP (quick trades)
        - 1h -> SCALP if low vol (<1%), DAY if medium vol
        - 4h -> DAY if moderate vol, SWING if low vol (<0.5%)
        - 1d -> SWING always
        
        Volatility (ATR %) overrides timeframe:
        - ATR > 2% = More aggressive style (can scalp on 4h)
        - ATR < 0.5% = More conservative style (prefer SWING)
        """
        # Volatility-based adjustments
        if atr_pct is not None:
            if atr_pct > 2.0:
                # High volatility = fast moves = SCALP/DAY preferred
                if timeframe in ["5m", "15m"]:
                    return "SCALP"
                elif timeframe == "1h":
                    return "SCALP"  # Quick scalps in high vol
                elif timeframe == "4h":
                    return "DAY"  # DAY trades in high vol 4h
                else:
                    return "SWING"
            elif atr_pct > 1.0:
                # Medium volatility
                if timeframe in ["5m", "15m"]:
                    return "SCALP"
                elif timeframe == "1h":
                    return "DAY"  # DAY trades in medium vol
                elif timeframe == "4h":
                    return "DAY"
                else:
                    return "SWING"
            else:
                # Low volatility (<1%) = slower moves = prefer longer holds
                if timeframe in ["5m", "15m"]:
                    return "SCALP"
                elif timeframe == "1h":
                    return "DAY"
                elif timeframe == "4h":
                    return "SWING" if atr_pct < 0.5 else "DAY"
                else:
                    return "SWING"
        
        # Fallback: timeframe-only logic
        if timeframe in ["5m", "15m"]:
            return "SCALP"
        elif timeframe == "1h":
            return "SCALP" if confidence < 70 else "DAY"
        elif timeframe == "4h":
            return "DAY"
        else:  # 1d+
            return "SWING"
    
    def calculate_leverage(self, confidence: float, market_regime: str = None, trade_style: str = None, atr_pct: float = None) -> int:
        """
        Deterministic ATR-based leverage calculation (volatility-adjusted):
        - ATR > 2% = 10-25x (high volatility → lower leverage)
        - ATR 1-2% = 25-75x (moderate)
        - ATR < 1% = 50-125x (low volatility → higher leverage)
        Confidence scales within the ATR band; regime applies fixed adjustments.
        """
        if not self.dynamic_leverage:
            return self.min_leverage

        # Get style config
        style = trade_style or "DAY"
        style_config = TRADE_STYLES.get(style, TRADE_STYLES["DAY"])
        style_min = style_config["min_leverage"]
        style_max = style_config["max_leverage"]

        # ATR-based base leverage (deterministic band midpoints)
        # NOTE: Bands halved after 44% liquidation rate at avg 50x leverage
        if atr_pct is not None:
            if atr_pct > 2.0:
                band_min, band_max = 3, 10    # High volatility → very conservative
            elif atr_pct > 1.0:
                band_min, band_max = 5, 15    # Moderate volatility
            else:
                band_min, band_max = 8, 20    # Low volatility
            # Scale within band by confidence
            style_min_conf = style_config["min_confidence"]
            conf_normalized = (confidence - style_min_conf) / max(1, 95 - style_min_conf)
            conf_normalized = max(0.0, min(1.0, conf_normalized))
            base_leverage = band_min + (band_max - band_min) * conf_normalized
        else:
            # Fallback: confidence-based within style range
            style_min_conf = style_config["min_confidence"]
            conf_normalized = (confidence - style_min_conf) / max(1, 95 - style_min_conf)
            conf_normalized = max(0.0, min(1.0, conf_normalized))
            base_leverage = style_min + (style_max - style_min) * conf_normalized

        # Fixed regime adjustments (no randomness)
        regime = market_regime or self.market_regime
        if regime == "VOLATILE":
            base_leverage *= 0.8    # Reduce 20% in choppy/volatile
        elif regime in ("TRENDING_UP", "TRENDING_DOWN"):
            base_leverage *= 1.1   # Add 10% with clear trend
        elif regime == "RANGING":
            base_leverage *= 0.7   # Reduce 30% in ranging market

        # Cap within style bounds, round to nearest 5
        leverage = max(style_min, min(style_max, int(base_leverage)))
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
    # POSITION SCALING - Scale into positions for better entries
    # ═══════════════════════════════════════════════════════════════════════════
    
    def calculate_scaled_position(self, full_size: float, is_initial: bool = True) -> float:
        """
        Calculate position size for scaled entry.
        Initial entry = 50% of full size, scale-in = remaining 50%
        """
        if not self.position_scaling_enabled:
            return full_size
        
        if is_initial:
            return full_size * (self.initial_entry_pct / 100)
        else:
            return full_size * (self.scale_in_pct / 100)
    
    async def check_scale_in_opportunities(self) -> List[Dict]:
        """
        Check for scale-in opportunities on existing positions.
        Scale in when:
        1. Price moves in our favor slightly (confirmation)
        2. Original signal still valid
        3. Position not yet scaled
        """
        scaled = []
        
        for trade in self.open_trades[:]:
            # Skip if already fully scaled or scaling disabled
            if trade.get("is_fully_scaled", False) or not self.position_scaling_enabled:
                continue
            
            # Skip if not marked for scaling
            if not trade.get("pending_scale_in", False):
                continue
            
            try:
                # Check if scale-in timeout exceeded (2 hours)
                entry_time = trade.get("entry_time")
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                
                hours_since_entry = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                if hours_since_entry > self.scale_in_max_hours:
                    # Cancel scale-in after 2 hours
                    trade["pending_scale_in"] = False
                    trade["is_fully_scaled"] = True  # Mark as done (won't scale)
                    trade["scale_in_cancelled"] = True
                    await self.save_open_trade(trade)
                    logger.info(f"Scale-in CANCELLED for {trade['symbol']} - exceeded {self.scale_in_max_hours}h timeout")
                    continue
                
                # Get current price
                ticker = await self.market_intel.get_ticker(trade["symbol"])
                if not ticker or not ticker.get("price"):
                    continue
                
                current_price = ticker["price"]
                entry = trade["entry_price"]
                direction = trade["direction"]
                
                # Calculate current PnL
                if direction == "LONG":
                    pnl_pct = ((current_price - entry) / entry) * 100
                else:
                    pnl_pct = ((entry - current_price) / entry) * 100
                
                # V2.1: Scale in only if PROFITABLE and moved at least 0.5% in our favor
                # Must be between 0.5% and 2% profit (confirmation zone)
                if self.scale_in_min_profit_pct <= pnl_pct <= 2.0:
                    # Calculate scale-in size
                    full_size = trade["original_full_size"]
                    scale_size = self.calculate_scaled_position(full_size, is_initial=False)
                    
                    # Update trade with scaled position
                    old_size = trade["position_size"]
                    trade["position_size"] = old_size + scale_size
                    trade["is_fully_scaled"] = True
                    trade["pending_scale_in"] = False
                    trade["scale_in_price"] = current_price
                    trade["scale_in_time"] = datetime.now(timezone.utc)
                    
                    # Calculate new average entry
                    old_entry = trade["entry_price"]
                    new_avg = ((old_entry * old_size) + (current_price * scale_size)) / (old_size + scale_size)
                    trade["avg_entry_price"] = new_avg
                    
                    # Persist to DB
                    await self.save_open_trade(trade)
                    
                    logger.info(f"📈 SCALED IN: {trade['symbol']} +${scale_size:.0f} @ ${current_price:,.2f} | PnL: +{pnl_pct:.2f}% | Total: ${trade['position_size']:.0f}")
                    
                    scaled.append({
                        "trade_id": trade["id"],
                        "symbol": trade["symbol"],
                        "scale_size": scale_size,
                        "scale_price": current_price,
                        "total_size": trade["position_size"],
                        "pnl_at_scale": pnl_pct
                    })
                elif pnl_pct < 0:
                    # Position is in loss - don't scale in, will check again later
                    logger.debug(f"Scale-in deferred for {trade['symbol']} - position in loss ({pnl_pct:.2f}%)")
                    
            except Exception as e:
                logger.error(f"Scale-in check error for {trade['symbol']}: {e}")
        
        return scaled

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
        return session in ["LONDON", "NEW_YORK", "OVERLAP", "LONDON_NY_OVERLAP"]
    
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
        self.smc_analysis = kwargs.get('smc_analysis')  # Smart Money Concepts
        self.send_alert = kwargs.get('send_alert')
        self.chat_ids = kwargs.get('chat_ids', set())
    
    async def load_settings(self):
        """Load persisted settings from database"""
        try:
            settings = await self.db.trader_settings.find_one({"_id": "v2_settings"})
            logger.info(f"Loading settings from DB: {settings}")
            if settings:
                self.active = settings.get("active", True)
                self.min_confidence = settings.get("min_confidence", 75)
                self.min_confirmations = settings.get("min_confirmations", 3)
                self.min_rr_ratio = settings.get("min_rr_ratio", 2.0)
                self.max_open_trades = settings.get("max_open_trades", 5)  # V2.1 default
                self.ema_200_filter_enabled = settings.get("ema_200_filter_enabled", True)
                self.adx_filter_enabled = settings.get("adx_filter_enabled", True)
                self.volume_filter_enabled = settings.get("volume_filter_enabled", True)
                self.session_filter_enabled = settings.get("session_filter_enabled", True)
                logger.info(f"Loaded V2.1 settings: conf={self.min_confidence}%, confirms={self.min_confirmations}, R:R={self.min_rr_ratio}:1")
            else:
                # Save default V2.1 settings
                await self.save_settings()
                logger.info("Created default V2.1 settings")
            
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
                    "min_rr_ratio": self.min_rr_ratio,
                    "max_open_trades": self.max_open_trades,
                    "ema_200_filter_enabled": self.ema_200_filter_enabled,
                    "adx_filter_enabled": self.adx_filter_enabled,
                    "volume_filter_enabled": self.volume_filter_enabled,
                    "session_filter_enabled": self.session_filter_enabled,
                    "filter_stats": self.filter_stats,
                    "updated_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get_filter_stats(self) -> Dict:
        """Get statistics on how many trades were filtered by each rule"""
        total_analyzed = sum(self.filter_stats.values())
        return {
            "total_signals_analyzed": self.total_signals,
            "filters": {
                "200_ema_trend": self.filter_stats.get("ema_200_filtered", 0),
                "adx_ranging": self.filter_stats.get("adx_filtered", 0),
                "low_volume": self.filter_stats.get("volume_filtered", 0),
                "bad_session": self.filter_stats.get("session_filtered", 0),
                "low_confidence": self.filter_stats.get("confidence_filtered", 0),
                "poor_rr_ratio": self.filter_stats.get("rr_filtered", 0),
                "rsi_counter_trend": self.filter_stats.get("rsi_trend_filtered", 0),
            },
            "passed_all_filters": self.filter_stats.get("total_passed", 0),
            "pass_rate": f"{(self.filter_stats.get('total_passed', 0) / max(1, self.total_signals)) * 100:.1f}%"
        }
    
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
        """
        Detect current trading session based on EST time.
        
        High liquidity sessions (OK to trade SCALP/DAY):
        - London: 3:00 AM - 12:00 PM EST
        - New York: 8:00 AM - 5:00 PM EST
        - Overlap: 8:00 AM - 12:00 PM EST (best)
        
        Low liquidity (AVOID for SCALP/DAY):
        - 5:00 PM - 3:00 AM EST
        """
        # Convert to EST
        est = pytz.timezone('America/New_York')
        now = datetime.now(est)
        hour = now.hour
        
        # Trading sessions (EST)
        if 8 <= hour < 12:
            return "LONDON_NY_OVERLAP"  # Best time to trade
        elif 3 <= hour < 8:
            return "LONDON"  # Good
        elif 12 <= hour < 17:
            return "NEW_YORK"  # Good
        elif 17 <= hour or hour < 3:
            return "OFF_HOURS"  # Avoid for SCALP/DAY
        
        return "UNKNOWN"
    
    def is_good_session_for_style(self, trade_style: str) -> bool:
        """
        Check if current session is good for the trade style.
        SWING trades ignore session filter.
        SCALP and DAY trades must be in London or NY session.
        """
        if not self.session_filter_enabled:
            return True
        
        if trade_style == "SWING":
            return True  # SWING can trade anytime
        
        session = self.get_current_session()
        good_sessions = ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]
        return session in good_sessions
    
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
        V2.1 HIGH WIN RATE - Complete multi-source signal analysis
        Returns signal only if ALL quality thresholds are met.

        PRE-CHECKS (in order):
        1. Pair not blacklisted/on cooldown
        2. 200 EMA Trend Filter (MANDATORY FIRST)
        3. ADX > 25 (trending market filter)
        4. Volume > 1.5x average
        5. Session filter (for SCALP/DAY)
        6. ATR volatility filter

        POST-CHECKS:
        - 90% minimum confidence
        - 5/5 confirmations
        - 3:1 R:R minimum
        - RSI must agree with trend
        """
        from post_mortem_engine import get_post_mortem
        if get_post_mortem().is_engine_paused("autonomous_trader_v2"):
            return None  # blindspot pause active
        self.total_signals += 1
        
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PRE-CHECK 1: Blacklist and Cooldown
            # ═══════════════════════════════════════════════════════════════════
            
            if self.is_pair_blacklisted(symbol):
                logger.debug(f"Skipping {symbol} - BLACKLISTED")
                return None
            
            if self.is_pair_on_cooldown(symbol):
                logger.debug(f"Skipping {symbol} - ON COOLDOWN")
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # GET TECHNICAL DATA
            # ═══════════════════════════════════════════════════════════════════
            
            if not self.market_intel:
                return None
            
            ta = await self.market_intel.get_technical_analysis(symbol, timeframe)
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
            ema_200 = indicators.get("ema_200") or None  # None if not available (insufficient candles)
            atr = indicators.get("atr") or price * 0.02
            atr_avg = indicators.get("atr_avg") or atr
            volume = indicators.get("volume", 0)
            volume_avg = indicators.get("volume_sma_20", volume)
            volume_spike = indicators.get("volume_spike", False)
            stoch_k = indicators.get("stoch_k", 50)
            stoch_d = indicators.get("stoch_d", 50)
            adx = indicators.get("adx", 30)
            
            # Get support/resistance for smart stop loss
            support = indicators.get("support", price * 0.97)
            resistance = indicators.get("resistance", price * 1.03)
            
            # ═══════════════════════════════════════════════════════════════════
            # PRE-CHECK 2: 200 EMA TREND FILTER (MOST IMPORTANT)
            # Only LONG above 200 EMA, only SHORT below
            # Skip if within 0.5% (no trade zone)
            # ═══════════════════════════════════════════════════════════════════
            
            ema_200_trend = None
            if self.ema_200_filter_enabled and ema_200 is not None:
                ema_distance_pct = ((price - ema_200) / ema_200) * 100

                if abs(ema_distance_pct) < self.ema_no_trade_zone_pct:
                    self.filter_stats["ema_200_filtered"] += 1
                    logger.debug(f"Skipping {symbol} - Price within {self.ema_no_trade_zone_pct}% of 200 EMA (no trade zone)")
                    return None

                # Determine allowed direction based on 200 EMA
                if ema_distance_pct > 0:
                    ema_200_trend = "BULLISH"  # Price above 200 EMA = LONG only
                else:
                    ema_200_trend = "BEARISH"  # Price below 200 EMA = SHORT only
            
            # ═══════════════════════════════════════════════════════════════════
            # PRE-CHECK 3: ADX TRENDING FILTER
            # Only trade when ADX > 25 (trending market)
            # ═══════════════════════════════════════════════════════════════════
            
            if self.adx_filter_enabled and adx < self.min_adx:
                self.filter_stats["adx_filtered"] += 1
                logger.debug(f"Skipping {symbol} - ADX {adx:.1f} < {self.min_adx} (ranging market)")
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # PRE-CHECK 4: VOLUME CONFIRMATION
            # Signal candle must have 1.5x average volume
            # ═══════════════════════════════════════════════════════════════════
            
            if self.volume_filter_enabled and volume_avg > 0:
                volume_ratio = volume / volume_avg if volume_avg > 0 else 1
                if volume_ratio < self.min_volume_multiplier:
                    self.filter_stats["volume_filtered"] += 1
                    logger.debug(f"Skipping {symbol} - Volume {volume_ratio:.2f}x < {self.min_volume_multiplier}x required")
                    return None
            
            # ═══════════════════════════════════════════════════════════════════
            # PRE-CHECK 5: ATR VOLATILITY FILTER
            # ═══════════════════════════════════════════════════════════════════
            
            atr_pct = (atr / price) * 100 if price > 0 else 0
            if atr > (atr_avg * 2):
                logger.debug(f"Skipping {symbol} - ATR too high (chop filter)")
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # BEGIN SIGNAL SCORING
            # ═══════════════════════════════════════════════════════════════════
            
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
            # RSI SIGNALS MUST AGREE WITH 200 EMA TREND
            # ═══════════════════════════════════════════════════════════════════
            
            # RSI (14): ONLY count if agrees with 200 EMA trend
            # No counter-trend RSI signals allowed
            rsi_signal_given = False
            if rsi < 25:
                if ema_200_trend == "BULLISH":  # RSI oversold in uptrend = valid buy
                    tech_signals_buy += 3
                    confirmations.append(f"RSI<30 extreme in uptrend ({rsi:.0f})")
                    rsi_signal_given = True
                else:
                    self.filter_stats["rsi_trend_filtered"] += 1
                    # Don't count oversold in downtrend as buy signal
            elif rsi < 30:
                if ema_200_trend == "BULLISH":
                    tech_signals_buy += 2
                    confirmations.append(f"RSI<30 in uptrend ({rsi:.0f})")
                    rsi_signal_given = True
            elif rsi > 75:
                if ema_200_trend == "BEARISH":  # RSI overbought in downtrend = valid sell
                    tech_signals_sell += 3
                    confirmations.append(f"RSI>70 extreme in downtrend ({rsi:.0f})")
                    rsi_signal_given = True
                else:
                    self.filter_stats["rsi_trend_filtered"] += 1
                    # Don't count overbought in uptrend as sell signal
            elif rsi > 70:
                if ema_200_trend == "BEARISH":
                    tech_signals_sell += 2
                    confirmations.append(f"RSI>70 in downtrend ({rsi:.0f})")
                    rsi_signal_given = True
            
            # RSI Divergence (stronger signal than simple oversold/overbought)
            if self.advanced_strategies:
                try:
                    div = await self.advanced_strategies.detect_divergence(symbol, timeframe)
                    if div.get("has_divergence"):
                        for d in div.get("divergences", []):
                            div_type = d.get("type", "")
                            # Bullish divergence (price lower low, RSI higher low) in uptrend
                            if d.get("signal") == "BUY" and "BULLISH" in div_type:
                                if ema_200_trend == "BULLISH":
                                    strength = 4 if d.get("strength") == "STRONG" else 3  # Stronger than simple RSI
                                    tech_signals_buy += strength
                                    confirmations.append(f"RSI BULLISH DIVERGENCE ({div_type})")
                            # Bearish divergence in downtrend
                            elif d.get("signal") == "SELL" and "BEARISH" in div_type:
                                if ema_200_trend == "BEARISH":
                                    strength = 4 if d.get("strength") == "STRONG" else 3
                                    tech_signals_sell += strength
                                    confirmations.append(f"RSI BEARISH DIVERGENCE ({div_type})")
                except Exception as e:
                    logger.debug(f"Divergence analysis unavailable for {symbol}: {e}")
            
            # MACD (12,26,9): Crossover + histogram expansion
            if "BULLISH" in str(macd_signal).upper():
                if ema_200_trend == "BULLISH":  # Only count MACD buy in uptrend
                    if macd_hist > 0:
                        tech_signals_buy += 2
                        confirmations.append("MACD bull cross + expansion")
                    else:
                        tech_signals_buy += 1
                        confirmations.append("MACD bull cross")
            elif "BEARISH" in str(macd_signal).upper():
                if ema_200_trend == "BEARISH":  # Only count MACD sell in downtrend
                    if macd_hist < 0:
                        tech_signals_sell += 2
                        confirmations.append("MACD bear cross + expansion")
                    else:
                        tech_signals_sell += 1
                        confirmations.append("MACD bear cross")
            
            # Bollinger Bands (20,2): Band touch (trend-aligned)
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            if price <= bb_lower and ema_200_trend == "BULLISH":
                tech_signals_buy += 2
                confirmations.append("BB lower band touch (uptrend)")
                entry_levels.append(("BB_LOWER", bb_lower))
            elif price >= bb_upper and ema_200_trend == "BEARISH":
                tech_signals_sell += 2
                confirmations.append("BB upper band touch (downtrend)")
                entry_levels.append(("BB_UPPER", bb_upper))
            if bb_width < 0.02:
                confirmations.append("BB squeeze (breakout pending)")
            
            # EMAs (9/21/50): Stack alignment (must agree with 200 EMA)
            if ema_9 > ema_21 > ema_50 and ema_200_trend == "BULLISH":
                tech_signals_buy += 2
                confirmations.append("Bullish EMA stack (9>21>50>200)")
            elif ema_9 < ema_21 < ema_50 and ema_200_trend == "BEARISH":
                tech_signals_sell += 2
                confirmations.append("Bearish EMA stack (9<21<50<200)")
            
            # EMA pullback entry
            if ema_9 > ema_21 > ema_50 and price < ema_21 and price > ema_50 and ema_200_trend == "BULLISH":
                tech_signals_buy += 1
                confirmations.append("Pullback to EMA21 (long)")
                entry_levels.append(("EMA21_PULLBACK", ema_21))
            elif ema_9 < ema_21 < ema_50 and price > ema_21 and price < ema_50 and ema_200_trend == "BEARISH":
                tech_signals_sell += 1
                confirmations.append("Pullback to EMA21 (short)")
                entry_levels.append(("EMA21_PULLBACK", ema_21))
            
            # Stochastic crossover (trend-aligned)
            if stoch_k < 20 and stoch_k > stoch_d and ema_200_trend == "BULLISH":
                tech_signals_buy += 1
                confirmations.append(f"Stoch bullish cross ({stoch_k:.0f})")
            elif stoch_k > 80 and stoch_k < stoch_d and ema_200_trend == "BEARISH":
                tech_signals_sell += 1
                confirmations.append(f"Stoch bearish cross ({stoch_k:.0f})")
            
            # Volume spike confirmation
            if volume_spike:
                confirmations.append("Volume spike confirmed")
            
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
                except Exception as e:
                    logger.debug(f"Market structure unavailable for {symbol}: {e}")
            
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
                except Exception as e:
                    logger.debug(f"SMC analysis unavailable for {symbol}: {e}")

            # ── VP Institutional Levels (bonus SMC confirmations) ──────────────
            try:
                from app_state import state as _state
                if _state.vp_engine:
                    vp_levels = await _state.vp_engine.get_key_vp_levels(symbol)
                    if vp_levels and vp_levels.get("current_price"):
                        poc = vp_levels.get("poc", 0)
                        vah = vp_levels.get("vah", 0)
                        val = vp_levels.get("val", 0)
                        liq_above = vp_levels.get("nearest_liq_above")
                        liq_below = vp_levels.get("nearest_liq_below")
                        price_loc = vp_levels.get("price_location", "")

                        # Entry near POC (high-probability reversal zone) → +1 confirmation
                        if poc and abs(price - poc) / poc < 0.005:
                            smc_signals_buy += 1 if price > poc else 0
                            smc_signals_sell += 1 if price < poc else 0
                            confirmations.append(f"Price at VP POC ${poc:,.2f}")

                        # Price at VAL (LONG) or VAH (SHORT) → institutional level
                        if val and abs(price - val) / val < 0.008:
                            smc_signals_buy += 1
                            confirmations.append(f"Price at Value Area Low ${val:,.2f} (LONG setup)")
                        if vah and abs(price - vah) / vah < 0.008:
                            smc_signals_sell += 1
                            confirmations.append(f"Price at Value Area High ${vah:,.2f} (SHORT setup)")

                        # Liq cluster as TP target magnet
                        if liq_above and price_loc in ("below_value_area", "near_val"):
                            smc_signals_buy += 1
                            confirmations.append(f"Liq cluster above @ ${liq_above:,.2f} (LONG target)")
                        if liq_below and price_loc in ("above_value_area", "near_vah"):
                            smc_signals_sell += 1
                            confirmations.append(f"Liq cluster below @ ${liq_below:,.2f} (SHORT target)")
            except Exception as vp_err:
                logger.debug(f"VP levels check failed for {symbol}: {vp_err}")

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
                except Exception as e:
                    logger.debug(f"CVD data unavailable for {symbol}: {e}")
            
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

                    # Funding MOMENTUM: velocity matters more than absolute level
                    try:
                        fm = await self.market_intel.get_funding_momentum(symbol)
                        fm_signal = fm.get("signal", "NEUTRAL")
                        fm_squeeze = fm.get("squeeze_risk", "LOW")
                        if fm_signal == "BEARISH" and fm_squeeze == "HIGH":
                            deriv_signals_sell += 2
                            confirmations.append(f"Funding momentum rising — HIGH squeeze risk")
                        elif fm_signal == "BEARISH" and fm_squeeze == "MEDIUM":
                            deriv_signals_sell += 1
                            confirmations.append(f"Funding momentum rising — MEDIUM squeeze risk")
                        elif fm_signal == "BULLISH" and fm_squeeze == "HIGH":
                            deriv_signals_buy += 2
                            confirmations.append(f"Funding momentum bearish — HIGH short squeeze risk")
                        elif fm_signal == "BULLISH" and fm_squeeze == "MEDIUM":
                            deriv_signals_buy += 1
                            confirmations.append(f"Funding momentum bearish — MEDIUM short squeeze risk")
                        elif fm_signal == "REVERSAL":
                            if avg_funding > 0:
                                deriv_signals_buy += 1
                                confirmations.append("Funding squeeze complete — long squeeze done")
                            else:
                                deriv_signals_sell += 1
                                confirmations.append("Funding squeeze complete — short squeeze done")
                    except Exception:
                        pass

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
                except Exception as e:
                    logger.debug(f"Derivatives data unavailable for {symbol}: {e}")
            
            # ═══════════════════════════════════════════════════════════════════
            # F&G (Context display only - NO direction influence)
            # ═══════════════════════════════════════════════════════════════════
            if self.enhanced_intel:
                try:
                    fg = await self.enhanced_intel.get_fear_greed_index()
                    fg_value = fg.get("value", 50)
                    self.fear_greed = fg_value
                except Exception as e:
                    logger.debug(f"Fear & Greed data unavailable: {e}")
            
            # ═══════════════════════════════════════════════════════════════════
            # WEIGHTED CONFLUENCE SCORING
            # Tech (60%), SMC (20%), Derivatives (20%)
            # V2.1: ALL 5 categories must agree for valid signal
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
            # DETERMINE DIRECTION (5/5 confluences - ALL must agree)
            # ═══════════════════════════════════════════════════════════════════
            
            # Count confirmation categories (need ALL 5 to agree)
            # 1. Technicals, 2. SMC Structure, 3. Derivatives, 4. 200 EMA Trend, 5. Volume
            buy_confirmations = [
                total_tech_buy >= 4,  # Strong tech confirmation
                total_smc_buy >= 2,   # SMC confirmation
                total_deriv_buy >= 2, # Derivatives confirmation
                ema_200_trend == "BULLISH",  # 200 EMA agrees
                volume_spike or (volume / volume_avg if volume_avg > 0 else 1) >= self.min_volume_multiplier,  # Volume confirms
            ]
            sell_confirmations = [
                total_tech_sell >= 4,
                total_smc_sell >= 2,
                total_deriv_sell >= 2,
                ema_200_trend == "BEARISH",
                volume_spike or (volume / volume_avg if volume_avg > 0 else 1) >= self.min_volume_multiplier,
            ]
            
            buy_categories = sum(buy_confirmations)
            sell_categories = sum(sell_confirmations)
            
            # V2.1: Need ALL 5 categories (5/5) for valid signal
            if signals_buy > signals_sell and buy_categories >= 5:
                direction = "LONG"
                signal_strength = signals_buy
                conf_level = "ULTRA" if buy_categories == 5 else "HIGH"
            elif signals_sell > signals_buy and sell_categories >= 5:
                direction = "SHORT"
                signal_strength = signals_sell
                conf_level = "ULTRA" if sell_categories == 5 else "HIGH"
            else:
                # Not enough confirmations
                self.filter_stats["confidence_filtered"] += 1
                return None
            
            # Verify direction matches 200 EMA trend (double check)
            if direction == "LONG" and ema_200_trend != "BULLISH":
                self.filter_stats["ema_200_filtered"] += 1
                return None
            if direction == "SHORT" and ema_200_trend != "BEARISH":
                self.filter_stats["ema_200_filtered"] += 1
                return None

            # ═══════════════════════════════════════════════════════════════════
            # BTC MACRO TREND GATE - Never trade against the macro trend.
            # Data: 0 LONG wins in bearish BTC macro (0/32 trades).
            # btc_bias is updated by detect_market_regime() each scan cycle.
            # ═══════════════════════════════════════════════════════════════════
            if direction == "LONG" and self.btc_bias == "BEARISH":
                logger.debug(f"Skipping {symbol} LONG - BTC macro trend is BEARISH")
                self.filter_stats["ema_200_filtered"] += 1
                return None
            if direction == "SHORT" and self.btc_bias == "BULLISH":
                logger.debug(f"Skipping {symbol} SHORT - BTC macro trend is BULLISH")
                self.filter_stats["ema_200_filtered"] += 1
                return None

            # ── Regime Gate ────────────────────────────────────────────────────
            # Block in VOLATILE_EXPANSION; require higher confidence in RANGING
            try:
                from regime_engine import get_regime_engine
                regime_result = await get_regime_engine().detect_regime(symbol, self.market_intel)
                regime = regime_result.get("regime", "WEAK_TREND")
                if regime == "VOLATILE_EXPANSION":
                    logger.debug(f"⛔ Regime BLOCK {symbol}: VOLATILE_EXPANSION")
                    return None
            except Exception as _re:
                logger.debug(f"Regime check failed for {symbol}: {_re}")

            # Calculate weighted confidence score
            tech_score = min(100, (total_tech_buy if direction == "LONG" else total_tech_sell) * 12)
            smc_score = min(100, (total_smc_buy if direction == "LONG" else total_smc_sell) * 25)
            deriv_score = min(100, (total_deriv_buy if direction == "LONG" else total_deriv_sell) * 25)
            
            # Weighted: Tech 60%, SMC 20%, Deriv 20%
            confidence = (tech_score * 0.60) + (smc_score * 0.20) + (deriv_score * 0.20)
            confidence = min(98, max(50, confidence))
            
            # V2.1: Must hit 90% minimum confidence
            if confidence < self.min_confidence:
                self.filter_stats["confidence_filtered"] += 1
                logger.debug(f"Skipping {symbol} - Confidence {confidence:.1f}% < {self.min_confidence}% required")
                return None
            
            if len(confirmations) < self.min_confirmations:
                self.filter_stats["confidence_filtered"] += 1
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # SESSION FILTER (for SCALP/DAY only)
            # ═══════════════════════════════════════════════════════════════════
            
            # Determine trade style first to check session
            atr_pct_calc = (atr / price * 100) if price > 0 else None
            trade_style = self.determine_trade_style(timeframe, confidence, atr_pct_calc)
            
            if not self.is_good_session_for_style(trade_style):
                self.filter_stats["session_filtered"] += 1
                logger.debug(f"Skipping {symbol} - Bad session for {trade_style} trade")
                return None
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE ENTRY, STOP, TARGET (R:R min 3:1)
            # SMART STOP LOSS at support/resistance levels
            # ═══════════════════════════════════════════════════════════════════
            
            # Smart entry - look for pullback level
            best_entry = price
            entry_reason = "Market"
            
            for level_type, level_price in entry_levels:
                if direction == "LONG" and level_price < price and level_price > price * 0.97:
                    if level_price > best_entry * 0.99:
                        best_entry = level_price
                        entry_reason = level_type
                elif direction == "SHORT" and level_price > price and level_price < price * 1.03:
                    if level_price < best_entry * 1.01:
                        best_entry = level_price
                        entry_reason = level_type
            
            # SMART STOP LOSS - Place at support/resistance, bounded by ATR
            min_stop_distance = atr * 1.0  # Minimum 1x ATR
            max_stop_distance = atr * 2.0  # Maximum 2x ATR
            
            if direction == "LONG":
                # Stop below support level
                ideal_stop = support - (atr * 0.2)  # Slightly below support
                distance_to_ideal = best_entry - ideal_stop
                
                # Bound by ATR range
                if distance_to_ideal < min_stop_distance:
                    stop = best_entry - min_stop_distance
                elif distance_to_ideal > max_stop_distance:
                    stop = best_entry - max_stop_distance
                else:
                    stop = ideal_stop
                
                # Calculate target for 3:1 R:R
                risk = best_entry - stop
                target = best_entry + (risk * self.min_rr_ratio)
                partial_target = best_entry + (risk * 1.5)  # 1.5:1 for partial
            else:
                # Stop above resistance level
                ideal_stop = resistance + (atr * 0.2)  # Slightly above resistance
                distance_to_ideal = ideal_stop - best_entry
                
                # Bound by ATR range
                if distance_to_ideal < min_stop_distance:
                    stop = best_entry + min_stop_distance
                elif distance_to_ideal > max_stop_distance:
                    stop = best_entry + max_stop_distance
                else:
                    stop = ideal_stop
                
                # Calculate target for 3:1 R:R
                risk = stop - best_entry
                target = best_entry - (risk * self.min_rr_ratio)
                partial_target = best_entry - (risk * 1.5)
            
            # Verify R:R ratio meets minimum
            risk = abs(best_entry - stop)
            reward = abs(target - best_entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio < self.min_rr_ratio:
                self.filter_stats["rr_filtered"] += 1
                logger.debug(f"Skipping {symbol} - R:R {rr_ratio:.1f}:1 < {self.min_rr_ratio}:1 required")
                return None
            
            # Position size based on confidence
            position_size_pct = self.base_position_pct
            if confidence >= 95:
                position_size_pct = self.max_position_pct
            elif confidence >= 92:
                position_size_pct = self.max_position_pct * 0.8
            elif confidence >= 90:
                position_size_pct = self.max_position_pct * 0.6
            
            # Track passed signal
            self.filter_stats["total_passed"] += 1
            
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
                "atr_pct": round(atr_pct_calc, 3) if atr_pct_calc else None,
                
                # Trade style (dynamically determined)
                "trade_type": trade_style,
                "conf_level": conf_level,
                
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
    
    async def process_scalper_signals(self) -> List[Dict]:
        """
        Process signals from the Aggressive Scalper via V2 integration.
        This allows the scalper to run independently while feeding high-confidence
        signals to the main V2.1 trading engine.
        
        Returns: List of scalper signals converted to V2.1 format
        """
        try:
            from scalper_learning import v2_integration
            
            # Get queued signals from scalper
            scalper_signals = v2_integration.get_queued_signals()
            
            if not scalper_signals:
                return []
            
            converted = []
            for sig in scalper_signals:
                # Convert scalper signal to V2.1 format
                v2_signal = {
                    "symbol": sig.get("symbol"),
                    "timeframe": sig.get("timeframe", "5m"),
                    "direction": sig.get("direction"),
                    "confidence": sig.get("confidence", 75),
                    "confirmations": [
                        f"SCALPER_STR_{sig.get('scalper_strength', 0)}",
                        f"VOL_{sig.get('volume_ratio', 1.0):.1f}x",
                        f"RSI_{sig.get('rsi', 50):.0f}",
                        sig.get("reason", "Scalper signal")
                    ],
                    "confirmation_count": 4,
                    "price": sig.get("entry_price", 0),
                    "entry": sig.get("entry_price", 0),
                    "entry_type": "SCALPER",
                    "stop": sig.get("stop_loss", 0),
                    "target": sig.get("take_profit", 0),
                    "partial_target": sig.get("entry_price", 0) * (1.01 if sig.get("direction") == "LONG" else 0.99),
                    "risk_reward": 3.0,  # Scalper default R:R
                    "atr": 0,  # Will be calculated
                    "atr_pct": None,
                    "trade_type": "SCALP",  # Scalper signals are always SCALP style
                    "conf_level": "SCALPER",
                    "position_size_pct": 5,
                    "session": self.get_current_session(),
                    "market_regime": self.market_regime,
                    "btc_bias": self.btc_bias,
                    "fear_greed": self.fear_greed,
                    "source": "SCALPER",
                    "timestamp": sig.get("timestamp", datetime.now(timezone.utc).isoformat())
                }
                converted.append(v2_signal)
                logger.info(f"⚡ SCALPER→V2.1: {sig.get('symbol')} {sig.get('direction')} (str={sig.get('scalper_strength')})")
            
            return converted
            
        except ImportError:
            logger.debug("Scalper integration not available")
            return []
        except Exception as e:
            logger.error(f"Error processing scalper signals: {e}")
            return []
    
    async def scan_all_markets(self) -> List[Dict]:
        """Scan all pairs for quality signals, including scalper signals"""
        signals = []
        
        # Update market regime first
        await self.detect_market_regime()
        
        # First, process any queued scalper signals
        scalper_signals = await self.process_scalper_signals()
        for sig in scalper_signals:
            signals.append(sig)
        
        # Then scan traditional markets
        for symbol in TRADING_PAIRS:
            for tf in TIMEFRAMES:
                signal = await self.analyze_signal(symbol, tf)
                
                if signal:
                    # Check if we already have a signal for this symbol (including from scalper)
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
        """Execute a paper trade - validates through unified engine system first"""
        if len(self.open_trades) >= self.max_open_trades:
            return {"error": "Max open trades reached"}
        
        # Check if already in this symbol
        for trade in self.open_trades:
            if trade["symbol"] == signal["symbol"]:
                return {"error": f"Already in {signal['symbol']}"}
        
        # Calculate ATR percentage for dynamic trade style
        price = signal.get("price", signal.get("entry", 0))
        atr = signal.get("atr", 0)
        atr_pct = (atr / price * 100) if price > 0 else None
        
        # Determine trade style dynamically based on timeframe AND volatility
        trade_style = self.determine_trade_style(
            timeframe=signal["timeframe"],
            confidence=signal["confidence"],
            atr_pct=atr_pct
        )
        
        # Calculate full position size
        full_position_size = self.calculate_position_size(signal["confidence"], signal.get("position_size_pct", 2))

        # ═══════════════════════════════════════════════════════════════
        # UNIFIED ENGINE VALIDATION
        # ═══════════════════════════════════════════════════════════════
        if get_engine_manager and EngineType:
            try:
                engine_manager = get_engine_manager()
                _symbol    = signal["symbol"]
                _direction = signal["direction"].lower()

                # Compute quant-driven leverage before building signal
                final_leverage, lev_bd = await engine_manager.get_dynamic_leverage(
                    _symbol, _direction, EngineType.AUTONOMOUS_TRADER_V2
                )

                # Build signal for unified validation
                engine_signal = {
                    "symbol":        _symbol,
                    "direction":     _direction,
                    "entry_price":   signal["entry"],
                    "position_size": full_position_size,
                    "leverage":      final_leverage,
                    "stop_loss":     signal["stop"],
                    "take_profit":   signal["target"],
                    "confidence":    signal["confidence"],
                    "confluences":   len(signal.get("confirmations", [])),
                    "reason":        "; ".join(signal.get("confirmations", [])[:3])
                }

                # Submit to unified validator
                result = await engine_manager.submit_signal_gated(engine_signal, EngineType.AUTONOMOUS_TRADER_V2)

                _signal_adapted = False
                if result["action"] == "REJECT":
                    qr = result.get("quant_report", {})
                    if qr and not result.get("adapted"):
                        adapted_signal = dict(engine_signal)
                        if qr.get("suggested_sl"):    adapted_signal["stop_loss"]    = qr["suggested_sl"]
                        if qr.get("suggested_entry"): adapted_signal["entry_price"]  = qr["suggested_entry"]
                        if qr.get("suggested_tp1"):   adapted_signal["take_profit"]  = qr["suggested_tp1"]
                        adapted_signal["position_size"] = round(adapted_signal["position_size"] * 0.70, 2)
                        adapted_lev, adapted_lev_bd = await engine_manager.get_dynamic_leverage(
                            _symbol, _direction, EngineType.AUTONOMOUS_TRADER_V2, quant_report=qr
                        )
                        adapted_signal["leverage"] = adapted_lev
                        lev_bd = adapted_lev_bd  # use post-adaptation breakdown
                        logger.info(f"🔄 [{signal['symbol']}] adapting signal — resubmitting to Quant")
                        result = await engine_manager.submit_signal_gated(adapted_signal, EngineType.AUTONOMOUS_TRADER_V2, adapted=True)
                        if result["action"] == "REJECT":
                            logger.warning(f"❌ [{signal['symbol']}] adapted attempt BLOCKED: {result.get('reason')}")
                            return {"error": f"Blocked (adapted): {result.get('reason')}", "issues": []}
                        _signal_adapted = True
                    else:
                        logger.warning(f"❌ [{signal['symbol']}] BLOCKED by unified validator: {result.get('reason')}")
                        return {"error": f"Blocked: {result.get('reason')}", "issues": result.get("issues", [])}

                # Attach quant/leverage data to signal for Telegram formatting
                signal["_lev_bd"]   = lev_bd
                signal["_adapted"]  = _signal_adapted
                signal["_position_size"] = full_position_size

                # Use the validated trade ID from engine manager
                unified_trade_id = result.get("trade", {}).get("trade_id")
                logger.info(f"✅ [{signal['symbol']}] VALIDATED by unified engine system")
                
            except Exception as e:
                logger.warning(f"Unified engine validation failed (proceeding anyway): {e}")
                unified_trade_id = None
        else:
            unified_trade_id = None
        
        # Get style config for this trade
        style_config = self.get_trade_style_config(trade_style)
        
        trade = {
            "id": f"trade_{self.total_trades + 1}",
            "unified_id": unified_trade_id,  # Link to unified engine system
            "symbol": signal["symbol"],
            "direction": signal["direction"],
            "entry_price": signal["entry"],
            "stop_price": signal["stop"],
            "target_price": signal["target"],
            "partial_target": signal["partial_target"],
            "position_size_pct": signal["position_size_pct"],
            "leverage": leverage,
            "confidence": signal["confidence"],
            "confirmations": signal["confirmations"],
            "timeframe": signal["timeframe"],
            "trade_type": trade_style,
            "atr_pct": round(atr_pct, 3) if atr_pct else None,
            "entry_time": datetime.now(timezone.utc),
            "status": "OPEN",
            "partial_closed": False,
            "pnl_pct": 0,
            "trail_stop": signal["stop"]
        }
        
        # Apply position scaling if enabled
        if self.position_scaling_enabled:
            initial_size = self.calculate_scaled_position(full_position_size, is_initial=True)
            trade["position_size"] = initial_size
            trade["original_full_size"] = full_position_size
            trade["pending_scale_in"] = True
            trade["is_fully_scaled"] = False
            logger.info(f"Scaled entry: ${initial_size:.0f} (50% of ${full_position_size:.0f}), awaiting confirmation for scale-in")
        else:
            trade["position_size"] = full_position_size
            trade["original_full_size"] = full_position_size
            trade["pending_scale_in"] = False
            trade["is_fully_scaled"] = True
        
        self.open_trades.append(trade)
        self.total_trades += 1
        
        # Persist trade to database
        await self.save_open_trade(trade)
        
        # Route signal to paper trading accounts (both PRO and STARTER)
        if route_engine_signal:
            try:
                paper_signal = {
                    "symbol": signal["symbol"],
                    "direction": signal["direction"],
                    "entry_price": signal["entry"],
                    "stop_loss": signal["stop"],
                    "take_profit": signal["target"],
                    "confidence": signal["confidence"],
                    "confirmations": signal["confirmations"],
                    "timeframe": signal["timeframe"],
                    "risk_pct": signal.get("position_size_pct", 2),
                    "unified_trade_id": unified_trade_id
                }
                paper_results = await route_engine_signal(paper_signal, "AUTONOMOUS_V2")
                for r in paper_results:
                    if r.get("success"):
                        pos = r.get("position", {})
                        logger.info(f"📊 Paper [{r['account']}]: {signal['direction']} {signal['symbol']} | "
                                  f"{pos.get('leverage')}x | Margin: ${pos.get('margin', 0):,.2f}")
            except Exception as e:
                logger.warning(f"Failed to route to paper trading: {e}")
        
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
                ta = await self.market_intel.get_technical_analysis(trade["symbol"], "1h")
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
                
                # REVERSAL PATTERN DETECTION - Exit on reversal candle patterns
                reversal_exit = False
                reversal_pattern = None
                if current_pnl_pct > 0.5 and not momentum_exit:  # In profit, check for reversals
                    try:
                        from scalper_learning import reversal_detector
                        reversal_data = await reversal_detector.analyze(
                            trade["symbol"], 
                            trade.get("timeframe", "1h")
                        )
                        
                        if reversal_data.get("should_exit"):
                            reversal_pattern = reversal_data.get("pattern")
                            # Only exit on reversal if pattern goes against our position
                            if direction == "LONG" and reversal_data.get("direction") == "BEARISH":
                                reversal_exit = True
                                logger.info(f"🔄 REVERSAL EXIT: {trade['symbol']} detected {reversal_pattern} (bearish reversal while LONG)")
                            elif direction == "SHORT" and reversal_data.get("direction") == "BULLISH":
                                reversal_exit = True
                                logger.info(f"🔄 REVERSAL EXIT: {trade['symbol']} detected {reversal_pattern} (bullish reversal while SHORT)")
                    except Exception as e:
                        # Reversal detection is optional enhancement
                        pass
                
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
                
                # Handle full exit (including momentum exit and reversal exit)
                if hit_stop or hit_target or momentum_exit or reversal_exit:
                    exit_price = current_price if (momentum_exit or reversal_exit) else (stop if hit_stop else target)
                    
                    if direction == "LONG":
                        pnl_pct = ((exit_price - entry) / entry) * 100
                    else:
                        pnl_pct = ((entry - exit_price) / entry) * 100
                    
                    # Calculate USD PnL for unified engine
                    pnl_usd = trade.get("position_size", 0) * (pnl_pct / 100)
                    
                    trade["status"] = "CLOSED"
                    trade["exit_price"] = exit_price
                    trade["pnl_pct"] = pnl_pct
                    trade["pnl_usd"] = pnl_usd
                    trade["exit_time"] = datetime.now(timezone.utc)
                    
                    # Determine exit reason with pattern info
                    if hit_target:
                        trade["exit_reason"] = "TARGET"
                    elif momentum_exit:
                        trade["exit_reason"] = "MOMENTUM"
                    elif reversal_exit:
                        trade["exit_reason"] = f"REVERSAL_{reversal_pattern}" if reversal_pattern else "REVERSAL"
                    else:
                        trade["exit_reason"] = "STOP"
                    
                    # Update pair stats (for blacklist/cooldown)
                    is_win = pnl_pct > 0
                    self.update_pair_stats(trade["symbol"], is_win)
                    
                    # ═══════════════════════════════════════════════════════════════
                    # NOTIFY UNIFIED ENGINE SYSTEM OF CLOSED TRADE
                    # ═══════════════════════════════════════════════════════════════
                    if get_engine_manager and EngineType and trade.get("unified_id"):
                        try:
                            engine_manager = get_engine_manager()
                            engine_manager.close_trade(
                                EngineType.AUTONOMOUS_TRADER_V2,
                                trade["unified_id"],
                                exit_price,
                                pnl_usd
                            )
                        except Exception as e:
                            logger.warning(f"Failed to close trade in unified engine: {e}")
                    
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
        """Get comprehensive trading statistics (includes paper trades)"""
        # Pull closed paper trades from DB to include in stats
        paper_closed = []
        try:
            if self.db is not None:
                raw = await self.db.paper_trades.find({"status": "closed"}).to_list(500)
                for t in raw:
                    pnl = t.get("pnl_pct") or t.get("unrealized_pnl_pct") or t.get("pnl", 0) or 0
                    paper_closed.append({"pnl_pct": float(pnl)})
        except Exception as e:
            logger.warning(f"Could not load paper trades for stats: {e}")

        all_closed = self.closed_trades + paper_closed

        wins = [t for t in all_closed if t["pnl_pct"] > 0]
        losses = [t for t in all_closed if t["pnl_pct"] <= 0]

        total_pnl = sum(t["pnl_pct"] for t in all_closed)
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0

        # Profit factor
        gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0
        gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Expectancy
        win_rate = len(wins) / len(all_closed) * 100 if all_closed else 0
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
            except Exception as e:
                logger.debug(f"PnL calc error for {trade.get('symbol')}: {e}")

        total_count = self.total_trades + len(paper_closed)

        return {
            "active": self.active,
            "total_signals_analyzed": self.total_signals,
            "total_trades": total_count,
            "open_trades": len(self.open_trades),
            "closed_trades": len(all_closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl_pct": round(total_pnl, 2),
            "open_pnl_pct": round(open_pnl, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "best_trade": max(all_closed, key=lambda x: x["pnl_pct"])["pnl_pct"] if all_closed else 0,
            "worst_trade": min(all_closed, key=lambda x: x["pnl_pct"])["pnl_pct"] if all_closed else 0,
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
        alert = (
            f"🧠 AEON: {symbol}USDT {direction} | {trade_type}\n"
            f"\n"
            f"📊 Signals: {signal_list}\n"
            f"\n"
            f"⚡ Confidence: {conf_level} ({confidence:.0f}%)\n"
            f"\n"
            f"💰 Trade Setup:\n"
            f"Entry: ${entry:,.2f}\n"
            f"SL: ${stop:,.2f} (ATR-based)\n"
            f"TP1: ${partial:,.2f} (50%)\n"
            f"TP2: ${target:,.2f}\n"
            f"R:R 1:{rr:.1f}\n"
            f"\n"
            f"📐 Position: ${position_size:,.0f} @ {leverage}x\n"
            f"\n"
            f"💡 {reason}\n"
        )

        # Append Quant Gate / Leverage Engine / ATR Stop blocks if data available
        lev_bd = signal.get("_lev_bd", {})
        if lev_bd and _tg_formatters_ok:
            adapted = signal.get("_adapted", False)
            alert += "\n" + format_quant_block(lev_bd, adapted)
            alert += "\n\n" + format_leverage_block(lev_bd)
            alert += "\n\n" + format_atr_block(signal)

        alert += "\n\n⚠️ PAPER TRADE | 1% risk max"
        return alert


# Initialization
def init_autonomous_trader_v2(db: AsyncIOMotorDatabase) -> AutonomousTraderV2:
    return AutonomousTraderV2(db)


# Global placeholder
autonomous_trader_v2 = None
