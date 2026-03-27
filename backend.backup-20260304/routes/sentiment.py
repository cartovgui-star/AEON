"""
Sentiment Analysis API Routes
Composite sentiment, news, Fear & Greed
"""

from fastapi import APIRouter
import app_state as state

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/composite")
async def api_sentiment_composite(symbol: str = "BTC"):
    """Get composite sentiment from all sources"""
    return await state.sentiment_analyzer.get_composite_sentiment(symbol.upper())


@router.get("/news")
async def api_sentiment_news():
    """Get news sentiment analysis"""
    return await state.sentiment_analyzer.get_news_sentiment()


@router.get("/fear-greed")
async def api_sentiment_fear_greed():
    """Get Fear & Greed Index with history"""
    return await state.sentiment_analyzer.get_fear_greed()


@router.get("/history")
async def api_sentiment_history():
    """Get sentiment history"""
    return {"history": state.sentiment_analyzer.get_sentiment_history()}
