"""
Bot Status API Routes
Telegram bot statistics and testing
"""

from fastapi import APIRouter
from datetime import datetime, timezone
import sys
sys.path.append('..')

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get("/stats")
async def api_stats():
    """Get bot statistics"""
    from server import db, chat_ids
    
    total = await db.chat_messages.count_documents({})
    unique = len(await db.chat_messages.distinct("chat_id"))
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await db.chat_messages.count_documents({"timestamp": {"$gte": today}})
    freewill = await db.user_settings.count_documents({"free_will": True})
    
    return {
        "total_messages": total,
        "unique_users": unique,
        "messages_today": today_count,
        "freewill_users": freewill,
        "active_users": len(chat_ids)
    }


@router.get("/messages")
async def api_messages(limit: int = 50, context: str = None):
    """Get recent bot messages"""
    from server import db
    
    query = {"context": context} if context else {}
    return await db.chat_messages.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


@router.get("/test")
async def api_test():
    """Test all integrations"""
    import os
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from server import market_intel, mexc_api_key, telegram_token, chat_ids
    
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    
    try:
        # Test Binance
        btc = await market_intel.get_technical_analysis("BTCUSDT", "1h")
        binance_ok = "error" not in btc
        
        # Test LLM
        chat = LlmChat(api_key=emergent_key, session_id="test", system_message="Test").with_model("openai", "gpt-4o-mini")
        await chat.send_message(UserMessage(text="Hi"))
        
        return {
            "status": "success",
            "llm": True,
            "binance": binance_ok,
            "mexc": bool(mexc_api_key),
            "telegram": bool(telegram_token),
            "users": len(chat_ids)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
