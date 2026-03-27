"""
User Profile API Routes
User profiling and personalization
"""

from fastapi import APIRouter, Request
import app_state as state

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile")
async def api_user_profile(chat_id: int = None):
    """Get user profile summary"""
    # For web dashboard, use a default profile or first user
    if not chat_id and state.chat_ids:
        chat_id = list(state.chat_ids)[0]
    elif not chat_id:
        return {"error": "No users found"}
    
    return await state.user_profiler.get_profile_summary(chat_id)


@router.get("/profile/{chat_id}")
async def api_user_profile_by_id(chat_id: int):
    """Get user profile by chat ID"""
    return await state.user_profiler.get_profile_summary(chat_id)


@router.post("/profile/{chat_id}/fact")
async def api_add_user_fact(chat_id: int, request: Request):
    """Add a key fact about the user"""
    data = await request.json()
    fact = data.get("fact", "")
    category = data.get("category", "general")
    
    if not fact:
        return {"error": "Fact is required"}
    
    await state.user_profiler.add_key_fact(chat_id, fact, category)
    return {"status": "ok", "fact": fact}
