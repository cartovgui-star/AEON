"""
Learning System API Routes
AI learning and prediction tracking
"""

from fastapi import APIRouter
import sys
sys.path.append('..')

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/stats")
async def api_learning_stats():
    """Get learning system prediction stats"""
    from learning_system import learning_system
    return await learning_system.get_prediction_stats()


@router.get("/open")
async def api_open_predictions():
    """Get open predictions awaiting resolution"""
    from learning_system import learning_system
    return await learning_system.get_open_predictions()
