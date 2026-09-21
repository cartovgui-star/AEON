"""
oracle_entropy_gate.py — ORACLE Market-Wide Entropy Gatekeeper
==============================================================
Outermost gate in AEON's trade decision pipeline.

H_market = Σ wⱼ · Hⱼ   (Shannon entropy, normalised to [0,1])

Regimes:
  H < 0.40  → STRUCTURED   🟢  engines fully active
  0.40–0.65 → TRANSITIONAL 🟡  position size ×0.50
  > 0.65    → CHAOTIC      🔴  all engines blocked

Gate is always fail-safe: if ANY error occurs → TRANSITIONAL 🟡.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Regime thresholds ──────────────────────────────────────────────────────────

H_STRUCTURED   = 0.40   # below → STRUCTURED
H_CHAOTIC      = 0.65   # above → CHAOTIC
TRANSITIONAL_MULTIPLIER = 0.50

# ── Window weights (short-term heavier) ───────────────────────────────────────

WINDOW_WEIGHTS = {21: 0.4, 63: 0.3, 126: 0.2, 252: 0.1}
N_BINS = 20
LN_BINS = math.log(N_BINS)          # normalisation constant

# ── Singleton ─────────────────────────────────────────────────────────────────

_gate: Optional["OracleEntropyGate"] = None


def get_oracle_entropy_gate() -> Optional["OracleEntropyGate"]:
    return _gate


def init_oracle_entropy_gate(db=None, send_telegram=None, chat_ids=None) -> "OracleEntropyGate":
    global _gate
    _gate = OracleEntropyGate(db=db, send_telegram=send_telegram, chat_ids=chat_ids)
    logger.info("[ORACLE] OracleEntropyGate initialised ✓")
    return _gate


# ── Entropy math ───────────────────────────────────────────────────────────────

def _log_returns(closes: List[float]) -> List[float]:
    out = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            out.append(math.log(closes[i] / closes[i - 1]))
    return out


def _shannon_entropy_normalised(values: List[float], n_bins: int = N_BINS) -> float:
    """
    Bin `values` into n_bins histogram buckets, compute Shannon entropy,
    then normalise by ln(n_bins) → result ∈ [0, 1].
    Returns 1.0 (max entropy / chaotic) when less than 2 values.
    """
    if len(values) < 2:
        return 1.0

    lo, hi = min(values), max(values)
    if lo == hi:
        # All returns identical → perfectly ordered → H = 0
        return 0.0

    width = (hi - lo) / n_bins
    counts = [0] * n_bins
    for v in values:
        idx = int((v - lo) / width)
        idx = min(idx, n_bins - 1)
        counts[idx] += 1

    total = len(values)
    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log(p)

    return entropy / LN_BINS


def _asset_entropy(closes: List[float]) -> Tuple[float, Dict[str, float]]:
    """
    Compute per-asset multi-window entropy and weighted combination.
    Returns (H_j, {window_label: H_normalised})
    """
    log_rets = _log_returns(closes)
    window_entropies: Dict[str, float] = {}
    H_j = 0.0

    for window, weight in WINDOW_WEIGHTS.items():
        if len(log_rets) >= window:
            segment = log_rets[-window:]
        elif log_rets:
            segment = log_rets   # use all available (shorter window)
        else:
            segment = []

        h = _shannon_entropy_normalised(segment)
        label = f"H_{window}"
        window_entropies[label] = round(h, 4)
        H_j += weight * h

    return round(H_j, 4), window_entropies


# ── Main gate class ────────────────────────────────────────────────────────────

class OracleEntropyGate:
    """
    Computes H_market every hour from multi-asset OHLCV data.
    Exposes evaluate() for injection into EngineManager.submit_signal_gated().
    """

    # ── Public state (read by API/dashboard) ──────────────────────────────────

    def __init__(self, db=None, send_telegram=None, chat_ids=None) -> None:
        self.db             = db
        self.send_telegram  = send_telegram
        self.chat_ids: List = chat_ids or []

        # Current values
        self.H_market: float    = 0.50          # default to transitional
        self.H_internal: float  = 0.50          # filled by quantum state
        self.H_combined: float  = 0.50
        self.regime: str        = "TRANSITIONAL"
        self.regime_emoji: str  = "🟡"
        self.size_modifier: float = TRANSITIONAL_MULTIPLIER
        self.weights: Dict[str, float] = {}
        self.per_asset: Dict[str, Dict] = {}    # {asset: {H_j, windows}}
        self.last_updated: Optional[float] = None
        self.error_state: bool  = False

        # Regime change tracking (for alerts)
        self._last_regime: Optional[str] = None
        self._active = True

    # ── Gate interface ─────────────────────────────────────────────────────────

    def evaluate(self, symbol: str = "", engine_type: str = "") -> Tuple[bool, str]:
        """
        Called by EngineManager.submit_signal_gated() for every signal.

        Returns (allowed: bool, reason: str)
        - STRUCTURED   → (True,  "ORACLE: STRUCTURED H={value}")
        - TRANSITIONAL → (True,  "ORACLE: TRANSITIONAL H={value} [size×0.50]")
        - CHAOTIC      → (False, "ORACLE: CHAOTIC H={value} — engines standing down")
        """
        h = self.H_market
        regime = self.regime

        if regime == "STRUCTURED":
            return True, f"ORACLE: STRUCTURED H={h:.3f}"
        elif regime == "TRANSITIONAL":
            return True, f"ORACLE: TRANSITIONAL H={h:.3f} [size×{TRANSITIONAL_MULTIPLIER}]"
        else:  # CHAOTIC
            return False, f"ORACLE: CHAOTIC H={h:.3f} — engines standing down"

    def get_size_modifier(self) -> float:
        """
        Position size modifier based on inverse entropy.
        size_modifier = 1 - H_market
        In TRANSITIONAL regime, cap at 0.50.
        """
        return self.size_modifier

    # ── Entropy computation ────────────────────────────────────────────────────

    async def _refresh(self) -> None:
        """Fetch fresh OHLCV data, recompute H_market, update state & DB."""
        from market_data_fetcher import fetch_ohlcv_all, fetch_market_cap_weights

        try:
            # Fetch data
            candles_map, weights = await asyncio.gather(
                fetch_ohlcv_all(limit=252),
                fetch_market_cap_weights(),
            )

            if not candles_map:
                logger.warning("[ORACLE] No OHLCV data returned — keeping last regime")
                self.error_state = True
                return

            self.weights = weights

            # Per-asset entropy
            per_asset: Dict[str, Dict] = {}
            H_market = 0.0
            total_weight = 0.0

            for asset in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
                if asset not in candles_map:
                    logger.warning(f"[ORACLE] No data for {asset} — skipping")
                    continue

                closes = [c[4] for c in candles_map[asset] if c[4] is not None]
                if len(closes) < 22:
                    logger.warning(f"[ORACLE] {asset}: only {len(closes)} closes — skipping")
                    continue

                H_j, windows = _asset_entropy(closes)
                w = weights.get(asset, 0.10)
                per_asset[asset] = {
                    "H_j": H_j,
                    "weight": round(w, 4),
                    "windows": windows,
                    "candles": len(closes),
                }
                H_market += w * H_j
                total_weight += w

            if total_weight <= 0:
                logger.error("[ORACLE] No assets computed — defaulting to TRANSITIONAL")
                self.error_state = True
                return

            # Renormalise if not all assets available
            if abs(total_weight - 1.0) > 0.01:
                H_market /= total_weight

            H_market = round(H_market, 4)
            self.per_asset = per_asset
            self.error_state = False

            # Classify regime
            regime, emoji = self._classify(H_market)

            # Combined score (with internal quantum entropy)
            H_combined = round(0.6 * H_market + 0.4 * self.H_internal, 4)

            # Position modifier: inverse entropy, capped by regime
            if regime == "CHAOTIC":
                size_mod = 0.0
            elif regime == "TRANSITIONAL":
                size_mod = TRANSITIONAL_MULTIPLIER
            else:
                size_mod = round(max(0.1, 1.0 - H_market), 4)

            # Detect regime change
            regime_changed = (regime != self._last_regime) and (self._last_regime is not None)

            # Update state
            self.H_market       = H_market
            self.H_combined     = H_combined
            self.regime         = regime
            self.regime_emoji   = emoji
            self.size_modifier  = size_mod
            self.last_updated   = time.time()

            logger.info(
                f"[ORACLE] H_market={H_market:.4f} | H_combined={H_combined:.4f} "
                f"| regime={emoji} {regime} | size_mod={size_mod}"
            )

            # Persist to MongoDB
            await self._persist(H_market, H_combined, regime, size_mod, per_asset, weights)

            # Telegram alert on regime change
            if regime_changed:
                await self._send_regime_alert(regime, emoji, H_market)

            self._last_regime = regime

        except Exception as exc:
            logger.exception(f"[ORACLE] _refresh() error: {exc}")
            self.error_state = True
            # Fail-safe: keep TRANSITIONAL

    def _classify(self, H: float) -> Tuple[str, str]:
        if H < H_STRUCTURED:
            return "STRUCTURED", "🟢"
        elif H < H_CHAOTIC:
            return "TRANSITIONAL", "🟡"
        else:
            return "CHAOTIC", "🔴"

    # ── MongoDB ────────────────────────────────────────────────────────────────

    async def _persist(
        self,
        H_market: float,
        H_combined: float,
        regime: str,
        size_mod: float,
        per_asset: Dict,
        weights: Dict,
    ) -> None:
        if self.db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            doc = {
                "timestamp":    now,
                "H_market":     H_market,
                "H_combined":   H_combined,
                "H_internal":   self.H_internal,
                "regime":       regime,
                "size_modifier": size_mod,
                "per_asset":    per_asset,
                "weights":      weights,
            }
            # Upsert current regime doc (single live record)
            await self.db["current_market_regime"].replace_one(
                {"_id": "live"},
                {"_id": "live", **doc},
                upsert=True,
            )
            # Append to history
            await self.db["market_entropy_history"].insert_one(doc)
        except Exception as exc:
            logger.warning(f"[ORACLE] MongoDB persist failed: {exc}")

    # ── Telegram alerts ────────────────────────────────────────────────────────

    async def _send_regime_alert(self, regime: str, emoji: str, H: float) -> None:
        if not self.send_telegram or not self.chat_ids:
            return

        messages = {
            "STRUCTURED":   f"🟢 *ORACLE: Market structured.*\nH = `{H:.4f}`\nEngines fully active.",
            "TRANSITIONAL": f"🟡 *ORACLE: Transitional regime.*\nH = `{H:.4f}`\nPosition size reduced 50%.",
            "CHAOTIC":      f"🔴 *ORACLE: Market chaotic.*\nH = `{H:.4f}`\nAll engines standing down.",
        }
        text = messages.get(regime, f"{emoji} ORACLE: {regime} H={H:.4f}")

        for chat_id in self.chat_ids:
            try:
                await self.send_telegram(chat_id, text, parse_mode="Markdown")
            except Exception as exc:
                logger.warning(f"[ORACLE] Telegram alert failed for {chat_id}: {exc}")

    # ── API helpers ────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Snapshot for the /api/oracle-entropy/status endpoint."""
        return {
            "H_market":      self.H_market,
            "H_combined":    self.H_combined,
            "H_internal":    self.H_internal,
            "regime":        self.regime,
            "regime_emoji":  self.regime_emoji,
            "size_modifier": self.size_modifier,
            "per_asset":     self.per_asset,
            "weights":       self.weights,
            "last_updated":  self.last_updated,
            "error_state":   self.error_state,
            "thresholds": {
                "structured":   H_STRUCTURED,
                "chaotic":      H_CHAOTIC,
            },
        }

    def set_internal_entropy(self, H_internal: float) -> None:
        """Called by quantum state engine to feed internal entropy."""
        self.H_internal = max(0.0, min(1.0, H_internal))
        self.H_combined = round(0.6 * self.H_market + 0.4 * self.H_internal, 4)

    # ── Background loop ────────────────────────────────────────────────────────

    async def run_loop(self, interval_seconds: int = 3600) -> None:
        """
        Runs every `interval_seconds` (default 1h) on each candle close.
        Always does an initial run immediately on startup.
        """
        logger.info(f"[ORACLE] Entropy gate loop starting — interval {interval_seconds}s")
        while self._active:
            try:
                await self._refresh()
                # Heartbeat for health monitor (immediately after refresh)
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("oracle_entropy_gate")
                except Exception:
                    pass
            except Exception as exc:
                logger.error(f"[ORACLE] run_loop iteration error: {exc}")
            # Sleep in 60s chunks so heartbeat can be sent periodically
            elapsed = 0
            while self._active and elapsed < interval_seconds:
                await asyncio.sleep(60)
                elapsed += 60
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("oracle_entropy_gate")
                except Exception:
                    pass

    def stop(self) -> None:
        self._active = False
