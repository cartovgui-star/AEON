"""
AEON Research Team — Base Types
Shared dataclasses and enums used by all 10 specialists.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class MarketSignal(str, Enum):
    BULLISH  = "BULLISH"
    BEARISH  = "BEARISH"
    NEUTRAL  = "NEUTRAL"
    VOLATILE = "VOLATILE"
    CAUTION  = "CAUTION"


class RecType(str, Enum):
    BLOCK_DIRECTION   = "block_direction"    # block LONG or SHORT on a symbol (or all)
    AVOID_SYMBOL      = "avoid_symbol"       # no trades on a specific symbol
    RAISE_CONFIDENCE  = "raise_confidence"   # require higher confidence minimum


@dataclass
class Recommendation:
    type:           RecType
    reasoning:      str
    confidence:     float       # 0-1, specialist confidence in this call
    params:         Dict[str, Any] = field(default_factory=dict)
    # params keys by type:
    #   block_direction  → symbol (str|None=all), direction ("LONG"|"SHORT")
    #   avoid_symbol     → symbol (str)
    #   raise_confidence → min_confidence (int 60-95), symbol (str|None=all)
    duration_hours: int = 4     # how long the gate stays active if approved


@dataclass
class AnalysisResult:
    specialist:     str
    signal:         MarketSignal
    confidence:     int                       # 0-100
    observations:   List[str]                 # bullet points for the brief
    recommendation: Optional[Recommendation] = None
    raw_data:       Dict[str, Any] = field(default_factory=dict)
    error:          Optional[str]  = None     # set if analysis partially failed


def make_rec_doc(specialist: str, analysis: AnalysisResult, brief: str) -> Dict:
    """Build the MongoDB document for a pending recommendation."""
    rec = analysis.recommendation
    return {
        "rec_id":       str(uuid.uuid4()),
        "specialist":   specialist,
        "type":         rec.type.value,
        "params":       rec.params,
        "reasoning":    rec.reasoning,
        "brief":        brief,
        "confidence":   rec.confidence,
        "signal":       analysis.signal.value,
        "status":       "pending",
        "created_at":   datetime.now(timezone.utc),
        "expires_at":   datetime.now(timezone.utc) + timedelta(hours=rec.duration_hours + 24),
        "approved_at":  None,
        "rejected_at":  None,
        "active_until": None,      # set when approved
        "duration_hours": rec.duration_hours,
    }


def make_research_doc(specialist: str, analysis: AnalysisResult, brief: str) -> Dict:
    """Build the MongoDB document for a completed research cycle."""
    return {
        "specialist":    specialist,
        "signal":        analysis.signal.value,
        "confidence":    analysis.confidence,
        "observations":  analysis.observations,
        "brief":         brief,
        "has_rec":       analysis.recommendation is not None,
        "rec_type":      analysis.recommendation.type.value if analysis.recommendation else None,
        "raw_data":      analysis.raw_data,
        "error":         analysis.error,
        "created_at":    datetime.now(timezone.utc),
    }
