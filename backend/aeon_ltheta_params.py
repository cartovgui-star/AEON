"""
=============================================================
  aeon_ltheta_params.py — Lθ Parameter Override Manager
=============================================================

  Position in the identity: L = Lθ ⊕ LΣ ⊕ LΦ

  Lθ is the safest learning layer — it adjusts numerical
  thresholds (confidence floors, leverage caps, daily limits)
  without touching signal logic. Every change is:

    1. Validated in sandbox (H_new > H_current)
    2. Written to ltheta_params.json (survives restarts)
    3. Applied to ENGINE_CONFIGS in memory (immediate effect)
    4. Logged to MongoDB fixes collection
    5. Reported to Telegram

  This module owns the persistence and live-apply mechanism.
  omega_cycle.py calls apply_override() after sandbox passes.
  aeon_engine_system.py calls load_overrides() at startup.

  Override file: backend/ltheta_params.json
  Bounds: PARAM_BOUNDS dict — Lθ cannot exceed these limits.
=============================================================
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

PARAMS_FILE = os.path.join(os.path.dirname(__file__), "ltheta_params.json")

# Hard bounds per parameter — Lθ cannot move outside these.
# (min, max) inclusive. Constitutional layer: AEON cannot override these.
PARAM_BOUNDS: Dict[str, Tuple] = {
    "min_confidence":    (60.0,  95.0),   # % — never lower than 60 or higher than 95
    "max_leverage":      (5,     150),    # x — never below 5 or above 150
    "max_loss_per_day":  (-2000, -50),    # USD — worst daily loss floor
    "max_daily_trades":  (3,     100),    # count
    "min_confluences":   (1,     8),      # count
}

# ─── In-memory override cache ─────────────────────────────────────────────────

# engine_key (str) → { param: value, _metadata... }
_overrides: Dict[str, Dict[str, Any]] = {}


# ─── File I/O ─────────────────────────────────────────────────────────────────

def _load_file() -> Dict:
    """Load JSON file. Returns empty structure if missing or corrupt."""
    try:
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and "overrides" in data:
                return data
    except Exception as e:
        logger.warning(f"[Lθ] Params file load failed ({PARAMS_FILE}): {e}")
    return {"version": 1, "overrides": {}, "history": []}


def _save_file(data: Dict):
    """Persist to JSON atomically using a tmp-rename pattern."""
    tmp = PARAMS_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, PARAMS_FILE)
    except Exception as e:
        logger.error(f"[Lθ] Params file save failed: {e}")


# ─── Engine config lookup ─────────────────────────────────────────────────────

def _find_config(engine_configs: Dict, engine_key: str):
    """
    Find an EngineConfig by engine_key string.
    Matches against both EngineType.value (e.g. "yolo_engine") and
    EngineType.name (e.g. "YOLO_ENGINE").
    Returns None if not found.
    """
    for et, cfg in engine_configs.items():
        if et.value == engine_key or et.name == engine_key:
            return cfg
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def load_overrides(engine_configs: Dict) -> int:
    """
    Called once at startup from aeon_engine_system.py.

    Reads ltheta_params.json and applies all stored overrides to the
    live ENGINE_CONFIGS dataclass instances in memory.

    Returns number of individual parameter values applied.
    """
    global _overrides

    data = _load_file()
    stored = data.get("overrides", {})
    _overrides = stored

    applied = 0
    for engine_key, params in stored.items():
        cfg = _find_config(engine_configs, engine_key)
        if cfg is None:
            logger.debug(f"[Lθ] Startup: engine '{engine_key}' not in configs — skipped")
            continue

        for param, value in params.items():
            if param.startswith("_"):   # metadata fields (_last_updated, etc.)
                continue
            if hasattr(cfg, param):
                old = getattr(cfg, param)
                setattr(cfg, param, value)
                applied += 1
                logger.info(
                    "[Lθ] Startup restore: %s.%s = %s (was %s)",
                    engine_key, param, value, old,
                )
            else:
                logger.debug(f"[Lθ] Startup: param '{param}' not on {engine_key} config")

    if applied:
        logger.info("[Lθ] Applied %d stored overrides from ltheta_params.json", applied)
    return applied


def apply_override(
    engine_configs: Dict,
    engine_key: str,
    param: str,
    value: Any,
    *,
    cycle: int = 0,
    H_before: float = 0.0,
    H_after: float = 0.0,
) -> bool:
    """
    Apply a validated Lθ parameter override.

    Steps:
      1. Check bounds — reject if outside PARAM_BOUNDS
      2. Find live EngineConfig — reject if engine not found
      3. Setattr on the live config object (immediate effect, no restart)
      4. Persist to ltheta_params.json
      5. Update in-memory cache

    Returns True if applied, False if rejected.

    Called by omega_cycle._apply_L_theta() after sandbox validates H_new > H_current.
    """
    global _overrides

    # 1. Bounds check
    if param in PARAM_BOUNDS:
        lo, hi = PARAM_BOUNDS[param]
        if not (lo <= value <= hi):
            logger.warning(
                "[Lθ] REJECTED %s.%s = %s — outside bounds [%s, %s]",
                engine_key, param, value, lo, hi,
            )
            return False

    # 2. Find config
    cfg = _find_config(engine_configs, engine_key)
    if cfg is None:
        logger.warning("[Lθ] REJECTED — engine '%s' not in ENGINE_CONFIGS", engine_key)
        return False

    if not hasattr(cfg, param):
        logger.warning("[Lθ] REJECTED — param '%s' not found on %s config", param, engine_key)
        return False

    # 3. Apply in memory — takes effect on the next signal submission
    old_val = getattr(cfg, param)
    setattr(cfg, param, value)
    logger.info(
        "[Lθ] APPLIED: %s.%s: %s → %s  (Ω-cycle %d, H: %.3f → %.3f sim)",
        engine_key, param, old_val, value, cycle, H_before, H_after,
    )

    # 4. Persist to JSON
    data = _load_file()
    if engine_key not in data["overrides"]:
        data["overrides"][engine_key] = {}

    data["overrides"][engine_key][param] = value
    data["overrides"][engine_key]["_last_updated"] = datetime.now(timezone.utc).isoformat()
    data["overrides"][engine_key]["_omega_cycle"] = cycle
    data["overrides"][engine_key]["_H_before"] = round(H_before, 4)
    data["overrides"][engine_key]["_H_after_sim"] = round(H_after, 4)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Append to history for audit trail
    history_entry = {
        "ts":       datetime.now(timezone.utc).isoformat(),
        "engine":   engine_key,
        "param":    param,
        "old":      old_val,
        "new":      value,
        "cycle":    cycle,
        "H_before": round(H_before, 4),
        "H_after":  round(H_after, 4),
    }
    if "history" not in data:
        data["history"] = []
    data["history"].append(history_entry)
    # Keep last 200 history entries
    if len(data["history"]) > 200:
        data["history"] = data["history"][-200:]

    _save_file(data)

    # 5. Update cache
    if engine_key not in _overrides:
        _overrides[engine_key] = {}
    _overrides[engine_key][param] = value

    return True


def get_override(engine_key: str, param: str, default: Any = None) -> Any:
    """Return current override value for a param, or default if none set."""
    return _overrides.get(engine_key, {}).get(param, default)


def get_all_overrides() -> Dict:
    """Return a snapshot of all current overrides. Used by the API/dashboard."""
    # Strip metadata fields from returned copy
    clean: Dict[str, Dict] = {}
    for engine_key, params in _overrides.items():
        clean[engine_key] = {k: v for k, v in params.items() if not k.startswith("_")}
    return clean


def get_history(last_n: int = 50) -> list:
    """Return last N override history entries from the JSON file."""
    data = _load_file()
    history = data.get("history", [])
    return history[-last_n:]
