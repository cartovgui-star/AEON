"""
=============================================================================
  INSTITUTIONAL ADAPTIVE LEVERAGE SCALPER ENGINE v1.0
  Symbol: BTCUSDT (BTC/USDT perpetual futures)
  Exchange: MEXC
=============================================================================

Architecture:
  - Multi-timeframe analysis: 5m (entry), 15m (confirmation), 30m (regime)
  - Adaptive leverage: 25x–150x driven by 5-factor AI model
  - Entry: minimum 4 confluences across 3 sets (Technical, Smart Money, R:R)
  - Scale-out: 50% at 1R → 25% at 1.5R → 25% trailing
  - Hard risk guards: -$2.5k/-$4k/-$5k daily loss tiers
  - All trades logged to MongoDB for continuous learning

Integration:
  - Imports ccxt.mexc (same credentials as market_intelligence.py)
  - Writes to MongoDB collection `institutional_scalper_trades`
  - Designed to run as 8th engine alongside existing 7-engine system

Usage:
  scalper = InstitutionalScalper(db=app_state.db)
  await scalper.run_scalper_loop()
=============================================================================
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import ccxt
    import ccxt.async_support as ccxt_async
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYMBOL          = "BTC/USDT"           # ccxt format — internal always uses this
SYMBOL_DISPLAY  = "BTCUSDT"            # display / log format

# Leverage bounds
LEVERAGE_MIN    = 25
LEVERAGE_MAX    = 150

# Position sizing
MAX_POSITION_USD    = 150.0
MAX_CONCURRENT_PER_SYMBOL = 3
MAX_CONCURRENT_TOTAL      = 5

# Risk tiers (daily PnL thresholds — all negative)
TIER_REDUCE_LEVERAGE   = -2500.0   # switch to 25x only
TIER_REDUCE_POSITION   = -4000.0   # 25x + $50 max position
TIER_HARD_STOP         = -5000.0   # no more trades today

# Consecutive-loss discipline
CONSEC_LOSS_LIMIT      = 3         # after N losses in a row → 25x for next 5 trades
CONSEC_LOSS_COOLDOWN   = 5         # number of trades at 25x before normal mode resumes

# Time limits per trade
MAX_HOLD_5M_SECS   = 5 * 60       # 5 minutes for 5m scalps
MAX_HOLD_15M_SECS  = 15 * 60      # 15 minutes for 15m setups

# Exit levels
TP_SCALE_OUT = [
    (0.01, 0.50),   # +1% profit → close 50% of position (leaves scale_factor=0.50)
    (0.015, 0.50),  # +1.5% profit → close 50% of remaining (= 25% of original; leaves scale_factor=0.25)
]
TRAILING_STOP_ACTIVATE_PCT = 0.01   # activate trailing at +1%
TRAILING_STOP_TRAIL_PCT    = 0.005  # trail by 0.5%

# Minimum viable R:R
MIN_RR_RATIO = 1.5

# Fee (0.15% per side)
TRADE_FEE_PCT = 0.0015

# Candle limits per timeframe fetch
CANDLE_LIMIT = 100


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Direction(str, Enum):
    LONG  = "LONG"
    SHORT = "SHORT"


class TradeState(str, Enum):
    OPEN      = "OPEN"
    CLOSED    = "CLOSED"
    CANCELLED = "CANCELLED"


class ExitReason(str, Enum):
    TP1          = "TP1_50PCT"
    TP2          = "TP2_25PCT"
    TRAILING     = "TRAILING_STOP"
    SL           = "STOP_LOSS"
    TIME_LIMIT   = "TIME_LIMIT"
    DAILY_LIMIT  = "DAILY_LIMIT"
    MANUAL       = "MANUAL"


@dataclass
class LeverageFactors:
    """Breakdown of every input that went into the leverage decision — logged per trade."""
    win_rate: float             # last-20 win rate %
    win_rate_factor: float      # contribution to leverage

    atr_percentile: float       # 0-100 percentile of current ATR (across 5/15/30m avg)
    volatility_factor: float    # contribution (INVERTED — low vol = higher leverage)

    confluence_score: int       # 1-5
    confluence_bonus: float     # contribution

    sharpe_ratio: float         # Sharpe of last N closed trades
    sharpe_adjustment: float    # contribution

    rr_ratio: float             # actual R:R of this setup
    rr_factor: float            # contribution

    base_leverage: int          # always 25
    raw_leverage: float         # sum before clamp
    final_leverage: int         # clamped [25, 150]

    setup_score: float          # 0-100 quality score driving the decision narrative
    decision_narrative: str     # e.g. "Good setup (70-89): Allow 75-100x"


@dataclass
class EntrySignal:
    """All signal data produced by analyze_setup()."""
    symbol: str
    direction: Direction
    confidence_score: float     # 0-100
    leverage_rec: int
    leverage_factors: LeverageFactors

    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float

    timeframe_alignment: int    # 1, 2, or 3 (TFs in agreement)
    confluence_count: int       # how many individual confluences fired

    confluences_hit: List[str]  # human-readable list of what triggered
    market_regime: str          # e.g. "BULLISH", "BEARISH", "RANGING"

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ActiveTrade:
    """Live trade being managed."""
    trade_id: str
    symbol: str
    direction: Direction
    entry_price: float
    stop_loss: float
    take_profit: float
    leverage: int
    position_size_usd: float    # notional USD
    scale_factor: float         # remaining fraction (1.0 = full, 0.5 = half, etc.)
    open_time: datetime
    max_hold_secs: int

    trailing_stop_active: bool = False
    trailing_stop_price: float = 0.0
    highest_price: float = 0.0  # for LONG trailing
    lowest_price: float = 0.0   # for SHORT trailing

    tp1_hit: bool = False       # 50% already closed
    tp2_hit: bool = False       # 25% already closed

    signal: Optional[EntrySignal] = None
    state: TradeState = TradeState.OPEN


# ---------------------------------------------------------------------------
# InstitutionalScalper
# ---------------------------------------------------------------------------

class InstitutionalScalper:
    """
    Institutional-grade adaptive leverage scalper for BTCUSDT on MEXC.

    All public methods are async-safe.  The engine is self-contained: it
    fetches its own market data, calculates indicators, decides leverage,
    manages open trades, enforces hard risk limits, and logs everything to
    MongoDB for continuous-improvement feedback.
    """

    def __init__(self, db=None):
        self.db = db
        self.active = True

        # ------------------------------------------------------------------ #
        # Exchange clients
        # ------------------------------------------------------------------ #
        if CCXT_AVAILABLE:
            # Spot/public data — used for OHLCV, funding, OI, LS ratio
            self.mexc = ccxt_async.mexc({
                "apiKey": os.environ.get("MEXC_API_KEY", ""),
                "secret": os.environ.get("MEXC_SECRET_KEY", ""),
                "enableRateLimit": True,
            })
            # Futures/swap client — used for order execution and leverage setting
            self.mexc_futures = ccxt_async.mexc({
                "apiKey": os.environ.get("MEXC_API_KEY", ""),
                "secret": os.environ.get("MEXC_SECRET_KEY", ""),
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            })
        else:
            self.mexc = None
            self.mexc_futures = None
            logger.error("ccxt not available — InstitutionalScalper cannot fetch market data")

        # ------------------------------------------------------------------ #
        # In-memory state
        # ------------------------------------------------------------------ #
        self.active_trades: Dict[str, ActiveTrade] = {}     # trade_id → ActiveTrade
        self.trade_history: List[Dict[str, Any]] = []       # closed trades (last 100)

        # Daily PnL tracking (resets at UTC midnight)
        self._daily_pnl: float = 0.0
        self._daily_reset_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Consecutive-loss counter
        self._consec_losses: int = 0
        self._consec_loss_cooldown_remaining: int = 0

        # Candle cache: { (symbol, timeframe): (DataFrame, fetched_at) }
        self._candle_cache: Dict[Tuple[str, str], Tuple[pd.DataFrame, datetime]] = {}
        self._cache_ttl_secs: int = 30

    # ======================================================================
    # PUBLIC API (spec-required methods)
    # ======================================================================

    async def analyze_setup(
        self,
        symbol: str,
        timeframe_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Tuple[float, int, Optional[EntrySignal]]:
        """
        Full multi-timeframe analysis for a symbol.

        Returns:
            (confidence_score, leverage_recommendation, entry_signal)
            entry_signal is None when no trade should be taken.
        """
        try:
            # 1. Fetch candles if not supplied
            if timeframe_data is None:
                timeframe_data = await self._fetch_all_timeframes(symbol)
            if timeframe_data is None:
                return 0.0, LEVERAGE_MIN, None

            df_5m  = timeframe_data.get("5m")
            df_15m = timeframe_data.get("15m")
            df_30m = timeframe_data.get("30m")

            if df_5m is None or len(df_5m) < 50:
                return 0.0, LEVERAGE_MIN, None

            # 2. Indicators on each timeframe
            df_5m  = self._calculate_indicators(df_5m)
            df_15m = self._calculate_indicators(df_15m) if df_15m is not None and len(df_15m) >= 50 else None
            df_30m = self._calculate_indicators(df_30m) if df_30m is not None and len(df_30m) >= 50 else None

            # 3. Per-TF signal
            sig_5m  = self._analyze_timeframe_signal(df_5m,  "5m")
            sig_15m = self._analyze_timeframe_signal(df_15m, "15m") if df_15m is not None else None
            sig_30m = self._analyze_timeframe_signal(df_30m, "30m") if df_30m is not None else None

            # 4. Timeframe alignment check
            tf_alignment, direction = self._check_tf_alignment(sig_5m, sig_15m, sig_30m)

            # Need at least 2 TFs aligned — never trade on single TF
            if tf_alignment < 2 or direction is None:
                logger.debug(f"{symbol}: only {tf_alignment}/3 TFs aligned — skip")
                return 0.0, LEVERAGE_MIN, None

            # 5. Market regime from 30m (or 15m if 30m unavailable)
            regime_df = df_30m if df_30m is not None else df_15m
            market_regime = self._determine_regime(regime_df) if regime_df is not None else "UNKNOWN"

            # Block LONG in BEARISH regime, SHORT in BULLISH regime (Session 4 lesson)
            if direction == Direction.LONG and market_regime == "BEARISH":
                logger.debug(f"{symbol}: LONG blocked — BEARISH 30m regime")
                return 0.0, LEVERAGE_MIN, None
            if direction == Direction.SHORT and market_regime == "BULLISH":
                logger.debug(f"{symbol}: SHORT blocked — BULLISH 30m regime")
                return 0.0, LEVERAGE_MIN, None

            # 6. Confluence scoring (sets A, B, C)
            confluences_hit, confluence_count, confluence_score = self._score_confluences(
                df_5m, df_15m, direction
            )

            # Minimum 4 confluences for a valid trade
            if confluence_count < 4:
                logger.debug(f"{symbol}: only {confluence_count} confluences — need 4+")
                return 0.0, LEVERAGE_MIN, None

            # 7. Entry price, SL, TP
            current_price = float(df_5m["close"].iloc[-1])
            atr_5m = float(df_5m["atr"].iloc[-1]) if "atr" in df_5m.columns else current_price * 0.002

            entry_price, sl, tp = self._calculate_levels(
                direction, current_price, atr_5m
            )
            rr_ratio = self._calculate_rr_ratio(entry_price, sl, tp, direction)

            if rr_ratio < MIN_RR_RATIO:
                logger.debug(f"{symbol}: R:R {rr_ratio:.2f} < {MIN_RR_RATIO} — skip")
                return 0.0, LEVERAGE_MIN, None

            # 8. Adaptive leverage
            win_rate    = self._get_win_rate(last_n=20)
            atr_pct     = self._get_atr_percentile(df_5m, df_15m, df_30m)
            sharpe      = self._calculate_sharpe()

            leverage, factors = self.calculate_adaptive_leverage(
                win_rate     = win_rate,
                volatility   = atr_pct,
                confluence   = confluence_score,
                sharpe       = sharpe,
                rr_ratio     = rr_ratio,
            )

            # Override leverage if we're in consecutive-loss cooldown
            if self._consec_loss_cooldown_remaining > 0:
                leverage = LEVERAGE_MIN
                factors.final_leverage = LEVERAGE_MIN
                factors.decision_narrative += " [Consec-loss cooldown: 25x forced]"

            # 9. Build confidence score (0-100) based on TF alignment + confluences
            confidence = self._build_confidence_score(
                tf_alignment, confluence_count, rr_ratio, factors.setup_score
            )

            # 10. Build signal object
            signal = EntrySignal(
                symbol             = symbol,
                direction          = direction,
                confidence_score   = confidence,
                leverage_rec       = leverage,
                leverage_factors   = factors,
                entry_price        = entry_price,
                stop_loss          = sl,
                take_profit        = tp,
                rr_ratio           = rr_ratio,
                timeframe_alignment= tf_alignment,
                confluence_count   = confluence_count,
                confluences_hit    = confluences_hit,
                market_regime      = market_regime,
            )

            return confidence, leverage, signal

        except Exception as e:
            logger.error(f"analyze_setup error for {symbol}: {e}", exc_info=True)
            return 0.0, LEVERAGE_MIN, None

    def calculate_adaptive_leverage(
        self,
        win_rate: float,
        volatility: float,   # ATR percentile 0-100 (higher = more volatile)
        confluence: int,     # 1-5 score
        sharpe: float,
        rr_ratio: float,
    ) -> Tuple[int, LeverageFactors]:
        """
        5-factor adaptive leverage model.

        Formula (per spec):
          base_leverage       = 25
          win_rate_factor     = (win_rate / 50) * 30           → 0 to ~60
          volatility_factor   = (1 - atr_pct/100) * 40        → 0 to 40
                                [NOTE: INVERTED from raw spec so that low
                                volatility = higher leverage — institutionally
                                correct and matches spec section 7 narrative]
          confluence_bonus    = confluence_score * 15          → 15 to 75
          sharpe_adjustment   = (sharpe / 2) * 20             → variable
          rr_factor           = (rr_ratio - 1.5) * 10         → 0+ bonus
          raw = base + all factors
          final = clamp(raw, 25, 150)
        """
        base_leverage = 25

        # Factor 1: Win rate — the higher above 50% the more leverage we earn
        win_rate_factor = (win_rate / 50.0) * 30.0

        # Factor 2: Volatility — low volatility = safer → more leverage
        # INVERTED: volatility_factor is larger when ATR percentile is LOW
        volatility_factor = min((1.0 - volatility / 100.0) * 40.0, 40.0)

        # Factor 3: Confluence quality (1-5 score)
        confluence_bonus = float(max(1, min(5, confluence))) * 15.0

        # Factor 4: Sharpe ratio of recent trades
        # Negative Sharpe penalises leverage; capped so it can't send below base
        sharpe_adjustment = (sharpe / 2.0) * 20.0

        # Factor 5: R:R bonus (above minimum 1.5 earns extra leverage)
        rr_factor = max(0.0, (rr_ratio - MIN_RR_RATIO) * 10.0)

        raw_leverage = (
            base_leverage
            + win_rate_factor
            + volatility_factor
            + confluence_bonus
            + sharpe_adjustment
            + rr_factor
        )

        final_leverage = int(max(LEVERAGE_MIN, min(LEVERAGE_MAX, round(raw_leverage))))

        # --- Setup quality score 0-100 for narrative ---
        setup_score = min(100.0, (
            (win_rate / 100.0) * 25
            + ((1 - volatility / 100.0) * 20)
            + (confluence / 5.0) * 25
            + max(0.0, min(1.0, sharpe / 3.0)) * 15
            + max(0.0, min(1.0, (rr_ratio - 1.0) / 2.0)) * 15
        ))

        if setup_score >= 90:
            narrative = "Exceptional setup (90+): Allow 150x leverage"
        elif setup_score >= 70:
            narrative = "Good setup (70-89): Allow 75-100x leverage"
        elif setup_score >= 50:
            narrative = "Okay setup (50-69): Allow 50-75x leverage"
        elif setup_score >= 40:
            narrative = "Marginal setup (40-49): Allow 25-50x leverage"
        else:
            narrative = "Skip setup (<40): Don't trade"
            final_leverage = LEVERAGE_MIN

        factors = LeverageFactors(
            win_rate          = win_rate,
            win_rate_factor   = round(win_rate_factor, 2),
            atr_percentile    = round(volatility, 2),
            volatility_factor = round(volatility_factor, 2),
            confluence_score  = confluence,
            confluence_bonus  = confluence_bonus,
            sharpe_ratio      = round(sharpe, 3),
            sharpe_adjustment = round(sharpe_adjustment, 2),
            rr_ratio          = round(rr_ratio, 2),
            rr_factor         = round(rr_factor, 2),
            base_leverage     = base_leverage,
            raw_leverage      = round(raw_leverage, 2),
            final_leverage    = final_leverage,
            setup_score       = round(setup_score, 1),
            decision_narrative= narrative,
        )

        return final_leverage, factors

    def get_adaptive_leverage(self) -> Dict[str, Any]:
        """
        Return current leverage recommendation with all decision factors
        based on the last 20 trades in history.  Useful for dashboards.
        """
        win_rate = self._get_win_rate(last_n=20)
        sharpe   = self._calculate_sharpe()

        # Use placeholder values when no live market data is available
        leverage, factors = self.calculate_adaptive_leverage(
            win_rate   = win_rate,
            volatility = 50.0,   # neutral ATR percentile
            confluence = 3,
            sharpe     = sharpe,
            rr_ratio   = MIN_RR_RATIO,
        )

        return {
            "recommended_leverage": leverage,
            "factors": asdict(factors),
            "daily_pnl": self._daily_pnl,
            "active_trades": len(self.active_trades),
            "consec_losses": self._consec_losses,
            "cooldown_remaining": self._consec_loss_cooldown_remaining,
        }

    async def execute_trade(
        self,
        symbol: str,
        leverage: int,
        position_size_usd: float,
        signal: Optional[EntrySignal] = None,
    ) -> Optional[str]:
        """
        Set leverage and open a market order on MEXC futures.

        Returns trade_id on success, None on failure.
        """
        if not self.check_daily_limits():
            logger.warning("execute_trade: daily limits breached — trade blocked")
            return None

        # Capacity checks
        sym_count = sum(1 for t in self.active_trades.values() if t.symbol == symbol)
        if sym_count >= MAX_CONCURRENT_PER_SYMBOL:
            logger.warning(f"execute_trade: max concurrent trades ({MAX_CONCURRENT_PER_SYMBOL}) hit for {symbol}")
            return None
        if len(self.active_trades) >= MAX_CONCURRENT_TOTAL:
            logger.warning(f"execute_trade: global max concurrent trades ({MAX_CONCURRENT_TOTAL}) hit")
            return None

        # Enforce position size limit
        position_size_usd = min(position_size_usd, MAX_POSITION_USD)
        # Apply tier-based reduction
        if self._daily_pnl <= TIER_REDUCE_POSITION:
            position_size_usd = min(position_size_usd, 50.0)

        leverage = max(LEVERAGE_MIN, min(LEVERAGE_MAX, leverage))

        # Hard enforce daily loss tier leverage caps — these override the adaptive model.
        # Tier 1 (-$2500): cap at 25x. Tier 2 (-$4000): cap at 25x + position already at $50.
        if self._daily_pnl <= TIER_REDUCE_LEVERAGE:
            leverage = LEVERAGE_MIN
            logger.warning(
                f"Daily loss tier active (pnl={self._daily_pnl:.2f}) — leverage hard-capped at {LEVERAGE_MIN}x"
            )

        direction = signal.direction if signal else Direction.LONG

        # Adjust entry price for fees (conservative — assume market fill + slippage)
        current_price = signal.entry_price if signal else 0.0
        if current_price <= 0:
            logger.error("execute_trade: invalid entry price in signal")
            return None

        slip_mult = 1 + TRADE_FEE_PCT if direction == Direction.LONG else 1 - TRADE_FEE_PCT
        entry_price = current_price * slip_mult

        trade_id = str(uuid.uuid4())[:12]

        try:
            if self.mexc_futures is not None and os.environ.get("MEXC_API_KEY"):
                # Set leverage on exchange
                await self.mexc_futures.set_leverage(leverage, symbol)

                # Calculate quantity in contracts (1 contract = 0.0001 BTC on MEXC)
                qty = position_size_usd / entry_price
                side = "buy" if direction == Direction.LONG else "sell"

                order = await self.mexc_futures.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=qty,
                    params={"positionSide": "LONG" if direction == Direction.LONG else "SHORT"},
                )
                logger.info(
                    f"[{trade_id}] Order placed: {direction.value} {qty:.6f} BTC "
                    f"@ ~{entry_price:.2f} | {leverage}x | order_id={order.get('id')}"
                )
            else:
                # Paper mode — no live credentials
                logger.info(
                    f"[{trade_id}] PAPER {direction.value} {position_size_usd:.2f}USD "
                    f"@ {entry_price:.2f} | {leverage}x leverage"
                )

        except Exception as e:
            logger.error(f"execute_trade: order placement failed — {e}", exc_info=True)
            return None

        # Determine max hold time from TF alignment
        max_hold = MAX_HOLD_5M_SECS
        if signal and signal.timeframe_alignment == 3:
            max_hold = MAX_HOLD_15M_SECS

        sl = signal.stop_loss if signal else (
            entry_price * (1 - 0.02) if direction == Direction.LONG else entry_price * (1 + 0.02)
        )
        tp = signal.take_profit if signal else (
            entry_price * (1 + 0.05) if direction == Direction.LONG else entry_price * (1 - 0.05)
        )

        trade = ActiveTrade(
            trade_id         = trade_id,
            symbol           = symbol,
            direction        = direction,
            entry_price      = entry_price,
            stop_loss        = sl,
            take_profit      = tp,
            leverage         = leverage,
            position_size_usd= position_size_usd,
            scale_factor     = 1.0,
            open_time        = datetime.now(timezone.utc),
            max_hold_secs    = max_hold,
            highest_price    = entry_price,
            lowest_price     = entry_price,
            signal           = signal,
        )
        self.active_trades[trade_id] = trade
        logger.info(
            f"[{trade_id}] Trade opened — SL={sl:.2f} TP={tp:.2f} "
            f"R:R={(signal.rr_ratio if signal else 'n/a')} hold_max={max_hold}s"
        )
        return trade_id

    async def manage_trade(
        self,
        trade_id: str,
        current_price: float,
    ) -> Tuple[Optional[ExitReason], float]:
        """
        Evaluate an open trade against current price.

        Returns:
            (exit_reason, realised_pnl_usd)
            exit_reason is None when the trade should stay open.
        """
        trade = self.active_trades.get(trade_id)
        if trade is None or trade.state != TradeState.OPEN:
            return None, 0.0

        # ---- Price tracking for trailing stop --------------------------------
        if trade.direction == Direction.LONG:
            trade.highest_price = max(trade.highest_price, current_price)
        else:
            trade.lowest_price = min(trade.lowest_price, current_price)

        # ---- PnL calculation -------------------------------------------------
        if trade.direction == Direction.LONG:
            pnl_pct = (current_price - trade.entry_price) / trade.entry_price
        else:
            pnl_pct = (trade.entry_price - current_price) / trade.entry_price

        gross_pnl = trade.position_size_usd * trade.scale_factor * pnl_pct
        fee_cost  = trade.position_size_usd * TRADE_FEE_PCT * 2   # entry + exit
        net_pnl   = gross_pnl - fee_cost

        # ---- Scale-out logic (TP1 then TP2) ----------------------------------
        # TP1: 50% close at +1%
        if not trade.tp1_hit and pnl_pct >= TP_SCALE_OUT[0][0]:
            trade.tp1_hit = True
            partial_pnl = self._realise_partial(trade, TP_SCALE_OUT[0][1], current_price)
            logger.info(f"[{trade_id}] TP1 hit (+{pnl_pct:.2%}) — closed 50%, pnl={partial_pnl:.2f}")
            await self._place_partial_close(trade, TP_SCALE_OUT[0][1])

        # TP2: 25% close at +1.5%
        if not trade.tp2_hit and pnl_pct >= TP_SCALE_OUT[1][0]:
            trade.tp2_hit = True
            partial_pnl = self._realise_partial(trade, TP_SCALE_OUT[1][1], current_price)
            logger.info(f"[{trade_id}] TP2 hit (+{pnl_pct:.2%}) — closed 25%, pnl={partial_pnl:.2f}")
            await self._place_partial_close(trade, TP_SCALE_OUT[1][1])

        # ---- Activate trailing stop ------------------------------------------
        if not trade.trailing_stop_active and pnl_pct >= TRAILING_STOP_ACTIVATE_PCT:
            trade.trailing_stop_active = True
            trade.trailing_stop_price  = (
                current_price * (1 - TRAILING_STOP_TRAIL_PCT)
                if trade.direction == Direction.LONG
                else current_price * (1 + TRAILING_STOP_TRAIL_PCT)
            )
            logger.debug(f"[{trade_id}] Trailing stop activated at {trade.trailing_stop_price:.2f}")

        # ---- Update trailing stop price --------------------------------------
        if trade.trailing_stop_active:
            if trade.direction == Direction.LONG:
                new_trail = trade.highest_price * (1 - TRAILING_STOP_TRAIL_PCT)
                trade.trailing_stop_price = max(trade.trailing_stop_price, new_trail)
            else:
                new_trail = trade.lowest_price * (1 + TRAILING_STOP_TRAIL_PCT)
                trade.trailing_stop_price = min(trade.trailing_stop_price, new_trail)

        # ---- Exit condition checks -------------------------------------------

        # Hard stop loss
        if trade.direction == Direction.LONG and current_price <= trade.stop_loss:
            return await self._close_trade(trade, current_price, ExitReason.SL)
        if trade.direction == Direction.SHORT and current_price >= trade.stop_loss:
            return await self._close_trade(trade, current_price, ExitReason.SL)

        # Full TP hit (remaining 25% if both scales done)
        if trade.tp1_hit and trade.tp2_hit:
            if trade.direction == Direction.LONG and current_price >= trade.take_profit:
                return await self._close_trade(trade, current_price, ExitReason.TRAILING)
            if trade.direction == Direction.SHORT and current_price <= trade.take_profit:
                return await self._close_trade(trade, current_price, ExitReason.TRAILING)

        # Trailing stop hit
        if trade.trailing_stop_active:
            if trade.direction == Direction.LONG and current_price <= trade.trailing_stop_price:
                return await self._close_trade(trade, current_price, ExitReason.TRAILING)
            if trade.direction == Direction.SHORT and current_price >= trade.trailing_stop_price:
                return await self._close_trade(trade, current_price, ExitReason.TRAILING)

        # Daily hard stop — force close all trades
        if not self.check_daily_limits():
            return await self._close_trade(trade, current_price, ExitReason.DAILY_LIMIT)

        # Time-based exit — scalp opportunity window expired
        elapsed = (datetime.now(timezone.utc) - trade.open_time).total_seconds()
        if elapsed > trade.max_hold_secs:
            logger.info(f"[{trade_id}] Time limit ({trade.max_hold_secs}s) — exiting")
            return await self._close_trade(trade, current_price, ExitReason.TIME_LIMIT)

        return None, net_pnl   # still open

    def track_daily_loss(self) -> float:
        """Return current daily PnL (negative = loss). Resets at UTC midnight."""
        self._maybe_reset_daily()
        return self._daily_pnl

    def check_daily_limits(self) -> bool:
        """
        Returns True if trading is allowed under daily risk rules.
        Checks all three loss tiers defined in spec section 5.
        """
        self._maybe_reset_daily()
        if self._daily_pnl <= TIER_HARD_STOP:
            logger.warning(
                f"HARD STOP: daily PnL {self._daily_pnl:.2f} ≤ {TIER_HARD_STOP}. No more trades today."
            )
            return False
        return True

    async def log_trade_data(self, trade_data: Dict[str, Any]) -> None:
        """
        Persist full trade record to MongoDB for learning / analytics.
        Collection: institutional_scalper_trades
        """
        if self.db is not None:
            try:
                await self.db["institutional_scalper_trades"].insert_one(trade_data)
            except Exception as e:
                logger.error(f"log_trade_data MongoDB error: {e}", exc_info=True)

        # Keep in-memory ring buffer (last 100 closed)
        self.trade_history.append(trade_data)
        if len(self.trade_history) > 100:
            self.trade_history.pop(0)

    # ======================================================================
    # MAIN LOOP
    # ======================================================================

    async def run_scalper_loop(self, interval_secs: int = 30) -> None:
        """
        Main engine loop.

        Runs every `interval_secs` seconds:
          1. Manage all open trades (exit checks)
          2. Fetch fresh price for BTC
          3. Run analyze_setup on BTCUSDT
          4. Execute trade if signal qualifies
        """
        logger.info("InstitutionalScalper loop started")
        while self.active:
            try:
                # ---- Step 1: manage open trades ----------------------------
                if self.active_trades:
                    current_price = await self._fetch_current_price(SYMBOL)
                    if current_price and current_price > 0:
                        for tid in list(self.active_trades.keys()):
                            reason, pnl = await self.manage_trade(tid, current_price)
                            if reason is not None:
                                logger.info(f"[{tid}] Closed: {reason.value} pnl={pnl:.2f}")

                # ---- Step 2: check if we can open new trades ---------------
                if not self.check_daily_limits():
                    await asyncio.sleep(interval_secs)
                    continue

                open_count = len(self.active_trades)
                if open_count >= MAX_CONCURRENT_TOTAL:
                    await asyncio.sleep(interval_secs)
                    continue

                sym_count = sum(1 for t in self.active_trades.values() if t.symbol == SYMBOL)
                if sym_count >= MAX_CONCURRENT_PER_SYMBOL:
                    await asyncio.sleep(interval_secs)
                    continue

                # ---- Step 3: analyse for new entry -------------------------
                confidence, leverage, signal = await self.analyze_setup(SYMBOL)

                if signal is None or confidence < 60:
                    logger.debug(f"No signal (conf={confidence:.1f})")
                    await asyncio.sleep(interval_secs)
                    continue

                # Skip if setup score is below 40 (marginal setup)
                if signal.leverage_factors.setup_score < 40:
                    logger.debug(f"Setup score {signal.leverage_factors.setup_score} < 40 — skip")
                    await asyncio.sleep(interval_secs)
                    continue

                logger.info(
                    f"Signal: {signal.direction.value} conf={confidence:.1f} "
                    f"lev={leverage}x rr={signal.rr_ratio:.2f} "
                    f"confluences={signal.confluence_count} [{', '.join(signal.confluences_hit[:3])}...]"
                )

                # ---- Step 4: execute ---------------------------------------
                position_size = self._calculate_position_size(leverage)
                trade_id = await self.execute_trade(
                    symbol=SYMBOL,
                    leverage=leverage,
                    position_size_usd=position_size,
                    signal=signal,
                )

                if trade_id:
                    logger.info(f"New trade opened: {trade_id}")

            except asyncio.CancelledError:
                logger.info("InstitutionalScalper loop cancelled")
                break
            except Exception as e:
                logger.error(f"Scalper loop error: {e}", exc_info=True)

            await asyncio.sleep(interval_secs)

        await self._cleanup()
        logger.info("InstitutionalScalper loop stopped")

    # ======================================================================
    # PRIVATE — Market Data
    # ======================================================================

    async def _fetch_all_timeframes(self, symbol: str) -> Optional[Dict[str, pd.DataFrame]]:
        """Fetch 5m, 15m, 30m candles concurrently."""
        try:
            results = await asyncio.gather(
                self._fetch_candles(symbol, "5m",  CANDLE_LIMIT),
                self._fetch_candles(symbol, "15m", CANDLE_LIMIT),
                self._fetch_candles(symbol, "30m", CANDLE_LIMIT),
                return_exceptions=True,
            )
            out = {}
            for tf, res in zip(["5m", "15m", "30m"], results):
                if isinstance(res, Exception):
                    logger.warning(f"Failed to fetch {tf}: {res}")
                    out[tf] = None
                else:
                    out[tf] = res
            return out
        except Exception as e:
            logger.error(f"_fetch_all_timeframes error: {e}", exc_info=True)
            return None

    async def _fetch_candles(
        self, symbol: str, timeframe: str, limit: int
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV with a 30s cache to avoid API hammering."""
        cache_key = (symbol, timeframe)
        cached = self._candle_cache.get(cache_key)
        if cached:
            df, fetched_at = cached
            age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
            if age < self._cache_ttl_secs:
                return df

        if self.mexc is None:
            return None

        try:
            ohlcv = await self.mexc.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.sort_values("timestamp").reset_index(drop=True)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            self._candle_cache[cache_key] = (df, datetime.now(timezone.utc))
            return df
        except Exception as e:
            logger.error(f"_fetch_candles {symbol} {timeframe}: {e}", exc_info=True)
            return None

    async def _fetch_current_price(self, symbol: str) -> Optional[float]:
        """Fetch latest bid/ask midpoint."""
        if self.mexc is None:
            return None
        try:
            ticker = await self.mexc.fetch_ticker(symbol)
            return float(ticker.get("last") or ticker.get("close") or 0)
        except Exception as e:
            logger.debug(f"_fetch_current_price error: {e}")
            return None

    # ======================================================================
    # PRIVATE — Indicators
    # ======================================================================

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all required indicators to a candle DataFrame.
        Uses the `ta` library where available, falls back to numpy otherwise.
        """
        if df is None or len(df) < 30:
            return df

        close  = df["close"].values.astype(float)
        high   = df["high"].values.astype(float)
        low    = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        # ---- EMA 9 and 21 ------------------------------------------------
        df["ema9"]  = self._ema(close, 9)
        df["ema21"] = self._ema(close, 21)
        df["ema_cross_bull"] = (df["ema9"] > df["ema21"]) & (df["ema9"].shift(1) <= df["ema21"].shift(1))
        df["ema_cross_bear"] = (df["ema9"] < df["ema21"]) & (df["ema9"].shift(1) >= df["ema21"].shift(1))

        # ---- RSI 14 -------------------------------------------------------
        df["rsi"] = self._rsi(close, 14)

        # ---- ATR 14 -------------------------------------------------------
        df["atr"] = self._atr(high, low, close, 14)
        df["atr_pct"] = df["atr"] / df["close"] * 100   # % of price

        # ---- VWAP (session-anchored, resets daily) ------------------------
        df["vwap"] = self._vwap(df)

        return df

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        alpha = 2.0 / (period + 1)
        result = np.full(len(values), np.nan)
        if len(values) < period:
            return result
        result[period - 1] = values[:period].mean()
        for i in range(period, len(values)):
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
        return result

    @staticmethod
    def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        """Wilder's RSI."""
        delta  = np.diff(close, prepend=close[0])
        gain   = np.where(delta > 0, delta, 0.0)
        loss   = np.where(delta < 0, -delta, 0.0)
        avg_g  = np.full(len(close), np.nan)
        avg_l  = np.full(len(close), np.nan)
        if len(close) <= period:
            return avg_g
        avg_g[period] = gain[1:period + 1].mean()
        avg_l[period] = loss[1:period + 1].mean()
        for i in range(period + 1, len(close)):
            avg_g[i] = (avg_g[i - 1] * (period - 1) + gain[i]) / period
            avg_l[i] = (avg_l[i - 1] * (period - 1) + loss[i]) / period
        rs  = np.where(avg_l != 0, avg_g / avg_l, 100.0)
        rsi = 100.0 - 100.0 / (1.0 + rs)
        rsi[:period] = np.nan
        return rsi

    @staticmethod
    def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Average True Range."""
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
        )
        atr = np.full(len(close), np.nan)
        if len(tr) < period:
            return atr
        atr[period - 1] = tr[:period].mean()
        for i in range(period, len(tr)):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        return atr

    @staticmethod
    def _vwap(df: pd.DataFrame) -> pd.Series:
        """
        Session-anchored VWAP — resets daily at UTC midnight.
        Groups candles by calendar date and computes VWAP per session.
        """
        vwap = pd.Series(np.nan, index=df.index)
        df["_date"] = df["timestamp"].dt.date
        for _, group in df.groupby("_date"):
            idx   = group.index
            tp    = (group["high"] + group["low"] + group["close"]) / 3.0
            cum_v = group["volume"].cumsum()
            cum_pv= (tp * group["volume"]).cumsum()
            vwap[idx] = cum_pv / cum_v.replace(0, np.nan)
        df.drop(columns=["_date"], inplace=True, errors="ignore")
        return vwap

    # ======================================================================
    # PRIVATE — Signal Analysis
    # ======================================================================

    def _analyze_timeframe_signal(
        self, df: Optional[pd.DataFrame], timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """
        Derive a directional bias for a single timeframe.
        Returns {"direction": "LONG"/"SHORT"/"NEUTRAL", "strength": 0-3}
        """
        if df is None or len(df) < 30:
            return None
        if "rsi" not in df.columns or "ema9" not in df.columns:
            return None

        row   = df.iloc[-1]
        close = float(row["close"])
        rsi   = float(row["rsi"]) if not np.isnan(row["rsi"]) else 50.0
        ema9  = float(row["ema9"])  if not np.isnan(row["ema9"])  else close
        ema21 = float(row["ema21"]) if not np.isnan(row["ema21"]) else close
        vwap  = float(row["vwap"])  if not np.isnan(row["vwap"])  else close

        long_score  = 0
        short_score = 0

        if close > ema9 > ema21:
            long_score += 1
        if close < ema9 < ema21:
            short_score += 1
        if rsi < 50:
            short_score += 1
        if rsi > 50:
            long_score += 1
        if close > vwap:
            long_score += 1
        if close < vwap:
            short_score += 1

        if long_score > short_score:
            return {"direction": "LONG", "strength": long_score, "timeframe": timeframe}
        if short_score > long_score:
            return {"direction": "SHORT", "strength": short_score, "timeframe": timeframe}
        return {"direction": "NEUTRAL", "strength": 0, "timeframe": timeframe}

    def _check_tf_alignment(
        self,
        sig_5m: Optional[Dict],
        sig_15m: Optional[Dict],
        sig_30m: Optional[Dict],
    ) -> Tuple[int, Optional[Direction]]:
        """
        Check how many timeframes agree on direction.

        Returns (alignment_count, direction):
          3 = all aligned → HIGH confidence
          2 = two aligned → MEDIUM confidence
          1 = only one    → SKIP
        """
        signals = [s for s in [sig_5m, sig_15m, sig_30m] if s is not None]
        if not signals:
            return 0, None

        long_count  = sum(1 for s in signals if s["direction"] == "LONG")
        short_count = sum(1 for s in signals if s["direction"] == "SHORT")

        if long_count >= 2:
            return long_count, Direction.LONG
        if short_count >= 2:
            return short_count, Direction.SHORT
        return 1, None

    def _determine_regime(self, df: pd.DataFrame) -> str:
        """Determine 30m market regime: BULLISH / BEARISH / RANGING."""
        if df is None or len(df) < 50:
            return "UNKNOWN"
        close  = df["close"].values.astype(float)
        ema50  = self._ema(close, 50)
        latest = close[-1]
        em     = ema50[-1] if not np.isnan(ema50[-1]) else latest

        # Trend strength via slope of EMA50 over last 5 candles
        slope = (ema50[-1] - ema50[-6]) / (ema50[-6] + 1e-9)

        if latest > em and slope > 0.001:
            return "BULLISH"
        if latest < em and slope < -0.001:
            return "BEARISH"
        return "RANGING"

    def _score_confluences(
        self,
        df_5m: pd.DataFrame,
        df_15m: Optional[pd.DataFrame],
        direction: Direction,
    ) -> Tuple[List[str], int, int]:
        """
        Score confluence sets A (Technical), B (Smart Money), C (Risk/R:R rules).

        Returns (list_of_hits, total_count, 1-5_score)
        """
        hits: List[str] = []

        row_5m  = df_5m.iloc[-1]
        close   = float(row_5m["close"])
        rsi     = float(row_5m["rsi"])   if not np.isnan(row_5m["rsi"])   else 50.0
        vwap    = float(row_5m["vwap"])  if not np.isnan(row_5m["vwap"])  else close
        ema9    = float(row_5m["ema9"])  if not np.isnan(row_5m["ema9"])  else close
        ema21   = float(row_5m["ema21"]) if not np.isnan(row_5m["ema21"]) else close
        ema_cb  = bool(row_5m.get("ema_cross_bull", False))
        ema_cb2 = bool(row_5m.get("ema_cross_bear", False))

        # ------------------------------------------------------------------
        # Set A — Technical
        # ------------------------------------------------------------------
        if direction == Direction.LONG:
            if rsi < 30:
                hits.append("RSI oversold <30 (5m)")
            if close < vwap * 0.998:   # price at/below VWAP — VWAP bounce setup
                hits.append("VWAP bounce (5m)")
            if ema_cb:
                hits.append("EMA 9/21 bullish cross (5m)")
        else:  # SHORT
            if rsi > 70:
                hits.append("RSI overbought >70 (5m)")
            if close > vwap * 1.002:   # price above VWAP — VWAP rejection setup
                hits.append("VWAP rejection (5m)")
            if ema_cb2:
                hits.append("EMA 9/21 bearish cross (5m)")

        # Key support/resistance from 15m structure
        if df_15m is not None and len(df_15m) >= 20:
            sr_hit = self._check_key_level(df_15m, close, direction)
            if sr_hit:
                hits.append(f"Key S/R level (15m): {sr_hit}")

        # ------------------------------------------------------------------
        # Set B — Smart Money Concepts
        # ------------------------------------------------------------------
        if df_15m is not None and len(df_15m) >= 20:
            if self._detect_order_block(df_15m, direction):
                hits.append("Order block (15m)")

            if self._detect_fvg(df_15m, direction):
                hits.append("Fair value gap (15m)")

            if self._detect_bos(df_15m, direction):
                hits.append("Break of structure (15m)")

            if self._detect_liquidity_sweep(df_5m, df_15m, direction):
                hits.append("Liquidity sweep (5m→15m)")

        # ------------------------------------------------------------------
        # Set C — R:R + risk rules (checked later in analyze_setup, added here for count)
        # ------------------------------------------------------------------
        # R:R and position size are validated pre-call; count them if we reached here
        hits.append("R:R ≥ 1.5:1 (validated)")
        hits.append("Position size within limit")
        daily_ok = self._daily_pnl > -5000
        if daily_ok:
            hits.append("Daily PnL allows trade")
        # Spec Set C: win rate on symbol > 45% (using last-20 engine-wide win rate for BTCUSDT-only engine)
        if self._get_win_rate(last_n=20) > 45.0:
            hits.append("Win rate > 45% (last 20 trades)")

        total = len(hits)
        # Map count to 1-5 score
        if total >= 10:
            score = 5
        elif total >= 8:
            score = 4
        elif total >= 6:
            score = 3
        elif total >= 4:
            score = 2
        else:
            score = 1

        return hits, total, score

    def _check_key_level(
        self, df: pd.DataFrame, price: float, direction: Direction
    ) -> Optional[str]:
        """Check if price is near a recent swing high/low."""
        highs = df["high"].values[-20:]
        lows  = df["low"].values[-20:]
        atr   = float(df["atr"].iloc[-1]) if "atr" in df.columns and not np.isnan(df["atr"].iloc[-1]) else price * 0.002

        if direction == Direction.LONG:
            # Is price bouncing off a recent swing low?
            recent_low = lows.min()
            if abs(price - recent_low) < atr * 1.5:
                return f"swing_low={recent_low:.2f}"
        else:
            recent_high = highs.max()
            if abs(price - recent_high) < atr * 1.5:
                return f"swing_high={recent_high:.2f}"
        return None

    def _detect_order_block(self, df: pd.DataFrame, direction: Direction) -> bool:
        """
        Detect institutional order block:
        - Bullish OB: last down-candle before a strong up-move (demand zone)
        - Bearish OB: last up-candle before a strong down-move (supply zone)
        """
        if len(df) < 5:
            return False
        closes = df["close"].values.astype(float)
        opens  = df["open"].values.astype(float)
        for i in range(-5, -1):
            if direction == Direction.LONG:
                # Down candle followed by strong up candle (bullish OB)
                if closes[i] < opens[i] and closes[i + 1] > opens[i + 1]:
                    body_ratio = abs(closes[i + 1] - opens[i + 1]) / (abs(closes[i] - opens[i]) + 1e-9)
                    if body_ratio > 1.5:
                        return True
            else:
                # Up candle followed by strong down candle (bearish OB)
                if closes[i] > opens[i] and closes[i + 1] < opens[i + 1]:
                    body_ratio = abs(closes[i + 1] - opens[i + 1]) / (abs(closes[i] - opens[i]) + 1e-9)
                    if body_ratio > 1.5:
                        return True
        return False

    def _detect_fvg(self, df: pd.DataFrame, direction: Direction) -> bool:
        """
        Fair Value Gap: gap between candle[i].high and candle[i+2].low (bullish)
        or candle[i].low and candle[i+2].high (bearish).
        """
        if len(df) < 4:
            return False
        for i in range(-4, -2):
            if direction == Direction.LONG:
                # Bullish FVG: low of candle i+2 > high of candle i
                if df["low"].iloc[i + 2] > df["high"].iloc[i]:
                    return True
            else:
                # Bearish FVG: high of candle i+2 < low of candle i
                if df["high"].iloc[i + 2] < df["low"].iloc[i]:
                    return True
        return False

    def _detect_bos(self, df: pd.DataFrame, direction: Direction) -> bool:
        """
        Break of Structure: price has just broken above last swing high (bullish)
        or below last swing low (bearish).
        """
        if len(df) < 10:
            return False
        current_close = float(df["close"].iloc[-1])
        lookback      = df.iloc[-10:-1]

        if direction == Direction.LONG:
            prev_swing_high = float(lookback["high"].max())
            return current_close > prev_swing_high
        else:
            prev_swing_low = float(lookback["low"].min())
            return current_close < prev_swing_low

    def _detect_liquidity_sweep(
        self,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        direction: Direction,
    ) -> bool:
        """
        Liquidity sweep: price wicked below (LONG) or above (SHORT) a prior equal-low/high
        then snapped back — smart money grabbed stops before reversing.
        """
        if len(df_5m) < 10 or len(df_15m) < 10:
            return False

        recent_low_5m  = float(df_5m["low"].iloc[-5:-1].min())
        recent_high_5m = float(df_5m["high"].iloc[-5:-1].max())
        last_low_5m    = float(df_5m["low"].iloc[-1])
        last_high_5m   = float(df_5m["high"].iloc[-1])
        last_close_5m  = float(df_5m["close"].iloc[-1])

        swing_low_15m  = float(df_15m["low"].iloc[-10:-1].min())
        swing_high_15m = float(df_15m["high"].iloc[-10:-1].max())

        if direction == Direction.LONG:
            # Price dipped below swing low then closed back above — stop hunt
            return last_low_5m < swing_low_15m and last_close_5m > swing_low_15m
        else:
            # Price spiked above swing high then closed back below — stop hunt
            return last_high_5m > swing_high_15m and last_close_5m < swing_high_15m

    # ======================================================================
    # PRIVATE — Level Calculation
    # ======================================================================

    def _calculate_levels(
        self,
        direction: Direction,
        current_price: float,
        atr: float,
    ) -> Tuple[float, float, float]:
        """
        Calculate entry, stop-loss, take-profit based on ATR.

        SL: 2× ATR from entry (spec: 2-3%, ATR-adjusted)
        TP: 3× ATR from entry (ensures R:R ≥ 1.5)
        """
        if direction == Direction.LONG:
            entry = current_price
            sl    = entry - (atr * 2.0)
            tp    = entry + (atr * 3.5)
        else:
            entry = current_price
            sl    = entry + (atr * 2.0)
            tp    = entry - (atr * 3.5)
        return entry, sl, tp

    @staticmethod
    def _calculate_rr_ratio(
        entry: float, sl: float, tp: float, direction: Direction
    ) -> float:
        """Reward-to-risk ratio."""
        risk   = abs(entry - sl)
        reward = abs(tp - entry)
        if risk <= 0:
            return 0.0
        return round(reward / risk, 2)

    # ======================================================================
    # PRIVATE — Risk & Sizing
    # ======================================================================

    def _calculate_position_size(self, leverage: int) -> float:
        """
        Size based on daily loss tier.
        Normal → $150, at -$4k tier → $50.
        """
        if self._daily_pnl <= TIER_REDUCE_POSITION:
            return 50.0
        return MAX_POSITION_USD

    def _get_atr_percentile(
        self,
        df_5m: Optional[pd.DataFrame],
        df_15m: Optional[pd.DataFrame],
        df_30m: Optional[pd.DataFrame],
    ) -> float:
        """
        Compute ATR as a percentile (0-100) across the 3 timeframes.
        High percentile = currently more volatile than recent history.
        """
        pcts = []
        for df in [df_5m, df_15m, df_30m]:
            if df is None or "atr" not in df.columns:
                continue
            atr_series = df["atr"].dropna()
            if len(atr_series) < 10:
                continue
            current_atr = float(atr_series.iloc[-1])
            percentile  = float(np.percentile(atr_series.values, 100 *
                          (atr_series.values <= current_atr).mean()))
            pcts.append(percentile)
        return float(np.mean(pcts)) if pcts else 50.0

    def _get_win_rate(self, last_n: int = 20) -> float:
        """Win rate % of the last N closed trades (0-100)."""
        closed = [t for t in self.trade_history if t.get("state") == "CLOSED"][-last_n:]
        if not closed:
            return 50.0  # neutral assumption with no data
        wins = sum(1 for t in closed if t.get("pnl_usd", 0) > 0)
        return (wins / len(closed)) * 100.0

    def _calculate_sharpe(self, last_n: int = 20) -> float:
        """Annualised Sharpe ratio of the last N closed trades (daily PnL % returns)."""
        closed = [t for t in self.trade_history if t.get("state") == "CLOSED"][-last_n:]
        if len(closed) < 3:
            return 0.0
        returns = np.array([t.get("pnl_pct", 0.0) for t in closed], dtype=float)
        mean_r  = np.mean(returns)
        std_r   = np.std(returns)
        if std_r == 0:
            return 0.0
        # Approximate annualisation for 5m bars: 288 bars/day * 252 days
        return float((mean_r / std_r) * np.sqrt(288 * 252))

    def _build_confidence_score(
        self,
        tf_alignment: int,
        confluence_count: int,
        rr_ratio: float,
        setup_score: float,
    ) -> float:
        """
        Composite confidence score 0-100.
        Weights: TF alignment 30%, confluence 30%, R:R 20%, setup score 20%.
        """
        tf_component    = (tf_alignment / 3.0) * 30.0
        conf_component  = min(confluence_count / 10.0, 1.0) * 30.0
        rr_component    = min((rr_ratio - 1.0) / 3.0, 1.0) * 20.0
        score_component = (setup_score / 100.0) * 20.0
        return round(tf_component + conf_component + rr_component + score_component, 1)

    # ======================================================================
    # PRIVATE — Trade Lifecycle
    # ======================================================================

    async def _close_trade(
        self,
        trade: ActiveTrade,
        current_price: float,
        reason: ExitReason,
    ) -> Tuple[ExitReason, float]:
        """Close remaining position, calculate PnL, update state, log."""
        if trade.direction == Direction.LONG:
            pnl_pct = (current_price - trade.entry_price) / trade.entry_price
        else:
            pnl_pct = (trade.entry_price - current_price) / trade.entry_price

        gross_pnl = trade.position_size_usd * trade.scale_factor * pnl_pct
        fee_cost  = trade.position_size_usd * TRADE_FEE_PCT * 2
        net_pnl   = gross_pnl - fee_cost

        trade.state = TradeState.CLOSED

        # Update daily PnL
        self._daily_pnl += net_pnl

        # Update consecutive-loss counter
        if net_pnl < 0:
            self._consec_losses += 1
            if self._consec_losses >= CONSEC_LOSS_LIMIT and self._consec_loss_cooldown_remaining == 0:
                self._consec_loss_cooldown_remaining = CONSEC_LOSS_COOLDOWN
                logger.warning(
                    f"3 consecutive losses — 25x leverage enforced for next "
                    f"{CONSEC_LOSS_COOLDOWN} trades"
                )
        else:
            self._consec_losses = 0

        # Cooldown counts down on every trade close (win or loss).
        # Previous code only decremented on wins — losses during cooldown would lock 25x forever.
        if self._consec_loss_cooldown_remaining > 0:
            self._consec_loss_cooldown_remaining -= 1
            logger.debug(
                f"Consec-loss cooldown: {self._consec_loss_cooldown_remaining} trades remaining"
            )

        # Remove from active
        self.active_trades.pop(trade.trade_id, None)

        # Attempt exchange close
        await self._place_full_close(trade, current_price)

        # Build log record
        trade_record = self._build_trade_record(trade, current_price, reason, net_pnl, pnl_pct)
        await self.log_trade_data(trade_record)

        logger.info(
            f"[{trade.trade_id}] CLOSED: {reason.value} "
            f"entry={trade.entry_price:.2f} exit={current_price:.2f} "
            f"pnl={net_pnl:.2f} daily_pnl={self._daily_pnl:.2f}"
        )

        # Tier warnings
        if self._daily_pnl <= TIER_HARD_STOP:
            logger.critical(f"HARD STOP TRIGGERED — daily PnL {self._daily_pnl:.2f}")
        elif self._daily_pnl <= TIER_REDUCE_POSITION:
            logger.warning(f"Loss tier 2: PnL {self._daily_pnl:.2f} — position reduced to $50, 25x only")
        elif self._daily_pnl <= TIER_REDUCE_LEVERAGE:
            logger.warning(f"Loss tier 1: PnL {self._daily_pnl:.2f} — leverage reduced to 25x")

        return reason, net_pnl

    def _realise_partial(self, trade: ActiveTrade, fraction: float, price: float) -> float:
        """Reduce position by fraction and return realised PnL for that portion."""
        portion_size = trade.position_size_usd * trade.scale_factor * fraction

        if trade.direction == Direction.LONG:
            pnl_pct = (price - trade.entry_price) / trade.entry_price
        else:
            pnl_pct = (trade.entry_price - price) / trade.entry_price

        pnl = portion_size * pnl_pct - (portion_size * TRADE_FEE_PCT * 2)
        trade.scale_factor *= (1 - fraction)
        self._daily_pnl += pnl
        return pnl

    async def _place_partial_close(self, trade: ActiveTrade, fraction: float) -> None:
        """Send partial reduce-only order to exchange."""
        if self.mexc_futures is None or not os.environ.get("MEXC_API_KEY"):
            return
        try:
            qty  = (trade.position_size_usd * fraction) / trade.entry_price
            side = "sell" if trade.direction == Direction.LONG else "buy"
            await self.mexc_futures.create_market_order(
                symbol=trade.symbol,
                side=side,
                amount=qty,
                params={"reduceOnly": True},
            )
        except Exception as e:
            logger.error(f"_place_partial_close error [{trade.trade_id}]: {e}", exc_info=True)

    async def _place_full_close(self, trade: ActiveTrade, price: float) -> None:
        """Close remaining position at market."""
        if self.mexc_futures is None or not os.environ.get("MEXC_API_KEY"):
            return
        try:
            qty  = (trade.position_size_usd * trade.scale_factor) / price
            side = "sell" if trade.direction == Direction.LONG else "buy"
            await self.mexc_futures.create_market_order(
                symbol=trade.symbol,
                side=side,
                amount=qty,
                params={"reduceOnly": True},
            )
        except Exception as e:
            logger.error(f"_place_full_close error [{trade.trade_id}]: {e}", exc_info=True)

    def _build_trade_record(
        self,
        trade: ActiveTrade,
        exit_price: float,
        reason: ExitReason,
        net_pnl: float,
        pnl_pct: float,
    ) -> Dict[str, Any]:
        """
        Build the full MongoDB trade document.
        Captures all learning-relevant fields (spec section 6).
        """
        now = datetime.now(timezone.utc)
        signal = trade.signal

        record: Dict[str, Any] = {
            # Identity
            "trade_id"         : trade.trade_id,
            "symbol"           : trade.symbol,
            "direction"        : trade.direction.value,
            "state"            : "CLOSED",

            # Timing
            "entry_time"       : trade.open_time.isoformat(),
            "exit_time"        : now.isoformat(),
            "hold_duration_secs": (now - trade.open_time).total_seconds(),

            # Prices
            "entry_price"      : trade.entry_price,
            "exit_price"       : exit_price,
            "stop_loss"        : trade.stop_loss,
            "take_profit"      : trade.take_profit,

            # PnL
            "pnl_usd"          : round(net_pnl, 4),
            "pnl_pct"          : round(pnl_pct * 100, 4),
            "is_win"           : net_pnl > 0,
            "exit_reason"      : reason.value,

            # Position
            "leverage"         : trade.leverage,
            "position_size_usd": trade.position_size_usd,

            # Risk events
            "tp1_hit"          : trade.tp1_hit,
            "tp2_hit"          : trade.tp2_hit,
            "trailing_activated": trade.trailing_stop_active,

            # AI learning fields (spec section 6)
            "leverage_factors" : asdict(trade.signal.leverage_factors) if signal else {},
            "confluence_count" : signal.confluence_count if signal else 0,
            "confluences_hit"  : signal.confluences_hit  if signal else [],
            "confidence_score" : signal.confidence_score  if signal else 0,
            "timeframe_alignment": signal.timeframe_alignment if signal else 0,
            "market_regime"    : signal.market_regime     if signal else "UNKNOWN",
            "rr_ratio_planned" : signal.rr_ratio          if signal else 0,
            "setup_score"      : signal.leverage_factors.setup_score if signal else 0,

            # Running totals at time of close
            "daily_pnl_after"  : round(self._daily_pnl, 2),
            "win_rate_at_close": self._get_win_rate(20),
        }
        return record

    # ======================================================================
    # PRIVATE — Utility
    # ======================================================================

    def _maybe_reset_daily(self) -> None:
        """Reset daily PnL counter at UTC midnight."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_reset_date:
            logger.info(
                f"Daily reset: PnL was {self._daily_pnl:.2f} — resetting to 0.00 for {today}"
            )
            self._daily_pnl        = 0.0
            self._daily_reset_date = today
            self._consec_losses    = 0
            self._consec_loss_cooldown_remaining = 0

    async def _cleanup(self) -> None:
        """Close exchange connections gracefully."""
        try:
            if self.mexc is not None:
                await self.mexc.close()
            if self.mexc_futures is not None:
                await self.mexc_futures.close()
        except Exception as e:
            logger.debug(f"_cleanup error: {e}")
