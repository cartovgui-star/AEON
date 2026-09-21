"""
AEON Engine Simulation Routes
GET /api/sim/run?market=mixed&trades=100  — run simulation, return results
GET /api/sim/results                       — return last saved results

Simulation logic delegates to /sim/engine_sim.py which imports real engine
configs from aeon_engine_system.py (ENGINE_CONFIGS, EngineType).
"""

import sys
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# Resolve path to sim module
_BACKEND_DIR = Path(__file__).parent.parent
_SIM_DIR = _BACKEND_DIR.parent / "sim"
_RESULTS_FILE = _SIM_DIR / "sim_results.json"

# Add sim dir to path so we can import engine_sim
if str(_SIM_DIR) not in sys.path:
    sys.path.insert(0, str(_SIM_DIR))

try:
    from engine_sim import run_simulation, save_results
    _SIM_AVAILABLE = True
except ImportError as e:
    _SIM_AVAILABLE = False
    _SIM_IMPORT_ERROR = str(e)


@router.get("/sim/run")
async def run_sim(
    market: str = Query(default="mixed", description="bull | bear | sideways | mixed"),
    trades: int = Query(default=100, ge=50, le=10000, description="Trades per engine (50-10000)"),
):
    """
    Run the engine simulation and return results.

    - market: bull | bear | sideways | mixed
    - trades: number of simulated trades per engine (50–500)

    Engines simulated: autonomous_trader_v2, free_will_v2, dual_engine,
    yolo_engine, vwap_scalper, elite_strategy, day_trader

    Config values sourced from: aeon_engine_system.py ENGINE_CONFIGS
    """
    if not _SIM_AVAILABLE:
        raise HTTPException(status_code=500, detail=f"Simulation module unavailable: {_SIM_IMPORT_ERROR}")

    valid_markets = {"bull", "bear", "sideways", "mixed"}
    if market not in valid_markets:
        raise HTTPException(status_code=400, detail=f"market must be one of {valid_markets}")

    try:
        data = run_simulation(market=market, n_trades=trades)
        save_results(data)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/sim/results")
async def get_sim_results():
    """Return the last saved simulation results from sim/sim_results.json."""
    if not _RESULTS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="No simulation results found. Run GET /api/sim/run first."
        )
    try:
        with open(_RESULTS_FILE, "r") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read results: {str(e)}")
