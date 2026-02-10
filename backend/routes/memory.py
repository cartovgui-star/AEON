"""
Memory & Journal API Routes
Trade journaling and memory system endpoints
"""

from fastapi import APIRouter, Request
from memory_system import init_memory_system
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter(prefix="/memory", tags=["memory"])

# Get database connection
mongo_url = os.environ.get('MONGO_URL')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
memory_system = init_memory_system(db)


@router.get("/stats")
async def api_memory_stats():
    """Get memory system statistics"""
    return await memory_system.get_system_stats()


@router.get("/journal/stats")
async def api_journal_stats(days: int = 30, symbol: str = None):
    """Get trading journal performance statistics"""
    return await memory_system.journal.get_performance_stats(days, symbol)


@router.get("/journal/trades")
async def api_journal_trades(limit: int = 20):
    """Get recent trades from journal"""
    return await memory_system.journal.get_recent_trades(limit)


@router.post("/journal/log")
async def api_journal_log_trade(request: Request):
    """
    Log a trade to the journal
    
    Body:
    {
        "symbol": "BTC/USDT",
        "direction": "LONG",
        "entry_price": 65000,
        "exit_price": 67000,
        "size": 0.1,
        "leverage": 10,
        "pnl_usd": 200,
        "pnl_pct": 3.08,
        "strategy": "breakout",
        "timeframe": "4h",
        "setup_type": "range_breakout",
        "market_condition": "trending",
        "confidence": 75,
        "notes": "Clean breakout with volume",
        "tags": ["high_volume", "clean_break"]
    }
    """
    data = await request.json()
    return await memory_system.journal.log_trade(data)


@router.get("/journal/patterns")
async def api_journal_patterns(min_trades: int = 5):
    """Get best performing trading patterns"""
    return await memory_system.journal.get_best_patterns(min_trades)


@router.get("/insights")
async def api_insights_latest():
    """Get latest trading insights"""
    return await memory_system.insights.get_latest_insights()


@router.post("/insights/generate")
async def api_insights_generate():
    """Generate new insights from trading data"""
    return await memory_system.insights.generate_insights()


@router.get("/context/{chat_id}")
async def api_get_context(chat_id: int):
    """Get full context for a chat"""
    return await memory_system.get_full_context(chat_id)


@router.post("/preference")
async def api_set_preference(request: Request):
    """
    Set a user preference
    Body: {"chat_id": 123, "key": "risk_level", "value": "aggressive"}
    """
    data = await request.json()
    chat_id = data.get("chat_id")
    key = data.get("key")
    value = data.get("value")
    
    if not all([chat_id, key, value]):
        return {"error": "chat_id, key, and value required"}
    
    await memory_system.remember_preference(chat_id, key, value)
    return {"success": True, "key": key, "value": value}


@router.get("/preference/{chat_id}/{key}")
async def api_get_preference(chat_id: int, key: str):
    """Get a user preference"""
    value = await memory_system.get_preference(chat_id, key)
    return {"key": key, "value": value}


@router.get("/conversation/{chat_id}")
async def api_conversation_history(chat_id: int, limit: int = 20, context_type: str = None):
    """Get conversation history for a chat"""
    return await memory_system.conversation.get_conversation_history(chat_id, limit, context_type)
