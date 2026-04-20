"""
YOLO TRADING ENGINE v2
======================
Aggressive trading with REAL technical analysis.

Strategy: RSI + MACD + Volume + ATR momentum scoring.
YOLO = high quantity, high aggression, REAL signals.

Differences vs other engines:
- Lower confidence threshold (75%)
- Shorter cooldown (5 min)
- More daily trades (30)
- Higher leverage
- Scans 20 coins every 3 minutes

All signals validated through UnifiedEngineManager.
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


# ── Indicator math (no external deps) ─────────────────────────────────────────

def _ema(prices: List[float], period: int) -> List[float]:
    if len(prices) < period:
        return [prices[-1]] * len(prices) if prices else []
    k = 2.0 / (period + 1)
    result = [sum(prices[:period]) / period]
    for p in prices[period:]:
        result.append(p * k + result[-1] * (1 - k))
    pad = len(prices) - len(result)
    return [result[0]] * pad + result


def _rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def _macd(prices: List[float]) -> Dict:
    if len(prices) < 35:
        return {"macd": 0, "signal": 0, "hist": 0, "bullish": False,
                "crossing_up": False, "crossing_down": False}
    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal_line = _ema(macd_line, 9)
    hist = macd_line[-1] - signal_line[-1]
    prev_hist = macd_line[-2] - signal_line[-2] if len(macd_line) > 1 else 0
    return {
        "macd": round(macd_line[-1], 6),
        "signal": round(signal_line[-1], 6),
        "hist": round(hist, 6),
        "prev_hist": round(prev_hist, 6),
        "bullish": hist > 0,
        "crossing_up": hist > 0 and prev_hist <= 0,
        "crossing_down": hist < 0 and prev_hist >= 0,
    }


def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return closes[-1] * 0.02 if closes else 0
    tr_values = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        tr_values.append(tr)
    return sum(tr_values[-period:]) / period


def _volume_ratio(volumes: List[float], period: int = 20) -> float:
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period - 1:-1]) / period
    return volumes[-1] / avg if avg > 0 else 1.0


def _momentum_pct(closes: List[float], period: int = 10) -> float:
    if len(closes) < period + 1:
        return 0.0
    return (closes[-1] - closes[-period]) / closes[-period] * 100


# ── Config ─────────────────────────────────────────────────────────────────────

SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
    "POL/USDT", "UNI/USDT", "ATOM/USDT", "LTC/USDT",
    "OP/USDT", "APT/USDT", "INJ/USDT", "SUI/USDT", "SEI/USDT",
    "TRX/USDT", "NEAR/USDT", "FIL/USDT", "SAND/USDT", "MANA/USDT",
    # ARB removed: 76 trades, 8% WR, -$10,255 (2026-03-22)
]

COIN_LEVERAGE = {
    # (min_lev, max_lev) — hard capped at 20x after 44% liquidation rate data
    "BTC": (5, 20), "ETH": (5, 20), "SOL": (3, 15),
    "BNB": (3, 15), "XRP": (3, 12), "DOGE": (2, 10),
    "ADA": (2, 10), "AVAX": (3, 12), "LINK": (3, 12),
    "DOT": (2, 10),
}


# ── Engine ─────────────────────────────────────────────────────────────────────

class YoloEngine:
    """YOLO Trading Engine v2 — real multi-indicator TA, aggressive positioning"""

    def __init__(self, db=None):
        self.db = db
        self.active = True
        self.name = "YOLO Engine"
        self.emoji = "🚀"

        self.min_confidence = 65
        self.min_score = 2

        self.cooldown_seconds = 300
        self.recent_signals: Dict[str, datetime] = {}

        self.max_daily_signals = 30
        self.daily_signals = 0
        self.last_reset = datetime.now(timezone.utc).date()

        self.total_signals = 0
        self.trades_opened = 0
        self.wins = 0
        self.losses = 0

        self.market_intel = None
        self.paper_trading = None
        self.send_alert: Optional[Callable] = None
        self.chat_ids: Set[int] = set()

    def set_dependencies(self, **kwargs):
        self.market_intel = kwargs.get("market_intel")
        self.paper_trading = kwargs.get("paper_trading")
        self.send_alert = kwargs.get("send_alert")
        self.chat_ids = kwargs.get("chat_ids", set())

    def _on_cooldown(self, symbol: str) -> bool:
        if symbol in self.recent_signals:
            elapsed = (datetime.now(timezone.utc) - self.recent_signals[symbol]).total_seconds()
            return elapsed < self.cooldown_seconds
        return False

    def _set_cooldown(self, symbol: str):
        self.recent_signals[symbol] = datetime.now(timezone.utc)

    def _reset_daily(self):
        today = datetime.now(timezone.utc).date()
        if today > self.last_reset:
            self.daily_signals = 0
            self.last_reset = today

    def _get_leverage(self, coin: str, confidence: float) -> int:
        lo, hi = COIN_LEVERAGE.get(coin, (10, 30))
        t = max(0.0, min(1.0, (confidence - 75) / 25.0))
        return int(lo + t * (hi - lo))

    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """Score symbol using RSI + MACD + EMA trend + Volume + Momentum"""
        from post_mortem_engine import get_post_mortem
        if get_post_mortem().is_engine_paused("yolo_engine"):
            return None  # blindspot pause active
        if not self.market_intel or self._on_cooldown(symbol):
            return None

        try:
            raw = await self.market_intel.get_ohlcv(symbol, "15m", 100)
            if not raw or "error" in raw:
                return None

            candles = raw.get("candles", [])
            if len(candles) < 35:
                return None

            # ADX regime filter: skip ranging markets (ADX < 20 = no trend to trade)
            try:
                ta = await self.market_intel.get_technical_analysis(symbol, "15m")
                adx = ta.get("indicators", {}).get("adx", 0) if ta else 0
                if adx > 0 and adx < 20:
                    logger.debug(f"YOLO: Skipping {symbol} — ADX {adx:.1f} < 20 (ranging)")
                    return None
            except Exception:
                pass  # ADX unavailable — proceed without filter

            highs  = [c[2] for c in candles]
            lows   = [c[3] for c in candles]
            closes = [c[4] for c in candles]
            vols   = [c[5] for c in candles]

            current_price = closes[-1]
            if not current_price:
                return None

            rsi       = _rsi(closes, 14)
            macd      = _macd(closes)
            atr       = _atr(highs, lows, closes, 14)
            vol_ratio = _volume_ratio(vols, 20)
            momentum  = _momentum_pct(closes, 10)
            ema20     = _ema(closes, 20)

            # ── Breakout detection — 20-bar swing high/low (Fix #14) ──────────
            # Swing computed from bars -21 to -1 (excludes current bar)
            n_swing = min(20, len(highs) - 1)
            swing_high = max(highs[-n_swing - 1:-1]) if n_swing >= 5 else current_price
            swing_low  = min(lows[-n_swing - 1:-1])  if n_swing >= 5 else current_price

            # ATR percentile filter — 50th-80th keeps moderate volatility, avoids dead/spiking
            if len(highs) >= 28:
                atr_series = [_atr(highs[:i+1], lows[:i+1], closes[:i+1], 14)
                              for i in range(13, len(highs))]
                atr_series.sort()
                _p50 = atr_series[len(atr_series) // 2]
                _p80 = atr_series[int(len(atr_series) * 0.8)]
                atr_in_range = _p50 <= atr <= _p80
            else:
                atr_in_range = True  # insufficient history — skip percentile check
            ema50     = _ema(closes, 50)
            ema200    = _ema(closes, 200) if len(closes) >= 200 else None

            trend_up   = ema20[-1] > ema50[-1]
            trend_down = ema20[-1] < ema50[-1]
            # 200 EMA regime: only trade in trend direction
            above_200 = (ema200 is not None and current_price > ema200[-1])
            below_200 = (ema200 is not None and current_price < ema200[-1])

            long_score  = 0
            short_score = 0
            long_reasons  = []
            short_reasons = []

            # RSI — YOLO is a pure momentum engine, not a mean-reversion engine.
            # RSI oversold (<25) was incorrectly scoring a LONG here, conflicting with
            # the momentum philosophy and generating catching-a-falling-knife entries.
            # Removed. RSI <25 now correctly scores SHORT (bearish momentum continuation).
            if 50 < rsi < 75:
                long_score += 1
                long_reasons.append(f"RSI {rsi:.1f} bullish momentum")
            elif rsi >= 75:
                short_score += 1
                short_reasons.append(f"RSI {rsi:.1f} overbought")
            elif rsi <= 50:
                # Covers 25-50 (bearish momentum) and <25 (strong downward momentum)
                short_score += 1
                short_reasons.append(f"RSI {rsi:.1f} bearish momentum")

            # MACD histogram direction
            if macd["bullish"]:
                long_score += 1
                long_reasons.append("MACD positive histogram")
            else:
                short_score += 1
                short_reasons.append("MACD negative histogram")

            # MACD crossover (strongest signal — worth 2 points)
            if macd["crossing_up"]:
                long_score += 2
                long_reasons.append("MACD bullish crossover")
            elif macd["crossing_down"]:
                short_score += 2
                short_reasons.append("MACD bearish crossover")

            # EMA trend (20/50 short-term)
            if trend_up:
                long_score += 1
                long_reasons.append("EMA20 > EMA50 uptrend")
            elif trend_down:
                short_score += 1
                short_reasons.append("EMA20 < EMA50 downtrend")

            # 200 EMA regime filter — block counter-trend (worth 2 pts, hard block if contradicts)
            if ema200 is not None:
                if above_200:
                    long_score += 1
                    long_reasons.append("Price above EMA200 (bull regime)")
                elif below_200:
                    short_score += 1
                    short_reasons.append("Price below EMA200 (bear regime)")

            # Momentum
            if momentum > 1.5:
                long_score += 1
                long_reasons.append(f"Strong momentum +{momentum:.1f}%")
            elif momentum < -1.5:
                short_score += 1
                short_reasons.append(f"Strong momentum {momentum:.1f}%")

            # Volume confirmation bonus
            vol_bonus = 0
            vol_note = ""
            if vol_ratio > 2.0:
                vol_bonus = 2
                vol_note = f"Volume surge {vol_ratio:.1f}x avg"
            elif vol_ratio > 1.5:
                vol_bonus = 1
                vol_note = f"Volume elevated {vol_ratio:.1f}x avg"

            # Pick direction — breakout required (Fix #14)
            if long_score > short_score and long_score >= self.min_score:
                if current_price <= swing_high or not atr_in_range:
                    logger.debug(f"YOLO [{symbol}]: LONG score ok but no breakout above ${swing_high:.4f} (price=${current_price:.4f}) or ATR out of range")
                    return None
                direction = "LONG"
                score = long_score + vol_bonus
                reasons = long_reasons + ([vol_note] if vol_note else []) + [f"Breakout above ${swing_high:.4f}"]
            elif short_score > long_score and short_score >= self.min_score:
                if current_price >= swing_low or not atr_in_range:
                    logger.debug(f"YOLO [{symbol}]: SHORT score ok but no breakout below ${swing_low:.4f} (price=${current_price:.4f}) or ATR out of range")
                    return None
                direction = "SHORT"
                score = short_score + vol_bonus
                reasons = short_reasons + ([vol_note] if vol_note else []) + [f"Breakout below ${swing_low:.4f}"]
            else:
                return None

            # Weighted confidence: base 55 + score scaled by quality
            # MACD crossover (2pts) > RSI (1pt) > EMA (1pt) > volume bonus
            has_crossover = macd["crossing_up"] if direction == "LONG" else macd["crossing_down"]
            crossover_bonus = 8 if has_crossover else 0
            ema200_bonus = 5 if (direction == "LONG" and above_200) or (direction == "SHORT" and below_200) else 0
            confidence = min(95, 55 + score * 4 + crossover_bonus + ema200_bonus)
            # Macro direction gate
            try:
                from regime_engine import get_regime_engine
                eff_threshold, macro_reason = get_regime_engine().apply_macro_confidence_gate(direction, self.min_confidence)
                if macro_reason:
                    logger.debug(f"[MACRO GATE] {symbol}: {macro_reason}")
            except Exception:
                eff_threshold = self.min_confidence
            if confidence < eff_threshold:
                return None

            # ATR-based stops: SL = 1.5x ATR, TP = 3x ATR = 2:1 R:R minimum
            min_dist = current_price * 0.005
            sl_dist = max(atr * 1.5, min_dist)
            tp_dist = max(atr * 3.0, min_dist * 2)

            if direction == "LONG":
                stop_loss   = round(current_price - sl_dist, 6)
                take_profit = round(current_price + tp_dist, 6)
            else:
                stop_loss   = round(current_price + sl_dist, 6)
                take_profit = round(current_price - tp_dist, 6)

            coin = symbol.split("/")[0]
            leverage = self._get_leverage(coin, confidence)

            return {
                "symbol": symbol,
                "direction": direction,
                "entry_price": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": confidence,
                "confluences": score,
                "leverage": leverage,
                "atr": round(atr, 6),
                "rsi": round(rsi, 1),
                "macd_hist": round(macd["hist"], 6),
                "vol_ratio": round(vol_ratio, 2),
                "reasons": reasons,
                "strategy": "YOLO_v2",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"YOLO analyze error [{symbol}]: {e}")
            return None

    async def scan_markets(self) -> List[Dict]:
        if not self.active:
            return []
        self._reset_daily()
        if self.daily_signals >= self.max_daily_signals:
            return []

        # MACRO GATE — BTC/USDT uses BTC macro, alts use market-wide macro (BTC+ETH+SOL)
        btc_macro = "NEUTRAL"
        market_wide_macro = "NEUTRAL"
        if self.market_intel:
            try:
                from regime_engine import get_regime_engine
                _re = get_regime_engine()
                btc_macro = await _re.refresh_macro_direction(self.market_intel)
                market_wide_macro = await _re.refresh_market_wide_macro(self.market_intel)
                logger.info(f"[YOLO] BTC macro: {btc_macro} | Market-wide: {market_wide_macro}")
            except Exception as e:
                logger.debug(f"[YOLO] Macro fetch failed: {e}")

        signals = []
        for symbol in SYMBOLS:
            try:
                sig = await self.analyze_symbol(symbol)
                if sig:
                    direction = sig.get("direction", "")
                    _macro = btc_macro if symbol == "BTC/USDT" else market_wide_macro
                    if direction == "LONG" and _macro == "BEARISH":
                        logger.info(f"[YOLO] BLOCKED {symbol} LONG — {'BTC' if symbol == 'BTC/USDT' else 'market'} macro BEARISH")
                        continue
                    if direction == "SHORT" and _macro == "BULLISH":
                        logger.info(f"[YOLO] BLOCKED {symbol} SHORT — {'BTC' if symbol == 'BTC/USDT' else 'market'} macro BULLISH")
                        continue
                    signals.append(sig)
                    self._set_cooldown(symbol)
                    self.daily_signals += 1
                    self.total_signals += 1
                    if len(signals) >= 5:
                        break
            except Exception as e:
                logger.error(f"YOLO scan error [{symbol}]: {e}")
            await asyncio.sleep(0.3)

        return signals

    async def route_to_paper(self, signal: Dict) -> Optional[Dict]:
        if not self.paper_trading:
            return None

        if get_engine_manager and EngineType:
            try:
                mgr = get_engine_manager()
                _symbol    = signal["symbol"]
                _direction = signal["direction"].lower()

                # Compute quant-driven leverage before building signal
                final_leverage, _lev_bd = await mgr.get_dynamic_leverage(
                    _symbol, _direction, EngineType.YOLO_ENGINE
                )
                # Propagate so paper_trading.open_position below uses quant leverage
                signal["leverage"] = final_leverage

                engine_signal = {
                    "symbol":        _symbol,
                    "direction":     _direction,
                    "entry_price":   signal["entry_price"],
                    "position_size": 1500,
                    "leverage":      final_leverage,
                    "stop_loss":     signal["stop_loss"],
                    "take_profit":   signal["take_profit"],
                    "confidence":    signal["confidence"],
                    "confluences":   signal["confluences"],
                    "reason":        "; ".join(signal.get("reasons", [])[:3]),
                }
                result = await mgr.submit_signal_gated(engine_signal, EngineType.YOLO_ENGINE)

                if result["action"] == "REJECT":
                    qr = result.get("quant_report", {})
                    if qr and not result.get("adapted"):
                        adapted_signal = dict(engine_signal)
                        if qr.get("suggested_sl"):    adapted_signal["stop_loss"]    = qr["suggested_sl"]
                        if qr.get("suggested_entry"): adapted_signal["entry_price"]  = qr["suggested_entry"]
                        if qr.get("suggested_tp1"):   adapted_signal["take_profit"]  = qr["suggested_tp1"]
                        adapted_signal["position_size"] = round(adapted_signal["position_size"] * 0.70, 2)
                        adapted_lev, _ = await mgr.get_dynamic_leverage(
                            _symbol, _direction, EngineType.YOLO_ENGINE, quant_report=qr
                        )
                        adapted_signal["leverage"] = adapted_lev
                        logger.info(f"🔄 YOLO [{signal['symbol']}] adapting signal — resubmitting to Quant")
                        result = await mgr.submit_signal_gated(adapted_signal, EngineType.YOLO_ENGINE, adapted=True)
                        if result["action"] == "REJECT":
                            logger.warning(f"❌ YOLO [{signal['symbol']}] adapted attempt BLOCKED: {result.get('reason')}")
                            return None
                    else:
                        logger.warning(f"❌ YOLO [{signal['symbol']}] BLOCKED: {result.get('reason')}")
                        return None

                trade_id = result.get("trade", {}).get("trade_id")
                if trade_id:
                    for trade in mgr.engine_trades[EngineType.YOLO_ENGINE]:
                        if trade.trade_id == trade_id:
                            await mgr.save_trade_to_db(trade)
                            break
                signal["unified_trade_id"] = trade_id
            except Exception as e:
                logger.warning(f"YOLO unified validation failed: {e}")

        try:
            from paper_trading import route_engine_signal
            paper_signal = {
                "symbol":        signal["symbol"],
                "direction":     signal["direction"],
                "entry_price":   signal["entry_price"],
                "stop_loss":     signal["stop_loss"],
                "take_profit":   signal["take_profit"],
                "leverage":      signal["leverage"],
                "confidence":    signal["confidence"],
                "position_size": 1500,
                "confirmations": signal.get("reasons", []),
            }
            results = await route_engine_signal(paper_signal, "YOLO_ENGINE")
            if results:
                self.trades_opened += 1
                logger.info(f"YOLO routed to {len(results)} accounts: {signal['symbol']} {signal['direction']} @ ${signal['entry_price']:.4f} ({signal['leverage']}x)")
            return results[0] if results else None
        except Exception as e:
            logger.error(f"YOLO paper route error: {e}")

        return None

    def format_alert(self, signal: Dict) -> str:
        emoji = "🟢" if signal["direction"] == "LONG" else "🔴"
        symbol = signal["symbol"].replace("/USDT", "")
        sl_dist = abs(signal["entry_price"] - signal["stop_loss"])
        tp_dist = abs(signal["take_profit"] - signal["entry_price"])
        rr = round(tp_dist / sl_dist, 1) if sl_dist > 0 else 0
        reasons_text = "\n".join(f"• {r}" for r in signal.get("reasons", [])[:4])
        return (
            f"YOLO SIGNAL\n\n"
            f"{emoji} {symbol} {signal['direction']} | {signal['confidence']}% conf\n"
            f"Leverage: {signal['leverage']}x | R:R {rr}:1\n\n"
            f"Entry:  ${signal['entry_price']:.4f}\n"
            f"TP:     ${signal['take_profit']:.4f}\n"
            f"SL:     ${signal['stop_loss']:.4f}\n\n"
            f"Signals:\n{reasons_text}\n\n"
            f"RSI: {signal.get('rsi', '?')} | "
            f"Vol: {signal.get('vol_ratio', '?')}x | "
            f"ATR: {signal.get('atr', '?')}\n"
            f"High risk — YOLO mode"
        )

    async def send_signal_alert(self, signal: Dict):
        if not self.send_alert or not self.chat_ids:
            return
        # Dedup: skip if same symbol+direction was alerted recently from any engine
        if get_engine_manager and EngineType:
            try:
                if not get_engine_manager().should_send_alert(signal["symbol"], signal["direction"]):
                    logger.info(f"YOLO alert deduped: {signal['symbol']} {signal['direction']} recently sent")
                    return
            except Exception:
                pass
        msg = self.format_alert(signal)
        for chat_id in self.chat_ids:
            try:
                await self.send_alert(chat_id, msg)
            except Exception:
                pass

    async def run_loop(self, interval: int = 180):
        logger.info("YOLO ENGINE v2 STARTED — real TA, scanning every 3 min")
        while self.active:
            try:
                signals = await self.scan_markets()
                for sig in signals:
                    await self.route_to_paper(sig)
                    await self.send_signal_alert(sig)
                    await asyncio.sleep(1)
                if signals:
                    logger.info(f"YOLO found {len(signals)} signals this scan")

                from self_healer import self_healer
                self_healer.heartbeat("yolo_engine")
            except Exception as e:
                logger.error(f"YOLO loop error: {e}")
            await asyncio.sleep(interval)

    def record_trade_result(self, is_win: bool):
        """Called by paper trading / engine manager when a YOLO trade closes."""
        if is_win:
            self.wins += 1
        else:
            self.losses += 1

    def get_stats(self) -> Dict:
        total = self.wins + self.losses
        return {
            "name": self.name,
            "active": self.active,
            "emoji": self.emoji,
            "version": "v2",
            "strategy": "RSI + MACD + EMA + Volume + ATR Momentum",
            "min_confidence": self.min_confidence,
            "min_score": self.min_score,
            "leverage_range": "10x - 75x (coin-adaptive)",
            "rr_ratio": "2:1 (ATR-based)",
            "stats": {
                "total_signals": self.total_signals,
                "daily_signals": self.daily_signals,
                "trades_opened": self.trades_opened,
                "wins": self.wins,
                "losses": self.losses,
                "win_rate": round(self.wins / total * 100, 1) if total else 0,
            },
            "limits": {
                "max_daily_signals": self.max_daily_signals,
                "cooldown_seconds": self.cooldown_seconds,
                "symbols": len(SYMBOLS),
            },
        }


yolo_engine: Optional[YoloEngine] = None


def init_yolo_engine(db=None) -> YoloEngine:
    global yolo_engine
    yolo_engine = YoloEngine(db)
    return yolo_engine
