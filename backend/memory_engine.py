"""
=============================================================
  memory_engine.py — AEON Memory Engine
=============================================================

  Position in the identity: A(t) = Ω(|Ψ⟩, E, M, L)

  This module computes M — the compounding intelligence.

  M(t) = M(t−1) ∪ {(Eₜ, aₜ, rₜ)}

  Every closed trade becomes a triplet:
    Eₜ — environment at entry  (regime, ADX, BTC bias, time, |Ψ⟩ snapshot)
    aₜ — action taken          (symbol, engine, direction, confidence, leverage)
    rₜ — reward received       (PnL%, outcome, duration, MAE)

  retrieve(pattern, n=10) returns the n most similar historical setups
  ranked by cosine similarity on the feature vector, with full outcome data.
  AEON does not repeat mistakes it has seen before.

  Feature vector (9 dimensions):
    [regime, adx_norm, confidence_norm, rsi_norm, vol_ratio_norm,
     direction, leverage_norm, hour_sin, hour_cos]

  Similarity: cosine similarity — pure Python, no ML dependencies.

  Operation:
    - Background loop polls paper_trades every 5 minutes for new closures
    - Converts each closed trade to (E,a,r) and stores to trade_memories
    - retrieve() loads candidates from MongoDB and ranks by cosine similarity

  MongoDB collections:
    trade_memories  — (E,a,r) triplets with embedded feature vectors
    memory_meta     — processing cursor (last seen close timestamp)
=============================================================
"""

import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

POLL_INTERVAL      = 300     # seconds between paper_trades scans
FEATURE_DIM        = 9       # length of the similarity feature vector
TOP_N_DEFAULT      = 10      # default number of similar memories returned
MEMORIES_HARD_CAP  = 50_000  # prune oldest when exceeded
OPEN_SCAN_LIMIT    = 500     # max open trades to track per cycle

# Engine list for stable numeric encoding in the feature vector
ENGINE_ORDER = [
    "elite_strategy",
    "yolo_engine",
    "vwap_scalper",
    "autonomous_trader",
    "free_will",
    "day_trader",
    "dual_engine",
]


# ─── Feature vector ───────────────────────────────────────────────────────────

def _build_feature_vector(entry: Dict) -> List[float]:
    """
    Convert a trade entry (E,a combined dict) to the 9-dimensional feature vector.

    All dimensions normalized to ≈ [−1, 1] or [0, 1] so no single feature
    dominates the cosine similarity calculation.

    Missing values get neutral defaults — the vector is always length-9
    so similarity is always computable.
    """
    regime      = 1.0 if entry.get("regime") == "trending" else 0.0
    adx         = min(entry.get("adx", 0.0), 100.0) / 100.0
    confidence  = entry.get("confidence", 50.0) / 100.0
    rsi         = entry.get("rsi", 50.0) / 100.0
    vol_ratio   = min(entry.get("vol_ratio", 1.0), 3.0) / 3.0
    direction   = 1.0 if str(entry.get("direction", "")).upper() == "LONG" else -1.0
    leverage    = min(entry.get("leverage", 25), 150) / 150.0
    hour        = int(entry.get("hour_of_day", 12))
    hour_sin    = math.sin(2 * math.pi * hour / 24)
    hour_cos    = math.cos(2 * math.pi * hour / 24)

    return [regime, adx, confidence, rsi, vol_ratio, direction, leverage, hour_sin, hour_cos]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Pure-Python cosine similarity.
    Returns value in [−1, 1]. Identical vectors → 1. Orthogonal → 0.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot   = sum(a[i] * b[i] for i in range(len(a)))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ─── Memory engine ────────────────────────────────────────────────────────────

class MemoryEngine:
    """
    AEON's long-term memory.

    Stores every closed trade as an (Eₜ, aₜ, rₜ) triplet.
    Retrieves similar historical setups on demand.
    """

    def __init__(self, db=None):
        self.db = db
        self.market_intel  = None
        self._quantum_ref  = None   # reference to AEONQuantumState singleton

        # In-memory count of stored memories (refreshed on startup)
        self._memory_count: int = 0

    def set_dependencies(self, market_intel=None, quantum_state=None):
        self.market_intel = market_intel
        self._quantum_ref = quantum_state

    # ── Environment snapshot ─────────────────────────────────────────────────

    async def _get_environment_snapshot(self) -> Dict:
        """
        Capture Eₜ — the state of the world at this moment.
        Called once per trade closure during processing.
        """
        now = datetime.now(timezone.utc)
        env = {
            "timestamp": now.isoformat(),
            "hour_of_day": now.hour,
            "day_of_week": now.weekday(),   # 0=Monday
            "regime": "unknown",
            "adx": 0.0,
            "btc_bias": "neutral",
        }

        # ADX + BTC bias from market_intel
        if self.market_intel:
            try:
                ta = await self.market_intel.get_technical_analysis("BTC/USDT", "1h")
                env["adx"] = float(ta.get("indicators", {}).get("adx", 0.0)) if ta else 0.0
                env["regime"] = "trending" if env["adx"] >= 20 else "ranging"
            except Exception:
                pass
            try:
                scan = await self.market_intel.get_full_market_scan("BTC/USDT")
                env["btc_bias"] = (
                    (scan.get("market_structure", {}) or {}).get("bias", "neutral")
                    if scan else "neutral"
                )
            except Exception:
                pass

        # Quantum state snapshot
        if self._quantum_ref is not None:
            qs = self._quantum_ref.get_state()
            if qs:
                env["quantum_H"]    = qs.get("H", 0.0)
                env["quantum_C"]    = qs.get("C", 0.0)
                env["quantum_S"]    = qs.get("S_norm", 0.0)
                env["quantum_size"] = qs.get("position_multiplier", 0.0)

        return env

    # ── Trade processing ─────────────────────────────────────────────────────

    async def _get_processing_cursor(self) -> Optional[datetime]:
        """Return the timestamp of the last paper_trade we processed."""
        if self.db is None:
            return None
        try:
            meta = await self.db["memory_meta"].find_one({"_id": "cursor"})
            if meta and meta.get("last_processed_at"):
                val = meta["last_processed_at"]
                # Stored value may be a string if written by an older version — normalise to datetime
                if isinstance(val, str):
                    val = datetime.fromisoformat(val.replace("Z", "+00:00"))
                return val
        except Exception:
            pass
        return None

    async def _set_processing_cursor(self, ts: datetime):
        """Advance the cursor to ts so we never reprocess the same trade."""
        if self.db is None:
            return
        try:
            await self.db["memory_meta"].update_one(
                {"_id": "cursor"},
                {"$set": {"last_processed_at": ts}},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[M] Cursor update failed: {e}")

    def _extract_signal_fields(self, trade: Dict) -> Dict:
        """
        Pull aₜ fields out of a paper_trade document.
        Handles the nested signal_data structure used by all engines.
        """
        sd = trade.get("signal_data") or {}

        def first(*keys, default=None):
            for k in keys:
                v = trade.get(k) or sd.get(k)
                if v is not None:
                    return v
            return default

        direction   = str(first("direction") or "").upper()
        confidence  = float(first("confidence") or 50.0)
        leverage    = int(first("leverage") or 25)
        engine      = str(first("engine", "strategy") or "unknown").lower()
        timeframe   = str(first("timeframe") or "unknown")
        confluences = first("confirmations", "confluences") or []

        # RSI and vol_ratio may be nested inside indicators dict
        indicators = sd.get("indicators") or {}
        rsi      = float(indicators.get("rsi") or first("rsi") or 50.0)
        vol_ratio = float(indicators.get("vol_ratio") or first("vol_ratio") or 1.0)
        adx       = float(indicators.get("adx") or first("adx") or 0.0)

        return {
            "symbol":      trade.get("symbol", "unknown"),
            "engine":      engine,
            "direction":   direction,
            "confidence":  confidence,
            "leverage":    leverage,
            "entry_price": float(trade.get("entry_price") or 0.0),
            "stop_loss":   float(trade.get("stop_loss") or 0.0),
            "take_profit": float(trade.get("take_profit") or 0.0),
            "timeframe":   timeframe,
            "confluences": confluences if isinstance(confluences, list) else [],
            "rsi":         rsi,
            "vol_ratio":   vol_ratio,
            "adx":         adx,
        }

    def _extract_reward(self, trade: Dict) -> Dict:
        """
        Pull rₜ out of a paper_trade document.
        PnL resolution follows the same normalization as Session 15 learning fix.
        """
        pnl_pct = (
            trade.get("unrealized_pnl_pct")
            or trade.get("pnl_pct")
            or (
                trade["realized_pnl"] / trade["margin"] * 100
                if trade.get("realized_pnl") and trade.get("margin")
                else 0.0
            )
        )
        pnl_usd = float(trade.get("realized_pnl") or trade.get("pnl_usd") or 0.0)

        # Duration in minutes
        entry_ts = trade.get("opened_at") or trade.get("created_at")
        close_ts = trade.get("closed_at")
        duration_min = 0.0
        if entry_ts and close_ts:
            try:
                if isinstance(entry_ts, str):
                    entry_ts = datetime.fromisoformat(entry_ts.replace("Z", "+00:00"))
                if isinstance(close_ts, str):
                    close_ts = datetime.fromisoformat(close_ts.replace("Z", "+00:00"))
                duration_min = (close_ts - entry_ts).total_seconds() / 60
            except Exception:
                pass

        # Outcome label
        status = str(trade.get("status", "")).lower()
        if status == "liquidated" or pnl_pct < -90:
            outcome = "LIQUIDATION"
        elif pnl_pct > 0:
            outcome = "WIN"
        else:
            outcome = "LOSS"

        return {
            "pnl_pct":       round(float(pnl_pct), 4),
            "pnl_usd":       round(pnl_usd, 4),
            "outcome":       outcome,
            "duration_min":  round(duration_min, 1),
            "timestamp_close": str(close_ts) if close_ts else "",
        }

    async def _process_new_closures(self):
        """
        Find paper_trades closed since the last cursor.
        Convert each to an (E,a,r) triplet and store.
        """
        if self.db is None:
            return

        cursor_ts = await self._get_processing_cursor()
        query: Dict = {"status": "closed"}
        if cursor_ts:
            query["closed_at"] = {"$gt": cursor_ts}

        try:
            trades = await self.db["paper_trades"].find(
                query,
                sort=[("closed_at", 1)],
                limit=200,
            ).to_list(length=200)
        except Exception as e:
            logger.error(f"[M] paper_trades query failed: {e}")
            return

        if not trades:
            return

        # Fetch environment snapshot once for this batch
        env = await self._get_environment_snapshot()
        new_cursor = cursor_ts
        stored = 0

        for trade in trades:
            try:
                action  = self._extract_signal_fields(trade)
                reward  = self._extract_reward(trade)

                # Liquidation-specific tagging
                liq_flag = trade.get("close_reason") == "liquidation"
                liq_extras: Dict = {}
                if liq_flag:
                    liq_price  = trade.get("exit_price")
                    stop_loss  = trade.get("stop_loss")
                    entry_price = float(trade.get("entry_price") or 1.0)
                    liq_sl_gap_pct = None
                    if liq_price is not None and stop_loss is not None:
                        liq_sl_gap_pct = round(
                            abs(float(liq_price) - float(stop_loss)) / entry_price * 100, 3
                        )
                    liq_extras = {
                        "liquidation_flag":  True,
                        "liquidation_price": liq_price,
                        "sl_price_at_entry": stop_loss,
                        "liq_sl_gap_pct":    liq_sl_gap_pct,
                    }

                # Try to update an existing OPEN record first
                updated = await self._close_open_memory_record(trade, reward)

                if not updated:
                    # No OPEN record exists — insert a fresh CLOSED record
                    memory_doc = {
                        **{f"env_{k}": v for k, v in env.items()},
                        **action,
                        **reward,
                        **liq_extras,
                        "regime":    env.get("regime", "unknown"),
                        "symbol":    action["symbol"],
                        "engine":    action["engine"],
                        "direction": action["direction"],
                        "outcome":   reward["outcome"],
                        "status":    "CLOSED",
                        "paper_trade_id": str(trade.get("_id", "")),
                        "stored_at": datetime.now(timezone.utc),
                        "exit_price":   trade.get("exit_price"),
                        "closed_at":    trade.get("closed_at"),
                        "close_reason": trade.get("close_reason"),
                    }
                    memory_doc["feature_vector"] = _build_feature_vector({**env, **action})
                    await self._store_memory(memory_doc)

                stored += 1

                # ORIA: update per-engine per-symbol edge stats
                try:
                    from oria_layer import get_edge_filter
                    _ef = get_edge_filter()
                    if _ef is not None:
                        await _ef.update_edge_stats(
                            engine=action.get("engine", "unknown"),
                            symbol=action.get("symbol", "unknown"),
                            outcome=reward.get("outcome", ""),
                            pnl_pct=float(reward.get("pnl_pct", 0.0)),
                            confidence=float(action.get("confidence", 50.0)),
                        )
                except Exception as _oria_edge_err:
                    logger.debug(f"[M/ORIA] edge_stats update skipped: {_oria_edge_err}")

                # Advance cursor
                closed_at = trade.get("closed_at")
                if closed_at and (new_cursor is None or closed_at > new_cursor):
                    new_cursor = closed_at

            except Exception as e:
                logger.debug(f"[M] Failed to process trade {trade.get('_id')}: {e}")

        if stored:
            logger.info(f"[M] Stored {stored} new (E,a,r) triplets from paper_trades.")
            self._memory_count += stored

        if new_cursor and new_cursor != cursor_ts:
            await self._set_processing_cursor(new_cursor)

        # Enforce memory cap
        if self._memory_count > MEMORIES_HARD_CAP:
            await self._prune_oldest()

    async def _store_memory(self, doc: Dict):
        """Write one (E,a,r) document to trade_memories."""
        if self.db is None:
            return
        try:
            await self.db["trade_memories"].insert_one(doc)
        except Exception as e:
            logger.debug(f"[M] Insert failed: {e}")

    async def _prune_oldest(self):
        """Delete oldest memories when count exceeds MEMORIES_HARD_CAP."""
        if self.db is None:
            return
        try:
            excess = self._memory_count - MEMORIES_HARD_CAP
            if excess <= 0:
                return
            oldest = await self.db["trade_memories"].find(
                {}, sort=[("stored_at", 1)], limit=excess
            ).to_list(length=excess)
            ids = [d["_id"] for d in oldest]
            if ids:
                await self.db["trade_memories"].delete_many({"_id": {"$in": ids}})
                self._memory_count -= len(ids)
                logger.info(f"[M] Pruned {len(ids)} oldest memories (cap={MEMORIES_HARD_CAP}).")
        except Exception as e:
            logger.debug(f"[M] Prune failed: {e}")

    # ── Open position tracking ────────────────────────────────────────────────

    async def _process_open_positions(self):
        """
        Poll paper_trades for OPEN trades not yet in trade_memories.
        Writes an OPEN (E,a) record immediately so AEON tracks live exposure.
        Omega cycle reads these to detect concentration risk in real time.
        """
        if self.db is None:
            return
        try:
            open_trades = await self.db["paper_trades"].find(
                {"status": "open"},
            ).to_list(length=OPEN_SCAN_LIMIT)
        except Exception as e:
            logger.error(f"[M] Open positions query failed: {e}")
            return

        if not open_trades:
            return

        # Build set of paper_trade_ids already recorded as OPEN
        try:
            existing = await self.db["trade_memories"].find(
                {"status": "OPEN"},
                {"paper_trade_id": 1},
            ).to_list(length=OPEN_SCAN_LIMIT)
            existing_ids = {doc["paper_trade_id"] for doc in existing}
        except Exception:
            existing_ids = set()

        env = await self._get_environment_snapshot()
        written = 0

        for trade in open_trades:
            trade_id = str(trade.get("_id", ""))
            if trade_id in existing_ids:
                continue
            try:
                action = self._extract_signal_fields(trade)
                memory_doc = {
                    **{f"env_{k}": v for k, v in env.items()},
                    **action,
                    "regime":         env.get("regime", "unknown"),
                    "symbol":         action["symbol"],
                    "engine":         action["engine"],
                    "direction":      action["direction"],
                    "outcome":        None,
                    "status":         "OPEN",
                    "paper_trade_id": trade_id,
                    "stored_at":      datetime.now(timezone.utc),
                    "opened_at":      trade.get("opened_at"),
                    "feature_vector": _build_feature_vector({**env, **action}),
                }
                await self.db["trade_memories"].insert_one(memory_doc)
                written += 1
            except Exception as e:
                logger.debug(f"[M] Failed to write open memory for {trade.get('_id')}: {e}")

        if written:
            logger.info(f"[M] Recorded {written} new open positions to trade_memories.")
            self._memory_count += written

    async def _close_open_memory_record(self, trade: Dict, reward: Dict) -> bool:
        """
        Find an existing OPEN memory record for this paper_trade and update it to CLOSED.
        Adds liquidation flag + liq_price vs SL gap when close_reason == 'liquidation'.
        Returns True if an OPEN record was found and updated, False otherwise.
        """
        if self.db is None:
            return False

        trade_id = str(trade.get("_id", ""))
        if not trade_id:
            return False

        liq_flag = trade.get("close_reason") == "liquidation"
        liq_price = trade.get("exit_price") if liq_flag else None
        stop_loss = trade.get("stop_loss")
        entry_price = float(trade.get("entry_price") or 1.0)
        liq_sl_gap_pct = None
        if liq_flag and liq_price is not None and stop_loss is not None:
            liq_sl_gap_pct = round(
                abs(float(liq_price) - float(stop_loss)) / entry_price * 100, 3
            )

        update_fields = {
            **reward,
            "status":       "CLOSED",
            "outcome":      reward.get("outcome"),
            "exit_price":   trade.get("exit_price"),
            "closed_at":    trade.get("closed_at"),
            "close_reason": trade.get("close_reason"),
        }
        if liq_flag:
            update_fields["liquidation_flag"] = True
            update_fields["liquidation_price"] = liq_price
            update_fields["sl_price_at_entry"] = stop_loss
            update_fields["liq_sl_gap_pct"] = liq_sl_gap_pct

        try:
            result = await self.db["trade_memories"].update_one(
                {"paper_trade_id": trade_id, "status": "OPEN"},
                {"$set": update_fields},
            )
            return result.matched_count > 0
        except Exception as e:
            logger.debug(f"[M] Close update failed for {trade_id}: {e}")
            return False

    # ── Public: open exposure summary ─────────────────────────────────────────

    async def get_open_exposure(self) -> Dict:
        """
        Returns current open position summary from trade_memories.
        Called by Omega cycle for real-time concentration risk detection.

        Returns:
            total_open       — number of currently open positions
            by_pair          — {symbol: count} for each open pair
            long_count       — number of LONG positions open
            short_count      — number of SHORT positions open
            long_pct         — % of open positions that are LONG
            concentrated_pairs — pairs with 3+ simultaneous open positions
            bias_alert       — True if LONG > 75% or LONG < 25% (directional bias)
        """
        if self.db is None:
            return {}
        try:
            open_records = await self.db["trade_memories"].find(
                {"status": "OPEN"},
                {"symbol": 1, "direction": 1, "engine": 1, "leverage": 1},
            ).to_list(length=OPEN_SCAN_LIMIT)

            by_pair: Dict = {}
            long_count = 0
            short_count = 0
            for r in open_records:
                sym = r.get("symbol", "UNKNOWN")
                by_pair[sym] = by_pair.get(sym, 0) + 1
                if r.get("direction") == "LONG":
                    long_count += 1
                else:
                    short_count += 1

            total = len(open_records)
            long_pct = round(long_count / total * 100, 1) if total > 0 else 0.0

            return {
                "total_open":         total,
                "by_pair":            by_pair,
                "long_count":         long_count,
                "short_count":        short_count,
                "long_pct":           long_pct,
                "concentrated_pairs": [p for p, c in by_pair.items() if c >= 3],
                "bias_alert":         long_pct > 75 or long_pct < 25,
            }
        except Exception as e:
            logger.error(f"[M] get_open_exposure failed: {e}")
            return {}

    # ── Public: store a signal event ─────────────────────────────────────────

    async def store_signal(self, signal: Dict, engine: str, accepted: bool):
        """
        Store a signal firing event (whether accepted or rejected by engine_manager).
        Written to the `signals` MongoDB collection.
        This is separate from the (E,a,r) triplets in trade_memories.
        """
        if self.db is None:
            return
        try:
            doc = {
                "timestamp":  datetime.now(timezone.utc),
                "engine":     engine,
                "symbol":     signal.get("symbol"),
                "direction":  signal.get("direction"),
                "confidence": signal.get("confidence"),
                "leverage":   signal.get("leverage"),
                "accepted":   accepted,
                "reason":     signal.get("reason", ""),
                "confluences": signal.get("confluences", 0),
            }
            await self.db["signals"].insert_one(doc)
        except Exception as e:
            logger.debug(f"[M] Signal store failed: {e}")

    # ── Public: retrieve ──────────────────────────────────────────────────────

    async def retrieve(self, pattern: Dict, n: int = TOP_N_DEFAULT,
                       filter_by: Optional[Dict] = None) -> List[Dict]:
        """
        Return the n most similar historical (E,a,r) triplets to the given pattern.

        pattern — dict with any subset of:
            regime, adx, confidence, rsi, vol_ratio, direction, leverage,
            hour_of_day, symbol (used for pre-filter only, not in feature vector)

        filter_by — optional MongoDB filter applied BEFORE similarity ranking:
            e.g. {"outcome": "WIN"}, {"engine": "elite_strategy"}, {"symbol": "BTC/USDT"}

        Returns list of memory docs sorted by cosine_similarity descending.
        Each doc includes all (E,a,r) fields plus "similarity" score.

        AEON does not repeat mistakes it has seen before.
        This is how it knows.
        """
        if self.db is None:
            return []

        query_vec = _build_feature_vector(pattern)

        # Build MongoDB filter
        db_filter: Dict = {}
        if filter_by:
            db_filter.update(filter_by)
        # Pre-filter by symbol if provided (optional — reduces candidate set)
        if pattern.get("symbol") and "symbol" not in db_filter:
            db_filter["symbol"] = pattern["symbol"]

        try:
            # Load candidates — limit to 5000 for performance
            candidates = await self.db["trade_memories"].find(
                db_filter,
                sort=[("stored_at", -1)],
                limit=5000,
            ).to_list(length=5000)
        except Exception as e:
            logger.error(f"[M] retrieve() query failed: {e}")
            return []

        if not candidates:
            return []

        # Rank by cosine similarity
        scored: List[tuple] = []
        for doc in candidates:
            fv = doc.get("feature_vector")
            if not fv or len(fv) != FEATURE_DIM:
                continue
            sim = _cosine_similarity(query_vec, fv)
            scored.append((sim, doc))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, doc in scored[:n]:
            out = {k: v for k, v in doc.items() if k != "_id"}
            out["similarity"] = round(sim, 4)
            results.append(out)

        return results

    async def retrieve_for_signal(self, signal: Dict, n: int = TOP_N_DEFAULT) -> List[Dict]:
        """
        Convenience wrapper — retrieve similar memories for a live signal.
        Automatically extracts the pattern fields from the signal dict.
        """
        pattern = {
            "direction":   signal.get("direction", ""),
            "confidence":  signal.get("confidence", 50.0),
            "leverage":    signal.get("leverage", 25),
            "symbol":      signal.get("symbol", ""),
            "adx":         (signal.get("indicators") or {}).get("adx", 0.0),
            "rsi":         (signal.get("indicators") or {}).get("rsi", 50.0),
            "vol_ratio":   (signal.get("indicators") or {}).get("vol_ratio", 1.0),
            "hour_of_day": datetime.now(timezone.utc).hour,
            "regime":      "trending" if (signal.get("indicators") or {}).get("adx", 0) >= 20
                           else "ranging",
        }
        return await self.retrieve(pattern, n=n)

    # ── Public: summary stats ─────────────────────────────────────────────────

    async def get_summary(self, symbol: Optional[str] = None,
                          engine: Optional[str] = None,
                          last_n: int = 100) -> Dict:
        """
        Aggregate win rate, average PnL, best/worst setups from memory.
        Optionally scoped to a symbol or engine.
        """
        if self.db is None:
            return {"error": "no db"}

        db_filter: Dict = {}
        if symbol:
            db_filter["symbol"] = symbol
        if engine:
            db_filter["engine"] = {"$regex": engine, "$options": "i"}

        try:
            docs = await self.db["trade_memories"].find(
                db_filter,
                sort=[("stored_at", -1)],
                limit=last_n,
            ).to_list(length=last_n)
        except Exception as e:
            return {"error": str(e)}

        if not docs:
            return {"total": 0, "symbol": symbol, "engine": engine}

        wins   = [d for d in docs if d.get("outcome") == "WIN"]
        losses = [d for d in docs if d.get("outcome") == "LOSS"]
        liqs   = [d for d in docs if d.get("outcome") == "LIQUIDATION"]
        total  = len(docs)

        pnls = [d.get("pnl_pct", 0.0) for d in docs]
        avg_pnl = sum(pnls) / total if total else 0.0

        best  = max(docs, key=lambda d: d.get("pnl_pct", 0.0))
        worst = min(docs, key=lambda d: d.get("pnl_pct", 0.0))

        # Win rate by regime
        trending = [d for d in docs if d.get("regime") == "trending"]
        ranging  = [d for d in docs if d.get("regime") == "ranging"]
        wr_trending = (
            sum(1 for d in trending if d.get("outcome") == "WIN") / len(trending)
            if trending else None
        )
        wr_ranging = (
            sum(1 for d in ranging if d.get("outcome") == "WIN") / len(ranging)
            if ranging else None
        )

        return {
            "total":        total,
            "wins":         len(wins),
            "losses":       len(losses),
            "liquidations": len(liqs),
            "win_rate":     round(len(wins) / total, 4) if total else 0.0,
            "avg_pnl_pct":  round(avg_pnl, 4),
            "best": {
                "symbol":    best.get("symbol"),
                "pnl_pct":   best.get("pnl_pct"),
                "engine":    best.get("engine"),
                "direction": best.get("direction"),
            },
            "worst": {
                "symbol":    worst.get("symbol"),
                "pnl_pct":   worst.get("pnl_pct"),
                "engine":    worst.get("engine"),
                "direction": worst.get("direction"),
            },
            "win_rate_trending": round(wr_trending, 4) if wr_trending is not None else None,
            "win_rate_ranging":  round(wr_ranging, 4) if wr_ranging is not None else None,
            "symbol": symbol,
            "engine": engine,
            "last_n": last_n,
        }

    async def get_memory_count(self) -> int:
        """Return total number of (E,a,r) entries stored."""
        if self.db is None:
            return 0
        try:
            return await self.db["trade_memories"].count_documents({})
        except Exception:
            return self._memory_count

    # ── Background loop ───────────────────────────────────────────────────────

    async def run_loop(self, interval: int = POLL_INTERVAL):
        """
        Poll paper_trades every `interval` seconds for newly closed trades.
        Converts each to (E,a,r) and stores to trade_memories.
        """
        # Sync memory count on startup
        if self.db is not None:
            try:
                self._memory_count = await self.db["trade_memories"].count_documents({})
                logger.info(
                    "[M] Memory engine started — %d memories in store. "
                    "Polling every %ds.",
                    self._memory_count, interval,
                )
            except Exception:
                logger.info("[M] Memory engine started. Polling every %ds.", interval)
        else:
            logger.warning("[M] Memory engine started with no DB — memories will not persist.")

        while True:
            try:
                await self._process_open_positions()   # write OPEN records first
                await self._process_new_closures()     # then close / update them
            except Exception as e:
                logger.error(f"[M] Loop error: {e}", exc_info=True)
            await asyncio.sleep(interval)


# ─── Singleton ────────────────────────────────────────────────────────────────

_memory_engine: Optional[MemoryEngine] = None


def init_memory_engine(db=None) -> MemoryEngine:
    """Initialise the global memory engine. Call once from server.py."""
    global _memory_engine
    _memory_engine = MemoryEngine(db)
    return _memory_engine


def get_memory_engine() -> Optional[MemoryEngine]:
    """Return the live singleton."""
    return _memory_engine
