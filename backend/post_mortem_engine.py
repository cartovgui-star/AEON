"""
=============================================================
  post_mortem_engine.py — AEON Self-Awareness Layer
=============================================================

  Position in the identity: A(t) = Ω(|Ψ⟩, E, M, L)

  This module is AEON's ability to understand WHY it was wrong,
  learn from it, and never repeat the same blindspot twice.

  Pipeline:
    POST-TRADE  → trade closes as LOSS/LIQUIDATION
                → fetch full entry context from MongoDB
                → classify blindspot type(s)
                → score severity
                → upsert blindspot_memories (dedup by condition key)
                → MODERATE (4-6): Telegram + Lθ queue
                → CRITICAL (7-10): Telegram + Lθ auto-apply + engine pause

    PRE-TRADE   → check_blindspot_history() called BEFORE Quant gatekeeper
                → if historical loss rate > 60% for this condition → warn (+10 pts)
                → if times_seen > 5 AND loss_rate > 70% → block trade entirely

    STARTUP     → run_startup_audit() iterates all trade_memories
                → populates blindspot_memories from scratch
                → sends audit report to Telegram

    OMEGA       → get_cycle_report() returns blindspot summary string
                → appended to every 6h Omega cycle Telegram message

  MongoDB:
    READ   : paper_trades, trade_memories
    WRITE  : blindspot_memories (no TTL, no cap — permanent learning)

  Zero latency impact on live trading:
    - Post-trade analysis runs in background task (fire-and-forget)
    - Pre-trade check uses in-memory cache populated by background refresh
    - Never blocks signal generation or Quant gatekeeper
=============================================================
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── MongoDB collection ─────────────────────────────────────────────────────────

COLLECTION = "blindspot_memories"

# ── Severity bands ─────────────────────────────────────────────────────────────

SEV_MINOR    = 3    # 1-3: log only
SEV_MODERATE = 6    # 4-6: Telegram + Lθ queue
SEV_CRITICAL = 7    # 7-10: Telegram + auto-fix + engine pause

# ── Dedup & escalation thresholds ─────────────────────────────────────────────

_MODERATE_SEEN   = 3      # same blindspot seen 3+ times in 48h → MODERATE escalation
_CRITICAL_SEEN   = 5      # same blindspot seen 5+ times total → CRITICAL escalation
_BLOCK_SEEN      = 5      # times_seen threshold to block pre-trade (combined with loss rate)
_WARN_SEEN       = 2      # times_seen threshold for pre-trade warning
_WARN_LOSS_RATE  = 0.60   # 60% loss rate → pre-trade warning
_BLOCK_LOSS_RATE = 0.70   # 70% loss rate + seen > BLOCK_SEEN → block trade
_QUANT_ADD_PTS   = 10     # extra threshold points injected on blindspot warning

# ── Classification thresholds ─────────────────────────────────────────────────

_ADX_RANGING     = 20.0   # ADX below this = ranging market
_QUANTUM_H_FLOOR = 0.50   # quantum H below this = degraded system
_BIAS_ADX_STRONG = 30.0   # ADX above this amplifies BIAS severity
_DATA_GAP_CONF   = 85.0   # confidence above this + fast stop = DATA_GAP candidate
_DATA_GAP_MINS   = 10.0   # stop hit within this many minutes = suspiciously fast
_DATA_GAP_PNL    = -5.0   # pnl_pct below this = meaningful adverse move
_CONFLUENCE_MINS = 5.0    # stop hit within 5 min despite high confluence = CONFLUENCE_LIE
_CONFLUENCE_MIN  = 3      # minimum confluences fired for CONFLUENCE_LIE to apply
_LEV_SMALL_MOVE  = 2.0    # adverse move below this % at high leverage = LEV_BLINDSPOT
_LEV_MIN         = 10     # minimum leverage for leverage blindspot check
_LEV_BLOWUP_MULT = 100.0  # pct_to_sl × leverage > this = position-wipeout risk

# ── Timeframe → candle duration (minutes) ─────────────────────────────────────

_TF_MINUTES: Dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440,
}

# ── Lθ auto-fix specs: blindspot_type → (param, adjustment) ──────────────────
# Leverage adjustment is a ratio (multiplicative); all others are additive.

_AUTO_FIX: Dict[str, Tuple[str, float]] = {
    "BIAS_BLINDSPOT":      ("min_confidence", +2.0),
    "REGIME_BLINDSPOT":    ("min_confidence", +3.0),
    "CONFLUENCE_LIE":      ("min_confidence", +2.0),
    "DATA_GAP_BLINDSPOT":  ("min_confidence", +3.0),
    "QUANTUM_BLINDSPOT":   ("min_confidence", +2.0),
    "LEVERAGE_BLINDSPOT":  ("max_leverage",   -0.10),   # −10% of current value
    "COMPOUND_BLINDSPOT":  ("min_confidence", +5.0),
}

# ── Base severity by blindspot type ───────────────────────────────────────────

_BASE_SEVERITY: Dict[str, int] = {
    "BIAS_BLINDSPOT":      4,
    "REGIME_BLINDSPOT":    3,
    "CONFLUENCE_LIE":      3,
    "DATA_GAP_BLINDSPOT":  5,
    "QUANTUM_BLINDSPOT":   4,
    "LEVERAGE_BLINDSPOT":  4,
    "COMPOUND_BLINDSPOT":  7,
}


# ── BlindspotType enum ────────────────────────────────────────────────────────

class BlindspotType(str, Enum):
    BIAS_BLINDSPOT      = "BIAS_BLINDSPOT"
    REGIME_BLINDSPOT    = "REGIME_BLINDSPOT"
    CONFLUENCE_LIE      = "CONFLUENCE_LIE"
    DATA_GAP_BLINDSPOT  = "DATA_GAP_BLINDSPOT"
    QUANTUM_BLINDSPOT   = "QUANTUM_BLINDSPOT"
    LEVERAGE_BLINDSPOT  = "LEVERAGE_BLINDSPOT"
    COMPOUND_BLINDSPOT  = "COMPOUND_BLINDSPOT"


# ── Module-level state ────────────────────────────────────────────────────────

# Engine pause registry: engine_id → resume datetime
_ENGINE_PAUSES: Dict[str, datetime] = {}

# Pre-trade cache: "engine:regime:btc_bias" → {type, times_seen, loss_rate, description}
_BLINDSPOT_CACHE: Dict[str, Dict] = {}

# Lθ lazy-loaded references (same pattern as omega_cycle.py)
_ltheta_apply: Optional[Any]          = None
_ltheta_engine_configs: Optional[Any] = None

# Singleton
_instance: Optional["PostMortemEngine"] = None


def _init_ltheta() -> None:
    global _ltheta_apply, _ltheta_engine_configs
    if _ltheta_apply is None:
        try:
            from aeon_ltheta_params import apply_override
            from aeon_engine_system import ENGINE_CONFIGS
            _ltheta_apply          = apply_override
            _ltheta_engine_configs = ENGINE_CONFIGS
            logger.debug("[PostMortem] Lθ lazy-loaded")
        except Exception as exc:
            logger.warning(f"[PostMortem] Lθ import failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  PostMortemEngine
# ─────────────────────────────────────────────────────────────────────────────

class PostMortemEngine:
    """
    AEON's self-awareness layer.

    Public API
    ----------
    analyze_closed_trade(trade_id)              async — call after LOSS/LIQUIDATION
    check_blindspot_history(engine, regime,
                            btc_bias, signal)   sync  — call BEFORE Quant gatekeeper
    run_startup_audit()                         async — call once on server start
    get_cycle_report()                          async — called by omega_cycle every 6h
    is_engine_paused(engine_id)                 sync  — engines call before firing
    """

    def __init__(self, db=None):
        self.db            = db
        self._send_alert   = None
        self._chat_ids: Set = set()
        self._quantum_ref  = None
        self._lock         = asyncio.Lock()
        self._in_flight: Set[str] = set()   # trade_ids currently being analyzed

        # Per-cycle counters (reset every get_cycle_report call)
        self._cycle: Dict[str, Any] = self._empty_cycle_stats()

    # ── Dependency injection ──────────────────────────────────────────────────

    def set_dependencies(self, **kwargs) -> None:
        self.db           = kwargs.get("db", self.db)
        self._send_alert  = kwargs.get("send_alert", self._send_alert)
        self._chat_ids    = kwargs.get("chat_ids", self._chat_ids)
        self._quantum_ref = kwargs.get("quantum_state", self._quantum_ref)

    # =========================================================================
    #  PUBLIC: pre-trade blindspot check
    # =========================================================================

    def check_blindspot_history(
        self,
        engine: str,
        regime: str,
        btc_bias: str,
        signal_data: Dict,
    ) -> Dict:
        """
        Called BEFORE the Quant gatekeeper.

        Uses an in-memory cache populated by background async refresh.
        The first call for an unseen condition returns {} and schedules
        a refresh — subsequent calls (after the next trade) use fresh data.

        Returns:
            {} — no blindspot concern
            {"blindspot_warning": True, "quant_threshold_add": 10}  — warn
            {"blindspot_block": True, ...}  — block trade entirely
        """
        key = f"{engine}:{regime}:{btc_bias}"
        cached = _BLINDSPOT_CACHE.get(key)

        if cached is None:
            # Schedule background refresh without blocking
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(
                        self._refresh_cache(engine, regime, btc_bias)
                    )
            except Exception:
                pass
            return {}

        loss_rate  = cached.get("loss_rate", 0.0)
        times_seen = cached.get("times_seen", 0)

        # Block
        if times_seen > _BLOCK_SEEN and loss_rate > _BLOCK_LOSS_RATE:
            self._cycle["pre_trade_blocks"] += 1
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(
                        self._send_block_alert(engine, regime, btc_bias, cached)
                    )
            except Exception:
                pass
            return {
                "blindspot_block":       True,
                "blindspot_type":        cached.get("type"),
                "historical_loss_rate":  loss_rate,
                "times_seen":            times_seen,
                "description":           cached.get("description", ""),
            }

        # Warn
        if times_seen >= _WARN_SEEN and loss_rate > _WARN_LOSS_RATE:
            signal_data["blindspot_warning"]     = True
            signal_data["blindspot_type"]        = cached.get("type")
            signal_data["historical_loss_rate"]  = loss_rate
            signal_data["times_seen"]            = times_seen
            signal_data["description"]           = cached.get("description", "")
            return {
                "blindspot_warning":   True,
                "quant_threshold_add": _QUANT_ADD_PTS,
            }

        return {}

    # =========================================================================
    #  PUBLIC: post-trade trigger
    # =========================================================================

    async def analyze_closed_trade(self, trade_id: str) -> None:
        """
        Entry point — call after any trade closes as LOSS or LIQUIDATION.
        Fire-and-forget: runs fully async, never blocks the caller.
        """
        if self.db is None:
            return
        if trade_id in self._in_flight:
            return
        self._in_flight.add(trade_id)
        try:
            await self._analyze(trade_id)
        except Exception as exc:
            logger.error(
                f"[PostMortem] analyze error trade={trade_id}: {exc}",
                exc_info=True,
            )
        finally:
            self._in_flight.discard(trade_id)

    # =========================================================================
    #  PUBLIC: engine pause check
    # =========================================================================

    def is_engine_paused(self, engine_id: str) -> bool:
        """Engines call this before firing a signal."""
        resume = _ENGINE_PAUSES.get(engine_id)
        if resume is None:
            return False
        if datetime.now(timezone.utc) >= resume:
            _ENGINE_PAUSES.pop(engine_id, None)
            return False
        return True

    # =========================================================================
    #  PUBLIC: startup audit
    # =========================================================================

    async def run_startup_audit(self) -> None:
        if self.db is None:
            return
        try:
            await self._startup_audit()
        except Exception as exc:
            logger.error(f"[PostMortem] startup audit error: {exc}", exc_info=True)

    # =========================================================================
    #  PUBLIC: omega cycle report block
    # =========================================================================

    async def get_cycle_report(self) -> str:
        if self.db is None:
            return ""
        try:
            return await self._build_cycle_report()
        except Exception as exc:
            logger.error(f"[PostMortem] cycle report error: {exc}", exc_info=True)
            return ""

    # =========================================================================
    #  CORE ANALYSIS PIPELINE
    # =========================================================================

    async def _analyze(self, trade_id: str) -> None:
        ctx = await self._fetch_trade_context(trade_id)
        if ctx is None:
            return

        outcome = ctx.get("outcome", "LOSS")
        if outcome not in ("LOSS", "LIQUIDATION"):
            return

        # Classify all applicable blindspot types
        btypes = self._classify_blindspot(ctx)
        if not btypes:
            logger.debug(
                f"[PostMortem] trade={trade_id} engine={ctx.get('engine')} "
                f"— no blindspot classified (outcome={outcome})"
            )
            return

        # COMPOUND if multiple types detected
        if len(btypes) > 1:
            primary = BlindspotType.COMPOUND_BLINDSPOT
        else:
            primary = btypes[0]

        root_cause = self._describe_root_cause(ctx, btypes)

        async with self._lock:
            record = await self._upsert_blindspot_memory(ctx, primary, root_cause, outcome)
            if record is None:
                return

            times_seen = record.get("times_seen", 1)
            loss_rate  = await self._compute_loss_rate(record)
            severity   = self._score_severity(primary, times_seen, outcome, loss_rate, ctx)

            # Persist computed severity and loss rate
            await self.db[COLLECTION].update_one(
                {"_id": record["_id"]},
                {"$set": {"severity": severity, "loss_rate": round(loss_rate, 4)}},
            )

            # Invalidate pre-trade cache for this condition so next call is fresh
            cache_key = (
                f"{ctx.get('engine','')}:"
                f"{ctx.get('regime','UNKNOWN')}:"
                f"{ctx.get('btc_bias','NEUTRAL')}"
            )
            _BLINDSPOT_CACHE.pop(cache_key, None)
            asyncio.ensure_future(
                self._refresh_cache(
                    ctx.get("engine", ""),
                    ctx.get("regime", "UNKNOWN"),
                    ctx.get("btc_bias", "NEUTRAL"),
                )
            )

            self._cycle["blindspots"] += 1

            if severity >= SEV_CRITICAL:
                self._cycle["critical"] += 1
                await self._handle_critical(
                    ctx, record, primary, severity, times_seen, loss_rate
                )
            elif severity >= SEV_MODERATE + 1:
                await self._handle_moderate(ctx, record, primary, severity, times_seen)
            else:
                logger.info(
                    f"[PostMortem] MINOR blindspot={primary.value} "
                    f"engine={ctx.get('engine')} severity={severity} — logged only"
                )

    # =========================================================================
    #  CONTEXT FETCH
    # =========================================================================

    async def _fetch_trade_context(self, trade_id: str) -> Optional[Dict]:
        """
        Pull full entry context by merging paper_trades (exit data)
        with trade_memories (entry environment — btc_bias, regime, quantum_H, etc.).
        """
        try:
            from bson import ObjectId

            # ── paper_trades lookup ───────────────────────────────────────────
            pt: Optional[Dict] = None
            try:
                oid = ObjectId(trade_id)
                pt  = await self.db["paper_trades"].find_one({"_id": oid})
            except Exception:
                pass
            if pt is None:
                pt = await self.db["paper_trades"].find_one(
                    {"paper_trade_id": trade_id}
                )
            if pt is None:
                logger.debug(f"[PostMortem] paper_trade not found: {trade_id}")
                return None

            # ── Identify engine string ────────────────────────────────────────
            engine: str = (
                (pt.get("signal_data") or {}).get("engine")
                or pt.get("strategy", "")
            )
            symbol:    str            = pt.get("symbol", "")
            direction: str            = pt.get("direction", "") or (pt.get("signal_data") or {}).get("direction", "")
            closed_at: Optional[datetime] = pt.get("closed_at")
            opened_at: Optional[datetime] = pt.get("opened_at")

            # ── trade_memories lookup (richest source of entry conditions) ────
            mem_query: Dict[str, Any] = {
                "symbol":  symbol,
                "outcome": {"$in": ["LOSS", "LIQUIDATION"]},
            }
            if engine:
                mem_query["engine"] = {"$regex": engine, "$options": "i"}
            if closed_at:
                mem_query["timestamp_close"] = {
                    "$gte": closed_at - timedelta(minutes=5),
                    "$lte": closed_at + timedelta(minutes=5),
                }
            mem: Optional[Dict] = await self.db["trade_memories"].find_one(
                mem_query, sort=[("timestamp_close", -1)]
            )

            # ── Merge fields ──────────────────────────────────────────────────
            def _pick(*keys: str, docs: List[Optional[Dict]], default=None):
                for k in keys:
                    for d in docs:
                        if d and d.get(k) is not None:
                            return d.get(k)
                return default

            docs = [pt, mem]

            entry_price: float = _pick("entry_price", docs=docs, default=0.0)
            stop_loss:   float = _pick("stop_loss",   docs=docs, default=0.0)
            leverage:    int   = int(_pick("leverage", docs=docs, default=1) or 1)
            confidence:  float = _pick("confidence",  docs=docs, default=0.0)
            timeframe:   str   = (
                (mem.get("timeframe") if mem else None)
                or (pt.get("signal_data") or {}).get("timeframe", "1h")
            )
            pnl_pct: float = _pick("pnl_pct", docs=docs, default=0.0)

            exit_price: Optional[float] = _derive_exit_price(
                pt, mem, entry_price, pnl_pct, direction
            )

            # ── Entry environment — from trade_memories env_* fields ──────────
            btc_bias  = (mem.get("env_btc_bias") if mem else None) or "NEUTRAL"
            regime    = (mem.get("env_regime")   if mem else None) or "UNKNOWN"
            adx_raw   = (mem.get("env_adx") if mem else None) or (mem.get("adx") if mem else None) or \
                        (pt.get("signal_data") or {}).get("indicators", {}).get("adx", 0.0)
            adx:     float = float(adx_raw or 0.0)
            quantum_H: float = float((mem.get("quantum_H") if mem else 0.0) or 0.0)
            quantum_C: float = float((mem.get("quantum_C") if mem else 0.0) or 0.0)
            confluences: int = int(_pick("confluences", docs=[mem], default=0) or 0)

            # ── Price movement analysis ───────────────────────────────────────
            price_moved_against_pct: Optional[float] = None
            if entry_price and exit_price:
                if direction == "LONG":
                    price_moved_against_pct = round(
                        (entry_price - exit_price) / entry_price * 100, 3
                    )
                else:
                    price_moved_against_pct = round(
                        (exit_price - entry_price) / entry_price * 100, 3
                    )

            stop_hit_minutes: Optional[float] = None
            if opened_at and closed_at:
                stop_hit_minutes = round(
                    (closed_at - opened_at).total_seconds() / 60.0, 1
                )
            elif mem and mem.get("duration_min") is not None:
                stop_hit_minutes = float(mem["duration_min"])

            # ── Infer outcome ─────────────────────────────────────────────────
            outcome = (mem.get("outcome") if mem else None) or _infer_outcome(pt)

            return {
                "trade_id":                trade_id,
                "paper_trade_id":          str(pt.get("_id", trade_id)),
                "engine":                  engine,
                "symbol":                  symbol,
                "direction":               direction,
                "outcome":                 outcome,
                "entry_price":             entry_price,
                "stop_loss":               stop_loss,
                "exit_price":              exit_price,
                "pnl_pct":                 float(pnl_pct or 0.0),
                "leverage":                leverage,
                "confidence":              float(confidence or 0.0),
                "timeframe":               timeframe,
                # Entry environment
                "btc_bias":                btc_bias,
                "regime":                  regime,
                "adx":                     adx,
                "quantum_H":               quantum_H,
                "quantum_C":               quantum_C,
                "quant_score":             float(confidence or 0.0),
                "confluences":             confluences,
                # Movement analysis
                "price_moved_against_pct": price_moved_against_pct,
                "stop_hit_minutes":        stop_hit_minutes,
                "btc_price_change_4h":     mem.get("btc_price_change_4h") if mem else None,
                "btc_price_change_1h":     mem.get("btc_price_change_1h") if mem else None,
                # Raw docs kept for deep inspection
                "_pt":  pt,
                "_mem": mem,
            }

        except Exception as exc:
            logger.error(
                f"[PostMortem] _fetch_trade_context error: {exc}", exc_info=True
            )
            return None

    # =========================================================================
    #  BLINDSPOT CLASSIFICATION
    # =========================================================================

    def _classify_blindspot(self, ctx: Dict) -> List[BlindspotType]:
        found: List[BlindspotType] = []

        direction    = ctx.get("direction", "")
        btc_bias     = ctx.get("btc_bias", "NEUTRAL")
        regime       = (ctx.get("regime") or "UNKNOWN").upper()
        adx          = float(ctx.get("adx") or 0.0)
        quantum_H    = float(ctx.get("quantum_H") or 0.0)
        leverage     = int(ctx.get("leverage") or 1)
        entry_price  = float(ctx.get("entry_price") or 0.0)
        stop_loss    = float(ctx.get("stop_loss") or 0.0)
        exit_price   = ctx.get("exit_price")
        pnl_pct      = float(ctx.get("pnl_pct") or 0.0)
        quant_score  = float(ctx.get("quant_score") or 0.0)
        confluences  = int(ctx.get("confluences") or 0)
        stop_mins    = ctx.get("stop_hit_minutes") or 9999.0

        # ── BIAS_BLINDSPOT ────────────────────────────────────────────────────
        if (btc_bias == "BEARISH" and direction == "LONG") or \
           (btc_bias == "BULLISH" and direction == "SHORT"):
            found.append(BlindspotType.BIAS_BLINDSPOT)

        # ── REGIME_BLINDSPOT ──────────────────────────────────────────────────
        if adx < _ADX_RANGING or regime in ("CHAOS", "RANGING", "SIDEWAYS"):
            found.append(BlindspotType.REGIME_BLINDSPOT)

        # ── QUANTUM_BLINDSPOT ─────────────────────────────────────────────────
        if 0.0 < quantum_H < _QUANTUM_H_FLOOR:
            found.append(BlindspotType.QUANTUM_BLINDSPOT)

        # ── LEVERAGE_BLINDSPOT ────────────────────────────────────────────────
        if entry_price and stop_loss and exit_price and leverage >= _LEV_MIN:
            if direction == "LONG":
                pct_to_sl = abs(entry_price - stop_loss) / entry_price * 100.0
                actual_adverse = abs(entry_price - float(exit_price)) / entry_price * 100.0
            else:
                pct_to_sl = abs(stop_loss - entry_price) / entry_price * 100.0
                actual_adverse = abs(float(exit_price) - entry_price) / entry_price * 100.0

            # Small adverse price move amplified by leverage into a liquidation/stop
            lev_blowup = pct_to_sl * leverage > _LEV_BLOWUP_MULT
            small_move = actual_adverse < _LEV_SMALL_MOVE
            if small_move or lev_blowup:
                found.append(BlindspotType.LEVERAGE_BLINDSPOT)

        # ── CONFLUENCE_LIE ────────────────────────────────────────────────────
        # High confluence count but price reversed immediately
        if (
            confluences >= _CONFLUENCE_MIN
            and stop_mins < _CONFLUENCE_MINS
            and pnl_pct < 0
        ):
            found.append(BlindspotType.CONFLUENCE_LIE)

        # ── DATA_GAP_BLINDSPOT ────────────────────────────────────────────────
        # High confidence signal but stop hit almost instantly → data was stale
        if (
            quant_score >= _DATA_GAP_CONF
            and stop_mins < _DATA_GAP_MINS
            and pnl_pct < _DATA_GAP_PNL
            and BlindspotType.CONFLUENCE_LIE not in found  # avoid double-classify
        ):
            found.append(BlindspotType.DATA_GAP_BLINDSPOT)

        return found

    # =========================================================================
    #  SEVERITY SCORING
    # =========================================================================

    def _score_severity(
        self,
        btype: BlindspotType,
        times_seen: int,
        outcome: str,
        loss_rate: float,
        ctx: Dict,
    ) -> int:
        score = _BASE_SEVERITY.get(btype.value, 3)

        # Escalate by recurrence
        if times_seen >= _CRITICAL_SEEN:
            score += 3
        elif times_seen >= _MODERATE_SEEN:
            score += 2

        # Liquidation is worse than a plain loss
        if outcome == "LIQUIDATION":
            score += 3

        # High loss rate for this condition
        if loss_rate > _BLOCK_LOSS_RATE:
            score += 2
        elif loss_rate > _WARN_LOSS_RATE:
            score += 1

        # Strong BTC trend amplifies BIAS_BLINDSPOT severity
        if btype == BlindspotType.BIAS_BLINDSPOT:
            if float(ctx.get("adx") or 0.0) > _BIAS_ADX_STRONG:
                score += 1

        return min(score, 10)

    # =========================================================================
    #  MONGODB UPSERT (dedup by condition key)
    # =========================================================================

    async def _upsert_blindspot_memory(
        self,
        ctx: Dict,
        btype: BlindspotType,
        root_cause: str,
        outcome: str,
    ) -> Optional[Dict]:
        """
        Dedup key: engine + blindspot_type + entry_context.regime + entry_context.btc_bias
        Same condition → increment times_seen (no duplicate records).
        New condition  → insert fresh record.
        Returns the current record after write.
        """
        engine   = ctx.get("engine", "unknown")
        regime   = ctx.get("regime", "UNKNOWN")
        btc_bias = ctx.get("btc_bias", "NEUTRAL")
        now      = datetime.now(timezone.utc)

        dedup_filter = {
            "engine":                    engine,
            "blindspot_type":            btype.value,
            "entry_context.regime":      regime,
            "entry_context.btc_bias":    btc_bias,
        }

        entry_context = {
            "btc_bias":          btc_bias,
            "regime":            regime,
            "adx":               ctx.get("adx"),
            "quantum_H":         ctx.get("quantum_H"),
            "quant_score":       ctx.get("quant_score"),
            "confluences_fired": ctx.get("confluences"),
            "direction":         ctx.get("direction"),
            "leverage":          ctx.get("leverage"),
            "timeframe":         ctx.get("timeframe"),
        }

        what_happened = {
            "price_moved_against_pct": ctx.get("price_moved_against_pct"),
            "stop_hit_minutes":        ctx.get("stop_hit_minutes"),
            "actual_exit":             ctx.get("exit_price"),
            "btc_move_during_trade":   ctx.get("btc_price_change_4h"),
            "outcome":                 outcome,
        }

        try:
            existing = await self.db[COLLECTION].find_one(dedup_filter)

            if existing:
                await self.db[COLLECTION].update_one(
                    {"_id": existing["_id"]},
                    {
                        "$inc": {"times_seen": 1},
                        "$set": {
                            "last_seen":    now,
                            "what_happened": what_happened,
                            "root_cause":    root_cause,
                        },
                        "$push": {
                            "recent_trade_ids": {
                                "$each":  [ctx.get("paper_trade_id", "")],
                                "$slice": -20,
                            }
                        },
                    },
                )
                return await self.db[COLLECTION].find_one({"_id": existing["_id"]})

            else:
                doc = {
                    "blindspot_id":    str(uuid.uuid4()),
                    "timestamp":       now,
                    "last_seen":       now,
                    "engine":          engine,
                    "symbol":          ctx.get("symbol", ""),
                    "blindspot_type":  btype.value,
                    "severity":        5,       # updated after scoring
                    "loss_rate":       0.0,     # updated after compute_loss_rate
                    "entry_context":   entry_context,
                    "what_happened":   what_happened,
                    "root_cause":      root_cause,
                    "auto_fix_applied": False,
                    "fix_description":  "",
                    "times_seen":       1,
                    "recent_trade_ids": [ctx.get("paper_trade_id", "")],
                }
                result = await self.db[COLLECTION].insert_one(doc)
                return await self.db[COLLECTION].find_one({"_id": result.inserted_id})

        except Exception as exc:
            logger.error(f"[PostMortem] _upsert_blindspot_memory error: {exc}", exc_info=True)
            return None

    # =========================================================================
    #  LOSS RATE COMPUTATION
    # =========================================================================

    async def _compute_loss_rate(self, record: Dict) -> float:
        """
        Historical loss rate for this exact engine + regime + btc_bias condition,
        computed from trade_memories collection.
        """
        engine   = record.get("engine", "")
        ec       = record.get("entry_context", {})
        regime   = ec.get("regime", "")
        btc_bias = ec.get("btc_bias", "")

        if not engine or not regime:
            ts = record.get("times_seen", 1)
            return ts / max(ts, 1)

        try:
            base_q: Dict[str, Any] = {
                "engine":       {"$regex": engine, "$options": "i"},
                "env_regime":   regime,
                "env_btc_bias": btc_bias,
            }
            total  = await self.db["trade_memories"].count_documents(base_q)
            if total == 0:
                return 1.0

            loss_q = {**base_q, "outcome": {"$in": ["LOSS", "LIQUIDATION"]}}
            losses = await self.db["trade_memories"].count_documents(loss_q)
            return losses / total

        except Exception as exc:
            logger.debug(f"[PostMortem] _compute_loss_rate error: {exc}")
            return 0.5

    # =========================================================================
    #  ROOT CAUSE NARRATIVE
    # =========================================================================

    def _describe_root_cause(
        self, ctx: Dict, btypes: List[BlindspotType]
    ) -> str:
        parts: List[str] = []

        direction   = ctx.get("direction", "?")
        btc_bias    = ctx.get("btc_bias", "NEUTRAL")
        adx         = float(ctx.get("adx") or 0.0)
        regime      = ctx.get("regime", "UNKNOWN")
        quantum_H   = float(ctx.get("quantum_H") or 0.0)
        leverage    = int(ctx.get("leverage") or 1)
        stop_mins   = ctx.get("stop_hit_minutes") or 0
        pnl_pct     = float(ctx.get("pnl_pct") or 0.0)
        quant_score = float(ctx.get("quant_score") or 0.0)
        confluences = ctx.get("confluences", "?")

        for bt in btypes:
            if bt == BlindspotType.BIAS_BLINDSPOT:
                parts.append(
                    f"BTC macro bias was {btc_bias} but engine fired {direction}. "
                    f"ADX={adx:.1f} — directional momentum opposed this trade."
                )
            elif bt == BlindspotType.REGIME_BLINDSPOT:
                parts.append(
                    f"Regime '{regime}' with ADX={adx:.1f} (below {_ADX_RANGING} = ranging). "
                    f"No trending edge — engine fired into choppy conditions."
                )
            elif bt == BlindspotType.QUANTUM_BLINDSPOT:
                parts.append(
                    f"System H={quantum_H:.4f} below floor {_QUANTUM_H_FLOOR} at entry. "
                    f"Degraded engine performance — should have reduced size or skipped."
                )
            elif bt == BlindspotType.LEVERAGE_BLINDSPOT:
                parts.append(
                    f"{leverage}x leverage amplified a small adverse move into a stop/liquidation "
                    f"({pnl_pct:.2f}% PnL in {stop_mins:.0f} min). "
                    f"Lower leverage would have survived the same price action."
                )
            elif bt == BlindspotType.CONFLUENCE_LIE:
                parts.append(
                    f"{confluences} confluences fired but price reversed immediately "
                    f"({pnl_pct:.2f}% PnL in {stop_mins:.0f} min). "
                    f"One or more confluences produced a false directional signal."
                )
            elif bt == BlindspotType.DATA_GAP_BLINDSPOT:
                parts.append(
                    f"High confidence ({quant_score:.0f}/100) but stop hit in {stop_mins:.0f} min. "
                    f"Stale or cached data likely inflated the score at entry time."
                )

        if not parts:
            return "Trade outcome did not match entry conditions."
        return " | ".join(parts)

    # =========================================================================
    #  HANDLERS
    # =========================================================================

    async def _handle_moderate(
        self,
        ctx: Dict,
        record: Dict,
        btype: BlindspotType,
        severity: int,
        times_seen: int,
    ) -> None:
        logger.warning(
            f"[PostMortem] MODERATE blindspot={btype.value} "
            f"engine={ctx.get('engine')} severity={severity} times_seen={times_seen}"
        )
        await self._send_moderate_alert(ctx, record, btype, severity, times_seen)

    async def _handle_critical(
        self,
        ctx: Dict,
        record: Dict,
        btype: BlindspotType,
        severity: int,
        times_seen: int,
        loss_rate: float,
    ) -> None:
        engine    = ctx.get("engine", "")
        timeframe = ctx.get("timeframe", "1h")

        H_before = 0.0
        if self._quantum_ref:
            try:
                H_before = self._quantum_ref.get_health()
            except Exception:
                pass

        # Apply Lθ auto-fix
        fix_desc = await self._apply_auto_fix(ctx, btype, H_before)

        # Pause engine for 1 candle
        resume_time = self._pause_engine(engine, timeframe)

        H_after = H_before
        if self._quantum_ref:
            try:
                H_after = self._quantum_ref.get_health()
            except Exception:
                pass

        # Persist fix metadata
        try:
            await self.db[COLLECTION].update_one(
                {"_id": record["_id"]},
                {"$set": {"auto_fix_applied": True, "fix_description": fix_desc}},
            )
        except Exception:
            pass

        self._cycle["auto_fixes"] += 1

        logger.warning(
            f"[PostMortem] CRITICAL blindspot={btype.value} engine={engine} "
            f"severity={severity} times_seen={times_seen} loss_rate={loss_rate:.1%} "
            f"fix='{fix_desc}' paused_until={resume_time.isoformat()}"
        )
        await self._send_critical_alert(
            ctx, record, btype, severity, times_seen, loss_rate,
            fix_desc, resume_time, H_before, H_after,
        )

    # =========================================================================
    #  LΘ AUTO-FIX
    # =========================================================================

    async def _apply_auto_fix(
        self, ctx: Dict, btype: BlindspotType, H_before: float
    ) -> str:
        _init_ltheta()
        if _ltheta_apply is None or _ltheta_engine_configs is None:
            return "Lθ not available — fix logged only"

        engine   = ctx.get("engine", "")
        fix_spec = _AUTO_FIX.get(btype.value)
        if fix_spec is None:
            return f"No auto-fix defined for {btype.value}"

        param, delta = fix_spec

        # Find current config value for this engine
        current_value: Optional[Any] = None
        for et, cfg in _ltheta_engine_configs.items():
            if et.value == engine or engine in str(et.value):
                current_value = getattr(cfg, param, None)
                break

        if current_value is None:
            return f"Engine '{engine}' not found in ENGINE_CONFIGS"

        # Compute new value
        if param == "max_leverage":
            new_value = max(5, int(current_value * (1.0 + delta)))   # delta is negative ratio
        else:
            new_value = round(float(current_value) + delta, 2)

        applied = _ltheta_apply(
            _ltheta_engine_configs,
            engine,
            param,
            new_value,
            cycle=0,
            H_before=H_before,
            H_after=H_before,   # estimated; real measurement is post-apply
        )

        if applied:
            return f"{param}: {current_value} → {new_value} (blindspot auto-fix Δ={delta:+})"
        return f"Lθ rejected {param}={new_value} for '{engine}' (bounds check failed)"

    # =========================================================================
    #  ENGINE PAUSE
    # =========================================================================

    def _pause_engine(self, engine_id: str, timeframe: str) -> datetime:
        candle_minutes = _TF_MINUTES.get(timeframe, 60)
        resume         = datetime.now(timezone.utc) + timedelta(minutes=candle_minutes)
        _ENGINE_PAUSES[engine_id] = resume
        logger.info(f"[PostMortem] Engine '{engine_id}' paused for {candle_minutes}m → resumes {resume.isoformat()}")
        return resume

    # =========================================================================
    #  PRE-TRADE CACHE REFRESH
    # =========================================================================

    async def _refresh_cache(self, engine: str, regime: str, btc_bias: str) -> None:
        if self.db is None:
            return
        key = f"{engine}:{regime}:{btc_bias}"
        try:
            record = await self.db[COLLECTION].find_one(
                {
                    "engine":                 engine,
                    "entry_context.regime":   regime,
                    "entry_context.btc_bias": btc_bias,
                    "times_seen":             {"$gte": _WARN_SEEN},
                },
                sort=[("times_seen", -1)],
            )
            if record:
                _BLINDSPOT_CACHE[key] = {
                    "type":        record.get("blindspot_type"),
                    "times_seen":  record.get("times_seen", 0),
                    "loss_rate":   record.get("loss_rate", 0.0),
                    "description": record.get("root_cause", ""),
                }
            else:
                _BLINDSPOT_CACHE.pop(key, None)
        except Exception as exc:
            logger.debug(f"[PostMortem] _refresh_cache error: {exc}")

    # =========================================================================
    #  STARTUP AUDIT
    # =========================================================================

    async def _startup_audit(self) -> None:
        logger.info("[PostMortem] Running startup audit of trade_memories …")

        losses_cur = self.db["trade_memories"].find(
            {"outcome": {"$in": ["LOSS", "LIQUIDATION"]}}
        )
        losses = await losses_cur.to_list(length=5000)

        if not losses:
            logger.info("[PostMortem] No losses in trade_memories — audit empty")
            return

        type_counts: Dict[str, int] = {bt.value: 0 for bt in BlindspotType}
        n_loss = n_liq = 0

        for mem in losses:
            if mem.get("outcome") == "LIQUIDATION":
                n_liq += 1
            else:
                n_loss += 1

            ctx    = _mem_to_ctx(mem)
            btypes = self._classify_blindspot(ctx)
            if not btypes:
                continue

            primary    = BlindspotType.COMPOUND_BLINDSPOT if len(btypes) > 1 else btypes[0]
            root_cause = self._describe_root_cause(ctx, btypes)
            type_counts[primary.value] += 1
            await self._upsert_blindspot_memory(ctx, primary, root_cause, ctx.get("outcome", "LOSS"))

        # Count active pre-trade filter conditions
        filters_active = await self.db[COLLECTION].count_documents(
            {"times_seen": {"$gte": _WARN_SEEN}}
        )

        total_bs = sum(type_counts.values())

        worst = await self.db[COLLECTION].find_one(
            {}, sort=[("times_seen", -1)]
        )
        worst_desc = ""
        if worst:
            worst_desc = (
                f"{worst.get('blindspot_type')} — {worst.get('engine')} — "
                f"seen {worst.get('times_seen')}x — "
                f"{str(worst.get('root_cause',''))[:120]}"
            )

        def pct(n: int) -> str:
            return f"{n / max(total_bs, 1) * 100:.1f}"

        msg = (
            f"🔍 POST-MORTEM STARTUP AUDIT\n"
            f"Analyzed: {n_loss} losses + {n_liq} liquidations\n"
            f"Blindspots found: {total_bs}\n"
            f"\nBreakdown:\n"
            f"BIAS_BLINDSPOT:     {type_counts['BIAS_BLINDSPOT']} ({pct(type_counts['BIAS_BLINDSPOT'])}%)\n"
            f"REGIME_BLINDSPOT:   {type_counts['REGIME_BLINDSPOT']} ({pct(type_counts['REGIME_BLINDSPOT'])}%)\n"
            f"CONFLUENCE_LIE:     {type_counts['CONFLUENCE_LIE']} ({pct(type_counts['CONFLUENCE_LIE'])}%)\n"
            f"DATA_GAP:           {type_counts['DATA_GAP_BLINDSPOT']} ({pct(type_counts['DATA_GAP_BLINDSPOT'])}%)\n"
            f"QUANTUM_BLINDSPOT:  {type_counts['QUANTUM_BLINDSPOT']} ({pct(type_counts['QUANTUM_BLINDSPOT'])}%)\n"
            f"LEVERAGE_BLINDSPOT: {type_counts['LEVERAGE_BLINDSPOT']} ({pct(type_counts['LEVERAGE_BLINDSPOT'])}%)\n"
            f"COMPOUND:           {type_counts['COMPOUND_BLINDSPOT']} ({pct(type_counts['COMPOUND_BLINDSPOT'])}%)\n"
            f"\nMost dangerous condition right now:\n{worst_desc}\n"
            f"\nPre-trade filters activated: {filters_active}\n"
            f"AEON is aware of its weaknesses.\n"
            f"Learning mode: ACTIVE"
        )

        await self._send_telegram(msg)
        logger.info(
            f"[PostMortem] Startup audit complete — {total_bs} blindspots, "
            f"{filters_active} pre-trade filters active"
        )

    # =========================================================================
    #  OMEGA CYCLE REPORT
    # =========================================================================

    async def _build_cycle_report(self) -> str:
        total = await self.db[COLLECTION].count_documents({})

        top3_cur = self.db[COLLECTION].find(
            {}, sort=[("times_seen", -1)]
        ).limit(3)
        top3 = await top3_cur.to_list(length=3)

        # Most common blindspot type
        type_pipeline = [
            {"$group": {"_id": "$blindspot_type", "count": {"$sum": 1}}},
            {"$sort":  {"count": -1}},
            {"$limit": 1},
        ]
        type_res = await self.db[COLLECTION].aggregate(type_pipeline).to_list(1)
        most_common_type = type_res[0]["_id"] if type_res else "N/A"

        # Most affected engine
        eng_pipeline = [
            {"$group": {"_id": "$engine", "count": {"$sum": 1}}},
            {"$sort":  {"count": -1}},
            {"$limit": 1},
        ]
        eng_res = await self.db[COLLECTION].aggregate(eng_pipeline).to_list(1)
        most_affected_engine = eng_res[0]["_id"] if eng_res else "N/A"

        # Snapshot and reset cycle counters
        n_this_cycle = self._cycle["blindspots"]
        n_critical   = self._cycle["critical"]
        n_fixes      = self._cycle["auto_fixes"]
        n_blocks     = self._cycle["pre_trade_blocks"]
        self._cycle  = self._empty_cycle_stats()

        lines = [
            "🔍 BLINDSPOT REPORT",
            f"Total blindspots logged: {total}",
            f"Critical this cycle:     {n_critical}",
            f"Most common type:        {most_common_type}",
            f"Most affected engine:    {most_affected_engine}",
            f"Auto-fixes applied:      {n_fixes}",
            f"Pre-trade blocks:        {n_blocks}",
            "",
            "Top 3 active blindspots:",
        ]
        for i, r in enumerate(top3, 1):
            lr   = float(r.get("loss_rate") or 0.0)
            ts   = r.get("times_seen", 0)
            btyp = r.get("blindspot_type", "UNKNOWN")
            eng  = r.get("engine", "unknown")
            lines.append(
                f"{i}. {btyp} — {eng} — seen {ts}x — {lr * 100:.0f}% loss rate"
            )

        return "\n".join(lines)

    # =========================================================================
    #  TELEGRAM SENDERS
    # =========================================================================

    async def _send_telegram(self, msg: str) -> None:
        if not self._send_alert or not self._chat_ids:
            return
        for chat_id in self._chat_ids:
            try:
                await self._send_alert(chat_id, msg)
            except Exception as exc:
                logger.debug(f"[PostMortem] Telegram send error: {exc}")

    async def _send_moderate_alert(
        self,
        ctx: Dict,
        record: Dict,
        btype: BlindspotType,
        severity: int,
        times_seen: int,
    ) -> None:
        pct_against = ctx.get("price_moved_against_pct") or 0.0
        stop_mins   = ctx.get("stop_hit_minutes") or 0
        msg = (
            f"🔍 BLINDSPOT DETECTED\n"
            f"Engine:     {ctx.get('engine', 'N/A')}\n"
            f"Symbol:     {ctx.get('symbol', 'N/A')}\n"
            f"Type:       {btype.value}\n"
            f"Severity:   {severity}/10\n"
            f"Times seen: {times_seen}\n"
            f"\nWhat happened:\n"
            f"Entry: {ctx.get('direction', '?')} @ {ctx.get('entry_price', '?')}\n"
            f"BTC Bias at entry: {ctx.get('btc_bias', 'NEUTRAL')}\n"
            f"Regime: {ctx.get('regime', 'UNKNOWN')} (ADX: {ctx.get('adx', 0):.1f})\n"
            f"Quant Score: {ctx.get('quant_score', 0):.0f}/100\n"
            f"Price moved: {pct_against:.2f}% against trade\n"
            f"Stop hit in: {stop_mins:.0f} minutes\n"
            f"\nRoot cause:\n{record.get('root_cause', 'N/A')}\n"
            f"\nLearning: threshold +{_QUANT_ADD_PTS}pts next time\n"
            f"this condition is seen."
        )
        await self._send_telegram(msg)

    async def _send_critical_alert(
        self,
        ctx: Dict,
        record: Dict,
        btype: BlindspotType,
        severity: int,
        times_seen: int,
        loss_rate: float,
        fix_desc: str,
        resume_time: datetime,
        H_before: float,
        H_after: float,
    ) -> None:
        timeframe = ctx.get("timeframe", "1h")
        msg = (
            f"🚨 CRITICAL BLINDSPOT — AEON AUTO-ADJUSTING\n"
            f"Engine:    {ctx.get('engine', 'N/A')}\n"
            f"Type:      {btype.value}\n"
            f"Severity:  {severity}/10\n"
            f"Times seen: {times_seen}\n"
            f"Loss rate this condition: {loss_rate * 100:.1f}%\n"
            f"\nAuto-fix applied:\n{fix_desc}\n"
            f"\nEngine paused: {timeframe} candle\n"
            f"Resumes: {resume_time.strftime('%H:%M:%S UTC')}\n"
            f"\nH before: {H_before:.4f}\n"
            f"H after:  {H_after:.4f}\n"
            f"\nAEON has learned. This condition is now\n"
            f"flagged system-wide."
        )
        await self._send_telegram(msg)

    async def _send_block_alert(
        self,
        engine: str,
        regime: str,
        btc_bias: str,
        cached: Dict,
    ) -> None:
        msg = (
            f"🛑 PRE-TRADE BLOCK — BLINDSPOT MEMORY\n"
            f"Engine:    {engine}\n"
            f"Regime:    {regime}\n"
            f"BTC Bias:  {btc_bias}\n"
            f"Type:      {cached.get('type', 'N/A')}\n"
            f"Times seen: {cached.get('times_seen', 0)}\n"
            f"Loss rate: {float(cached.get('loss_rate', 0)) * 100:.1f}%\n"
            f"\nTrade blocked. AEON will not repeat this mistake."
        )
        await self._send_telegram(msg)

    # =========================================================================
    #  HELPERS
    # =========================================================================

    @staticmethod
    def _empty_cycle_stats() -> Dict[str, Any]:
        return {
            "blindspots":       0,
            "critical":         0,
            "auto_fixes":       0,
            "pre_trade_blocks": 0,
            "cycle_start":      datetime.now(timezone.utc),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE-LEVEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _derive_exit_price(
    pt: Dict,
    mem: Optional[Dict],
    entry_price: float,
    pnl_pct: float,
    direction: str,
) -> Optional[float]:
    """Best-effort exit price from available fields."""
    ep = pt.get("exit_price") or (mem.get("exit_price") if mem else None)
    if ep:
        return float(ep)
    if entry_price and pnl_pct is not None:
        if direction == "LONG":
            return round(entry_price * (1.0 + pnl_pct / 100.0), 6)
        else:
            return round(entry_price * (1.0 - pnl_pct / 100.0), 6)
    return None


def _infer_outcome(pt: Dict) -> str:
    """Infer outcome from paper_trade fields when trade_memory is unavailable."""
    strategy = (pt.get("strategy") or "").upper()
    if "LIQ" in strategy:
        return "LIQUIDATION"
    pnl = pt.get("realized_pnl") or pt.get("pnl_pct")
    if pnl is not None:
        return "WIN" if float(pnl) > 0 else "LOSS"
    return "LOSS"


def _mem_to_ctx(mem: Dict) -> Dict:
    """
    Convert a trade_memory document into the ctx dict format
    expected by _classify_blindspot and _describe_root_cause.
    """
    direction   = mem.get("direction", "LONG")
    entry_price = float(mem.get("entry_price") or 0.0)
    pnl_pct     = float(mem.get("pnl_pct") or 0.0)
    leverage    = int(mem.get("leverage") or 1)
    confidence  = float(mem.get("confidence") or 0.0)

    exit_price: Optional[float] = None
    if entry_price and pnl_pct is not None:
        if direction == "LONG":
            exit_price = round(entry_price * (1.0 + pnl_pct / 100.0), 6)
        else:
            exit_price = round(entry_price * (1.0 - pnl_pct / 100.0), 6)

    price_moved_against_pct: Optional[float] = None
    if entry_price and exit_price:
        if direction == "LONG":
            price_moved_against_pct = round(
                (entry_price - exit_price) / entry_price * 100, 3
            )
        else:
            price_moved_against_pct = round(
                (exit_price - entry_price) / entry_price * 100, 3
            )

    return {
        "trade_id":                str(mem.get("_id", "")),
        "paper_trade_id":          str(mem.get("_id", "")),
        "engine":                  mem.get("engine", "unknown"),
        "symbol":                  mem.get("symbol", ""),
        "direction":               direction,
        "outcome":                 mem.get("outcome", "LOSS"),
        "entry_price":             entry_price,
        "stop_loss":               float(mem.get("stop_loss") or 0.0),
        "exit_price":              exit_price,
        "pnl_pct":                 pnl_pct,
        "leverage":                leverage,
        "confidence":              confidence,
        "timeframe":               mem.get("timeframe", "1h"),
        # Entry environment
        "btc_bias":                mem.get("env_btc_bias") or "NEUTRAL",
        "regime":                  mem.get("env_regime")   or "UNKNOWN",
        "adx":                     float(mem.get("env_adx") or mem.get("adx") or 0.0),
        "quantum_H":               float(mem.get("quantum_H") or 0.0),
        "quantum_C":               float(mem.get("quantum_C") or 0.0),
        "quant_score":             confidence,
        "confluences":             len(mem.get("confluences")) if isinstance(mem.get("confluences"), list) else int(mem.get("confluences") or 0),
        # Movement analysis
        "price_moved_against_pct": price_moved_against_pct,
        "stop_hit_minutes":        mem.get("duration_min"),
        "btc_price_change_4h":     mem.get("btc_price_change_4h"),
        "btc_price_change_1h":     mem.get("btc_price_change_1h"),
        "_pt":  None,
        "_mem": mem,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON ACCESSOR
# ─────────────────────────────────────────────────────────────────────────────

def get_post_mortem(db=None) -> PostMortemEngine:
    """
    Returns the module-level singleton.
    Pass db on first call to initialise; subsequent calls without db
    return the already-initialised instance.
    """
    global _instance
    if _instance is None:
        _instance = PostMortemEngine(db=db)
    elif db is not None and _instance.db is None:
        _instance.db = db
    return _instance
