"""
=============================================================
  VWAP Scalper — Institutional Rebuild (Session 11)
=============================================================
Timeframes : 5m / 15m / 30m  (MTF confluence — 2 of 3 must agree)
Signal Logic:
  LONG : EMA9 > EMA21, price > VWAP, RSI bullish zone, 2/3 TF agree
  SHORT: EMA9 < EMA21, price < VWAP, RSI bearish zone, 2/3 TF agree

Smart Money confluences: Order Blocks, FVG, BOS, Liquidity Sweep
Risk management:
  - ATR-based SL (2× ATR) and TP (3.5× ATR)   → ~1.75 R:R
  - Adaptive leverage 25–150x  (5-factor model)
  - Daily loss tiers:
      > $2,500  → max 25x leverage
      > $4,000  → max 25x + $50 position cap
      > $5,000  → hard stop (engine paused until UTC midnight)
  - Consecutive loss cooldown: 3 losses → 25x for next 5 trades

Data source : MEXC via market_intel only (yfinance removed)
Routes to   : PRO account (primary) + STARTER account (secondary)
MongoDB     : vwap_scalper_trades collection
=============================================================
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Set, Any

logger = logging.getLogger(__name__)

# Import unified engine system
try:
    from aeon_engine_system import get_engine_manager, EngineType
except ImportError:
    get_engine_manager = None
    EngineType = None
    logger.warning("Unified engine system not available for VWAP Scalper")


TRADING_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "MATIC/USDT",
    # ARB removed: 76 trades, 8% WR, -$10,255 (2026-03-22)
]

MTF_TIMEFRAMES = ["5m", "15m", "30m"]    # need 2/3 aligned for a signal

# ─── Daily-loss thresholds ────────────────────────────────────────────────────
DAILY_LOSS_TIER_1 = 2_500.0   # cap leverage at 25x
DAILY_LOSS_TIER_2 = 4_000.0   # cap leverage at 25x + cap position at $50
DAILY_LOSS_HARD_STOP = 5_000.0  # pause engine until UTC midnight

# ─── Consecutive-loss cooldown ────────────────────────────────────────────────
CONSEC_LOSS_TRIGGER = 3        # 3 losses in a row
COOLDOWN_TRADE_COUNT = 5       # trades at reduced 25x before normal resumes


class VWAPScalper:
    """
    Institutional VWAP Scalper — MTF, Smart Money, Adaptive Leverage.

    Entry:
      - EMA9/EMA21 cross on primary (5m) + confirmed on 15m or 30m
      - Price above/below session-anchored VWAP
      - RSI in directional zone (not extreme)
      - Volume elevated vs 20-bar average
      - BB not in squeeze (wait for expansion)

    Exit:
      - TP = entry ± 3.5× ATR(14)
      - SL = entry ∓ 2.0× ATR(14)
    """

    def __init__(self, db=None):
        self.db = db
        self.active = True

        # ─── Indicator parameters ─────────────────────────────────────
        self.ema_fast = 9
        self.ema_slow = 21
        self.rsi_period = 14
        self.atr_period = 14
        self.bb_period = 20
        self.bb_std = 2.0

        # ─── RSI zones (directional, not extreme) ─────────────────────
        self.rsi_long_min = 45
        self.rsi_long_max = 70
        self.rsi_short_min = 30
        self.rsi_short_max = 55

        # ─── Volume filter ─────────────────────────────────────────────
        self.min_volume_ratio = 1.3

        # ─── Adaptive leverage (25–150x) — overridden per-signal ──────
        self.min_leverage = 25
        self.max_leverage = 150

        # ─── Daily loss tracking ──────────────────────────────────────
        self.daily_loss_usd = 0.0
        self._last_reset_date = None

        # ─── Consecutive loss cooldown ────────────────────────────────
        self.consec_losses = 0
        self.cooldown_trades_remaining = 0

        # ─── Signal throttle ──────────────────────────────────────────
        self.signals_today = 0
        self.max_signals_per_day = 30

        # ─── Stats ────────────────────────────────────────────────────
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.trade_history: List[Dict] = []   # last 100 closed trades

        # ─── Dependencies ─────────────────────────────────────────────
        self.market_intel = None
        self.send_alert: Optional[Callable] = None
        self.chat_ids: Set[int] = set()
        self.paper_trading = None

        # ─── OHLCV cache (per symbol+timeframe) ───────────────────────
        self._data_cache: Dict[str, Dict] = {}
        self._cache_ttl = 60  # seconds

    def set_dependencies(self, **kwargs):
        """Inject external dependencies."""
        self.market_intel = kwargs.get("market_intel")
        self.send_alert = kwargs.get("send_alert")
        self.chat_ids = kwargs.get("chat_ids", set())
        self.paper_trading = kwargs.get("paper_trading")

    # ─── DAILY RESET ──────────────────────────────────────────────────────────

    def _maybe_reset_daily(self):
        """Reset per-day counters at UTC midnight (date comparison, not hour/minute window)."""
        today = datetime.now(timezone.utc).date()
        if self._last_reset_date != today:
            self.signals_today = 0
            self.daily_loss_usd = 0.0
            self.consec_losses = 0
            self.cooldown_trades_remaining = 0
            self._last_reset_date = today
            logger.info("[VWAP] Daily counters reset for %s", today)

    def _check_daily_loss_limits(self) -> str:
        """
        Returns:
          "hard_stop"  — engine must not place any trades
          "tier2"      — max 25x + $50 position cap
          "tier1"      — max 25x leverage only
          "ok"         — no restriction
        """
        if self.daily_loss_usd >= DAILY_LOSS_HARD_STOP:
            return "hard_stop"
        if self.daily_loss_usd >= DAILY_LOSS_TIER_2:
            return "tier2"
        if self.daily_loss_usd >= DAILY_LOSS_TIER_1:
            return "tier1"
        return "ok"

    # ─── INDICATORS ───────────────────────────────────────────────────────────

    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Exponential Moving Average."""
        if len(prices) < period:
            return [prices[-1]] * len(prices) if prices else []
        multiplier = 2.0 / (period + 1)
        ema_vals = [sum(prices[:period]) / period]
        for price in prices[period:]:
            ema_vals.append((price - ema_vals[-1]) * multiplier + ema_vals[-1])
        return [ema_vals[0]] * (len(prices) - len(ema_vals)) + ema_vals

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[float]:
        """Wilder RSI."""
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        rsi_vals: List[float] = []
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_vals.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_vals.append(100.0 - (100.0 / (1.0 + rs)))
        return [50.0] * (len(prices) - len(rsi_vals)) + rsi_vals

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Average True Range — returns the most-recent ATR value."""
        if len(closes) < period + 1:
            return 0.0
        trs: List[float] = []
        for i in range(1, len(closes)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
            trs.append(max(hl, hc, lc))
        if not trs:
            return 0.0
        # Wilder smoothing
        atr_val = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr_val = (atr_val * (period - 1) + tr) / period
        return atr_val

    @staticmethod
    def vwap(highs: List[float], lows: List[float], closes: List[float],
             volumes: List[float], timestamps: List = None) -> List[float]:
        """
        Session-anchored intraday VWAP.
        Resets at UTC midnight so it reflects today's institutional participation.
        Falls back to single-session cumulative when timestamps are unavailable.
        """
        if not all([highs, lows, closes, volumes]):
            return []
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        vwap_values: List[float] = []
        cum_tp_vol = 0.0
        cum_vol = 0.0

        for i, (tp, vol) in enumerate(zip(typical_prices, volumes)):
            if timestamps is not None and i > 0:
                try:
                    prev_ts = timestamps[i - 1]
                    curr_ts = timestamps[i]
                    if isinstance(prev_ts, (int, float)) and isinstance(curr_ts, (int, float)):
                        prev_day = int(prev_ts // 86_400_000)
                        curr_day = int(curr_ts // 86_400_000)
                    else:
                        def _to_day(ts):
                            if isinstance(ts, str):
                                return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
                            return datetime.fromtimestamp(float(ts) / 1000, tz=timezone.utc).date()
                        prev_day = _to_day(prev_ts)
                        curr_day = _to_day(curr_ts)
                    if curr_day != prev_day:
                        cum_tp_vol = 0.0
                        cum_vol = 0.0
                except Exception:
                    pass  # keep accumulating if timestamp parse fails

            cum_tp_vol += tp * vol
            cum_vol += vol
            vwap_values.append(cum_tp_vol / cum_vol if cum_vol > 0 else tp)

        return vwap_values

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_mult: float = 2.0) -> Dict:
        """Bollinger Bands with squeeze and expansion detection."""
        if len(prices) < period:
            mid = prices[-1] if prices else 0.0
            return {"upper": mid, "middle": mid, "lower": mid,
                    "width_pct": 0.05, "squeeze": False, "expanding": False}
        window = prices[-period:]
        mid = sum(window) / period
        variance = sum((p - mid) ** 2 for p in window) / period
        std = variance ** 0.5
        upper = mid + std_mult * std
        lower = mid - std_mult * std
        width_pct = (upper - lower) / mid if mid > 0 else 0.0

        expanding = False
        if len(prices) >= period + 1:
            prev_window = prices[-period - 1:-1]
            prev_mid = sum(prev_window) / period
            prev_std = (sum((p - prev_mid) ** 2 for p in prev_window) / period) ** 0.5
            prev_width = ((2 * std_mult * prev_std) / prev_mid) if prev_mid > 0 else 0.0
            expanding = width_pct > prev_width * 1.05

        return {
            "upper": round(upper, 4),
            "middle": round(mid, 4),
            "lower": round(lower, 4),
            "width_pct": round(width_pct, 4),
            "squeeze": width_pct < 0.015,
            "expanding": expanding,
        }

    @staticmethod
    def volume_ratio(volumes: List[float], period: int = 20) -> float:
        """Current volume vs N-period average."""
        if len(volumes) < period + 1:
            return 1.0
        avg = sum(volumes[-period - 1:-1]) / period
        return volumes[-1] / avg if avg > 0 else 1.0

    # ─── ADAPTIVE LEVERAGE ────────────────────────────────────────────────────

    def _calc_adaptive_leverage(self, adx: float, rsi: float, vol_ratio: float,
                                confidence: float, atr_pct: float) -> int:
        """
        5-Factor adaptive leverage model (25–150x).

        Factor 1 — ADX trend strength   (0–4 pts)
        Factor 2 — Confidence score      (1–4 pts)
        Factor 3 — Volume ratio          (0–3 pts)
        Factor 4 — ATR% volatility       (0–4 pts, lower ATR = more pts)
        Factor 5 — RSI distance from 50  (0–3 pts)

        Total pts → leverage:
          0–3 → 25x | 4–6 → 40x | 7–9 → 60x | 10–12 → 80x
          13–15 → 100x | 16–17 → 125x | 18+ → 150x
        """
        pts = 0

        # Factor 1: ADX
        if adx >= 40:
            pts += 4
        elif adx >= 30:
            pts += 3
        elif adx >= 20:
            pts += 2

        # Factor 2: Confidence
        if confidence >= 90:
            pts += 4
        elif confidence >= 82:
            pts += 3
        elif confidence >= 75:
            pts += 2
        else:
            pts += 1

        # Factor 3: Volume ratio
        if vol_ratio >= 2.0:
            pts += 3
        elif vol_ratio >= 1.5:
            pts += 2
        elif vol_ratio >= 1.3:
            pts += 1

        # Factor 4: ATR% (inverse — lower volatility = safer = more leverage)
        if atr_pct < 0.5:
            pts += 4
        elif atr_pct < 1.0:
            pts += 3
        elif atr_pct < 2.0:
            pts += 2
        elif atr_pct < 3.0:
            pts += 1

        # Factor 5: RSI distance from 50 (momentum strength)
        rsi_dist = abs(rsi - 50)
        if rsi_dist >= 20:
            pts += 3
        elif rsi_dist >= 15:
            pts += 2
        elif rsi_dist >= 10:
            pts += 1

        # Map points → leverage
        if pts >= 18:
            lev = 150
        elif pts >= 16:
            lev = 125
        elif pts >= 13:
            lev = 100
        elif pts >= 10:
            lev = 80
        elif pts >= 7:
            lev = 60
        elif pts >= 4:
            lev = 40
        else:
            lev = 25

        return max(self.min_leverage, min(self.max_leverage, lev))

    # ─── SMART MONEY CONFLUENCES ──────────────────────────────────────────────

    def _detect_smart_money(self, highs: List[float], lows: List[float],
                            closes: List[float], volumes: List[float],
                            direction: str) -> List[str]:
        """
        Detect Smart Money signals:
          - Order Block  : strong engulfing candle before reversal
          - FVG          : Fair Value Gap (imbalance / inefficiency)
          - BOS          : Break of Structure
          - Liquidity Sweep : wick past swing extreme then close beyond
        Returns list of found confirmation strings.
        """
        confluences: List[str] = []
        n = len(closes)
        if n < 10:
            return confluences

        opens = []  # we don't have open but we'll approximate from close delta
        # Derive approximate opens: open[i] ≈ close[i-1] (OHLCV from MEXC candles)
        # The MEXC OHLCV candles do include open; they're parsed in get_ohlcv but
        # analyze_symbol_tf doesn't pass opens separately. Use high/low midpoint as proxy.
        o = [(h + l) / 2 for h, l in zip(highs, lows)]  # proxy open

        # ── Order Block ──────────────────────────────────────────────────────
        # A bullish OB: strong bearish candle (close << open) that is later swept up.
        # We detect it as: last 5 bars — find a candle where |close-open|/open > 0.3%
        # with high volume that goes against the current direction (swept OB).
        for i in range(max(0, n - 6), n - 1):
            body = abs(closes[i] - o[i])
            body_pct = body / o[i] if o[i] > 0 else 0
            vol_above_avg = volumes[i] > (sum(volumes[max(0, i - 10):i]) / max(1, min(10, i))) * 1.3
            if body_pct > 0.003 and vol_above_avg:
                if direction == "LONG" and closes[i] < o[i]:
                    confluences.append("Bullish Order Block swept")
                    break
                if direction == "SHORT" and closes[i] > o[i]:
                    confluences.append("Bearish Order Block swept")
                    break

        # ── Fair Value Gap (FVG) ─────────────────────────────────────────────
        # Bullish FVG: candle[i].low > candle[i-2].high  (gap upward)
        # Bearish FVG: candle[i].high < candle[i-2].low  (gap downward)
        if n >= 5:
            for i in range(n - 4, n - 1):
                if direction == "LONG" and lows[i] > highs[i - 2]:
                    confluences.append(f"Bullish FVG ${highs[i-2]:.4f}–${lows[i]:.4f}")
                    break
                if direction == "SHORT" and highs[i] < lows[i - 2]:
                    confluences.append(f"Bearish FVG ${highs[i]:.4f}–${lows[i-2]:.4f}")
                    break

        # ── Break of Structure (BOS) ─────────────────────────────────────────
        # LONG BOS: current close > highest high of last 10 bars (excluding last)
        # SHORT BOS: current close < lowest low of last 10 bars (excluding last)
        lookback = min(10, n - 1)
        recent_highs = highs[n - 1 - lookback: n - 1]
        recent_lows = lows[n - 1 - lookback: n - 1]
        if recent_highs and recent_lows:
            swing_high = max(recent_highs)
            swing_low = min(recent_lows)
            if direction == "LONG" and closes[-1] > swing_high:
                confluences.append(f"BOS — broke ${swing_high:.4f} swing high")
            elif direction == "SHORT" and closes[-1] < swing_low:
                confluences.append(f"BOS — broke ${swing_low:.4f} swing low")

        # ── Liquidity Sweep ──────────────────────────────────────────────────
        # Bullish sweep: last 3 candles — any low wicked below recent swing low
        #   and closed ABOVE it (swept liq then recovered)
        # Bearish sweep: any high wicked above swing high then closed below it
        if n >= 6:
            ref_high = max(highs[n - 7: n - 3])
            ref_low = min(lows[n - 7: n - 3])
            for i in range(n - 3, n):
                if direction == "LONG":
                    if lows[i] < ref_low and closes[i] > ref_low:
                        confluences.append(f"Liquidity sweep below ${ref_low:.4f}")
                        break
                if direction == "SHORT":
                    if highs[i] > ref_high and closes[i] < ref_high:
                        confluences.append(f"Liquidity sweep above ${ref_high:.4f}")
                        break

        return confluences

    # ─── DATA FETCHING ────────────────────────────────────────────────────────

    async def fetch_ohlcv_mexc(self, symbol: str, timeframe: str = "5m",
                               limit: int = 200) -> Optional[Dict]:
        """Fetch OHLCV data from MEXC via market_intel."""
        if not self.market_intel:
            return None
        try:
            data = await self.market_intel.get_ohlcv(symbol, timeframe, limit)
            if not data or "error" in data:
                return None
            candles = data.get("candles", [])
            if not candles:
                return None
            return {
                "open":  [c[1] for c in candles],
                "high":  [c[2] for c in candles],
                "low":   [c[3] for c in candles],
                "close": [c[4] for c in candles],
                "volume": [c[5] for c in candles],
                "timestamps": [c[0] for c in candles],
                "source": "mexc",
            }
        except Exception as e:
            logger.error(f"MEXC OHLCV error for {symbol} {timeframe}: {e}")
            return None

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m") -> Optional[Dict]:
        """Return OHLCV for symbol+timeframe, using cache when fresh."""
        cache_key = f"{symbol}_{timeframe}"
        if cache_key in self._data_cache:
            cached = self._data_cache[cache_key]
            age = (datetime.now(timezone.utc) - cached["timestamp"]).total_seconds()
            if age < self._cache_ttl:
                return cached["data"]
        data = await self.fetch_ohlcv_mexc(symbol, timeframe)
        if data:
            self._data_cache[cache_key] = {
                "data": data,
                "timestamp": datetime.now(timezone.utc),
            }
        return data

    # ─── SINGLE-TIMEFRAME ANALYSIS ────────────────────────────────────────────

    async def analyze_symbol_tf(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Analyse one timeframe.
        Returns {"direction": "LONG"|"SHORT", "rsi": float, "adx": float,
                 "vol_ratio": float, "atr": float, "atr_pct": float,
                 "vwap": float, "price": float, "bb": dict}
        or None if no clear signal.
        """
        data = await self.get_ohlcv(symbol, timeframe)
        if not data:
            return None

        closes  = data["close"]
        highs   = data["high"]
        lows    = data["low"]
        volumes = data["volume"]

        if len(closes) < 50:
            return None

        # ── Indicators ─────────────────────────────────────────────────
        ema_f = self.ema(closes, self.ema_fast)
        ema_s = self.ema(closes, self.ema_slow)
        rsi_v = self.rsi(closes, self.rsi_period)
        vwap_v = self.vwap(highs, lows, closes, volumes, timestamps=data.get("timestamps"))
        bb = self.bollinger_bands(closes, self.bb_period, self.bb_std)
        vol_r = self.volume_ratio(volumes, 20)
        atr_val = self.atr(highs, lows, closes, self.atr_period)

        price     = closes[-1]
        ema_fast  = ema_f[-1]
        ema_slow  = ema_s[-1]
        prev_fast = ema_f[-2]
        prev_slow = ema_s[-2]
        rsi_cur   = rsi_v[-1]
        vwap_cur  = vwap_v[-1] if vwap_v else price
        atr_pct   = (atr_val / price * 100) if price > 0 else 0.0

        # ── Fetch ADX from market_intel ─────────────────────────────────
        adx = 0.0
        if self.market_intel:
            try:
                ta = await self.market_intel.get_technical_analysis(symbol, timeframe)
                adx = ta.get("indicators", {}).get("adx", 0.0) if ta else 0.0
            except Exception:
                pass

        # ── ADX regime filter ───────────────────────────────────────────
        if adx > 0 and adx < 20:
            logger.debug(f"[VWAP] {symbol} {timeframe} — ADX {adx:.1f} < 20 (ranging), skip")
            return None

        # ── EMA crossover ───────────────────────────────────────────────
        cross_up   = (ema_fast > ema_slow) and (prev_fast <= prev_slow)
        cross_down = (ema_fast < ema_slow) and (prev_fast >= prev_slow)

        # ── BB squeeze → skip ───────────────────────────────────────────
        if bb["squeeze"]:
            return None

        # ── Volume filter ───────────────────────────────────────────────
        if vol_r < self.min_volume_ratio:
            return None

        # ── Signal direction ────────────────────────────────────────────
        direction = None
        if cross_up and price > vwap_cur and self.rsi_long_min < rsi_cur < self.rsi_long_max:
            direction = "LONG"
        elif cross_down and price < vwap_cur and self.rsi_short_min < rsi_cur < self.rsi_short_max:
            direction = "SHORT"

        if not direction:
            return None

        return {
            "direction": direction,
            "rsi": rsi_cur,
            "adx": adx,
            "vol_ratio": vol_r,
            "atr": atr_val,
            "atr_pct": atr_pct,
            "vwap": vwap_cur,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "price": price,
            "bb": bb,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": volumes,
        }

    # ─── MTF SIGNAL AGGREGATION ───────────────────────────────────────────────

    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Run MTF analysis across 5m / 15m / 30m.
        Requires at least 2 of 3 timeframes to agree on direction.
        Primary timeframe is 5m (provides ATR, indicators for SL/TP/leverage).
        """
        from post_mortem_engine import get_post_mortem
        if get_post_mortem().is_engine_paused("vwap_scalper"):
            return None  # blindspot pause active
        # Analyse all three timeframes concurrently
        results = await asyncio.gather(
            self.analyze_symbol_tf(symbol, "5m"),
            self.analyze_symbol_tf(symbol, "15m"),
            self.analyze_symbol_tf(symbol, "30m"),
            return_exceptions=True,
        )

        tf_results = {}
        for tf, res in zip(MTF_TIMEFRAMES, results):
            if isinstance(res, Exception) or res is None:
                continue
            tf_results[tf] = res

        if not tf_results:
            return None

        # Count directional votes
        long_votes  = sum(1 for r in tf_results.values() if r["direction"] == "LONG")
        short_votes = sum(1 for r in tf_results.values() if r["direction"] == "SHORT")

        if long_votes >= 2:
            direction = "LONG"
        elif short_votes >= 2:
            direction = "SHORT"
        else:
            return None   # less than 2/3 timeframes agree

        # Use 5m result as primary; fall back to first available
        primary = tf_results.get("5m") or next(iter(tf_results.values()))
        price    = primary["price"]
        atr_val  = primary["atr"]
        rsi_cur  = primary["rsi"]
        adx      = primary["adx"]
        vol_r    = primary["vol_ratio"]
        atr_pct  = primary["atr_pct"]
        vwap_cur = primary["vwap"]
        bb       = primary["bb"]

        if atr_val <= 0:
            return None   # cannot compute ATR-based SL/TP

        # ── ATR-based SL / TP ───────────────────────────────────────────
        sl_dist = 2.0 * atr_val
        tp_dist = 3.5 * atr_val
        if direction == "LONG":
            stop_loss   = price - sl_dist
            take_profit = price + tp_dist
        else:
            stop_loss   = price + sl_dist
            take_profit = price - tp_dist

        # ── Confidence scoring ──────────────────────────────────────────
        confidence = 70

        # EMA separation strength
        ema_diff_pct = abs(primary["ema_fast"] - primary["ema_slow"]) / primary["ema_slow"] * 100
        if ema_diff_pct > 0.2:
            confidence += 5

        # RSI optimal zone
        if direction == "LONG" and 55 < rsi_cur < 65:
            confidence += 5
        elif direction == "SHORT" and 35 < rsi_cur < 45:
            confidence += 5

        # Volume bonus
        if vol_r >= 2.0:
            confidence += 8
        elif vol_r >= 1.5:
            confidence += 5
        elif vol_r >= 1.3:
            confidence += 2

        # BB expansion (breakout timing)
        if bb["expanding"]:
            confidence += 5

        # MTF confluence bonus: all 3 timeframes agree
        total_votes = long_votes if direction == "LONG" else short_votes
        if total_votes == 3:
            confidence += 5

        # ADX trending bonus
        if adx >= 30:
            confidence += 5
        elif adx >= 25:
            confidence += 3

        confidence = min(95, confidence)

        # ── Smart Money confluences ─────────────────────────────────────
        sm_confluences = self._detect_smart_money(
            primary["highs"], primary["lows"], primary["closes"],
            primary["volumes"], direction,
        )
        if sm_confluences:
            confidence = min(95, confidence + 3 * len(sm_confluences))

        # ── Build confirmations list ────────────────────────────────────
        aligned_tfs = [tf for tf, r in tf_results.items() if r["direction"] == direction]
        confirmations = [
            f"EMA9/EMA21 cross — {direction} on {', '.join(aligned_tfs)}",
            f"Price ${price:.4f} {'>' if direction == 'LONG' else '<'} VWAP ${vwap_cur:.4f}",
            f"RSI {rsi_cur:.1f} in {'bullish' if direction == 'LONG' else 'bearish'} zone",
            f"Volume {vol_r:.1f}x average",
        ]
        if bb["expanding"]:
            confirmations.append("BB expanding — volatility breakout")
        if adx > 0:
            confirmations.append(f"ADX {adx:.1f} — {'trending' if adx >= 20 else 'weak trend'}")
        confirmations.extend(sm_confluences)

        # ── Macro Direction Gate ─────────────────────────────────────────
        try:
            from regime_engine import get_regime_engine
            eff_threshold, macro_reason = get_regime_engine().apply_macro_confidence_gate(direction, 70)
            if macro_reason:
                logger.debug(f"[MACRO GATE] {symbol}: {macro_reason}")
            if confidence < eff_threshold:
                return None
        except Exception:
            pass

        # ── Adaptive leverage ───────────────────────────────────────────
        leverage = self._calc_adaptive_leverage(adx, rsi_cur, vol_r, confidence, atr_pct)

        return {
            "symbol": symbol,
            "direction": direction,
            "signal": direction,
            "entry_price": price,
            "stop_loss": round(stop_loss, 6),
            "take_profit": round(take_profit, 6),
            "confidence": confidence,
            "leverage": leverage,
            "atr": round(atr_val, 6),
            "atr_pct": round(atr_pct, 3),
            "confirmations": confirmations,
            "smart_money": sm_confluences,
            "tf_votes": {"long": long_votes, "short": short_votes, "aligned": aligned_tfs},
            "indicators": {
                "ema_fast": round(primary["ema_fast"], 6),
                "ema_slow": round(primary["ema_slow"], 6),
                "rsi": round(rsi_cur, 2),
                "vwap": round(vwap_cur, 6),
                "adx": round(adx, 2),
                "vol_ratio": round(vol_r, 2),
                "price": round(price, 6),
                "atr": round(atr_val, 6),
            },
            "strategy": "VWAP_SCALP_MTF",
            "timeframe": "5m/15m/30m",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─── SCAN ALL SYMBOLS ─────────────────────────────────────────────────────

    async def scan_all_symbols(self) -> List[Dict]:
        """Scan all TRADING_PAIRS for MTF VWAP scalp signals."""
        self._maybe_reset_daily()

        loss_status = self._check_daily_loss_limits()
        if loss_status == "hard_stop":
            logger.warning("[VWAP] Hard stop active — daily loss $%.0f ≥ $%.0f. Engine paused.",
                           self.daily_loss_usd, DAILY_LOSS_HARD_STOP)
            return []

        if not self.active:
            return []

        # ── BTC macro gate ────────────────────────────────────────────
        btc_is_bearish = False
        btc_is_bullish = False
        if self.market_intel:
            try:
                btc_scan = await self.market_intel.get_full_market_scan("BTC/USDT")
                btc_bias = (
                    (btc_scan.get("market_structure", {}) or {}).get("bias", "neutral")
                    if btc_scan else "neutral"
                )
                btc_is_bearish = btc_bias == "bearish"
                btc_is_bullish = btc_bias == "bullish"
                logger.info(f"[VWAP] BTC macro: {btc_bias}")
            except Exception as e:
                logger.debug(f"[VWAP] BTC macro fetch failed: {e}")

        signals: List[Dict] = []

        for symbol in TRADING_PAIRS:
            if self.signals_today >= self.max_signals_per_day:
                logger.info("[VWAP] Daily signal limit reached (%d).", self.max_signals_per_day)
                break
            try:
                signal = await self.analyze_symbol(symbol)
                if not signal:
                    continue
                if signal["confidence"] < 70:
                    continue
                direction = signal["direction"]
                if direction == "LONG" and btc_is_bearish:
                    logger.info(f"[VWAP] BLOCKED {symbol} LONG — BTC macro BEARISH")
                    continue
                if direction == "SHORT" and btc_is_bullish:
                    logger.info(f"[VWAP] BLOCKED {symbol} SHORT — BTC macro BULLISH")
                    continue
                # Apply daily loss tier leverage cap
                if loss_status in ("tier1", "tier2"):
                    signal["leverage"] = min(signal["leverage"], 25)
                    if loss_status == "tier2":
                        signal["position_size_cap"] = 50.0
                # Apply consecutive-loss cooldown leverage cap
                if self.cooldown_trades_remaining > 0:
                    signal["leverage"] = min(signal["leverage"], 25)
                    signal["cooldown_active"] = True
                signals.append(signal)
                self.signals_today += 1
            except Exception as e:
                logger.error(f"[VWAP] Error scanning {symbol}: {e}")

        return signals

    # ─── PAPER TRADING ROUTING ────────────────────────────────────────────────

    async def route_to_paper_trading(self, signal: Dict) -> Optional[Dict]:
        """
        Validate through EngineManager, then open positions on PRO and STARTER accounts.
        """
        if not self.paper_trading:
            return None

        position_size = 800
        if signal.get("position_size_cap"):
            position_size = min(position_size, signal["position_size_cap"])

        # ── Unified engine validation ────────────────────────────────
        if get_engine_manager and EngineType:
            try:
                engine_manager = get_engine_manager()
                _symbol    = signal["symbol"]
                _direction = signal["direction"].lower()

                # Compute quant-driven leverage before building signal
                final_leverage, _lev_bd = await engine_manager.get_dynamic_leverage(
                    _symbol, _direction, EngineType.VWAP_SCALPER
                )
                # Respect any daily-loss-tier / cooldown cap applied by scanner
                # (scan_markets() may have set signal["leverage"] = min(x, tier_cap))
                scanner_cap = signal.get("leverage")
                if scanner_cap is not None:
                    final_leverage = min(final_leverage, scanner_cap)
                # Propagate so open_position calls below use quant leverage
                signal["leverage"] = final_leverage

                engine_signal = {
                    "symbol":        _symbol,
                    "direction":     _direction,
                    "entry_price":   signal["entry_price"],
                    "position_size": position_size,
                    "leverage":      final_leverage,
                    "stop_loss":     signal["stop_loss"],
                    "take_profit":   signal["take_profit"],
                    "confidence":    signal["confidence"],
                    "confluences":   len(signal.get("confirmations", [])),
                    "reason":        "; ".join(signal.get("confirmations", [])[:3]),
                }
                result = await engine_manager.submit_signal_gated(engine_signal, EngineType.VWAP_SCALPER)
                if result["action"] == "REJECT":
                    qr = result.get("quant_report", {})
                    if qr and not result.get("adapted"):
                        adapted_signal = dict(engine_signal)
                        if qr.get("suggested_sl"):    adapted_signal["stop_loss"]    = qr["suggested_sl"]
                        if qr.get("suggested_entry"): adapted_signal["entry_price"]  = qr["suggested_entry"]
                        if qr.get("suggested_tp1"):   adapted_signal["take_profit"]  = qr["suggested_tp1"]
                        adapted_signal["position_size"] = round(adapted_signal["position_size"] * 0.70, 2)
                        adapted_lev, _ = await engine_manager.get_dynamic_leverage(
                            _symbol, _direction, EngineType.VWAP_SCALPER, quant_report=qr
                        )
                        adapted_signal["leverage"] = adapted_lev
                        logger.info(f"🔄 [VWAP] {signal['symbol']} adapting signal — resubmitting to Quant")
                        result = await engine_manager.submit_signal_gated(adapted_signal, EngineType.VWAP_SCALPER, adapted=True)
                        if result["action"] == "REJECT":
                            logger.warning(f"❌ [VWAP] {signal['symbol']} adapted attempt BLOCKED: {result.get('reason')}")
                            return None
                    else:
                        logger.warning(f"❌ [VWAP] {signal['symbol']} BLOCKED: {result.get('reason')}")
                        return None
                signal["unified_trade_id"] = result.get("trade", {}).get("trade_id")
                logger.info(f"[VWAP] {signal['symbol']} VALIDATED by engine manager")
            except Exception as e:
                logger.warning(f"[VWAP] Unified validation failed: {e}")

        open_result = None
        common_kwargs = dict(
            symbol=signal["symbol"],
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            confidence=signal["confidence"],
            leverage=leverage,
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
            strategy="VWAP_SCALP_MTF",
            signal_data={
                "unified_trade_id": signal.get("unified_trade_id"),
                "engine": "vwap_scalper",
                "tf_votes": signal.get("tf_votes"),
                "atr": signal.get("atr"),
                "smart_money": signal.get("smart_money"),
            },
        )

        # PRO account (primary)
        try:
            open_result = await self.paper_trading.open_position(account_id="PRO", **common_kwargs)
            if open_result and "error" not in open_result:
                logger.info(
                    f"[VWAP] PRO: {signal['symbol']} {signal['direction']} "
                    f"@ ${signal['entry_price']:.4f} {leverage}x"
                )
        except Exception as e:
            logger.error(f"[VWAP] PRO paper trade error: {e}")

        # STARTER account (secondary)
        try:
            starter_kwargs = dict(common_kwargs)
            starter_kwargs["leverage"] = min(leverage, 25)   # conservative on starter
            await self.paper_trading.open_position(account_id="STARTER", **starter_kwargs)
            logger.info(
                f"[VWAP] STARTER: {signal['symbol']} {signal['direction']} "
                f"@ ${signal['entry_price']:.4f} {starter_kwargs['leverage']}x"
            )
        except Exception as e:
            logger.error(f"[VWAP] STARTER paper trade error: {e}")

        await self._log_trade_to_mongo(signal, leverage)
        return open_result

    # ─── MONGODB LOGGING ──────────────────────────────────────────────────────

    async def _log_trade_to_mongo(self, signal: Dict, leverage: int):
        """Persist trade signal to vwap_scalper_trades collection."""
        if not self.db:
            return
        try:
            doc = {
                "timestamp": datetime.now(timezone.utc),
                "symbol": signal["symbol"],
                "direction": signal["direction"],
                "entry_price": signal["entry_price"],
                "stop_loss": signal["stop_loss"],
                "take_profit": signal["take_profit"],
                "confidence": signal["confidence"],
                "leverage": leverage,
                "atr": signal.get("atr"),
                "atr_pct": signal.get("atr_pct"),
                "tf_votes": signal.get("tf_votes"),
                "smart_money": signal.get("smart_money", []),
                "confirmations": signal.get("confirmations", []),
                "unified_trade_id": signal.get("unified_trade_id"),
                "strategy": "VWAP_SCALP_MTF",
            }
            await self.db["vwap_scalper_trades"].insert_one(doc)
        except Exception as e:
            logger.error(f"[VWAP] MongoDB log error: {e}")

    # ─── ALERT FORMATTING ─────────────────────────────────────────────────────

    def format_signal_alert(self, signal: Dict) -> str:
        """Format signal for Telegram alert."""
        direction = signal["direction"]
        symbol = signal["symbol"].replace("/USDT", "")
        conf = signal["confidence"]
        lev = signal.get("leverage", self.min_leverage)
        atr_pct = signal.get("atr_pct", 0)
        tf_votes = signal.get("tf_votes", {})
        aligned_tfs = ", ".join(tf_votes.get("aligned", []))
        emoji = "🟢" if direction == "LONG" else "🔴"

        msg = (
            f"{emoji} VWAP SCALP — {symbol} {direction}\n"
            f"Confidence: {conf}%  |  Leverage: {lev}x\n"
            f"Timeframes: {aligned_tfs}\n"
            f"\n"
            f"Entry: ${signal['entry_price']:.4f}\n"
            f"TP:    ${signal['take_profit']:.4f}  (+{3.5 * atr_pct:.2f}%)\n"
            f"SL:    ${signal['stop_loss']:.4f}  (-{2.0 * atr_pct:.2f}%)\n"
            f"ATR:   {atr_pct:.3f}%\n"
            f"\n"
            f"INDICATORS:\n"
            f"• EMA9:  ${signal['indicators']['ema_fast']:.4f}\n"
            f"• EMA21: ${signal['indicators']['ema_slow']:.4f}\n"
            f"• RSI:   {signal['indicators']['rsi']:.1f}\n"
            f"• VWAP:  ${signal['indicators']['vwap']:.4f}\n"
            f"• ADX:   {signal['indicators']['adx']:.1f}\n"
            f"• Vol:   {signal['indicators']['vol_ratio']:.1f}x\n"
            f"\n"
            f"CONFIRMATIONS:\n"
        )
        for c in signal.get("confirmations", []):
            msg += f"• {c}\n"
        smart = signal.get("smart_money", [])
        if smart:
            msg += "\nSMART MONEY:\n"
            for s in smart:
                msg += f"• {s}\n"
        if signal.get("cooldown_active"):
            msg += "\n⚠️ Cooldown active — leverage capped at 25x"
        return msg

    async def send_signal_alert(self, signal: Dict):
        """Send alert to all registered Telegram chats."""
        if not self.send_alert or not self.chat_ids:
            return
        # Cross-engine dedup
        try:
            from aeon_engine_system import get_engine_manager as _gem
            if not _gem().should_send_alert(signal["symbol"], signal["direction"]):
                logger.info(
                    f"[VWAP] Alert deduped: {signal['symbol']} {signal['direction']}"
                )
                return
        except Exception as e:
            logger.debug(f"[VWAP] Alert dedup check failed: {e}")

        msg = self.format_signal_alert(signal)
        for chat_id in self.chat_ids:
            try:
                await self.send_alert(chat_id, msg)
            except Exception as e:
                logger.error(f"[VWAP] Alert send error (chat {chat_id}): {e}")

    # ─── STATS & RESULTS ──────────────────────────────────────────────────────

    def record_trade_result(self, is_win: bool, pnl_usd: float = 0.0):
        """
        Called by engine manager when a VWAP trade closes.
        Updates win/loss counters, consecutive-loss cooldown, and daily loss tracking.
        """
        self.total_trades += 1
        if is_win:
            self.wins += 1
            self.consec_losses = 0   # reset on win
        else:
            self.losses += 1
            self.consec_losses += 1
            if pnl_usd < 0:
                self.daily_loss_usd += abs(pnl_usd)

        # Trigger cooldown after CONSEC_LOSS_TRIGGER consecutive losses
        if self.consec_losses >= CONSEC_LOSS_TRIGGER:
            if self.cooldown_trades_remaining == 0:
                self.cooldown_trades_remaining = COOLDOWN_TRADE_COUNT
                logger.warning(
                    f"[VWAP] {CONSEC_LOSS_TRIGGER} consecutive losses — "
                    f"leverage capped at 25x for next {COOLDOWN_TRADE_COUNT} trades"
                )

        # Decrement cooldown counter after each trade
        if self.cooldown_trades_remaining > 0:
            self.cooldown_trades_remaining -= 1

        # Record to trade history (cap at 100 entries)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": "WIN" if is_win else "LOSS",
            "pnl_usd": pnl_usd,
        }
        self.trade_history.append(entry)
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]

    def get_stats(self) -> Dict:
        """Return strategy statistics."""
        total = self.wins + self.losses
        win_rate = (self.wins / total * 100) if total > 0 else 0.0
        loss_status = self._check_daily_loss_limits()
        return {
            "strategy": "VWAP Scalper — MTF Institutional Rebuild",
            "active": self.active,
            "total_trades": total,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(win_rate, 1),
            "signals_today": self.signals_today,
            "max_signals_per_day": self.max_signals_per_day,
            "daily_loss_usd": round(self.daily_loss_usd, 2),
            "daily_loss_status": loss_status,
            "consec_losses": self.consec_losses,
            "cooldown_trades_remaining": self.cooldown_trades_remaining,
            "leverage_range": f"{self.min_leverage}–{self.max_leverage}x",
            "timeframes": MTF_TIMEFRAMES,
            "trading_pairs": TRADING_PAIRS,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 3.5,
        }

    # ─── MAIN LOOP ────────────────────────────────────────────────────────────

    async def run_scan_loop(self, interval_seconds: int = 300):
        """Continuous scan — every 5 minutes (300s default)."""
        logger.info("[VWAP] Institutional Scalper started — MTF scan every %ds", interval_seconds)

        while self.active:
            try:
                self._maybe_reset_daily()

                loss_status = self._check_daily_loss_limits()
                if loss_status == "hard_stop":
                    logger.warning(
                        "[VWAP] Hard stop — daily loss $%.0f. Sleeping 60s.",
                        self.daily_loss_usd,
                    )
                    await asyncio.sleep(60)
                    continue

                signals = await self.scan_all_symbols()

                for signal in signals:
                    await self.route_to_paper_trading(signal)
                    await self.send_signal_alert(signal)
                    await asyncio.sleep(1)

                if signals:
                    logger.info("[VWAP] Cycle complete — %d signal(s) found.", len(signals))

                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("vwap_scalper")
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"[VWAP] Scan loop error: {e}")

            await asyncio.sleep(interval_seconds)


# ─── MODULE-LEVEL SINGLETON ───────────────────────────────────────────────────

vwap_scalper = None


def init_vwap_scalper(db=None) -> VWAPScalper:
    """Initialise and return the global VWAPScalper instance."""
    global vwap_scalper
    vwap_scalper = VWAPScalper(db)
    return vwap_scalper
