#!/usr/bin/env python3
"""
AEON 7-ENGINE UNIFIED SYSTEM
Complete self-contained engine management with validation, stats, and risk controls.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
from enum import Enum
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)

# ── ORIA layer (optional — graceful degradation if file missing) ──────────────
try:
    from oria_layer import (
        init_oria, get_signal_aggregator, get_edge_filter, get_stress_monitor,
        apply_stress_sizing, apply_stress_leverage, apply_signal_freshness,
    )
    _ORIA_AVAILABLE = True
except ImportError:
    _ORIA_AVAILABLE = False
    logger.warning("[ORIA] oria_layer.py not found — ORIA features disabled")


class EngineType(Enum):
    """All 9 independent engines"""
    AUTONOMOUS_TRADER_V2   = "autonomous_trader_v2"
    FREE_WILL_V2           = "free_will_v2"
    DUAL_ENGINE            = "dual_engine"
    YOLO_ENGINE            = "yolo_engine"
    VWAP_SCALPER           = "vwap_scalper"
    ELITE_STRATEGY         = "elite_strategy"
    DAY_TRADER             = "day_trader"
    VOLUME_PROFILE         = "volume_profile"
    INSTITUTIONAL_SCALPER  = "institutional_scalper"


class TradeStatus(Enum):
    """Trade lifecycle states"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class EngineConfig:
    """Configuration for each engine"""
    engine_type: EngineType
    min_confidence: float
    min_confluences: int
    max_leverage: int
    max_position_size: float
    max_concurrent_trades: int
    max_daily_trades: int
    max_loss_per_day: float
    use_blacklist: bool = True
    use_cooldown: bool = True
    cooldown_hours: int = 4
    enable_scaling: bool = True
    description: str = ""
    risk_profile: str = "balanced"


# ============================================================================
# ENGINE CONFIGURATIONS - ALL 7 ENGINES
# ============================================================================

ENGINE_CONFIGS = {
    EngineType.AUTONOMOUS_TRADER_V2: EngineConfig(
        engine_type=EngineType.AUTONOMOUS_TRADER_V2,
        min_confidence=80.0,
        min_confluences=3,
        max_leverage=50,
        max_position_size=2500,
        max_concurrent_trades=8,
        max_daily_trades=15,
        max_loss_per_day=-500,
        description="Main SMC-based trading engine",
        risk_profile="balanced"
    ),
    
    EngineType.FREE_WILL_V2: EngineConfig(
        engine_type=EngineType.FREE_WILL_V2,
        min_confidence=75.0,
        min_confluences=2,
        max_leverage=75,
        max_position_size=2000,
        max_concurrent_trades=10,
        max_daily_trades=20,
        max_loss_per_day=-400,
        description="Proactive alerts, 24/7 scanning",
        risk_profile="balanced"
    ),
    
    EngineType.DUAL_ENGINE: EngineConfig(
        engine_type=EngineType.DUAL_ENGINE,
        min_confidence=82.0,
        min_confluences=4,
        max_leverage=35,
        max_position_size=1500,
        max_concurrent_trades=6,
        max_daily_trades=10,
        max_loss_per_day=-300,
        description="Day Trader (aggressive) + Long Term (smart)",
        risk_profile="conservative"
    ),
    
    EngineType.YOLO_ENGINE: EngineConfig(
        engine_type=EngineType.YOLO_ENGINE,
        min_confidence=75.0,
        min_confluences=2,
        max_leverage=50,
        max_position_size=3000,
        max_concurrent_trades=15,
        max_daily_trades=30,
        max_loss_per_day=-600,
        description="Maximum aggression with safety guardrails",
        risk_profile="aggressive"
    ),
    
    EngineType.VWAP_SCALPER: EngineConfig(
        engine_type=EngineType.VWAP_SCALPER,
        min_confidence=70.0,
        min_confluences=3,
        max_leverage=150,  # Matches internal adaptive range (25–150x)
        max_position_size=1000,
        max_concurrent_trades=5,
        max_daily_trades=50,
        max_loss_per_day=-400,
        description="VWAP + EMA Cross + RSI strategy",
        risk_profile="aggressive"
    ),
    
    EngineType.ELITE_STRATEGY: EngineConfig(
        engine_type=EngineType.ELITE_STRATEGY,
        min_confidence=90.0,
        min_confluences=5,
        max_leverage=25,
        max_position_size=2500,
        max_concurrent_trades=3,
        max_daily_trades=5,
        max_loss_per_day=-200,
        description="Ultra-selective, high-confidence only",
        risk_profile="conservative"
    ),
    
    EngineType.DAY_TRADER: EngineConfig(
        engine_type=EngineType.DAY_TRADER,
        min_confidence=77.0,
        min_confluences=2,
        max_leverage=60,
        max_position_size=1800,
        max_concurrent_trades=8,
        max_daily_trades=25,
        max_loss_per_day=-450,
        description="Part of Dual Engine - Day mode",
        risk_profile="balanced"
    ),

    EngineType.VOLUME_PROFILE: EngineConfig(
        engine_type=EngineType.VOLUME_PROFILE,
        min_confidence=70.0,
        min_confluences=3,
        max_leverage=50,
        max_position_size=1500,
        max_concurrent_trades=6,
        max_daily_trades=20,
        max_loss_per_day=-400,
        use_blacklist=True,
        use_cooldown=False,
        description="Hyper Accuracy: Volume Profile + Liquidation Heatmap + Orderbook",
        risk_profile="balanced"
    ),

    EngineType.INSTITUTIONAL_SCALPER: EngineConfig(
        engine_type=EngineType.INSTITUTIONAL_SCALPER,
        min_confidence=85.0,
        min_confluences=2,
        max_leverage=30,
        max_position_size=1200,
        max_concurrent_trades=3,
        max_daily_trades=3,
        max_loss_per_day=-350,
        use_blacklist=True,
        use_cooldown=True,
        cooldown_hours=6,
        description="Pure SMC: Order Blocks, FVG, BOS, Liq Sweeps on 1H/4H/1D",
        risk_profile="conservative"
    ),
}

# ── Lθ parameter overrides — restore any auto-applied learning from last run ──
# omega_cycle calls aeon_ltheta_params.apply_override() when a Lθ fix is validated.
# On restart, we reload those changes so they survive process restarts.
try:
    from aeon_ltheta_params import load_overrides as _load_ltheta_overrides
    _load_ltheta_overrides(ENGINE_CONFIGS)
except Exception as _ltheta_err:
    import logging as _log
    _log.getLogger(__name__).warning(f"Lθ override restore failed: {_ltheta_err}")

# ── Dynamic leverage model — minimum floors per engine ───────────────────────
# ENGINE_CONFIGS holds max_leverage; this holds the floor (anomaly/chaos hard floor).
_ENGINE_MIN_LEVERAGE: Dict[str, int] = {
    "autonomous_trader_v2": 2,
    "free_will_v2":         5,
    "dual_engine":          2,
    "day_trader":           2,
    "yolo_engine":          5,
    "vwap_scalper":         10,
    "elite_strategy":       2,
}

# Regime → leverage multiplier (HIGH_VOLATILITY is CHAOS, non-negotiable at 0.25×)
_REGIME_LEVERAGE_MULT: Dict[str, float] = {
    "TRENDING":        1.00,
    "ACCUMULATION":    0.85,
    "RANGING":         0.50,
    "HIGH_VOLATILITY": 0.25,   # CHAOS — multiplier is non-negotiable
}


def compute_dynamic_leverage(
    score:         int,
    regime:        str,
    anomaly_count: int,
    engine_max:    int,
    engine_min:    int,
    engine_label:  str = "",
) -> Tuple[int, Dict]:
    """
    Pure function — quant-score-driven leverage computation.

    Formula:
        base          = (score / 100) × engine_max
        after_regime  = base × regime_multiplier
        after_anomaly = after_regime × 0.80^anomaly_count   (compounding penalty)
        bonus         ×1.15 if score≥85 AND TRENDING AND anomaly_count==0
        final         = clamp(round(after_anomaly), engine_min, engine_max)

    Hard rules (non-negotiable):
        4+ anomalies  → final = engine_min  (floor, no bonus overrides)
        engine_max    → absolute ceiling, always
        CHAOS/HIGH_VOLATILITY multiplier (0.25×) cannot be bypassed by bonus
    """
    # Step 1: Base
    base = (score / 100.0) * engine_max

    # Step 2: Regime multiplier (CHAOS non-negotiable)
    reg_mult     = _REGIME_LEVERAGE_MULT.get(regime, 0.50)
    after_regime = base * reg_mult

    # Step 3: 4+ anomaly hard floor — non-negotiable
    if anomaly_count >= 4:
        final = engine_min
        breakdown = {
            "score":         score,
            "base":          round(base, 2),
            "regime":        regime,
            "regime_mult":   reg_mult,
            "after_regime":  round(after_regime, 2),
            "anomaly_count": anomaly_count,
            "penalty_factor": "FLOOR",
            "bonus":         False,
            "raw":           engine_min,
            "final":         final,
            "engine_min":    engine_min,
            "engine_max":    engine_max,
            "rule":          "4+ anomaly floor (non-negotiable)",
        }
        logger.info(
            f"⚖️ [LEV] {engine_label} score={score} regime={regime} "
            f"anomalies={anomaly_count} → FLOOR={final}x [4+ anomaly rule]"
        )
        return final, breakdown

    # Step 4: Anomaly penalty (0.80 compounding per anomaly)
    penalty      = 0.80 ** anomaly_count
    after_anomaly = after_regime * penalty

    # Step 5: Confidence bonus — only TRENDING + score≥85 + 0 anomalies
    # Does NOT apply in HIGH_VOLATILITY (enforced by TRENDING check)
    bonus = score >= 85 and regime == "TRENDING" and anomaly_count == 0
    if bonus:
        after_anomaly *= 1.15

    # Step 6: Clamp — engine_max is NON-NEGOTIABLE
    raw   = round(after_anomaly)
    final = max(engine_min, min(engine_max, raw))

    breakdown = {
        "score":          score,
        "base":           round(base, 2),
        "regime":         regime,
        "regime_mult":    reg_mult,
        "after_regime":   round(after_regime, 2),
        "anomaly_count":  anomaly_count,
        "penalty_factor": round(penalty, 4),
        "after_anomaly":  round(after_anomaly, 2),
        "bonus":          bonus,
        "raw":            raw,
        "final":          final,
        "engine_min":     engine_min,
        "engine_max":     engine_max,
        "rule":           (
            "confidence bonus" if bonus else
            f"standard ({anomaly_count} anomaly penalty)" if anomaly_count else
            "standard"
        ),
    }
    logger.info(
        f"⚖️ [LEV] {engine_label} score={score} regime={regime} "
        f"anomalies={anomaly_count} mult={reg_mult} penalty={penalty:.3f}"
        f"{' +bonus' if bonus else ''} → {final}x  [raw={raw} min={engine_min} max={engine_max}]"
    )
    return final, breakdown


@dataclass
class Trade:
    """Represents a single trade from any engine"""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    engine_type: EngineType = EngineType.AUTONOMOUS_TRADER_V2
    symbol: str = ""
    direction: str = "long"
    entry_price: float = 0.0
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    position_size: float = 0.0
    leverage: float = 1.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0
    confluences: int = 0
    status: TradeStatus = TradeStatus.PENDING
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""
    blocked_reason: str = ""
    
    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN
    
    @property
    def is_win(self) -> bool:
        return self.pnl_usd > 0
    
    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "engine": self.engine_type.value,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "position_size": self.position_size,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "confluences": self.confluences,
            "status": self.status.value,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl_usd": self.pnl_usd,
            "pnl_pct": self.pnl_pct,
            "reason": self.reason
        }


@dataclass
class EngineStats:
    """Per-engine statistics"""
    engine_type: EngineType
    total_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    daily_pnl: float = 0.0
    daily_trades: int = 0
    blocked_trades: int = 0
    
    def to_dict(self) -> dict:
        return {
            "engine": self.engine_type.value,
            "total_trades": self.total_trades,
            "open_trades": self.open_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate * 100, 1),
            "total_pnl": round(self.total_pnl, 2),
            "profit_factor": round(self.profit_factor, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "blocked_trades": self.blocked_trades,
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2)
        }


# ============================================================================
# UNIFIED ENTRY VALIDATOR
# ============================================================================

class UnifiedEntryValidator:
    """
    Validates all trade signals across all engines.
    Applies strict rules before ANY engine can execute.
    """
    
    def __init__(self):
        self.blocked_trades: List[Trade] = []
        self.validation_logs: List[Dict] = []
    
    def validate_signal(self, signal: Dict, engine_type: EngineType) -> Tuple[bool, Trade, List[str]]:
        """
        Validate a trade signal
        Returns: (is_valid, trade_object, issues_list)
        """
        
        config = ENGINE_CONFIGS[engine_type]
        trade = Trade(
            engine_type=engine_type,
            symbol=signal.get("symbol", ""),
            direction=signal.get("direction", "long").lower(),
            entry_price=signal.get("entry_price", 0),
            position_size=signal.get("position_size", 0),
            leverage=signal.get("leverage", 1),
            stop_loss=signal.get("stop_loss", 0),
            take_profit=signal.get("take_profit", 0),
            confidence=signal.get("confidence", 0),
            confluences=signal.get("confluences", 0),
            reason=signal.get("reason", "")
        )
        
        issues = []
        
        # HARD RULE 1: Minimum Confluences
        if trade.confluences < config.min_confluences:
            issues.append(
                f"BLOCK: {trade.confluences} confluences < {config.min_confluences} minimum for {engine_type.value}"
            )
        
        # HARD RULE 2: Minimum Confidence
        if trade.confidence < config.min_confidence:
            issues.append(
                f"BLOCK: {trade.confidence:.1f}% confidence < {config.min_confidence}% minimum for {engine_type.value}"
            )
        
        # HARD RULE 3: Valid Direction
        if trade.direction not in ["long", "short"]:
            issues.append(f"BLOCK: Invalid direction '{trade.direction}' (must be 'long' or 'short')")
        
        # HARD RULE 4: Position Size
        if trade.position_size > config.max_position_size:
            issues.append(
                f"BLOCK: ${trade.position_size} > ${config.max_position_size} max for {engine_type.value}"
            )
        
        if trade.position_size < 100:
            issues.append(f"BLOCK: ${trade.position_size} < $100 minimum")
        
        # HARD RULE 5: Leverage
        if trade.leverage > config.max_leverage:
            issues.append(
                f"BLOCK: {trade.leverage}x > {config.max_leverage}x max leverage for {engine_type.value}"
            )
        
        # HARD RULE 6-7: Stops & TP
        if trade.stop_loss == 0:
            issues.append("BLOCK: Stop loss not set")

        if trade.take_profit == 0:
            issues.append("BLOCK: Take profit not set")

        # HARD RULE 6b: Stop loss must differ from entry (catches ATR=0 bug for low-price coins)
        if trade.entry_price > 0 and trade.stop_loss > 0 and trade.stop_loss == trade.entry_price:
            issues.append("BLOCK: Stop loss equals entry price (invalid ATR calculation)")

        # HARD RULE 7b: Take profit must differ from entry
        if trade.entry_price > 0 and trade.take_profit > 0 and trade.take_profit == trade.entry_price:
            issues.append("BLOCK: Take profit equals entry price (invalid ATR calculation)")

        # HARD RULE 8: R:R Ratio
        if trade.entry_price > 0 and trade.stop_loss > 0:
            risk = abs(trade.entry_price - trade.stop_loss)
            reward = abs(trade.take_profit - trade.entry_price)
            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio < 1.5:
                    issues.append(
                        f"BLOCK: R:R ratio {rr_ratio:.2f}:1 < 1.5:1 minimum"
                    )
            else:
                issues.append("BLOCK: Zero risk (stop loss equals entry price)")
        
        is_valid = len([i for i in issues if i.startswith("BLOCK")]) == 0
        
        if not is_valid:
            trade.blocked_reason = " | ".join(issues)
            self.blocked_trades.append(trade)
        
        # Log validation
        self.validation_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine": engine_type.value,
            "symbol": trade.symbol,
            "valid": is_valid,
            "issues": issues
        })
        
        return is_valid, trade, issues
    
    def get_stats(self) -> Dict:
        """Get validation statistics"""
        total = len(self.validation_logs)
        blocked = len(self.blocked_trades)
        return {
            "total_validations": total,
            "total_blocked": blocked,
            "blocking_rate": round((blocked / max(1, total)) * 100, 1),
            "recent_blocks": [t.to_dict() for t in self.blocked_trades[-10:]]
        }


# ============================================================================
# ENGINE MANAGER
# ============================================================================

class EngineManager:
    """
    Manages all 7 engines independently.
    Each engine has its own trade history, blacklist, cooldown, stats.
    """

    def __init__(self, db=None):
        self.db = db
        self.validator = UnifiedEntryValidator()
        self.learning_callback = None  # Set by server.py for outcome feedback
        self._engine_instances: Dict[str, object] = {}  # engine_type.value -> engine obj
        # Injected by server.py after init: engine_manager.quant_gatekeeper = get_quant_gatekeeper()
        # When set, every submit_signal_gated call runs Quant analysis first.
        self.quant_gatekeeper: Optional[Any] = None
        # Injected by server.py: engine_manager.market_intel = market_intel
        self.market_intel: Optional[Any] = None

        # Per-engine state
        self.engine_trades: Dict[EngineType, List[Trade]] = {
            engine: [] for engine in EngineType
        }

        self.engine_stats: Dict[EngineType, EngineStats] = {
            engine: EngineStats(engine_type=engine) for engine in EngineType
        }

        self.engine_blacklists: Dict[EngineType, Dict[str, datetime]] = {
            engine: {} for engine in EngineType
        }

        self.engine_cooldowns: Dict[EngineType, Dict[str, datetime]] = {
            engine: {} for engine in EngineType
        }

        self.daily_reset_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Global kill switch: if combined daily loss across all engines exceeds this,
        # ALL engines are paused until the next UTC midnight reset.
        self.global_daily_loss_limit: float = -3000.0  # $3,000 combined max daily loss
        self._global_kill_active: bool = False

        # Alert deduplication: (base_symbol, direction) -> last alert sent time
        self._alert_sent: Dict[tuple, datetime] = {}

        # ORIA: per-engine consecutive loss counter (used by StressMonitor)
        self._consecutive_losses: Dict[str, int] = {e.value: 0 for e in EngineType}

        logger.info("🎯 EngineManager initialized with 7 independent engines")

    def should_send_alert(self, symbol: str, direction: str, window_minutes: int = 20) -> bool:
        """
        Returns True if this symbol+direction alert hasn't been sent in the last window_minutes.
        Call this before sending Telegram alerts to prevent duplicate notifications.
        """
        key = (self._normalize_symbol(symbol), direction.lower())
        last = self._alert_sent.get(key)
        if last and (datetime.now(timezone.utc) - last) < timedelta(minutes=window_minutes):
            return False
        self._alert_sent[key] = datetime.now(timezone.utc)
        return True
    
    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize symbol to base coin for cross-engine comparison: BTC/USDT → BTC"""
        return symbol.replace("/USDT", "").replace("USDT", "").replace("/USD", "").upper().strip()

    def _check_contradiction(self, engine_type: EngineType, symbol: str, direction: str) -> Optional[str]:
        """
        Cross-engine contradiction guard.
        Reject a LONG if another engine already has an open SHORT on the same coin (and vice versa).
        """
        base = self._normalize_symbol(symbol)
        direction_lower = direction.lower()

        for other_engine in EngineType:
            if other_engine == engine_type:
                continue
            for trade in self._get_open_trades(other_engine):
                trade_base = self._normalize_symbol(trade.symbol)
                if trade_base == base and trade.direction.lower() != direction_lower:
                    return (
                        f"Contradiction: {other_engine.value} already has an open "
                        f"{trade.direction.upper()} on {base}"
                    )
        return None

    async def save_trade_to_db(self, trade: Trade):
        """Persist a trade to MongoDB"""
        if self.db is None:
            return
        try:
            doc = trade.to_dict()
            doc["_id"] = doc["trade_id"]
            await self.db.engine_trades.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as e:
            logger.error(f"Failed to save trade to DB: {e}")

    async def load_trades_from_db(self):
        """Reload open trades from MongoDB on startup"""
        if self.db is None:
            return
        try:
            cursor = self.db.engine_trades.find({"status": "open"})
            count = 0
            async for doc in cursor:
                try:
                    engine_type = EngineType(doc["engine"])
                    trade = Trade(
                        trade_id=doc["trade_id"],
                        engine_type=engine_type,
                        symbol=doc["symbol"],
                        direction=doc["direction"],
                        entry_price=doc["entry_price"],
                        position_size=doc["position_size"],
                        leverage=doc["leverage"],
                        stop_loss=doc["stop_loss"],
                        take_profit=doc["take_profit"],
                        confidence=doc["confidence"],
                        confluences=doc["confluences"],
                        status=TradeStatus.OPEN,
                        reason=doc.get("reason", ""),
                    )
                    self.engine_trades[engine_type].append(trade)
                    self.engine_stats[engine_type].open_trades += 1
                    count += 1
                except Exception:
                    pass
            if count:
                logger.info(f"♻️ Reloaded {count} open engine trades from MongoDB")
        except Exception as e:
            logger.error(f"Failed to load trades from DB: {e}")

    async def submit_signal_gated(
        self,
        signal:      Dict,
        engine_type: EngineType,
        adapted:     bool = False,
    ) -> Dict:
        """
        Async entry point — runs QuantGatekeeperV2 (or legacy QuantGatekeeper)
        before the synchronous submit_signal pipeline.

        Engines call this instead of submit_signal directly.
        On Quant BLOCK the engine receives a full anomaly report so it can adapt
        and resubmit with adapted=True (allowed once).
        """
        # Refresh BTC macro direction in background (non-blocking, cached 30 min)
        if self.market_intel is not None:
            try:
                from regime_engine import get_regime_engine
                asyncio.create_task(
                    get_regime_engine().refresh_macro_direction(self.market_intel)
                )
            except Exception:
                pass

        if self.quant_gatekeeper is not None:
            config    = ENGINE_CONFIGS[engine_type]
            symbol    = signal.get("symbol", "")
            direction = signal.get("direction", "long")

            gate = await self.quant_gatekeeper.check(
                symbol      = symbol,
                direction   = direction,
                engine_type = engine_type.value,
                signal_data = signal,
                adapted     = adapted,
            )

            if not gate.get("approved", True):
                self.engine_stats[engine_type].blocked_trades += 1
                logger.warning(
                    f"🔬 [QUANT GATE] [{engine_type.value}] {symbol} "
                    f"{direction.upper()} BLOCKED — {gate.get('reason', 'quant threshold not met')}"
                )
                return {
                    "action":       "REJECT",
                    "engine":       engine_type.value,
                    "symbol":       symbol,
                    "reason":       f"QUANT GATE: {gate.get('reason', 'threshold not met')}",
                    "quant_report": gate,
                    "adapted":      adapted,
                }

            logger.debug(
                f"🔬 [QUANT GATE] [{engine_type.value}] {symbol} "
                f"{direction.upper()} PASSED — score {gate.get('score')}, "
                f"regime {gate.get('regime')}, threshold {gate.get('threshold_used')}, "
                f"size×{gate.get('position_multiplier', 1.0)}"
            )

            result = self.submit_signal(signal, engine_type)
            # Propagate position_multiplier so calling engines can scale position size
            result["position_multiplier"] = gate.get("position_multiplier", 1.0)
            result["marginal"] = gate.get("marginal", False)
            return result

        return self.submit_signal(signal, engine_type)

    async def get_dynamic_leverage(
        self,
        symbol:       str,
        direction:    str,
        engine_type:  EngineType,
        *,
        quant_report: Optional[Dict] = None,
    ) -> Tuple[int, Dict]:
        """
        Compute quant-score-driven leverage before building the signal.

        If quant_report is provided (e.g. from a prior REJECT), reads
        score/regime/anomaly_count directly from it — no extra API calls.
        Otherwise calls self.quant_gatekeeper.pre_check() — MongoDB only.
        Falls back to conservative defaults if no gatekeeper is set.

        Returns: (final_leverage: int, breakdown: Dict)
        """
        config     = ENGINE_CONFIGS[engine_type]
        engine_max = config.max_leverage
        engine_min = _ENGINE_MIN_LEVERAGE.get(engine_type.value, 2)

        if quant_report is not None:
            score         = quant_report.get("score", 50)
            regime        = quant_report.get("regime", "RANGING")
            anomaly_count = len(quant_report.get("anomalies_detected", []))
        elif self.quant_gatekeeper is not None:
            pre           = await self.quant_gatekeeper.pre_check(symbol, direction, engine_type.value)
            score         = pre.get("score", 50)
            regime        = pre.get("regime", "RANGING")
            anomaly_count = pre.get("anomaly_count", 0)
        else:
            score, regime, anomaly_count = 50, "RANGING", 0

        return compute_dynamic_leverage(
            score, regime, anomaly_count,
            engine_max, engine_min,
            engine_type.value,
        )

    def submit_signal(self, signal: Dict, engine_type: EngineType) -> Dict:
        """
        Main entry point for any engine to submit a trade signal.
        Returns complete trade plan or rejection reason.
        """

        config = ENGINE_CONFIGS[engine_type]

        # Step 0a: Midnight reset — must run BEFORE kill switch check so the switch
        # clears at UTC midnight even when no new signals were submitted during the day.
        self._try_midnight_reset()

        # Step 0: Global kill switch — pause all engines if combined daily loss exceeded
        combined_daily_pnl = sum(self.engine_stats[e].daily_pnl for e in EngineType)
        if combined_daily_pnl <= self.global_daily_loss_limit:
            self._global_kill_active = True
        if self._global_kill_active:
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": signal.get("symbol"),
                "reason": f"GLOBAL KILL SWITCH ACTIVE — combined daily loss ${combined_daily_pnl:+.2f} exceeds limit ${self.global_daily_loss_limit:+.2f}. Resumes at UTC midnight."
            }

        # Step 1: Validate entry criteria
        is_valid, trade, issues = self.validator.validate_signal(signal, engine_type)
        
        if not is_valid:
            self.engine_stats[engine_type].blocked_trades += 1
            logger.warning(f"❌ [{engine_type.value}] Signal REJECTED: {issues}")
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": signal.get("symbol"),
                "reason": "Failed entry validation",
                "issues": issues
            }

        # Step 1b: Cross-engine contradiction guard
        contradiction = self._check_contradiction(
            engine_type, trade.symbol, trade.direction
        )
        if contradiction:
            self.engine_stats[engine_type].blocked_trades += 1
            logger.warning(f"⚔️ [{engine_type.value}] CONTRADICTION BLOCKED: {contradiction}")
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": trade.symbol,
                "reason": contradiction
            }

        # Step 1c: Per-coin open position cap (max 2 across ALL engines combined)
        base_symbol = self._normalize_symbol(trade.symbol)
        coin_open_count = sum(
            1 for e in EngineType
            for t in self._get_open_trades(e)
            if self._normalize_symbol(t.symbol) == base_symbol
        )
        if coin_open_count >= 2:
            self.engine_stats[engine_type].blocked_trades += 1
            logger.warning(
                f"🔒 [{engine_type.value}] COIN LOCK: {trade.symbol} already has "
                f"{coin_open_count} open positions across engines"
            )
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": trade.symbol,
                "reason": f"COIN LOCK: {trade.symbol} already has {coin_open_count} open positions across engines"
            }

        # Step 1d: BTC macro direction gate
        # BEARISH: LONG entries require min_confidence + 10%
        # BULLISH: SHORT entries require min_confidence + 10%
        # NEUTRAL: no adjustment
        try:
            from regime_engine import get_regime_engine
            _macro_threshold, _macro_reason = get_regime_engine().apply_macro_confidence_gate(
                trade.direction, config.min_confidence
            )
            if _macro_reason and trade.confidence < _macro_threshold:
                self.engine_stats[engine_type].blocked_trades += 1
                logger.info(
                    f"[MACRO GATE] [{engine_type.value}] {trade.symbol} "
                    f"{trade.direction} BLOCKED — confidence {trade.confidence:.0f}% < {_macro_threshold:.0f}% required. {_macro_reason}"
                )
                return {
                    "action":    "REJECT",
                    "engine":    engine_type.value,
                    "symbol":    trade.symbol,
                    "reason":    _macro_reason,
                    "macro_dir": get_regime_engine().get_btc_macro_direction(),
                }
        except Exception as _macro_err:
            logger.debug(f"[MACRO GATE] Check skipped: {_macro_err}")

        # ── ORIA LAYER ────────────────────────────────────────────────────────

        # Step 1e — ORIA Layer 1: Signal aggregation (composite confidence)
        # If multiple engines have buffered a signal for the same coin+direction
        # within the 300s TTL, replace raw confidence with the weighted composite.
        if _ORIA_AVAILABLE:
            try:
                _agg = get_signal_aggregator()
                if _agg is not None:
                    # Buffer this engine's signal
                    _agg.buffer_signal(
                        symbol=trade.symbol,
                        direction=trade.direction,
                        engine=engine_type.value,
                        confidence=trade.confidence,
                        stop_loss=trade.stop_loss,
                        take_profit=trade.take_profit,
                        entry_price=trade.entry_price,
                    )
                    # Compute vector (returns None if only 1 engine buffered)
                    _vector = _agg.compute_vector(trade.symbol, trade.direction)
                    if _vector is not None and _vector.composite_confidence > trade.confidence:
                        logger.info(
                            f"🔗 [ORIA/L1] [{engine_type.value}] {trade.symbol} "
                            f"confidence upgraded {trade.confidence:.1f}% → "
                            f"{_vector.composite_confidence:.1f}% "
                            f"({_vector.engine_count} engines, "
                            f"+{_vector.convergence_bonus:.0f}% convergence bonus)"
                        )
                        trade.confidence = _vector.composite_confidence
            except Exception as _oria_l1_err:
                logger.debug(f"[ORIA/L1] Skipped: {_oria_l1_err}")

        # Step 1f — ORIA Layer 2: Edge / Uncertainty / Cost filter
        # Requires ≥20 trades of history per engine+symbol; passes through otherwise.
        if _ORIA_AVAILABLE:
            try:
                _ef = get_edge_filter()
                if _ef is not None:
                    # Soft blacklist check (edge decay detected in last 24h)
                    if _ef.is_soft_blacklisted(trade.symbol):
                        _decay_mult = _ef.soft_blacklist_size_mult(trade.symbol)
                        signal["position_size"] = round(
                            signal.get("position_size", trade.position_size) * _decay_mult, 2
                        )
                        trade.position_size = signal["position_size"]
                        logger.info(
                            f"[ORIA/L2] [{engine_type.value}] {trade.symbol} "
                            f"edge-decay soft blacklist → size ×{_decay_mult}"
                        )
                    # Regime-adaptive R:R floor (already enforced by UnifiedEntryValidator
                    # at 1.5:1; this upgrades the floor for non-trending regimes)
                    _current_regime = "TRENDING"
                    try:
                        from regime_engine import get_regime_engine
                        _det = get_regime_engine().detect_regime.__wrapped__ if hasattr(
                            get_regime_engine().detect_regime, "__wrapped__") else None
                        # Use cached last regime from quant_gatekeeper if available
                        if self.quant_gatekeeper:
                            _pre_r = getattr(self.quant_gatekeeper, "_last_regime", {})
                            _current_regime = _pre_r.get(trade.symbol, "TRENDING")
                    except Exception:
                        pass
                    _rr_floor = _ef.get_regime_rr_floor(_current_regime)
                    if trade.entry_price > 0 and trade.stop_loss > 0 and trade.take_profit > 0:
                        _risk   = abs(trade.entry_price - trade.stop_loss)
                        _reward = abs(trade.take_profit - trade.entry_price)
                        if _risk > 0 and (_reward / _risk) < _rr_floor:
                            self.engine_stats[engine_type].blocked_trades += 1
                            logger.info(
                                f"[ORIA/L2] [{engine_type.value}] {trade.symbol} "
                                f"R:R {_reward/_risk:.2f} < regime floor {_rr_floor} "
                                f"({_current_regime}) → REJECT"
                            )
                            return {
                                "action": "REJECT",
                                "engine": engine_type.value,
                                "symbol": trade.symbol,
                                "reason": (
                                    f"ORIA R:R floor: {_reward/_risk:.2f}:1 < "
                                    f"{_rr_floor}:1 required in {_current_regime} regime"
                                ),
                            }
            except Exception as _oria_l2_err:
                logger.debug(f"[ORIA/L2] Skipped: {_oria_l2_err}")

        # Step 1g — ORIA Layer 3: Stress-adjusted position sizing
        # Applies exp(−λ × S) to position_size and leverage using live stress score.
        if _ORIA_AVAILABLE:
            try:
                _sm = get_stress_monitor()
                if _sm is not None:
                    _size_mult, _stress_label = _sm.get_size_multiplier()
                    _lev_mult                 = _sm.get_leverage_multiplier()
                    if _size_mult < 0.99:   # only log/apply when meaningful
                        _orig_size = trade.position_size
                        _orig_lev  = trade.leverage
                        trade.position_size = max(
                            100.0,
                            apply_stress_sizing(trade.position_size, _sm.stress_score, _sm.LAMBDA)
                        )
                        trade.leverage = max(
                            _ENGINE_MIN_LEVERAGE.get(engine_type.value, 2),
                            apply_stress_leverage(trade.leverage, _sm.stress_score, _sm.LAMBDA)
                        )
                        signal["position_size"] = trade.position_size
                        signal["leverage"]       = trade.leverage
                        logger.info(
                            f"📉 [ORIA/L3] [{engine_type.value}] {trade.symbol} "
                            f"stress {_stress_label} → "
                            f"size ${_orig_size:.0f}→${trade.position_size:.0f} "
                            f"({_size_mult:.0%}), lev {_orig_lev}x→{trade.leverage}x"
                        )
            except Exception as _oria_l3_err:
                logger.debug(f"[ORIA/L3] Skipped: {_oria_l3_err}")

        # ── END ORIA LAYER ────────────────────────────────────────────────────

        # Step 2: Check blacklist/cooldown
        symbol = trade.symbol
        if config.use_blacklist:
            blacklist_status = self._check_blacklist(engine_type, symbol)
            if blacklist_status:
                return {
                    "action": "REJECT",
                    "engine": engine_type.value,
                    "symbol": symbol,
                    "reason": blacklist_status
                }
        
        if config.use_cooldown:
            cooldown_status = self._check_cooldown(engine_type, symbol)
            if cooldown_status:
                return {
                    "action": "REJECT",
                    "engine": engine_type.value,
                    "symbol": symbol,
                    "reason": cooldown_status
                }
        
        # Step 3: Check daily limits
        daily_check = self._check_daily_limits(engine_type)
        if not daily_check["ok"]:
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": symbol,
                "reason": daily_check["reason"]
            }
        
        # Step 4a: Check global position cap (all engines combined)
        GLOBAL_MAX_POSITIONS = 50
        total_open = sum(len(self._get_open_trades(e)) for e in EngineType)
        if total_open >= GLOBAL_MAX_POSITIONS:
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": symbol,
                "reason": f"Global cap: {total_open}/{GLOBAL_MAX_POSITIONS} total positions open across all engines"
            }

        # Step 4b: Check per-engine concurrent trades
        # ORIA Sharpe throttle: if engine 7d Sharpe < 0, halve concurrent limit
        _effective_concurrent = config.max_concurrent_trades
        if _ORIA_AVAILABLE:
            try:
                _sm = get_stress_monitor()
                if _sm is not None:
                    _effective_concurrent = _sm.effective_concurrent_limit(
                        engine_type.value, config.max_concurrent_trades
                    )
            except Exception:
                pass

        open_count = len(self._get_open_trades(engine_type))
        if open_count >= _effective_concurrent:
            throttle_note = (
                " [Sharpe-throttled]" if _effective_concurrent < config.max_concurrent_trades else ""
            )
            return {
                "action": "REJECT",
                "engine": engine_type.value,
                "symbol": symbol,
                "reason": (
                    f"Max {_effective_concurrent} concurrent trades reached "
                    f"({open_count} open){throttle_note}"
                ),
            }
        
        # Step 5: All checks passed - EXECUTE
        trade.status = TradeStatus.OPEN
        self.engine_trades[engine_type].append(trade)
        self.engine_stats[engine_type].open_trades += 1
        # Count trade at open time so the daily cap applies to trades entered, not closed
        self.engine_stats[engine_type].daily_trades += 1

        logger.info(f"✅ [{engine_type.value}] EXECUTE {trade.symbol} {trade.direction.upper()} @ ${trade.entry_price:.2f} | {trade.leverage}x | Conf: {trade.confidence}%")
        
        return {
            "action": "EXECUTE",
            "engine": engine_type.value,
            "trade": trade.to_dict(),
            "execution_plan": {
                "trade_id": trade.trade_id,
                "entry_price": trade.entry_price,
                "position_size": trade.position_size,
                "leverage": trade.leverage,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "confidence": trade.confidence,
                "confluences": trade.confluences
            }
        }
    
    def close_trade(self, engine_type: EngineType, trade_id: str, exit_price: float, pnl_usd: float) -> bool:
        """Close a trade and record result"""
        
        for trade in self.engine_trades[engine_type]:
            if trade.trade_id == trade_id and trade.status == TradeStatus.OPEN:
                trade.status = TradeStatus.CLOSED
                trade.exit_price = exit_price
                trade.exit_time = datetime.now(timezone.utc)
                trade.pnl_usd = pnl_usd
                trade.pnl_pct = (pnl_usd / (trade.position_size)) * 100 if trade.position_size > 0 else 0
                
                # Update stats
                self._update_stats(engine_type, trade)
                
                # Handle loss management
                config = ENGINE_CONFIGS[engine_type]
                if config.use_blacklist or config.use_cooldown:
                    self._process_loss_management(engine_type, trade)

                emoji = "🎯" if trade.is_win else "🛑"
                logger.info(f"{emoji} [{engine_type.value}] CLOSED {trade.symbol} | PnL: ${pnl_usd:+.2f}")

                # Notify engine instance so its internal win/loss counters stay accurate
                engine_instance = self._engine_instances.get(engine_type.value)
                if engine_instance and hasattr(engine_instance, "record_trade_result"):
                    try:
                        engine_instance.record_trade_result(trade.is_win)
                    except Exception:
                        pass

                # ORIA: update consecutive loss counter + Sharpe throttle
                if _ORIA_AVAILABLE:
                    try:
                        # Consecutive loss tracking (used by StressMonitor for S(t))
                        if trade.is_win:
                            self._consecutive_losses[engine_type.value] = 0
                        else:
                            self._consecutive_losses[engine_type.value] = (
                                self._consecutive_losses.get(engine_type.value, 0) + 1
                            )
                        # Record result in StressMonitor for Sharpe throttle
                        _sm = get_stress_monitor()
                        if _sm is not None:
                            _sm.record_engine_result(engine_type.value, trade.pnl_pct)
                    except Exception:
                        pass

                # Fire learning callback so continuous learner records outcome
                if self.learning_callback:
                    try:
                        import asyncio
                        asyncio.create_task(self.learning_callback({
                            "engine": engine_type.value,
                            "symbol": trade.symbol,
                            "direction": trade.direction,
                            "pnl_usd": pnl_usd,
                            "pnl_pct": trade.pnl_pct,
                            "confidence": trade.confidence,
                            "confluences": trade.confluences,
                            "is_win": trade.is_win,
                            "closed_at": datetime.now(timezone.utc).isoformat(),
                        }))
                    except Exception:
                        pass

                return True
        
        return False
    
    def close_trade_by_id(self, trade_id: str, exit_price: float, pnl_usd: float) -> bool:
        """Close a trade across any engine by ID"""
        for engine_type in EngineType:
            if self.close_trade(engine_type, trade_id, exit_price, pnl_usd):
                return True
        return False
    
    def _check_blacklist(self, engine_type: EngineType, symbol: str) -> Optional[str]:
        """Check if symbol is blacklisted for this engine"""
        if symbol in self.engine_blacklists[engine_type]:
            expiry = self.engine_blacklists[engine_type][symbol]
            if datetime.now(timezone.utc) < expiry:
                return f"{symbol} is blacklisted for {engine_type.value}"
            else:
                del self.engine_blacklists[engine_type][symbol]
        return None
    
    def _check_cooldown(self, engine_type: EngineType, symbol: str) -> Optional[str]:
        """Check if symbol is in cooldown for this engine"""
        if symbol in self.engine_cooldowns[engine_type]:
            expiry = self.engine_cooldowns[engine_type][symbol]
            if datetime.now(timezone.utc) < expiry:
                time_left = (expiry - datetime.now(timezone.utc)).total_seconds() / 3600
                return f"{symbol} in cooldown {time_left:.1f}h remaining"
            else:
                del self.engine_cooldowns[engine_type][symbol]
        return None
    
    def _try_midnight_reset(self):
        """Reset daily stats and kill switch at UTC midnight.
        Called unconditionally at the top of submit_signal so the kill switch
        clears even if no signals are being submitted (which would normally
        prevent _check_daily_limits from ever running).
        """
        now = datetime.now(timezone.utc)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if today_midnight > self.daily_reset_time:
            for e in EngineType:
                self.engine_stats[e].daily_trades = 0
                self.engine_stats[e].daily_pnl = 0.0
            self.daily_reset_time = today_midnight
            self._global_kill_active = False
            logger.info("🔄 Daily stats reset at UTC midnight. Kill switch cleared.")

    def _check_daily_limits(self, engine_type: EngineType) -> Dict:
        """Check daily trade count and loss limits"""
        config = ENGINE_CONFIGS[engine_type]
        stats = self.engine_stats[engine_type]

        # Reset daily stats at UTC midnight (also handled in _try_midnight_reset,
        # kept here as belt-and-suspenders for direct calls to this method)
        now = datetime.now(timezone.utc)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if today_midnight > self.daily_reset_time:
            for e in EngineType:
                self.engine_stats[e].daily_trades = 0
                self.engine_stats[e].daily_pnl = 0.0
            self.daily_reset_time = today_midnight
            self._global_kill_active = False
            logger.info("🔄 Daily stats reset at UTC midnight. Kill switch cleared.")
        
        # Check daily trade count
        if stats.daily_trades >= config.max_daily_trades:
            return {
                "ok": False,
                "reason": f"Daily trade limit {config.max_daily_trades} reached"
            }
        
        # Check daily loss limit
        if stats.daily_pnl < config.max_loss_per_day:
            return {
                "ok": False,
                "reason": f"Daily loss limit (${config.max_loss_per_day}) exceeded"
            }
        
        return {"ok": True}
    
    def _get_open_trades(self, engine_type: EngineType) -> List[Trade]:
        """Get all open trades for an engine"""
        return [t for t in self.engine_trades[engine_type] if t.status == TradeStatus.OPEN]
    
    def _update_stats(self, engine_type: EngineType, trade: Trade):
        """Update engine statistics after trade closes"""
        stats = self.engine_stats[engine_type]
        
        stats.total_trades += 1
        stats.closed_trades += 1
        stats.open_trades = len(self._get_open_trades(engine_type))
        # daily_trades already incremented at open time (do not double-count here)
        stats.daily_pnl += trade.pnl_usd
        
        if trade.is_win:
            stats.wins += 1
            if stats.wins > 0:
                stats.avg_win = (stats.avg_win * (stats.wins - 1) + trade.pnl_usd) / stats.wins
            stats.largest_win = max(stats.largest_win, trade.pnl_usd)
        else:
            stats.losses += 1
            if stats.losses > 0:
                stats.avg_loss = (stats.avg_loss * (stats.losses - 1) + trade.pnl_usd) / stats.losses
            stats.largest_loss = min(stats.largest_loss, trade.pnl_usd)
        
        stats.win_rate = stats.wins / stats.total_trades if stats.total_trades > 0 else 0
        stats.total_pnl += trade.pnl_usd
        
        # Calculate profit factor
        total_wins = stats.wins * stats.avg_win if stats.wins > 0 else 0
        total_losses = abs(stats.losses * stats.avg_loss) if stats.losses > 0 else 1
        stats.profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    def _process_loss_management(self, engine_type: EngineType, trade: Trade):
        """Handle blacklist/cooldown after a losing trade"""
        config = ENGINE_CONFIGS[engine_type]
        symbol = trade.symbol

        if not trade.is_win:
            if config.use_cooldown:
                expiry = datetime.now(timezone.utc) + timedelta(hours=config.cooldown_hours)
                self.engine_cooldowns[engine_type][symbol] = expiry
                logger.info(f"⏳ [{engine_type.value}] {symbol} in cooldown for {config.cooldown_hours}h")

            # Auto-blacklist if this engine has now lost on this symbol twice in the
            # current session (cooldown handles the first loss; blacklist the second).
            if config.use_blacklist:
                recent_losses = sum(
                    1 for t in self.engine_trades[engine_type]
                    if t.symbol == symbol
                    and t.status == TradeStatus.CLOSED
                    and not t.is_win
                    and t.exit_time
                    and (datetime.now(timezone.utc) - t.exit_time) < timedelta(hours=24)
                )
                if recent_losses >= 2:
                    blacklist_hours = config.cooldown_hours * 4  # 4× the cooldown window
                    expiry = datetime.now(timezone.utc) + timedelta(hours=blacklist_hours)
                    self.engine_blacklists[engine_type][symbol] = expiry
                    logger.warning(f"🚫 [{engine_type.value}] {symbol} AUTO-BLACKLISTED for {blacklist_hours}h after {recent_losses} losses in 24h")
    
    def register_engine_instance(self, engine_type: EngineType, instance: object):
        """Register a live engine object so close_trade can update its internal stats."""
        self._engine_instances[engine_type.value] = instance

    def add_to_blacklist(self, engine_type: EngineType, symbol: str, hours: int = 24):
        """Manually blacklist a symbol for an engine"""
        expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
        self.engine_blacklists[engine_type][symbol] = expiry
        logger.info(f"🚫 [{engine_type.value}] {symbol} blacklisted for {hours}h")
    
    def remove_from_blacklist(self, engine_type: EngineType, symbol: str):
        """Remove a symbol from blacklist"""
        if symbol in self.engine_blacklists[engine_type]:
            del self.engine_blacklists[engine_type][symbol]
            return True
        return False
    
    def get_engine_status(self, engine_type: EngineType) -> Dict:
        """Get complete status for an engine"""
        config = ENGINE_CONFIGS[engine_type]
        stats = self.engine_stats[engine_type]
        open_trades = self._get_open_trades(engine_type)
        
        return {
            "engine": engine_type.value,
            "description": config.description,
            "risk_profile": config.risk_profile,
            "config": {
                "min_confidence": config.min_confidence,
                "min_confluences": config.min_confluences,
                "max_leverage": config.max_leverage,
                "max_position_size": config.max_position_size,
                "max_concurrent_trades": config.max_concurrent_trades,
                "max_daily_trades": config.max_daily_trades,
                "max_loss_per_day": config.max_loss_per_day
            },
            "stats": stats.to_dict(),
            "open_trades": [t.to_dict() for t in open_trades],
            "open_count": len(open_trades),
            "blacklisted": list(self.engine_blacklists[engine_type].keys()),
            "in_cooldown": list(self.engine_cooldowns[engine_type].keys())
        }
    
    def get_all_engine_status(self) -> Dict:
        """Get status for all 7 engines"""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engines": {
                engine.value: self.get_engine_status(engine)
                for engine in EngineType
            },
            "global": self.get_global_stats()["global"]
        }
    
    def get_global_stats(self) -> Dict:
        """Get statistics across all engines"""
        total_trades = 0
        total_wins = 0
        total_pnl = 0.0
        total_open = 0
        total_blocked = 0
        
        by_engine = {}
        for engine_type in EngineType:
            stats = self.engine_stats[engine_type]
            by_engine[engine_type.value] = stats.to_dict()
            
            total_trades += stats.total_trades
            total_wins += stats.wins
            total_pnl += stats.total_pnl
            total_open += stats.open_trades
            total_blocked += stats.blocked_trades
        
        combined_daily_pnl = sum(self.engine_stats[e].daily_pnl for e in EngineType)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "by_engine": by_engine,
            "global": {
                "total_trades": total_trades,
                "total_wins": total_wins,
                "total_losses": total_trades - total_wins,
                "win_rate": round((total_wins / total_trades * 100) if total_trades > 0 else 0, 1),
                "total_pnl": round(total_pnl, 2),
                "total_open": total_open,
                "total_blocked": total_blocked,
                "combined_daily_pnl": round(combined_daily_pnl, 2),
                "global_daily_loss_limit": self.global_daily_loss_limit,
                "kill_switch_active": self._global_kill_active,
            },
            "validation": self.validator.get_stats()
        }
    
    def get_all_open_trades(self) -> List[Dict]:
        """Get all open trades across all engines"""
        all_trades = []
        for engine_type in EngineType:
            for trade in self._get_open_trades(engine_type):
                all_trades.append(trade.to_dict())
        return all_trades
    
    def get_engine_config(self, engine_type: EngineType) -> Dict:
        """Get configuration for an engine"""
        config = ENGINE_CONFIGS[engine_type]
        return {
            "engine": engine_type.value,
            "min_confidence": config.min_confidence,
            "min_confluences": config.min_confluences,
            "max_leverage": config.max_leverage,
            "max_position_size": config.max_position_size,
            "max_concurrent_trades": config.max_concurrent_trades,
            "max_daily_trades": config.max_daily_trades,
            "max_loss_per_day": config.max_loss_per_day,
            "use_blacklist": config.use_blacklist,
            "use_cooldown": config.use_cooldown,
            "cooldown_hours": config.cooldown_hours,
            "risk_profile": config.risk_profile,
            "description": config.description
        }
    
    def get_all_configs(self) -> Dict:
        """Get configuration for all engines"""
        return {
            engine.value: self.get_engine_config(engine)
            for engine in EngineType
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

engine_manager: EngineManager = None


def init_engine_manager(db=None) -> EngineManager:
    """Initialize the global engine manager"""
    global engine_manager
    engine_manager = EngineManager(db)
    return engine_manager


def get_engine_manager() -> EngineManager:
    """Get the global engine manager"""
    global engine_manager
    if engine_manager is None:
        engine_manager = EngineManager()
    return engine_manager
