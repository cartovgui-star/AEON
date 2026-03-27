"""
Calculator API Routes
PnL, position sizing, and scenario calculators
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/calc", tags=["calculators"])


@router.get("/pnl")
async def api_calc_pnl(
    entry: float,
    exit: float,
    size: float,
    leverage: int = 1,
    direction: str = "LONG"
):
    """Calculate futures PnL"""
    return state.futures_calc.calculate_pnl(entry, exit, size, leverage, direction)


@router.get("/position")
async def api_calc_position(
    balance: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: int = 1
):
    """Calculate recommended position size"""
    return state.futures_calc.calculate_position_size(balance, risk_pct, entry, stop, leverage)


@router.get("/scenarios")
async def api_calc_scenarios(
    entry: float,
    size: float,
    leverage: int = 1,
    direction: str = "LONG"
):
    """Generate PnL scenarios at different price levels"""
    return state.futures_calc.generate_scenarios(entry, size, leverage, direction)
