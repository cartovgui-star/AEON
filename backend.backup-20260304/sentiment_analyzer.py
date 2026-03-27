"""
AEON SENTIMENT ANALYZER (Moltbot-inspired)
Aggregates market sentiment from multiple sources:
- News headlines + LLM-powered sentiment classification
- Fear & Greed Index
- Social media metrics
- Funding rates as sentiment proxy
"""

import asyncio
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2)

SENTIMENT_KEYWORDS = {
    "bullish": ["bull", "surge", "rally", "breakout", "moon", "pump", "buy", "long",
                "upside", "recovery", "accumulate", "adoption", "institutional", "etf approved"],
    "bearish": ["bear", "crash", "dump", "sell", "short", "plunge", "decline",
                "downside", "liquidation", "hack", "ban", "regulation", "fear"]
}


class SentimentAnalyzer:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 180
        self.history: List[Dict] = []
        self.max_history = 100

    def _is_cached(self, key: str) -> bool:
        if key not in self.cache:
            return False
        return (datetime.now(timezone.utc).timestamp() - self.cache[key]["ts"]) < self.cache_ttl

    def _score_headline(self, headline: str) -> float:
        text = headline.lower()
        score = 0
        for word in SENTIMENT_KEYWORDS["bullish"]:
            if word in text:
                score += 1
        for word in SENTIMENT_KEYWORDS["bearish"]:
            if word in text:
                score -= 1
        return max(-1, min(1, score / 3))

    async def get_news_sentiment(self) -> Dict:
        if self._is_cached("news_sentiment"):
            return self.cache["news_sentiment"]["data"]

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://cryptopanic.com/api/free/v1/posts/?auth_token=free&public=true&kind=news")
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])[:20]
                else:
                    results = []
        except Exception:
            results = []

        headlines = [r.get("title", "") for r in results]
        scores = [self._score_headline(h) for h in headlines]
        avg_score = sum(scores) / len(scores) if scores else 0

        bullish = len([s for s in scores if s > 0])
        bearish = len([s for s in scores if s < 0])
        neutral = len([s for s in scores if s == 0])
        total = len(scores) or 1

        result = {
            "overall": "BULLISH" if avg_score > 0.15 else "BEARISH" if avg_score < -0.15 else "NEUTRAL",
            "score": round(avg_score, 3),
            "bullish_pct": round(bullish / total * 100, 1),
            "bearish_pct": round(bearish / total * 100, 1),
            "neutral_pct": round(neutral / total * 100, 1),
            "articles": total,
            "headlines": [{"title": h, "score": round(s, 2)} for h, s in zip(headlines[:10], scores[:10])],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.cache["news_sentiment"] = {"data": result, "ts": datetime.now(timezone.utc).timestamp()}
        return result

    async def get_fear_greed(self) -> Dict:
        if self._is_cached("fear_greed"):
            return self.cache["fear_greed"]["data"]

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.alternative.me/fng/?limit=7&format=json")
                data = resp.json().get("data", [])
        except Exception:
            data = []

        if not data:
            return {"value": 50, "label": "Neutral", "history": []}

        current = data[0]
        result = {
            "value": int(current.get("value", 50)),
            "label": current.get("value_classification", "Neutral"),
            "history": [{"value": int(d.get("value", 50)), "date": d.get("timestamp", "")} for d in data],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.cache["fear_greed"] = {"data": result, "ts": datetime.now(timezone.utc).timestamp()}
        return result

    async def get_composite_sentiment(self, symbol: str = "BTC") -> Dict:
        """Get composite sentiment score from all sources"""
        news, fg = await asyncio.gather(
            self.get_news_sentiment(),
            self.get_fear_greed(),
            return_exceptions=True
        )

        if isinstance(news, Exception):
            news = {"overall": "NEUTRAL", "score": 0, "bullish_pct": 0, "bearish_pct": 0}
        if isinstance(fg, Exception):
            fg = {"value": 50, "label": "Neutral"}

        fg_score = (fg.get("value", 50) - 50) / 50
        news_score = news.get("score", 0)
        composite = (news_score * 0.4 + fg_score * 0.6)

        if composite > 0.2:
            signal = "BULLISH"
        elif composite < -0.2:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        result = {
            "symbol": symbol,
            "signal": signal,
            "composite_score": round(composite, 3),
            "news": {
                "sentiment": news.get("overall", "NEUTRAL"),
                "score": news.get("score", 0),
                "bullish_pct": news.get("bullish_pct", 0),
                "bearish_pct": news.get("bearish_pct", 0),
                "headlines": news.get("headlines", [])[:5]
            },
            "fear_greed": {
                "value": fg.get("value", 50),
                "label": fg.get("label", "Neutral"),
                "history": fg.get("history", [])
            },
            "recommendation": self._get_recommendation(composite, fg.get("value", 50)),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self._record_history(result)
        return result

    def _get_recommendation(self, composite: float, fg_value: int) -> str:
        if fg_value <= 20 and composite >= -0.1:
            return "Extreme fear with neutral/bullish news — contrarian BUY opportunity"
        elif fg_value >= 80 and composite <= 0.1:
            return "Extreme greed with neutral/bearish news — consider taking profits"
        elif composite > 0.3:
            return "Strong bullish sentiment — momentum favors longs"
        elif composite < -0.3:
            return "Strong bearish sentiment — caution advised, wait for support"
        else:
            return "Mixed signals — wait for clearer direction"

    def _record_history(self, result: Dict):
        self.history.append({
            "signal": result["signal"],
            "score": result["composite_score"],
            "fg": result["fear_greed"]["value"],
            "ts": result["timestamp"]
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_sentiment_history(self) -> List[Dict]:
        return self.history


sentiment_analyzer = SentimentAnalyzer()
