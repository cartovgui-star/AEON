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
    return self_healer.get_status()


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
