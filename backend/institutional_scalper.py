"""
================================================================
  INSTITUTIONAL SCALPER  (standalone engine)
================================================================
Philosophy : Pure Smart Money Concepts on higher timeframes.
             Institutions leave footprints — Order Blocks swept,
             Fair Value Gaps filled, Structure Breaks with volume.
             We follow the money, not the noise.

Timeframes : 1H (entry trigger)  +  4H (direction bias)
             1D macro gate (EMA50 on daily as proxy for EMA200)

Signal logic:
  LONG : Bullish OB swept OR Bullish FVG fill + BOS up + vol spike
  SHORT: Bearish OB swept OR Bearish FVG fill + BOS down + vol spike
  Requires: 2+ SMC confirmations across 1H + 4H

Risk:
  - ATR(14) on 4H: SL = 1.5× ATR, TP = 4.5× ATR  →  3:1 R:R
  - Leverage: 5–30x (adaptive, institutional scale)
  - Max 3 signals/day  |  Daily loss cap: $350
  - Pairs: 8 deep-liquidity majors

Routes to: PRO (primary, $1200) + STARTER (conservative, $500, max 10x)
MongoDB  : institutional_scalper_trades
================================================================
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Set

logger = logging.getLogger(__name__)

try:
    from aeon_engine_system import get_engine_manager, EngineType
except ImportError:
    get_engine_manager = None
    EngineType = None
    logger.warning("[INST] Unified engine system not available")


# ── Pairs — majors only (deep OBs, institutional participation) ───────────────
TRADING_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT",
]

# ── Timeframes ────────────────────────────────────────────────────────────────
TF_ENTRY   = "1h"
TF_CONFIRM = "4h"
TF_MACRO   = "1d"

# ── Risk constants ────────────────────────────────────────────────────────────
SL_ATR_MULT        = 1.5
TP_ATR_MULT        = 4.5    # 3:1 R:R
MIN_CONFIDENCE     = 85
MAX_SIGNALS_PER_DAY = 3
DAILY_LOSS_CAP     = 350.0
MIN_LEVERAGE       = 5
MAX_LEVERAGE       = 30


class InstitutionalScalper:
    """
    Pure SMC engine on 1H / 4H / 1D timeframes.
    Entries triggered by Order Blocks, Fair Value Gaps,
    Break of Structure, Liquidity Sweeps, and Institutional Impulses.
    Completely independent of the VWAP Scalper.
    """

    def __init__(self, db=None):
        self.db    = db
        self.active = True

        self.daily_loss_usd   = 0.0
        self.signals_today    = 0
        self._last_reset_date = None

        self.total_trades  = 0
        self.wins          = 0
        self.losses        = 0
        self.trade_history: List[Dict] = []

        self.market_intel  = None
        self.send_alert:   Optional[Callable] = None
        self.chat_ids:     Set[int] = set()
        self.paper_trading = None

        self._cache:     Dict[str, Dict] = {}
        self._cache_ttl = 120  # 2 min — 4H candles change slowly

    def set_dependencies(self, **kwargs):
        self.market_intel  = kwargs.get("market_intel")
        self.send_alert    = kwargs.get("send_alert")
        self.chat_ids      = kwargs.get("chat_ids", set())
        self.paper_trading = kwargs.get("paper_trading")

    # ─── DAILY RESET ──────────────────────────────────────────────────────────

    def _maybe_reset_daily(self):
        today = datetime.now(timezone.utc).date()
        if self._last_reset_date != today:
            self.signals_today    = 0
            self.daily_loss_usd   = 0.0
            self._last_reset_date = today
            logger.info("[INST] Daily counters reset for %s", today)

    # ─── INDICATORS ───────────────────────────────────────────────────────────

    @staticmethod
    def _ema(prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return [prices[-1]] * len(prices) if prices else []
        mult = 2.0 / (period + 1)
        vals = [sum(prices[:period]) / period]
        for p in prices[period:]:
            vals.append((p - vals[-1]) * mult + vals[-1])
        return [vals[0]] * (len(prices) - len(vals)) + vals

    @staticmethod
    def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 0.0
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            for i in range(1, len(closes))
        ]
        if not trs:
            return 0.0
        atr_val = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr_val = (atr_val * (period - 1) + tr) / period
        return atr_val

    @staticmethod
    def _volume_ratio(volumes: List[float], period: int = 20) -> float:
        if len(volumes) < period + 1:
            return 1.0
        avg = sum(volumes[-period-1:-1]) / period
        return volumes[-1] / avg if avg > 0 else 1.0

    # ─── DATA FETCHING ────────────────────────────────────────────────────────

    async def _get_ohlcv(self, symbol: str, timeframe: str) -> Optional[Dict]:
        key = f"{symbol}_{timeframe}"
        if key in self._cache:
            age = (datetime.now(timezone.utc) - self._cache[key]["ts"]).total_seconds()
            if age < self._cache_ttl:
                return self._cache[key]["data"]
        if not self.market_intel:
            return None
        try:
            raw = await self.market_intel.get_ohlcv(symbol, timeframe, 200)
            if not raw or "error" in raw:
                return None
            candles = raw.get("candles", [])
            if not candles:
                return None
            data = {
                "open":       [c[1] for c in candles],
                "high":       [c[2] for c in candles],
                "low":        [c[3] for c in candles],
                "close":      [c[4] for c in candles],
                "volume":     [c[5] for c in candles],
                "timestamps": [c[0] for c in candles],
            }
            self._cache[key] = {"data": data, "ts": datetime.now(timezone.utc)}
            return data
        except Exception as e:
            logger.error(f"[INST] OHLCV error {symbol} {timeframe}: {e}")
            return None

    # ─── SMC DETECTION ────────────────────────────────────────────────────────

    def _detect_smc(self, highs: List[float], lows: List[float],
                    closes: List[float], volumes: List[float],
                    direction: str, lookback: int = 20) -> List[str]:
        """
        Detect institutional Smart Money Concepts on any timeframe.
        Returns list of confirmed pattern strings (used for confirmations + scoring).

        Patterns:
          1. Order Block (OB)     — high-volume engulf swept + reclaimed
          2. Fair Value Gap (FVG) — 3-candle imbalance, price retracing in
          3. Break of Structure   — close through swing high/low
          4. Liquidity Sweep      — wick past extreme, close back inside
          5. Institutional Impulse— 3 consecutive expanding candles
        """
        signals: List[str] = []
        n = len(closes)
        if n < lookback:
            return signals

        opens   = [(h + l) / 2 for h, l in zip(highs, lows)]
        avg_vol = sum(volumes[max(0, n - lookback): n - 1]) / max(1, lookback - 1)

        # ── 1. Order Block ────────────────────────────────────────────
        # Strong engulfing candle (>0.5% body, 1.4x avg vol) swept by current move.
        for i in range(max(0, n - lookback), n - 2):
            body     = abs(closes[i] - opens[i])
            body_pct = body / opens[i] if opens[i] > 0 else 0
            high_vol = volumes[i] > avg_vol * 1.4
            if body_pct > 0.005 and high_vol:
                if direction == "LONG" and closes[i] < opens[i]:
                    if closes[-1] > max(highs[i: i + 3]):
                        signals.append(f"Bullish OB swept @ ${opens[i]:.4f}")
                        break
                if direction == "SHORT" and closes[i] > opens[i]:
                    if closes[-1] < min(lows[i: i + 3]):
                        signals.append(f"Bearish OB swept @ ${opens[i]:.4f}")
                        break

        # ── 2. Fair Value Gap ─────────────────────────────────────────
        # Bullish FVG: candle[i-2].high < candle[i].low — gap up, price retracing in.
        # Bearish FVG: candle[i-2].low  > candle[i].high — gap down.
        for i in range(max(3, n - lookback), n):
            if direction == "LONG":
                gap_low  = lows[i]
                gap_high = highs[i - 2]
                if gap_low > gap_high:
                    if gap_high <= closes[-1] <= gap_low * 1.005:
                        signals.append(f"Bullish FVG fill ${gap_high:.4f}–${gap_low:.4f}")
                        break
            if direction == "SHORT":
                gap_high_s = highs[i]
                gap_low_s  = lows[i - 2]
                if gap_high_s < gap_low_s:
                    if gap_low_s * 0.995 <= closes[-1] <= gap_low_s:
                        signals.append(f"Bearish FVG fill ${gap_high_s:.4f}–${gap_low_s:.4f}")
                        break

        # ── 3. Break of Structure ─────────────────────────────────────
        swing_highs = highs[n - lookback: n - 1]
        swing_lows  = lows[n - lookback: n - 1]
        if swing_highs and swing_lows:
            swing_high = max(swing_highs)
            swing_low  = min(swing_lows)
            if direction == "LONG" and closes[-1] > swing_high:
                signals.append(f"BOS — broke swing high ${swing_high:.4f}")
            elif direction == "SHORT" and closes[-1] < swing_low:
                signals.append(f"BOS — broke swing low ${swing_low:.4f}")

        # ── 4. Liquidity Sweep ────────────────────────────────────────
        # Classic stop-hunt: wick past swing extreme, snap back — institutions
        # grabbed liquidity then reversed hard.
        if n >= 8:
            ref_high = max(highs[n - 8: n - 3])
            ref_low  = min(lows[n - 8: n - 3])
            for i in range(n - 3, n):
                if direction == "LONG":
                    if lows[i] < ref_low and closes[i] > ref_low:
                        signals.append(f"Liquidity sweep below ${ref_low:.4f}")
                        break
                if direction == "SHORT":
                    if highs[i] > ref_high and closes[i] < ref_high:
                        signals.append(f"Liquidity sweep above ${ref_high:.4f}")
                        break

        # ── 5. Institutional Impulse ──────────────────────────────────
        # 3 consecutive same-direction candles with expanding volume.
        if n >= 5:
            last3_bull = all(closes[i] > opens[i] for i in range(n - 3, n))
            last3_bear = all(closes[i] < opens[i] for i in range(n - 3, n))
            vol_expanding = volumes[-1] > volumes[-2] > volumes[-3]
            if direction == "LONG" and last3_bull and vol_expanding:
                signals.append("Institutional impulse — 3 expanding bull candles")
            elif direction == "SHORT" and last3_bear and vol_expanding:
                signals.append("Institutional impulse — 3 expanding bear candles")

        return signals

    # ─── ADAPTIVE LEVERAGE ────────────────────────────────────────────────────

    def _calc_leverage(self, confidence: float, smc_count: int, atr_pct: float) -> int:
        """
        Conservative leverage: 5–30x.
        Factor 1 — Confidence    (0–6 pts)
        Factor 2 — SMC count     (0–4 pts)
        Factor 3 — ATR% inverse  (0–4 pts, lower vol = more pts)
        """
        pts = 0
        if confidence >= 93:    pts += 6
        elif confidence >= 90:  pts += 5
        elif confidence >= 87:  pts += 4
        elif confidence >= 85:  pts += 3

        pts += min(4, smc_count)

        if atr_pct < 1.0:       pts += 4
        elif atr_pct < 2.0:     pts += 3
        elif atr_pct < 3.5:     pts += 2
        elif atr_pct < 5.0:     pts += 1

        if pts >= 12:   lev = 30
        elif pts >= 9:  lev = 20
        elif pts >= 6:  lev = 15
        elif pts >= 3:  lev = 10
        else:           lev = 5

        return max(MIN_LEVERAGE, min(MAX_LEVERAGE, lev))

    # ─── SINGLE SYMBOL ANALYSIS ───────────────────────────────────────────────

    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """
        3-layer SMC analysis:
          Layer 1 — 1D macro gate  (EMA50 direction)
          Layer 2 — 4H direction   (EMA21/EMA50 trend + SMC)
          Layer 3 — 1H entry       (SMC trigger)
        Returns signal dict or None.
        """
        from post_mortem_engine import get_post_mortem
        if get_post_mortem().is_engine_paused("institutional_scalper"):
            return None

        # ── Layer 1: 1D macro gate ──────────────────────────────────
        macro_bias = "neutral"
        try:
            d1_data = await self._get_ohlcv(symbol, TF_MACRO)
            if d1_data and len(d1_data["close"]) >= 50:
                ema50_1d = self._ema(d1_data["close"], 50)
                price_1d = d1_data["close"][-1]
                if price_1d > ema50_1d[-1] * 1.005:
                    macro_bias = "bullish"
                elif price_1d < ema50_1d[-1] * 0.995:
                    macro_bias = "bearish"
        except Exception as e:
            logger.debug(f"[INST] 1D macro failed {symbol}: {e}")

        # ── Layer 2: 4H direction + SMC ────────────────────────────
        h4_data = await self._get_ohlcv(symbol, TF_CONFIRM)
        if not h4_data or len(h4_data["close"]) < 50:
            return None

        h4_closes  = h4_data["close"]
        h4_highs   = h4_data["high"]
        h4_lows    = h4_data["low"]
        h4_volumes = h4_data["volume"]

        ema21_4h = self._ema(h4_closes, 21)
        ema50_4h = self._ema(h4_closes, 50)
        atr_4h   = self._atr(h4_highs, h4_lows, h4_closes, 14)
        vol_4h   = self._volume_ratio(h4_volumes, 20)
        price_4h = h4_closes[-1]
        atr_pct  = (atr_4h / price_4h * 100) if price_4h > 0 else 0.0

        if atr_4h <= 0:
            return None

        # 4H trend: EMA21 vs EMA50 + price side
        if ema21_4h[-1] > ema50_4h[-1] and h4_closes[-1] > ema21_4h[-1]:
            h4_direction = "LONG"
        elif ema21_4h[-1] < ema50_4h[-1] and h4_closes[-1] < ema21_4h[-1]:
            h4_direction = "SHORT"
        else:
            return None  # no clear 4H trend

        # Macro gate
        if macro_bias == "bearish" and h4_direction == "LONG":
            logger.debug(f"[INST] {symbol}: LONG blocked — 1D bearish macro")
            return None
        if macro_bias == "bullish" and h4_direction == "SHORT":
            logger.debug(f"[INST] {symbol}: SHORT blocked — 1D bullish macro")
            return None

        # Volume filter — need institutional participation on 4H
        if vol_4h < 1.2:
            return None

        smc_4h = self._detect_smc(h4_highs, h4_lows, h4_closes, h4_volumes, h4_direction)

        # ── Layer 3: 1H entry trigger ────────────────────────────────
        h1_data = await self._get_ohlcv(symbol, TF_ENTRY)
        if not h1_data or len(h1_data["close"]) < 30:
            return None

        smc_1h = self._detect_smc(
            h1_data["high"], h1_data["low"], h1_data["close"], h1_data["volume"], h4_direction
        )

        # Need at least 2 SMC signals across both timeframes
        all_smc = smc_4h + smc_1h
        if len(all_smc) < 2:
            return None

        # ── ADX filter (from market_intel on 4H) ─────────────────────
        adx = 0.0
        try:
            ta = await self.market_intel.get_technical_analysis(symbol, TF_CONFIRM)
            adx = ta.get("indicators", {}).get("adx", 0.0) if ta else 0.0
        except Exception:
            pass

        if adx > 0 and adx < 20:
            return None  # ranging market — OBs unreliable

        # ── Confidence scoring ────────────────────────────────────────
        confidence = 75
        confidence += min(15, len(all_smc) * 5)

        if (macro_bias == "bullish" and h4_direction == "LONG") or \
           (macro_bias == "bearish" and h4_direction == "SHORT"):
            confidence += 5

        if vol_4h >= 2.0:   confidence += 5
        elif vol_4h >= 1.5: confidence += 3

        if adx >= 35:       confidence += 5
        elif adx >= 25:     confidence += 3

        confidence = min(97, confidence)

        if confidence < MIN_CONFIDENCE:
            return None

        # ── Regime engine macro gate ─────────────────────────────────
        try:
            from regime_engine import get_regime_engine
            eff_threshold, _ = get_regime_engine().apply_macro_confidence_gate(h4_direction, 75)
            if confidence < eff_threshold:
                return None
        except Exception:
            pass

        # ── SL / TP (4H ATR-based) ───────────────────────────────────
        entry = h1_data["close"][-1]
        if h4_direction == "LONG":
            stop_loss   = entry - (SL_ATR_MULT * atr_4h)
            take_profit = entry + (TP_ATR_MULT * atr_4h)
        else:
            stop_loss   = entry + (SL_ATR_MULT * atr_4h)
            take_profit = entry - (TP_ATR_MULT * atr_4h)

        leverage = self._calc_leverage(confidence, len(all_smc), atr_pct)

        confirmations = [
            f"4H EMA21/EMA50: {h4_direction} trend",
            f"Volume: {vol_4h:.1f}x institutional level",
        ]
        if adx > 0:
            confirmations.append(f"ADX {adx:.1f} — {'strong trend' if adx >= 25 else 'developing'}")
        if macro_bias != "neutral":
            confirmations.append(f"1D macro: {macro_bias}")
        confirmations.extend([f"4H: {s}" for s in smc_4h])
        confirmations.extend([f"1H: {s}" for s in smc_1h])

        return {
            "symbol":        symbol,
            "direction":     h4_direction,
            "signal":        h4_direction,
            "entry_price":   round(entry, 6),
            "stop_loss":     round(stop_loss, 6),
            "take_profit":   round(take_profit, 6),
            "confidence":    confidence,
            "leverage":      leverage,
            "atr_4h":        round(atr_4h, 6),
            "atr_pct":       round(atr_pct, 3),
            "vol_ratio":     round(vol_4h, 2),
            "adx":           round(adx, 2),
            "macro_bias":    macro_bias,
            "smc_4h":        smc_4h,
            "smc_1h":        smc_1h,
            "smc_count":     len(all_smc),
            "confirmations": confirmations,
            "strategy":      "INSTITUTIONAL_SMC",
            "timeframe":     "1H/4H/1D",
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }

    # ─── SCAN ALL SYMBOLS ─────────────────────────────────────────────────────

    async def scan_all_symbols(self) -> List[Dict]:
        self._maybe_reset_daily()
        if not self.active:
            return []
        if self.signals_today >= MAX_SIGNALS_PER_DAY:
            logger.info("[INST] Daily signal limit reached (%d).", MAX_SIGNALS_PER_DAY)
            return []
        if self.daily_loss_usd >= DAILY_LOSS_CAP:
            logger.warning("[INST] Daily loss cap $%.0f hit — engine paused.", DAILY_LOSS_CAP)
            return []

        signals: List[Dict] = []
        for symbol in TRADING_PAIRS:
            if self.signals_today >= MAX_SIGNALS_PER_DAY:
                break
            try:
                signal = await self.analyze_symbol(symbol)
                if signal:
                    signals.append(signal)
                    self.signals_today += 1
                    logger.info(
                        f"[INST] {symbol} {signal['direction']} "
                        f"conf={signal['confidence']}% smc={signal['smc_count']}"
                    )
            except Exception as e:
                logger.error(f"[INST] Scan error {symbol}: {e}")
        return signals

    # ─── PAPER TRADING ROUTING ────────────────────────────────────────────────

    async def route_to_paper_trading(self, signal: Dict) -> Optional[Dict]:
        if not self.paper_trading:
            return None

        position_size = 1200  # Larger per-trade — fewer, higher-quality setups

        if get_engine_manager and EngineType:
            try:
                em  = get_engine_manager()
                _sym = signal["symbol"]
                _dir = signal["direction"].lower()

                final_leverage, _ = await em.get_dynamic_leverage(
                    _sym, _dir, EngineType.INSTITUTIONAL_SCALPER
                )
                final_leverage = min(final_leverage, signal["leverage"])
                signal["leverage"] = final_leverage

                engine_signal = {
                    "symbol":        _sym,
                    "direction":     _dir,
                    "entry_price":   signal["entry_price"],
                    "position_size": position_size,
                    "leverage":      final_leverage,
                    "stop_loss":     signal["stop_loss"],
                    "take_profit":   signal["take_profit"],
                    "confidence":    signal["confidence"],
                    "confluences":   signal["smc_count"],
                    "reason":        "; ".join(signal.get("confirmations", [])[:3]),
                }
                result = await em.submit_signal_gated(engine_signal, EngineType.INSTITUTIONAL_SCALPER)
                if result["action"] == "REJECT":
                    logger.warning(f"❌ [INST] {signal['symbol']} BLOCKED: {result.get('reason')}")
                    return None
                signal["unified_trade_id"] = result.get("trade", {}).get("trade_id")
            except Exception as e:
                logger.warning(f"[INST] Engine validation failed: {e}")

        leverage = signal.get("leverage", MIN_LEVERAGE)
        common_kwargs = dict(
            symbol=signal["symbol"],
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            confidence=signal["confidence"],
            leverage=leverage,
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
            strategy="INSTITUTIONAL_SMC",
            signal_data={
                "unified_trade_id": signal.get("unified_trade_id"),
                "engine":    "institutional_scalper",
                "smc_4h":   signal.get("smc_4h"),
                "smc_1h":   signal.get("smc_1h"),
                "atr_4h":   signal.get("atr_4h"),
                "macro_bias": signal.get("macro_bias"),
            },
        )

        paper_signal = {
            "symbol":        signal["symbol"],
            "direction":     signal["direction"],
            "entry_price":   signal["entry_price"],
            "stop_loss":     signal["stop_loss"],
            "take_profit":   signal["take_profit"],
            "confidence":    signal["confidence"],
            "leverage":      leverage,
            "position_size": position_size,
            "confirmations": signal.get("confirmations", []),
        }
        try:
            from paper_trading import route_engine_signal
            results = await route_engine_signal(paper_signal, "INSTITUTIONAL_SCALPER")
            logger.info(f"[INST] Routed to {len(results)} accounts: {signal['symbol']} {signal['direction']} @ ${signal['entry_price']:.4f} {leverage}x")
        except Exception as e:
            logger.error(f"[INST] route_engine_signal error: {e}")

        await self._log_to_mongo(signal, leverage)
        return paper_signal

    # ─── MONGODB LOGGING ──────────────────────────────────────────────────────

    async def _log_to_mongo(self, signal: Dict, leverage: int):
        if not self.db:
            return
        try:
            await self.db["institutional_scalper_trades"].insert_one({
                "timestamp":        datetime.now(timezone.utc),
                "symbol":           signal["symbol"],
                "direction":        signal["direction"],
                "entry_price":      signal["entry_price"],
                "stop_loss":        signal["stop_loss"],
                "take_profit":      signal["take_profit"],
                "confidence":       signal["confidence"],
                "leverage":         leverage,
                "atr_4h":           signal.get("atr_4h"),
                "atr_pct":          signal.get("atr_pct"),
                "smc_4h":           signal.get("smc_4h", []),
                "smc_1h":           signal.get("smc_1h", []),
                "smc_count":        signal.get("smc_count", 0),
                "macro_bias":       signal.get("macro_bias"),
                "confirmations":    signal.get("confirmations", []),
                "unified_trade_id": signal.get("unified_trade_id"),
                "strategy":         "INSTITUTIONAL_SMC",
            })
        except Exception as e:
            logger.error(f"[INST] MongoDB log error: {e}")

    # ─── ALERT FORMATTING ─────────────────────────────────────────────────────

    def format_signal_alert(self, signal: Dict) -> str:
        direction = signal["direction"]
        symbol    = signal["symbol"].replace("/USDT", "")
        conf      = signal["confidence"]
        lev       = signal.get("leverage", MIN_LEVERAGE)
        atr_pct   = signal.get("atr_pct", 0)
        macro     = signal.get("macro_bias", "neutral")
        emoji     = "🟢" if direction == "LONG" else "🔴"

        msg = (
            f"{emoji} INSTITUTIONAL SMC — {symbol} {direction}\n"
            f"Confidence: {conf}%  |  Leverage: {lev}x\n"
            f"Timeframe: 1H entry / 4H bias / 1D macro ({macro})\n"
            f"SMC Signals: {signal.get('smc_count', 0)}\n"
            f"\n"
            f"Entry:  ${signal['entry_price']:.4f}\n"
            f"TP:     ${signal['take_profit']:.4f}  (+{TP_ATR_MULT * atr_pct:.2f}%)\n"
            f"SL:     ${signal['stop_loss']:.4f}  (-{SL_ATR_MULT * atr_pct:.2f}%)\n"
            f"R:R:    {TP_ATR_MULT / SL_ATR_MULT:.1f}:1\n"
            f"4H ATR: {atr_pct:.3f}%\n"
            f"\n"
            f"SMC CONFIRMATIONS:\n"
        )
        for s in signal.get("smc_4h", []):
            msg += f"• [4H] {s}\n"
        for s in signal.get("smc_1h", []):
            msg += f"• [1H] {s}\n"
        return msg

    async def send_signal_alert(self, signal: Dict):
        if not self.send_alert or not self.chat_ids:
            return
        try:
            from aeon_engine_system import get_engine_manager as _gem
            if not _gem().should_send_alert(signal["symbol"], signal["direction"]):
                return
        except Exception:
            pass
        msg = self.format_signal_alert(signal)
        for chat_id in self.chat_ids:
            try:
                await self.send_alert(chat_id, msg)
            except Exception as e:
                logger.error(f"[INST] Alert error (chat {chat_id}): {e}")

    # ─── STATS & RESULTS ──────────────────────────────────────────────────────

    def record_trade_result(self, is_win: bool, pnl_usd: float = 0.0):
        self.total_trades += 1
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
            if pnl_usd < 0:
                self.daily_loss_usd += abs(pnl_usd)
        self.trade_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result":    "WIN" if is_win else "LOSS",
            "pnl_usd":  pnl_usd,
        })
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]

    def get_stats(self) -> Dict:
        total    = self.wins + self.losses
        win_rate = (self.wins / total * 100) if total > 0 else 0.0
        return {
            "strategy":            "Institutional Scalper — Pure SMC (1H/4H/1D)",
            "active":              self.active,
            "total_trades":        total,
            "wins":                self.wins,
            "losses":              self.losses,
            "win_rate":            round(win_rate, 1),
            "signals_today":       self.signals_today,
            "max_signals_per_day": MAX_SIGNALS_PER_DAY,
            "daily_loss_usd":      round(self.daily_loss_usd, 2),
            "daily_loss_cap":      DAILY_LOSS_CAP,
            "leverage_range":      f"{MIN_LEVERAGE}–{MAX_LEVERAGE}x",
            "min_confidence":      MIN_CONFIDENCE,
            "sl_atr_mult":         SL_ATR_MULT,
            "tp_atr_mult":         TP_ATR_MULT,
            "rr_ratio":            round(TP_ATR_MULT / SL_ATR_MULT, 2),
            "trading_pairs":       TRADING_PAIRS,
            "timeframes":          [TF_ENTRY, TF_CONFIRM, TF_MACRO],
        }

    # ─── MAIN LOOP ────────────────────────────────────────────────────────────

    async def run_loop(self, interval_seconds: int = 3600):
        """Scan every hour — 4H candles don't need faster polling."""
        logger.info("[INST] Institutional Scalper started — SMC scan every %ds", interval_seconds)
        while self.active:
            try:
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("institutional_scalper")
                except Exception:
                    pass
                signals = await self.scan_all_symbols()
                for signal in signals:
                    await self.route_to_paper_trading(signal)
                    await self.send_signal_alert(signal)
                    await asyncio.sleep(2)
                if signals:
                    logger.info("[INST] Cycle complete — %d signal(s).", len(signals))
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("institutional_scalper")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[INST] Loop error: {e}")
            elapsed = 0
            while elapsed < interval_seconds:
                await asyncio.sleep(min(60, interval_seconds - elapsed))
                elapsed += min(60, interval_seconds - elapsed)
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("institutional_scalper")
                except Exception:
                    pass


# ─── SINGLETON ────────────────────────────────────────────────────────────────

_inst_scalper: Optional[InstitutionalScalper] = None


def init_institutional_scalper(db=None) -> InstitutionalScalper:
    global _inst_scalper
    _inst_scalper = InstitutionalScalper(db)
    return _inst_scalper


def get_institutional_scalper() -> Optional[InstitutionalScalper]:
    return _inst_scalper
