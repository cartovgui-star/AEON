"""
=============================================================
  atr_stop_module.py — Wilder ATR(14) Stop Module
=============================================================

  Position in the identity: A(t) = Ω(|Ψ⟩, E, M, L)

  Layer ON TOP of all existing risk controls.
  Never bypasses ENGINE_CONFIGS. Never bypasses Quant gatekeeper.
  ATR always wins on stop placement.

  Stop placement:
    ATR14 = Wilder smoothing over 14 periods
    Stop$ = k × ATR14

    SL (LONG)  = Entry − Stop$
    SL (SHORT) = Entry + Stop$

  k optimization:
    J(k) = Sharpe(k) − λ · DD(k)        when n ≥ 30 trades
    J(k) = EV(k) / DD(k)                 when n < 30 trades

    λ by regime:
      TRENDING       → 0.3   tolerate drawdown
      RANGING        → 0.8   punish drawdown
      HIGH_VOLATILITY→ 1.5   capital preservation
      ACCUMULATION   → 0.5   balanced

    k tested: {1.5, 2.0, 2.5}
    Walk-forward: 90-day OHLCV split into 60d train / 30d validate
    Memory override: if 50+ recorded trades on coin → memory-weighted k

  Position sizing:
    risk_pct = |max_loss_per_day| / max_daily_trades / max_position_size
    Lots = (Equity × risk_pct) / Stop$

  Integrations:
    1. Engines call apply_atr_stop() after Quant approval, before submit
    2. log_trade_close() called on every close → feeds Omega + Memory
    3. omega_evaluate() called by Omega every 6h → adjusts λ per coin/regime
    4. get_volatility_amplitude() called by quantum state for |Ψ⟩ ATR input

  MongoDB collections:
    atr_profiles      — k profiles + λ per symbol (persistent)
    atr_stop_history  — per-trade ATR log (Omega reads this)
=============================================================
"""

import asyncio
import logging
import math
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any

from mexc_utils import format_mexc_symbol
from aeon_engine_system import ENGINE_CONFIGS, EngineType

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

ATR_PERIOD          = 14
K_CANDIDATES        = (1.5, 2.0, 2.5)
K_DEFAULT           = 2.0              # fallback until sufficient data
MIN_SAMPLE_SHARPE   = 30               # threshold for J = Sharpe − λ·DD
SIM_CANDLES_FORWARD = 20               # forward look-window per simulated entry
SIM_MAX_ENTRIES     = 200              # entries per simulation window (performance cap)
MEMORY_THRESHOLD    = 50              # trades needed to switch to memory-weighted k

LAMBDA_MIN          = 0.2
LAMBDA_MAX          = 2.0

_ATR_COLLECTION     = "atr_profiles"
_ATR_HISTORY        = "atr_stop_history"

# Default λ per regime — Omega overrides per coin via set_lambda()
_REGIME_LAMBDA_DEFAULT: Dict[str, float] = {
    "TRENDING":        0.3,
    "RANGING":         0.8,
    "HIGH_VOLATILITY": 1.5,
    "CHAOS":           1.5,
    "ACCUMULATION":    0.5,
}


# ─── ATR Stop Engine ──────────────────────────────────────────────────────────

class ATRStopEngine:
    """
    Wilder ATR(14) stop placement, k optimization, and lot sizing.

    Engines import and call:
        out_signal, atr_report = await atr_stop.apply_atr_stop(signal, engine_type, equity)

    On trade close:
        await atr_stop.log_trade_close(close_data)

    Omega calls every 6h:
        eval_result = await atr_stop.omega_evaluate(symbol)

    Quantum state calls:
        vol_amp = await atr_stop.get_volatility_amplitude(symbol)
    """

    def __init__(self, db=None):
        self.db            = db
        self._market_intel = None
        self._memory       = None
        self._quantum      = None

        # ATR cache: sym_tf → (atr14, ts)
        self._atr_cache:   Dict[str, Tuple[float, datetime]] = {}
        self._atr_ttl      = timedelta(minutes=5)

        # k optimization cache: sym_tf_regime_engine → (k, breakdown, ts)
        self._k_cache:     Dict[str, Tuple[float, Dict, datetime]] = {}
        self._k_ttl        = timedelta(hours=6)

    def set_dependencies(
        self,
        market_intel=None,
        memory_engine=None,
        quantum_state=None,
    ):
        self._market_intel = market_intel
        self._memory       = memory_engine
        self._quantum      = quantum_state

    # ── Risk % from ENGINE_CONFIGS ─────────────────────────────────────────────

    @staticmethod
    def _risk_pct(engine_type: EngineType) -> float:
        """
        Derive risk_pct from ENGINE_CONFIGS. Zero hardcoded values.
        Formula: |max_loss_per_day| / max_daily_trades / max_position_size
        Clamped to [0.5%, 2.5%].
        """
        cfg = ENGINE_CONFIGS[engine_type]
        raw = (
            abs(cfg.max_loss_per_day)
            / max(cfg.max_daily_trades, 1)
            / max(cfg.max_position_size, 1.0)
        )
        return max(0.005, min(0.025, raw))

    # ── Wilder ATR(14) — core math ────────────────────────────────────────────

    @staticmethod
    def _wilder_atr(ohlcv: List[List[float]]) -> float:
        """
        Wilder ATR(14) from OHLCV.
        ohlcv rows: [ts, open, high, low, close, volume]

        Seed  : ATR₁₄ = simple_avg(TR[1..14])
        Smooth: ATRᵢ  = ((ATR_PERIOD − 1) × ATRᵢ₋₁ + TRᵢ) / ATR_PERIOD

        Returns 0.0 when fewer than ATR_PERIOD + 1 candles.
        """
        if len(ohlcv) < ATR_PERIOD + 1:
            return 0.0

        trs: List[float] = []
        for i in range(1, len(ohlcv)):
            h  = float(ohlcv[i][2])
            l  = float(ohlcv[i][3])
            pc = float(ohlcv[i - 1][4])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))

        atr = sum(trs[:ATR_PERIOD]) / ATR_PERIOD
        for tr in trs[ATR_PERIOD:]:
            atr = ((ATR_PERIOD - 1) * atr + tr) / ATR_PERIOD

        return atr

    @staticmethod
    def _atr_series(ohlcv: List[List[float]]) -> List[float]:
        """
        Rolling Wilder ATR(14) aligned to ohlcv.
        First ATR_PERIOD indices are 0.0 (insufficient history).
        """
        n = len(ohlcv)
        if n < ATR_PERIOD + 1:
            return [0.0] * n

        trs: List[float] = [0.0]
        for i in range(1, n):
            h  = float(ohlcv[i][2])
            l  = float(ohlcv[i][3])
            pc = float(ohlcv[i - 1][4])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))

        out: List[float] = [0.0] * ATR_PERIOD
        seed = sum(trs[1: ATR_PERIOD + 1]) / ATR_PERIOD
        out.append(seed)

        for i in range(ATR_PERIOD + 1, n):
            prev = out[-1]
            out.append(((ATR_PERIOD - 1) * prev + trs[i]) / ATR_PERIOD)

        return out

    async def compute_atr14(self, symbol: str, timeframe: str = "1h") -> float:
        """
        Fetch OHLCV from MEXC and compute Wilder ATR(14). 5-minute cache.
        Returns 0.0 on failure.
        """
        sym       = format_mexc_symbol(symbol)
        cache_key = f"{sym}_{timeframe}"

        cached = self._atr_cache.get(cache_key)
        if cached:
            val, ts = cached
            if datetime.now(timezone.utc) - ts < self._atr_ttl:
                return val

        if self._market_intel is None:
            return 0.0

        try:
            ohlcv = await self._market_intel.get_ohlcv(sym, timeframe, limit=ATR_PERIOD + 50)
        except Exception as e:
            logger.debug(f"[ATR] OHLCV fetch failed {sym}/{timeframe}: {e}")
            return 0.0

        if not ohlcv or len(ohlcv) < ATR_PERIOD + 1:
            return 0.0

        val = self._wilder_atr(ohlcv)
        if val > 0:
            self._atr_cache[cache_key] = (val, datetime.now(timezone.utc))
        return val

    # ── Walk-forward OHLCV fetch ───────────────────────────────────────────────

    async def _fetch_ohlcv_90d(self, sym: str, timeframe: str) -> List[List[float]]:
        """
        Fetch ~90 days of OHLCV. Candle count depends on timeframe.
        """
        limits = {
            "1m": 2000, "3m": 2000, "5m": 2000, "15m": 2000,
            "30m": 2000, "1h": 2160, "2h": 1080, "4h": 540,
            "6h": 360, "12h": 180, "1d": 90,
        }
        limit = limits.get(timeframe, 2000)
        try:
            return await self._market_intel.get_ohlcv(sym, timeframe, limit=limit)
        except Exception as e:
            logger.debug(f"[ATR] 90d OHLCV failed {sym}/{timeframe}: {e}")
            return []

    # ── k simulation ──────────────────────────────────────────────────────────

    def _simulate_k(
        self,
        ohlcv:    List[List[float]],
        atrs:     List[float],
        k:        float,
        lam:      float,
    ) -> Dict[str, float]:
        """
        Simulate stop-placement across one OHLCV window.

        For each entry candle (evenly sampled, up to SIM_MAX_ENTRIES):
          stop$  = k × ATR14
          TP     = 1.5 × stop$  (R:R 1.5:1 for simulation neutrality)
          Direction neutral: simulate LONG + SHORT, average return.

          LONG:  WIN if any high[t+j] ≥ entry + TP$ before any low[t+j] ≤ entry − stop$
          SHORT: WIN if any low[t+j]  ≤ entry − TP$ before any high[t+j] ≥ entry + stop$

          Return = ±stop$ expressed as % of entry. Neutral avg = (long_ret + short_ret) / 2.

        J(k):
          n ≥ MIN_SAMPLE_SHARPE → Sharpe − λ · max_drawdown
          n < MIN_SAMPLE_SHARPE → EV / max_drawdown
        """
        start = ATR_PERIOD + 1
        end   = len(ohlcv) - SIM_CANDLES_FORWARD - 1
        empty = {"sharpe": 0.0, "max_dd": 1.0, "ev": 0.0, "J": 0.0, "sample_count": 0}

        if end <= start:
            return empty

        total = end - start
        step  = max(1, total // SIM_MAX_ENTRIES)
        idxs  = list(range(start, end, step))[:SIM_MAX_ENTRIES]

        rets: List[float] = []

        for i in idxs:
            atr = atrs[i]
            if atr <= 0:
                continue
            entry = float(ohlcv[i][4])
            if entry <= 0:
                continue
            stop_usd = k * atr
            tp_usd   = 1.5 * stop_usd

            # Simulate LONG
            long_ret = -stop_usd
            for j in range(i + 1, min(i + SIM_CANDLES_FORWARD + 1, len(ohlcv))):
                h = float(ohlcv[j][2])
                lo = float(ohlcv[j][3])
                if lo <= entry - stop_usd:
                    long_ret = -stop_usd
                    break
                if h >= entry + tp_usd:
                    long_ret = tp_usd
                    break

            # Simulate SHORT
            short_ret = -stop_usd
            for j in range(i + 1, min(i + SIM_CANDLES_FORWARD + 1, len(ohlcv))):
                h = float(ohlcv[j][2])
                lo = float(ohlcv[j][3])
                if h >= entry + stop_usd:
                    short_ret = -stop_usd
                    break
                if lo <= entry - tp_usd:
                    short_ret = tp_usd
                    break

            avg_ret = ((long_ret + short_ret) / 2) / entry * 100
            rets.append(avg_ret)

        n = len(rets)
        if n < 5:
            return {**empty, "sample_count": n}

        mean_r = sum(rets) / n
        std_r  = statistics.stdev(rets) if n > 1 else 0.0
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 1e-8 else 0.0

        cum = 0.0; peak = 0.0; max_dd = 0.0
        for r in rets:
            cum += r
            if cum > peak:
                peak = cum
            if peak > 1e-8:
                dd = (peak - cum) / peak
                if dd > max_dd:
                    max_dd = dd
        max_dd = min(max_dd, 1.0)

        J = (sharpe - lam * max_dd) if n >= MIN_SAMPLE_SHARPE else (mean_r / max(max_dd, 1e-6))

        return {
            "sharpe":       round(sharpe, 4),
            "max_dd":       round(max_dd, 4),
            "ev":           round(mean_r, 4),
            "J":            round(J, 4),
            "sample_count": n,
        }

    # ── λ management ──────────────────────────────────────────────────────────

    async def get_lambda(self, symbol: str, regime: str) -> float:
        """
        Get λ for symbol/regime. MongoDB first, default second.
        Omega updates these via set_lambda().
        """
        default = _REGIME_LAMBDA_DEFAULT.get(regime, 0.5)
        if self.db is None:
            return default
        try:
            doc = await self.db[_ATR_COLLECTION].find_one({"_id": symbol})
            if doc:
                lam = doc.get("lambda_by_regime", {}).get(regime)
                if lam is not None:
                    return max(LAMBDA_MIN, min(LAMBDA_MAX, float(lam)))
        except Exception as e:
            logger.debug(f"[ATR] lambda load {symbol}/{regime}: {e}")
        return default

    async def set_lambda(
        self,
        symbol:    str,
        regime:    str,
        new_lambda: float,
        reason:    str = "",
    ):
        """
        Omega calls this to adjust λ per coin per regime.
        Clamped to [LAMBDA_MIN, LAMBDA_MAX].
        """
        clamped = max(LAMBDA_MIN, min(LAMBDA_MAX, new_lambda))
        logger.info(
            "[ATR] λ update %s/%s %.3f (reason: %s)", symbol, regime, clamped, reason
        )
        if self.db is None:
            return
        try:
            await self.db[_ATR_COLLECTION].update_one(
                {"_id": symbol},
                {
                    "$set": {
                        f"lambda_by_regime.{regime}": clamped,
                        "lambda_updated_at":           datetime.now(timezone.utc).isoformat(),
                        "lambda_reason":               reason,
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[ATR] lambda save {symbol}/{regime}: {e}")

    # ── Memory-based k ─────────────────────────────────────────────────────────

    async def _k_from_memory(
        self,
        symbol: str,
        regime: str,
        lam:    float,
    ) -> Optional[Tuple[float, Dict]]:
        """
        If MEMORY_THRESHOLD+ ATR trades recorded for this coin/regime,
        compute J per k from historical outcomes and select the best.
        Returns (k, breakdown) or None if insufficient data.
        """
        if self.db is None:
            return None
        try:
            records = await self.db[_ATR_HISTORY].find(
                {"symbol": symbol, "regime": regime},
                sort=[("logged_at", -1)],
                limit=500,
            ).to_list(length=500)
        except Exception as e:
            logger.debug(f"[ATR] memory k query {symbol}: {e}")
            return None

        if len(records) < MEMORY_THRESHOLD:
            return None

        k_stats: Dict[float, Dict] = {}
        for k in K_CANDIDATES:
            recs = [r for r in records if abs(r.get("k_used", 0) - k) < 0.1]
            if len(recs) < 5:
                continue
            n    = len(recs)
            wins = [r for r in recs if r.get("outcome") == "WIN"]
            rets = [float(r.get("pnl_pct", 0)) for r in recs]
            mean_r = sum(rets) / n
            std_r  = statistics.stdev(rets) if n > 1 else 0.0
            sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 1e-8 else 0.0

            cum = 0.0; peak = 0.0; max_dd = 0.0
            for r in rets:
                cum += r
                if cum > peak:
                    peak = cum
                if peak > 1e-8:
                    dd = (peak - cum) / peak
                    if dd > max_dd:
                        max_dd = dd
            max_dd = min(max_dd, 1.0)

            J = (
                sharpe - lam * max_dd
                if n >= MIN_SAMPLE_SHARPE
                else mean_r / max(max_dd, 1e-6)
            )
            k_stats[k] = {
                "J":      round(J, 4),
                "sharpe": round(sharpe, 4),
                "max_dd": round(max_dd, 4),
                "wr":     round(len(wins) / n, 3),
                "n":      n,
            }

        if not k_stats:
            return None

        best_k = max(k_stats, key=lambda k: k_stats[k]["J"])
        bd = {
            "source":     "memory",
            "k_selected": best_k,
            "n_records":  len(records),
            "k_stats":    {str(k): v for k, v in k_stats.items()},
            "lambda":     lam,
        }
        return best_k, bd

    # ── k optimization — walk-forward ─────────────────────────────────────────

    async def optimize_k(
        self,
        symbol:      str,
        timeframe:   str,
        regime:      str,
        engine_type: EngineType,
    ) -> Tuple[float, Dict]:
        """
        Select optimal k ∈ {1.5, 2.0, 2.5} for this symbol/timeframe/regime.

        Priority:
          1. 6-hour k cache
          2. Memory-weighted k  (50+ recorded trades)
          3. Walk-forward validation on 90d OHLCV (train 60d / validate 30d)
          4. K_DEFAULT = 2.0  (insufficient data)

        Hard rule: minimum 3 k values must be tested before any is selected.
        All selections logged with full breakdown: symbol, regime, λ, J scores per k.
        """
        sym       = format_mexc_symbol(symbol)
        cache_key = f"{sym}_{timeframe}_{regime}_{engine_type.value}"

        # 1. Cache
        cached = self._k_cache.get(cache_key)
        if cached:
            k_val, bd, ts = cached
            if datetime.now(timezone.utc) - ts < self._k_ttl:
                return k_val, {**bd, "source": bd.get("source", "cache") + "_cached"}

        lam = await self.get_lambda(sym, regime)

        # 2. Memory-weighted k
        mem = await self._k_from_memory(sym, regime, lam)
        if mem is not None:
            k_mem, bd = mem
            self._k_cache[cache_key] = (k_mem, bd, datetime.now(timezone.utc))
            logger.info(
                "[ATR] k=%.1f from memory for %s/%s  λ=%.2f  J=%.4f  n=%d",
                k_mem, sym, regime, lam,
                bd["k_stats"][str(k_mem)]["J"], bd["n_records"],
            )
            return k_mem, bd

        # 3. Walk-forward validation
        if self._market_intel is None:
            return K_DEFAULT, {"source": "default", "reason": "no_market_intel", "lambda": lam}

        ohlcv = await self._fetch_ohlcv_90d(sym, timeframe)
        min_required = ATR_PERIOD + SIM_CANDLES_FORWARD + 20

        if len(ohlcv) < min_required:
            logger.info(
                "[ATR] Insufficient OHLCV (%d candles, need %d) — "
                "defaulting k=%.1f for %s/%s",
                len(ohlcv), min_required, K_DEFAULT, sym, timeframe,
            )
            return K_DEFAULT, {
                "source":  "default",
                "reason":  f"ohlcv_too_short ({len(ohlcv)})",
                "lambda":  lam,
            }

        atrs = self._atr_series(ohlcv)

        # Split: first 2/3 = train, last 1/3 = validate
        n         = len(ohlcv)
        train_end = (n * 2) // 3
        val_start = train_end - ATR_PERIOD  # include ATR warm-up for validate window

        train_ohlcv = ohlcv[:train_end]
        train_atrs  = atrs[:train_end]
        val_ohlcv   = ohlcv[val_start:]
        val_atrs    = self._atr_series(val_ohlcv)

        train_res: Dict[float, Dict] = {}
        val_res:   Dict[float, Dict] = {}

        for k in K_CANDIDATES:
            train_res[k] = self._simulate_k(train_ohlcv, train_atrs, k, lam)
            val_res[k]   = self._simulate_k(val_ohlcv,   val_atrs,   k, lam)

        # Require all 3 k values tested in validation window
        tested = [k for k in K_CANDIDATES if val_res[k]["sample_count"] >= 3]

        if len(tested) < 3:
            logger.info(
                "[ATR] Validation window sparse (%d/3 tested) — "
                "defaulting k=%.1f for %s",
                len(tested), K_DEFAULT, sym,
            )
            k_sel  = K_DEFAULT
            source = "default"
        else:
            k_sel  = max(K_CANDIDATES, key=lambda k: val_res[k]["J"])
            source = "walk_forward"

        bd = {
            "source":       source,
            "symbol":       sym,
            "timeframe":    timeframe,
            "regime":       regime,
            "engine":       engine_type.value,
            "lambda":       lam,
            "k_selected":   k_sel,
            "n_ohlcv":      n,
            "train_end":    train_end,
            "train_res":    {str(k): train_res[k] for k in K_CANDIDATES},
            "val_res":      {str(k): val_res[k]   for k in K_CANDIDATES},
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        }

        self._k_cache[cache_key] = (k_sel, bd, datetime.now(timezone.utc))

        logger.info(
            "[ATR] k=%.1f selected for %s/%s/%s  λ=%.2f  "
            "J(train)=%.4f  J(val)=%.4f  n=%d  source=%s",
            k_sel, sym, timeframe, regime, lam,
            train_res[k_sel]["J"], val_res[k_sel]["J"], n, source,
        )

        return k_sel, bd

    # ── Stop levels ────────────────────────────────────────────────────────────

    @staticmethod
    def compute_stop_levels(
        entry:     float,
        direction: str,
        atr14:     float,
        k:         float,
    ) -> Tuple[float, float]:
        """
        stop_dollar = k × ATR14
        SL (LONG)   = entry − stop_dollar
        SL (SHORT)  = entry + stop_dollar
        Returns (sl, stop_dollar).
        """
        stop_dollar = k * atr14
        if direction.lower() == "long":
            sl = entry - stop_dollar
        else:
            sl = entry + stop_dollar
        return sl, stop_dollar

    # ── Position sizing ────────────────────────────────────────────────────────

    @staticmethod
    def compute_lots(equity: float, risk_pct: float, stop_dollar: float) -> float:
        """
        Lots = (Equity × risk_pct) / Stop$
        risk_pct derived from ENGINE_CONFIGS. Never hardcoded.
        """
        if stop_dollar <= 0 or equity <= 0:
            return 0.0
        return (equity * risk_pct) / stop_dollar

    # ── Main integration point ─────────────────────────────────────────────────

    async def apply_atr_stop(
        self,
        signal:      Dict,
        engine_type: EngineType,
        equity:      float = 10_000.0,
        regime:      Optional[str] = None,
        timeframe:   Optional[str] = None,
    ) -> Tuple[Dict, Dict]:
        """
        Main entry point for all 6 engines.
        Called AFTER Quant approval, BEFORE submit_signal_gated().

        Validates Quant's suggested_sl against ATR volatility math.
        ATR always wins:
          - If Quant SL tighter than k_min × ATR14  → replace
          - If Quant SL wider  than k_max × ATR14   → replace
          - Otherwise keep Quant SL but log ATR context

        Also computes:
          - atr_position_size (lots from risk-based sizing)
          - atr_stop_dollar, atr_k, atr14

        Returns:
          (modified_signal, atr_report)

        modified_signal has stop_loss replaced (when ATR wins) and
        atr_* fields injected for downstream use and Omega logging.
        """
        sym       = format_mexc_symbol(signal.get("symbol", ""))
        direction = signal.get("direction", "long").lower()
        entry     = float(signal.get("entry_price") or signal.get("entry") or 0)
        tf        = timeframe or signal.get("timeframe", "1h")
        reg       = regime or signal.get("regime", "RANGING")

        report: Dict[str, Any] = {
            "symbol":    sym,
            "engine":    engine_type.value,
            "direction": direction,
            "entry":     entry,
            "timeframe": tf,
            "regime":    reg,
        }

        # ── ATR14 ────────────────────────────────────────────────────────────
        atr14 = await self.compute_atr14(sym, tf)
        report["atr14"] = round(atr14, 8)

        if atr14 <= 0 or entry <= 0:
            logger.warning(
                "[ATR] [%s] Skipping — atr14=%.8f entry=%.4f",
                engine_type.value, atr14, entry,
            )
            report["action"] = "skipped"
            report["reason"] = f"atr14={atr14:.8f} or entry={entry} is zero"
            return dict(signal), report

        # ── k selection ──────────────────────────────────────────────────────
        k, k_bd = await self.optimize_k(sym, tf, reg, engine_type)
        report["k_used"]      = k
        report["k_breakdown"] = k_bd
        report["lambda_used"] = k_bd.get("lambda", _REGIME_LAMBDA_DEFAULT.get(reg, 0.5))

        # ── ATR stop levels ───────────────────────────────────────────────────
        atr_sl, stop_dollar = self.compute_stop_levels(entry, direction, atr14, k)
        # ATR corridor: [k_min × ATR14, k_max × ATR14] from entry
        atr_dist_min = min(K_CANDIDATES) * atr14   # 1.5 × ATR14
        atr_dist_max = max(K_CANDIDATES) * atr14   # 2.5 × ATR14

        report["atr_sl"]         = round(atr_sl, 8)
        report["stop_dollar"]    = round(stop_dollar, 8)
        report["atr_dist_range"] = [round(atr_dist_min, 8), round(atr_dist_max, 8)]

        # ── Validate Quant's SL ───────────────────────────────────────────────
        quant_sl = float(
            signal.get("stop_loss")
            or signal.get("suggested_sl")
            or 0
        )
        report["quant_sl"] = quant_sl

        final_sl = atr_sl   # ATR is the default; overridden below if Quant is valid

        if quant_sl > 0 and entry > 0:
            quant_dist = abs(entry - quant_sl)
            too_tight  = quant_dist < atr_dist_min
            too_wide   = quant_dist > atr_dist_max

            if too_tight:
                action = "replaced_tight"
                report["quant_sl_rejected_reason"] = (
                    f"Quant SL distance {quant_dist:.6f} < ATR min {atr_dist_min:.6f} "
                    f"(k={min(K_CANDIDATES)} × ATR={atr14:.6f})"
                )
                logger.info(
                    "[ATR] [%s] %s %s — REPLACED tight SL %.6f → %.6f  "
                    "(k=%.1f ATR=%.6f)",
                    engine_type.value, sym, direction.upper(),
                    quant_sl, atr_sl, k, atr14,
                )
            elif too_wide:
                action = "replaced_wide"
                report["quant_sl_rejected_reason"] = (
                    f"Quant SL distance {quant_dist:.6f} > ATR max {atr_dist_max:.6f} "
                    f"(k={max(K_CANDIDATES)} × ATR={atr14:.6f})"
                )
                logger.info(
                    "[ATR] [%s] %s %s — REPLACED wide SL %.6f → %.6f  "
                    "(k=%.1f ATR=%.6f)",
                    engine_type.value, sym, direction.upper(),
                    quant_sl, atr_sl, k, atr14,
                )
            else:
                # Quant SL is within ATR corridor — accept it
                action   = "accepted"
                final_sl = quant_sl
                logger.debug(
                    "[ATR] [%s] %s %s — Quant SL %.6f accepted "
                    "(within ATR corridor [%.6f, %.6f])",
                    engine_type.value, sym, direction.upper(),
                    quant_sl,
                    entry - atr_dist_max if direction == "long" else entry + atr_dist_min,
                    entry - atr_dist_min if direction == "long" else entry + atr_dist_max,
                )
        elif quant_sl <= 0:
            action = "set"
            logger.info(
                "[ATR] [%s] %s %s — setting SL %.6f (k=%.1f × ATR=%.6f)",
                engine_type.value, sym, direction.upper(), atr_sl, k, atr14,
            )
        else:
            action   = "accepted"
            final_sl = quant_sl

        report["action"]   = action
        report["final_sl"] = round(final_sl, 8)

        # ── Position sizing ───────────────────────────────────────────────────
        risk_pct = self._risk_pct(engine_type)
        lots     = self.compute_lots(equity, risk_pct, stop_dollar)
        report["risk_pct"] = round(risk_pct, 5)
        report["lots"]     = round(lots, 6)
        report["equity"]   = equity

        # ── J score for logging ───────────────────────────────────────────────
        val_res = k_bd.get("val_res", k_bd.get("k_stats", {}))
        j_score = 0.0
        if val_res:
            j_entry = val_res.get(str(k), val_res.get(k, {}))
            if isinstance(j_entry, dict):
                j_score = j_entry.get("J", 0.0)
        report["J_score"] = round(j_score, 4)

        # ── Inject into signal ────────────────────────────────────────────────
        out = dict(signal)
        out["stop_loss"]         = round(final_sl, 8)
        out["atr_stop_dollar"]   = round(stop_dollar, 8)
        out["atr_position_size"] = round(lots, 6)
        out["atr_k"]             = k
        out["atr14"]             = round(atr14, 8)

        return out, report

    # ── Trade close logging ───────────────────────────────────────────────────

    async def log_trade_close(self, close_data: Dict):
        """
        Called on every trade close by paper_trading or engine_manager.
        Writes to atr_stop_history — Omega reads this collection for λ evaluation.

        Minimum expected keys in close_data:
          symbol, direction, engine, regime, k_used, atr14_at_entry,
          stop_dollar, entry_price, exit_price, pnl_pct, pnl_usd, outcome,
          lambda_used, J_score, closed_at
        """
        if self.db is None:
            return
        try:
            doc = {
                **close_data,
                "logged_at": datetime.now(timezone.utc),
            }
            doc.setdefault("closed_at", datetime.now(timezone.utc).isoformat())
            await self.db[_ATR_HISTORY].insert_one(doc)
        except Exception as e:
            logger.debug(f"[ATR] trade close log: {e}")

    # ── Omega evaluation ──────────────────────────────────────────────────────

    async def omega_evaluate(
        self,
        symbol:        str,
        lookback_days: int = 30,
    ) -> Optional[Dict]:
        """
        Omega calls this every 6h for each active symbol.
        Evaluates historical ATR stop performance and adjusts λ if warranted.

        Diagnostics:
          k too tight → WR < 35% AND avg_loss_pct < 1.5%
                        → λ += 0.1  (optimizer penalizes DD more → prefers wider k)

          k too wide  → WR > 65% AND avg_loss_pct > 5%
                        → λ −= 0.1  (optimizer tolerates more DD → allows tighter k)

        λ adjustment clamped to [LAMBDA_MIN, LAMBDA_MAX].
        Changes ≥ 0.05 auto-applied and logged.

        Returns evaluation dict for Omega's cycle report.
        """
        if self.db is None:
            return None

        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        try:
            records = await self.db[_ATR_HISTORY].find(
                {"symbol": symbol, "logged_at": {"$gt": since}},
                sort=[("logged_at", -1)],
            ).to_list(length=500)
        except Exception as e:
            logger.debug(f"[ATR] omega_evaluate {symbol}: {e}")
            return None

        if len(records) < 5:
            return {
                "symbol": symbol, "status": "insufficient_data",
                "n": len(records), "lookback_days": lookback_days,
            }

        by_regime: Dict[str, List[Dict]] = {}
        for r in records:
            by_regime.setdefault(r.get("regime", "RANGING"), []).append(r)

        recommendations: List[Dict] = []

        for regime, recs in by_regime.items():
            if len(recs) < 3:
                continue

            n     = len(recs)
            wins  = [r for r in recs if r.get("outcome") == "WIN"]
            losses = [r for r in recs if r.get("outcome") != "WIN"]
            wr    = len(wins) / n

            avg_loss_pct = (
                sum(abs(float(r.get("pnl_pct", 0))) for r in losses) / len(losses)
                if losses else 0.0
            )
            avg_win_pct = (
                sum(float(r.get("pnl_pct", 0)) for r in wins) / len(wins)
                if wins else 0.0
            )

            current_lam = await self.get_lambda(symbol, regime)
            new_lam     = current_lam
            reason      = "no_change"

            if wr < 0.35 and avg_loss_pct < 1.5:
                # k too tight — price reversed after stop
                new_lam = min(LAMBDA_MAX, current_lam + 0.1)
                reason  = (
                    f"k_too_tight (WR={wr:.1%}, avg_loss={avg_loss_pct:.2f}%) "
                    f"→ λ {current_lam:.2f}→{new_lam:.2f}"
                )
            elif wr > 0.65 and avg_loss_pct > 5.0:
                # k too wide — large losses when stop finally hit
                new_lam = max(LAMBDA_MIN, current_lam - 0.1)
                reason  = (
                    f"k_too_wide (WR={wr:.1%}, avg_loss={avg_loss_pct:.2f}%) "
                    f"→ λ {current_lam:.2f}→{new_lam:.2f}"
                )

            delta = abs(new_lam - current_lam)
            apply = delta >= 0.05

            if apply:
                await self.set_lambda(symbol, regime, new_lam, reason)
                # Invalidate k cache for this symbol/regime
                for key in list(self._k_cache):
                    if symbol in key and regime in key:
                        del self._k_cache[key]
                logger.info("[ATR] Ω applied λ update: %s/%s → %.3f (%s)", symbol, regime, new_lam, reason)

            recommendations.append({
                "regime":         regime,
                "n":              n,
                "wr":             round(wr, 3),
                "avg_win_pct":    round(avg_win_pct, 3),
                "avg_loss_pct":   round(avg_loss_pct, 3),
                "current_lambda": current_lam,
                "new_lambda":     round(new_lam, 3),
                "delta":          round(delta, 3),
                "reason":         reason,
                "applied":        apply,
            })

        return {
            "symbol":          symbol,
            "n_records":       len(records),
            "lookback_days":   lookback_days,
            "recommendations": recommendations,
            "evaluated_at":    datetime.now(timezone.utc).isoformat(),
        }

    # ── Quantum state: volatility amplitude ───────────────────────────────────

    async def get_volatility_amplitude(
        self,
        symbol:    str,
        timeframe: str = "1h",
    ) -> float:
        """
        ATR-based volatility amplitude for |Ψ⟩ quantum state input.

        Returns normalized relative ATR ∈ [0, 1]:
          0.0 → low volatility (coherent state, λ should decrease)
          1.0 → high volatility (chaotic state, λ should increase)

        Normalization: ATR / price, capped at 5% (5% relative ATR → amplitude 1.0).

        High amplitude → AEON's position_multiplier suppressed, λ increases.
        Low amplitude  → AEON's position_multiplier expands, λ decreases.
        """
        sym   = format_mexc_symbol(symbol)
        atr14 = await self.compute_atr14(sym, timeframe)
        if atr14 <= 0:
            return 0.5   # neutral when data unavailable

        if self._market_intel is None:
            return 0.5

        try:
            ticker = await self._market_intel.get_ticker_sync(sym)
            price  = float(ticker.get("price") or ticker.get("last") or 0)
            if price <= 0:
                return 0.5
            rel_atr = atr14 / price      # e.g. 0.02 = 2% relative ATR
            return min(rel_atr / 0.05, 1.0)  # 5% = full amplitude
        except Exception as e:
            logger.debug(f"[ATR] volatility_amplitude {sym}: {e}")
            return 0.5


# ─── Singleton ────────────────────────────────────────────────────────────────

_atr_stop_engine: Optional[ATRStopEngine] = None


def init_atr_stop(db=None) -> ATRStopEngine:
    """Initialise the global ATR stop engine. Call once from server.py."""
    global _atr_stop_engine
    _atr_stop_engine = ATRStopEngine(db)
    return _atr_stop_engine


def get_atr_stop() -> Optional[ATRStopEngine]:
    """Return the live singleton. Returns None before init_atr_stop() is called."""
    return _atr_stop_engine
