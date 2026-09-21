"""
NEXUS Data Models
All dataclasses and enums used across NEXUS layers.
No backend imports — fully standalone.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


# ── Regime Enums ──────────────────────────────────────────────────────────────

class MarketRegime(str, Enum):
    STRUCTURED   = "STRUCTURED"
    TRANSITIONAL = "TRANSITIONAL"
    CHAOTIC      = "CHAOTIC"

class VolatilityRegime(str, Enum):
    LOW    = "LOW"
    NORMAL = "NORMAL"
    SPIKE  = "SPIKE"

class TrendRegime(str, Enum):
    TRENDING  = "TRENDING"
    RANGING   = "RANGING"
    REVERSING = "REVERSING"

class EngineStatus(str, Enum):
    RUNNING   = "running"
    DEGRADED  = "degraded"
    DEAD      = "dead"
    SUSPENDED = "suspended"

class HealType(str, Enum):
    ENGINE_RESTART    = "ENGINE_RESTART"
    ENGINE_SUSPENDED  = "ENGINE_SUSPENDED"
    PROCESS_RESTART   = "PROCESS_RESTART"
    API_FAILOVER      = "API_FAILOVER"
    POSITION_CLOSE    = "POSITION_CLOSE"
    RESOURCE_THROTTLE = "RESOURCE_THROTTLE"
    DB_RECONNECT      = "DB_RECONNECT"
    LOG_ARCHIVE       = "LOG_ARCHIVE"
    SKIP              = "SKIP"


# ── Core Data Structures ──────────────────────────────────────────────────────

@dataclass
class EngineReport:
    name:                  str
    status:                str          # EngineStatus value
    win_rate:              float        # rolling 50 trades
    trade_count:           int
    last_signal_minutes:   Optional[float] # minutes since last signal
    alpha:                 float        # quantum amplitude αᵢ

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class PositionReport:
    symbol:           str
    direction:        str
    size_usd:         float
    pnl_pct:          float
    entry_price:      float
    current_price:    float
    stop_loss:        float
    opened_at:        str              # ISO string
    hours_open:       float
    engine:           str
    liq_dist_pct:     float           # % distance to liquidation
    leverage:         float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class SystemMetrics:
    cpu_pct:          float
    memory_pct:       float
    disk_pct:         float
    mongodb_ok:       bool
    mexc_ok:          bool
    aeon_process_ok:  bool
    frontend_ok:      bool

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class AwarenessSnapshot:
    timestamp:          datetime
    # Market
    market_regime:      str
    volatility_regime:  str
    trend_regime:       str
    H_market:           float
    H_internal:         float
    H_combined:         float
    adx:                float
    hurst:              float
    funding_rate_btc:   float
    oi_delta_btc:       float
    correlation_max:    float
    correlation_matrix: Dict[str, float]
    crisis_mode:        bool
    crisis_just_triggered: bool
    # Self
    consensus_C:        float
    health_H:           float
    engine_reports:     List[dict]
    open_positions:     List[dict]
    system_metrics:     dict

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class AdaptationEvent:
    timestamp:        datetime
    from_regime:      str
    to_regime:        str
    action_taken:     str
    engines_affected: List[str]
    position_modifier: float
    detail:           str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class HealAction:
    timestamp:        datetime
    heal_type:        str              # HealType value
    trigger:          str
    result:           str
    engine_affected:  Optional[str]
    original_state:   Optional[dict]
    success:          bool

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class WardanCheck:
    timestamp:      datetime
    component:      str
    status:         str             # "ok" | "down" | "stale"
    action_taken:   str
    detail:         str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["timestamp"] = self.timestamp.isoformat()
        return d


# ── NEXUS Config (written to MongoDB, read by AEON) ───────────────────────────

@dataclass
class NexusConfig:
    pause:             bool  = False
    crisis:            bool  = False
    position_modifier: float = 1.0
    regime:            str   = "STRUCTURED"
    trend_regime:      str   = "TRENDING"
    reason:            str   = ""
    active_engines:    List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "_id":               "live",
            "pause":             self.pause,
            "crisis":            self.crisis,
            "position_modifier": self.position_modifier,
            "regime":            self.regime,
            "trend_regime":      self.trend_regime,
            "reason":            self.reason,
            "active_engines":    self.active_engines,
        }
