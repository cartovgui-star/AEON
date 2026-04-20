from fastapi import APIRouter
from datetime import datetime, timezone
import app_state

router = APIRouter()


# ── GET /api/regime — current market regime summary ──────────────────────────
# Returns a single flat object usable by the frontend dashboard.
# Mirrors /api/regime/global but adds btc_trend from macro direction
# and trading session context.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/regime")
async def get_current_regime():
    """
    Single-endpoint regime summary.
    Returns: {regime, btc_trend, session, entropy, macro_direction, ...}
    """
    from regime_engine import get_regime_engine
    engine = get_regime_engine()

    # Try to get full global regime (includes BTC 1H analysis)
    global_regime = {}
    try:
        if app_state.market_intel:
            global_regime = await engine.get_global_regime(app_state.market_intel)
    except Exception:
        pass

    # Macro direction (BTC EMA20/4H trend gate)
    btc_trend = engine.get_btc_macro_direction()

    # Trading session (NY/ASIA/LONDON/OFF) — derive from UTC hour
    hour = datetime.now(timezone.utc).hour
    if 13 <= hour < 21:
        session = "NY"
    elif 7 <= hour < 16:
        session = "LONDON"
    elif 0 <= hour < 8:
        session = "ASIA"
    else:
        session = "OFF"

    regime_label = (
        global_regime.get("regime")
        or global_regime.get("market_regime")
        or "UNKNOWN"
    )

    return {
        "regime":         regime_label,
        "btc_trend":      btc_trend,
        "session":        session,
        "entropy":        global_regime.get("entropy", 0.0),
        "adx":            global_regime.get("adx", 0.0),
        "macro_direction": btc_trend,
        "details":        global_regime,
    }


@router.get("/api/regime/stats")
async def get_regime_stats():
    from regime_engine import get_regime_engine
    return get_regime_engine().get_stats()


@router.get("/api/regime/global")
async def get_global_regime():
    from regime_engine import get_regime_engine
    return await get_regime_engine().get_global_regime(app_state.market_intel)


@router.get("/api/regime/macro")
async def get_btc_macro_direction():
    """
    Returns the current BTC macro direction (BULLISH/BEARISH/NEUTRAL) from the
    EMA20 4H + daily gate. This is what controls the +10% confidence penalty on
    counter-trend trades.
    """
    from regime_engine import get_regime_engine
    engine = get_regime_engine()
    # Refresh if stale (non-blocking — uses cached value on failure)
    try:
        if app_state.market_intel:
            await engine.refresh_macro_direction(app_state.market_intel)
    except Exception:
        pass

    direction = engine.get_btc_macro_direction()
    updated = engine._macro_updated_at
    age = round((datetime.now(timezone.utc) - updated).total_seconds()) if updated else None

    penalty_direction = "LONG" if direction == "BEARISH" else ("SHORT" if direction == "BULLISH" else None)
    if direction == "BEARISH":
        penalty_label = "LONGs need +10% confidence"
    elif direction == "BULLISH":
        penalty_label = "SHORTs need +10% confidence"
    else:
        penalty_label = "No penalty active"

    return {
        "direction": direction,
        "penalty_direction": penalty_direction,
        "penalty_label": penalty_label,
        "penalty_amount": 10,
        "updated_at": updated.isoformat() if updated else None,
        "cache_age_seconds": age,
    }


@router.get("/api/regime/{symbol}")
async def get_symbol_regime(symbol: str):
    from regime_engine import get_regime_engine
    sym = symbol.upper().replace("-", "/")
    if "/" not in sym:
        sym = sym + "/USDT"
    return await get_regime_engine().detect_regime(sym, app_state.market_intel)
