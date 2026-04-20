"""
System API Routes
Health checks, status, and infrastructure endpoints
"""

from fastapi import APIRouter
import sys
sys.path.append('..')

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def api_system_health():
    """Self-healer status - shows all monitored services and recent healing actions."""
    from server import self_healer
    from feed_health import feed_health
    status = self_healer.get_status()
    status["feed_status"] = feed_health.feed_status
    status["feed_healthy"] = feed_health.is_healthy

    # Server resource snapshot
    try:
        import psutil
        status["server_resources"] = {
            "cpu_pct":  round(psutil.cpu_percent(interval=0.1), 1),
            "ram_pct":  round(psutil.virtual_memory().percent, 1),
            "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 2),
            "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
            "disk_pct": round(psutil.disk_usage("/").percent, 1),
            "disk_free_gb": round(psutil.disk_usage("/").free / 1e9, 1),
        }
    except Exception:
        status["server_resources"] = None

    return status


@router.get("/ws/stats")
async def ws_stats():
    """Get WebSocket connection statistics"""
    from server import ws_manager
    return ws_manager.get_stats()


@router.get("/pairs")
async def api_list_pairs():
    """List all supported trading pairs"""
    return {
        "total_pairs": 44,
        "pairs": [
            "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "SHIB", "DOT",
            "LINK", "TRX", "BCH", "LTC", "NEAR", "UNI", "APT", "ICP", "ETC", "FIL",
            "ATOM", "XLM", "ARB", "OP", "INJ", "HBAR", "VET", "GRT", "AAVE", "ALGO",
            "SAND", "AXS", "MANA", "XTZ", "FLOW", "NEO", "SNX", "CRV", "RUNE", "ZEC",
            "DASH", "COMP", "ENJ", "CHZ"
        ],
        "features": {
            "autonomous_trading": "All 44 pairs scanned every 5 minutes",
            "derivatives": "Funding rates from OKX, Bitget, KuCoin, Gate.io",
            "technical_analysis": "RSI, MACD, BB, EMA, Stoch for all pairs",
            "multi_timeframe": "1h, 4h, 1d analysis available"
        }
    }


@router.get("/news")
async def api_crypto_news(limit: int = 10):
    """Get aggregated crypto news from multiple sources"""
    from additional_data import additional_data
    return await additional_data.get_crypto_news(limit=limit)


# ── EMERGENCY KILL SWITCH ──────────────────────────────────────────────────────
# POST /api/system/kill-switch
# Stops ALL engines and closes all open paper positions at current market price.
# PAPER TRADING ONLY — will hard-refuse if paper_trading is not the active system.
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/kill-switch")
async def api_kill_switch():
    """
    Emergency stop: disable all engines + close all open paper positions.
    PAPER TRADING ONLY. Returns counts of engines stopped and positions closed.
    """
    from aeon_engine_system import get_engine_manager, EngineType
    from paper_trading import paper_trading
    import app_state

    # Safety assertion: this endpoint must NEVER touch real money
    PAPER_ONLY_GUARD = True
    if not PAPER_ONLY_GUARD:
        return {"error": "SAFETY: kill-switch only permitted in paper trading mode"}

    engines_stopped = 0
    positions_closed = 0
    errors = []

    # 1. Disable all engines via per-engine toggle (belt + suspenders on top of global kill)
    try:
        em = get_engine_manager()
        em._global_kill_active = True   # Activate global kill switch
        for et in EngineType:
            em.set_engine_active(et, False)
            engines_stopped += 1
        import logging as _log
        _log.getLogger(__name__).warning(
            f"🛑 [KILL SWITCH] Activated — {engines_stopped} engines disabled"
        )
    except Exception as e:
        errors.append(f"Engine disable error: {e}")

    # 2. Close all open paper positions at current price
    try:
        if paper_trading is not None:
            from paper_trading import ACCOUNTS
            from aeon_engine_system import get_engine_manager as _gem
            mi = app_state.market_intel
            for acc_id in ACCOUNTS:
                account = await paper_trading.get_account(acc_id)
                if not account:
                    continue
                for pos in account.get("positions", []):
                    if pos.get("status") != "open":
                        continue
                    symbol = pos.get("symbol", "")
                    try:
                        current_price = 0.0
                        if mi:
                            ticker = await mi.get_ticker(symbol)
                            current_price = ticker.get("price", 0) if ticker and "error" not in ticker else 0.0
                        if current_price <= 0:
                            current_price = pos.get("entry_price", 0)
                        result = await paper_trading.close_position(
                            account_id=acc_id,
                            position_id=pos.get("position_id") or pos.get("_id", ""),
                            close_price=current_price,
                            reason="KILL_SWITCH",
                        )
                        if "error" not in (result or {}):
                            positions_closed += 1
                    except Exception as pe:
                        errors.append(f"{acc_id}/{symbol} close error: {pe}")
    except Exception as e:
        errors.append(f"Position close error: {e}")

    return {
        "activated":        True,
        "engines_stopped":  engines_stopped,
        "positions_closed": positions_closed,
        "paper_only":       True,
        "errors":           errors,
        "message":          (
            f"Kill switch activated: {engines_stopped} engines stopped, "
            f"{positions_closed} positions closed. Restart backend to re-enable engines."
        ),
    }
