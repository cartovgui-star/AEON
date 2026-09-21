"""
AEON NEWS & ON-CHAIN INTELLIGENCE
Crypto news, sentiment, whale alerts, and on-chain data
"""

import aiohttp
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class NewsIntel:
    """
    Aggregates news and on-chain intelligence:
    - CryptoPanic: News with sentiment
    - Blockchain.com: On-chain stats
    - Public whale tracking
    """
    
    def __init__(self):
        # API endpoints
        self.cryptopanic_rss = "https://cryptopanic.com/news/rss/"
        self.blockchain_info = "https://api.blockchain.info"
        self.mempool_space = "https://mempool.space/api"
        
        # Cache
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes - fresh but not excessive
    
    async def _fetch(self, url: str, cache_key: str = None, timeout: int = 10) -> str:
        """Fetch URL content"""
        if cache_key and cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if (datetime.now() - ts).seconds < self._cache_ttl:
                return data
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        if cache_key:
                            self._cache[cache_key] = (content, datetime.now())
                        return content
                    return ""
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return ""
    
    async def _fetch_json(self, url: str, cache_key: str = None) -> Dict:
        """Fetch JSON"""
        if cache_key and cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if (datetime.now() - ts).seconds < self._cache_ttl:
                return data
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if cache_key:
                            self._cache[cache_key] = (data, datetime.now())
                        return data
                    return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"JSON fetch error: {e}")
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CRYPTO NEWS (CryptoPanic RSS - Free, no API key needed)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # RSS feed registry: (url, source_name, category, max_items)
    FEED_REGISTRY = [
        # ── Crypto ─────────────────────────────────────────────────────────
        ("https://cointelegraph.com/rss",                       "CoinTelegraph",  "CRYPTO",      3),
        ("https://blockworks.co/feed/",                          "Blockworks",     "CRYPTO",      3),
        ("https://decrypt.co/feed",                              "Decrypt",        "CRYPTO",      2),
        ("https://www.coindesk.com/arc/outboundfeeds/rss/",      "CoinDesk",       "CRYPTO",      2),
        ("https://bitcoinist.com/feed/",                         "Bitcoinist",     "CRYPTO",      2),
        # ── Macro / Traditional markets ────────────────────────────────────
        ("https://feeds.reuters.com/reuters/businessNews",        "Reuters",        "MACRO",       3),
        ("https://feeds.reuters.com/reuters/technologyNews",      "Reuters Tech",   "MACRO",       2),
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC Markets",   "EQUITIES",    2),
        ("https://www.cnbc.com/id/10001147/device/rss/rss.html",  "CNBC Economy",   "MACRO",       2),
        ("https://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch",    "EQUITIES",    2),
        ("https://feeds.marketwatch.com/marketwatch/marketpulse/","MarketWatch",    "EQUITIES",    2),
        ("https://rss.app/feeds/cNWRQ4qEPLkpPkYB.xml",           "Yahoo Finance",  "EQUITIES",    2),
        ("https://www.investing.com/rss/news.rss",                "Investing.com",  "MARKETS",     2),
        # ── Fed / Central Banks ────────────────────────────────────────────
        ("https://feeds.reuters.com/reuters/financialservicesNews","Reuters Finance","FED",         2),
        # ── Commodities / Energy ───────────────────────────────────────────
        ("https://oilprice.com/rss/main",                         "OilPrice",       "COMMODITIES", 2),
        # ── Geopolitical ───────────────────────────────────────────────────
        ("https://feeds.reuters.com/reuters/worldNews",           "Reuters World",  "GEO",         2),
    ]

    # Keywords that force override to MACRO/FED/GEO category
    _MACRO_KW   = ["fed", "fomc", "rate hike", "rate cut", "powell", "inflation", "cpi", "gdp",
                   "recession", "treasury", "yield", "ecb", "boj", "federal reserve", "interest rate",
                   "jobs report", "nonfarm", "payroll", "unemployment"]
    _FED_KW     = ["fed", "fomc", "powell", "federal reserve", "rate hike", "rate cut",
                   "interest rate", "ecb", "lagarde", "boj", "ueda", "central bank"]
    _GEO_KW     = ["war", "sanction", "geopolitical", "conflict", "military", "nato", "tariff",
                   "trade war", "china us", "us china", "middle east", "opec", "iran", "russia"]
    _EQUITY_KW  = ["nasdaq", "s&p", "dow jones", "nyse", "ipo", "earnings", "stock market",
                   "wall street", "sp500", "equities", "shares", "market cap"]
    _COMMODITY_KW=["oil", "gold", "silver", "copper", "wheat", "crude", "natural gas", "commodity"]

    def _categorize_news(self, title: str, default_cat: str) -> str:
        tl = title.lower()
        if any(k in tl for k in self._FED_KW):      return "FED"
        if any(k in tl for k in self._GEO_KW):      return "GEO"
        if any(k in tl for k in self._COMMODITY_KW):return "COMMODITIES"
        if any(k in tl for k in self._EQUITY_KW):   return "EQUITIES"
        if any(k in tl for k in self._MACRO_KW):    return "MACRO"
        return default_cat

    def _impact_score(self, title: str, category: str) -> int:
        """0-100 market impact score based on keywords"""
        tl = title.lower()
        score = 30  # base
        high_impact = ["crash", "collapse", "emergency", "ban", "hack", "war", "surge", "plunge",
                       "fomc", "fed", "rate", "cpi", "etf approval", "sec", "sanctions", "opec"]
        med_impact  = ["regulation", "adoption", "partnership", "lawsuit", "rally", "dump",
                       "earnings", "ipo", "inflation", "jobs", "yield", "payroll"]
        score += sum(15 for k in high_impact if k in tl)
        score += sum(8  for k in med_impact  if k in tl)
        if category in ("FED", "MACRO", "GEO"):  score += 20
        return min(score, 100)

    async def get_latest_news(self, limit: int = 20, filter_coin: str = None) -> List[Dict]:
        """Get latest news from crypto + traditional market sources"""
        try:
            news = []

            async def _fetch_feed(url, source_name, default_cat, max_items):
                try:
                    content = await self._fetch(url, f"news_{url[:35]}", timeout=6)
                    if not content:
                        return []
                    soup = BeautifulSoup(content, 'xml')
                    items = soup.find_all('item')
                    result = []
                    for item in items[:max_items]:
                        title_tag = item.find('title')
                        link_tag  = item.find('link')
                        pub_tag   = item.find('pubDate')
                        if not title_tag:
                            continue
                        title_text = title_tag.get_text(strip=True)
                        if not title_text or len(title_text) < 10:
                            continue
                        if filter_coin and filter_coin.lower() not in title_text.lower():
                            continue
                        cat = self._categorize_news(title_text, default_cat)
                        result.append({
                            "title": title_text[:120] + "…" if len(title_text) > 120 else title_text,
                            "url": link_tag.get_text(strip=True) if link_tag else "",
                            "published": pub_tag.get_text(strip=True) if pub_tag else "",
                            "sentiment": self._analyze_sentiment(title_text),
                            "source": source_name,
                            "category": cat,
                            "impact": self._impact_score(title_text, cat),
                        })
                    return result
                except Exception as e:
                    logger.warning(f"Feed error {source_name}: {e}")
                    return []

            tasks = [_fetch_feed(url, src, cat, mx) for url, src, cat, mx in self.FEED_REGISTRY]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    news.extend(r)

            # Deduplicate by first 45 chars of title
            seen, unique_news = set(), []
            for n in news:
                key = n["title"][:45].lower()
                if key not in seen:
                    seen.add(key)
                    unique_news.append(n)

            # Sort: high-impact first, then by recency proxy (insertion order from fresh feeds)
            unique_news.sort(key=lambda x: x.get("impact", 0), reverse=True)
            return unique_news[:limit]

        except Exception as e:
            logger.error(f"News fetch error: {e}")
            return []
    
    async def get_crypto_videos(self, limit: int = 3) -> List[Dict]:
        """Get latest crypto YouTube videos from top channels"""
        try:
            videos = []
            
            # Top crypto YouTube channel RSS feeds
            youtube_feeds = [
                ("Coin Bureau", "https://www.youtube.com/feeds/videos.xml?channel_id=UCqK_GSMbpiV8spgD3ZGloSw"),
                ("Benjamin Cowen", "https://www.youtube.com/feeds/videos.xml?channel_id=UCRvqjQPSeaWn-uEx-w0XOIg"),
                ("DataDash", "https://www.youtube.com/feeds/videos.xml?channel_id=UCCatR7nWbYrkVXdxXb4cGXw"),
            ]
            
            for channel_name, feed_url in youtube_feeds:
                try:
                    content = await self._fetch(feed_url, f"yt_{channel_name}", timeout=5)
                    if content:
                        soup = BeautifulSoup(content, 'xml')
                        entries = soup.find_all('entry')
                        
                        for entry in entries[:1]:  # Latest video from each channel
                            title = entry.find('title')
                            link = entry.find('link')
                            published = entry.find('published')
                            
                            if title:
                                video_id = ""
                                if link and link.get('href'):
                                    video_id = link.get('href').split('v=')[-1] if 'v=' in link.get('href', '') else ""
                                
                                videos.append({
                                    "title": title.text[:60] + "..." if len(title.text) > 60 else title.text,
                                    "channel": channel_name,
                                    "url": link.get('href') if link else "",
                                    "published": published.text[:10] if published else "",
                                    "source": "youtube"
                                })
                except Exception as e:
                    logger.warning(f"YouTube feed error for {channel_name}: {e}")
                    continue
            
            return videos[:limit]
            
        except Exception as e:
            logger.error(f"Video fetch error: {e}")
            return []
    
    async def get_crypto_social(self, limit: int = 3) -> List[Dict]:
        """Get crypto social media highlights from Reddit and crypto Twitter aggregators"""
        try:
            social = []
            
            # Reddit crypto RSS feeds (public, no auth needed)
            reddit_feeds = [
                ("r/CryptoCurrency", "https://www.reddit.com/r/CryptoCurrency/hot.rss"),
                ("r/Bitcoin", "https://www.reddit.com/r/Bitcoin/hot.rss"),
            ]
            
            for sub_name, feed_url in reddit_feeds:
                try:
                    content = await self._fetch(feed_url, f"reddit_{sub_name}", timeout=5)
                    if content and "<feed" in content[:200]:
                        soup = BeautifulSoup(content, 'xml')
                        entries = soup.find_all('entry')
                        
                        for entry in entries[:4]:  # Check more to filter
                            title = entry.find('title')
                            link = entry.find('link')
                            
                            if title:
                                title_text = title.text.strip()
                                # Skip pinned/meta posts
                                if any(skip in title_text.lower() for skip in ['daily discussion', 'daily crypto', 'weekly', 'monthly', 'megathread', 'skeptics', 'self-stories']):
                                    continue
                                
                                social.append({
                                    "title": title_text[:70] + "..." if len(title_text) > 70 else title_text,
                                    "url": link.get('href') if link else "",
                                    "source": "reddit",
                                    "sub": sub_name,
                                    "sentiment": self._analyze_sentiment(title_text)
                                })
                except Exception as e:
                    logger.warning(f"Reddit feed error for {sub_name}: {e}")
                    continue
            
            # Deduplicate
            seen = set()
            unique = []
            for s in social:
                key = s["title"][:30].lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(s)
            
            return unique[:limit]
            
        except Exception as e:
            logger.error(f"Social fetch error: {e}")
            return []
    
    async def get_crypto_twitter(self, limit: int = 2) -> List[Dict]:
        """Get crypto Twitter/X highlights via aggregator feeds"""
        try:
            tweets = []
            
            # Use Bitcoinist which often aggregates Twitter news
            twitter_sources = [
                ("Bitcoinist", "https://bitcoinist.com/feed/"),
                ("NewsBTC", "https://www.newsbtc.com/feed/"),
            ]
            
            for source_name, feed_url in twitter_sources:
                try:
                    content = await self._fetch(feed_url, f"twitter_{source_name}", timeout=5)
                    if content and ("<?xml" in content[:200] or "<rss" in content[:200]):
                        soup = BeautifulSoup(content, 'xml')
                        items = soup.find_all('item')
                        
                        for item in items[:2]:
                            title = item.find('title')
                            link = item.find('link')
                            
                            if title:
                                title_text = title.text.strip()
                                tweets.append({
                                    "title": title_text[:65] + "..." if len(title_text) > 65 else title_text,
                                    "url": link.text if link else "",
                                    "source": source_name
                                })
                except Exception as e:
                    logger.warning(f"Twitter source error for {source_name}: {e}")
                    continue
            
            return tweets[:limit]
            
        except Exception as e:
            logger.error(f"Twitter fetch error: {e}")
            return []
    
    async def get_full_news_feed(self) -> Dict:
        """Get comprehensive news feed with news, videos, reddit, and twitter"""
        news = await self.get_latest_news(limit=3)
        videos = await self.get_crypto_videos(limit=2)
        social = await self.get_crypto_social(limit=2)
        twitter = await self.get_crypto_twitter(limit=2)
        
        return {
            "news": news,
            "videos": videos,
            "social": social,
            "twitter": twitter,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _analyze_sentiment(self, text: str) -> Dict:
        """Simple sentiment analysis based on keywords"""
        text_lower = text.lower()
        
        bullish_words = ['surge', 'soar', 'rally', 'bullish', 'pump', 'moon', 'breakout', 
                        'ath', 'all-time high', 'adoption', 'partnership', 'approval',
                        'buy', 'accumulate', 'growth', 'gains', 'profit', 'up']
        bearish_words = ['crash', 'dump', 'plunge', 'bearish', 'sell', 'fear', 'panic',
                        'hack', 'scam', 'fraud', 'lawsuit', 'ban', 'regulation', 
                        'down', 'drop', 'fall', 'loss', 'decline', 'warning']
        
        bull_count = sum(1 for w in bullish_words if w in text_lower)
        bear_count = sum(1 for w in bearish_words if w in text_lower)
        
        if bull_count > bear_count + 1:
            return {"label": "BULLISH", "score": min(bull_count * 20, 100), "emoji": "🟢"}
        elif bear_count > bull_count + 1:
            return {"label": "BEARISH", "score": min(bear_count * 20, 100), "emoji": "🔴"}
        else:
            return {"label": "NEUTRAL", "score": 50, "emoji": "⚪"}
    
    async def get_news_sentiment_summary(self, limit: int = 20) -> Dict:
        """Get overall news sentiment from recent articles"""
        news = await self.get_latest_news(limit)
        
        if not news:
            return {"sentiment": "UNKNOWN", "score": 50}
        
        bullish = sum(1 for n in news if n["sentiment"]["label"] == "BULLISH")
        bearish = sum(1 for n in news if n["sentiment"]["label"] == "BEARISH")
        
        total = len(news)
        bull_pct = (bullish / total) * 100
        bear_pct = (bearish / total) * 100
        
        if bull_pct > 60:
            overall = "BULLISH"
        elif bear_pct > 60:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        return {
            "sentiment": overall,
            "bullish_pct": round(bull_pct, 1),
            "bearish_pct": round(bear_pct, 1),
            "neutral_pct": round(100 - bull_pct - bear_pct, 1),
            "articles_analyzed": total,
            "recent_headlines": [n["title"] for n in news[:5]]
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ON-CHAIN DATA (Bitcoin via blockchain.info & mempool.space - Free)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_btc_onchain_stats(self) -> Dict:
        """Get Bitcoin on-chain statistics"""
        try:
            # Mempool.space stats (free, no auth)
            stats = await self._fetch_json(f"{self.mempool_space}/v1/mining/pools/1w", "mempool_pools")
            fees = await self._fetch_json(f"{self.mempool_space}/v1/fees/recommended", "mempool_fees")
            hashrate = await self._fetch_json(f"{self.mempool_space}/v1/mining/hashrate/1w", "mempool_hashrate")
            
            # Process
            result = {
                "network": "Bitcoin",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Fees
            if fees and "error" not in fees:
                result["fees"] = {
                    "fastest": fees.get("fastestFee", 0),
                    "half_hour": fees.get("halfHourFee", 0),
                    "hour": fees.get("hourFee", 0),
                    "economy": fees.get("economyFee", 0),
                    "minimum": fees.get("minimumFee", 0),
                }
                
                # High fees = high demand = potentially bullish
                if fees.get("fastestFee", 0) > 50:
                    result["fee_interpretation"] = "🔥 HIGH DEMAND - Network congested"
                elif fees.get("fastestFee", 0) > 20:
                    result["fee_interpretation"] = "📈 MODERATE DEMAND"
                else:
                    result["fee_interpretation"] = "😴 LOW DEMAND"
            
            # Hashrate
            if hashrate and "error" not in hashrate and hashrate.get("hashrates"):
                latest = hashrate["hashrates"][-1] if hashrate["hashrates"] else {}
                result["hashrate"] = {
                    "current": f"{latest.get('avgHashrate', 0) / 1e18:.2f} EH/s",
                    "timestamp": latest.get("timestamp")
                }
            
            return result
            
        except Exception as e:
            logger.error(f"BTC on-chain error: {e}")
            return {"error": str(e)}
    
    async def get_exchange_flow_estimate(self) -> Dict:
        """
        Estimate exchange flows based on available public data.
        Note: True exchange flow requires paid APIs like Glassnode.
        This uses fee/mempool data as proxy indicators.
        """
        try:
            # Get mempool data
            mempool = await self._fetch_json(f"{self.mempool_space}/mempool", "mempool_info")
            
            if "error" in mempool:
                return {"error": "Mempool data unavailable"}
            
            tx_count = mempool.get("count", 0)
            vsize = mempool.get("vsize", 0)
            
            # Estimate based on mempool congestion
            # High mempool = lots of pending transactions = potential selling pressure
            if tx_count > 100000:
                flow_estimate = "🔴 HIGH OUTFLOW PRESSURE"
                interpretation = "Very congested mempool - possible exchange deposits"
            elif tx_count > 50000:
                flow_estimate = "🟡 MODERATE ACTIVITY"
                interpretation = "Normal transaction volume"
            else:
                flow_estimate = "🟢 LOW ACTIVITY"
                interpretation = "Low mempool - accumulation phase possible"
            
            return {
                "mempool_tx_count": tx_count,
                "mempool_size_mb": round(vsize / 1_000_000, 2),
                "flow_estimate": flow_estimate,
                "interpretation": interpretation,
                "note": "Estimate based on mempool. Real exchange flow requires premium APIs."
            }
            
        except Exception as e:
            logger.error(f"Exchange flow error: {e}")
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WHALE TRACKING (Free public sources)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_large_transactions(self) -> List[Dict]:
        """
        Get recent large BTC transactions from mempool.
        Filters for transactions > 10 BTC
        """
        try:
            # Get recent transactions
            recent = await self._fetch_json(f"{self.mempool_space}/mempool/recent", "mempool_recent")
            
            if not recent or "error" in recent:
                return []
            
            large_txs = []
            for tx in recent[:100]:
                # Value in satoshis
                value = tx.get("value", 0)
                btc_value = value / 100_000_000
                
                if btc_value >= 10:  # > 10 BTC
                    large_txs.append({
                        "txid": tx.get("txid", "")[:16] + "...",
                        "value_btc": round(btc_value, 2),
                        "value_usd_approx": f"~${btc_value * 65000:,.0f}",  # Rough estimate
                        "fee_rate": tx.get("rate", 0),
                        "size": "🐋 WHALE" if btc_value >= 100 else "🐟 LARGE"
                    })
            
            return large_txs[:10]  # Top 10 largest
            
        except Exception as e:
            logger.error(f"Whale tracking error: {e}")
            return []
    
    async def get_whale_summary(self) -> Dict:
        """Get whale activity summary"""
        txs = await self.get_large_transactions()
        
        if not txs:
            return {"activity": "LOW", "message": "No large transactions detected recently"}
        
        total_btc = sum(t["value_btc"] for t in txs)
        whale_count = sum(1 for t in txs if t["size"] == "🐋 WHALE")
        
        if whale_count >= 3 or total_btc > 500:
            activity = "HIGH"
            emoji = "🔴"
        elif whale_count >= 1 or total_btc > 100:
            activity = "MODERATE"
            emoji = "🟡"
        else:
            activity = "LOW"
            emoji = "🟢"
        
        return {
            "activity": activity,
            "emoji": emoji,
            "large_transactions": len(txs),
            "whale_transactions": whale_count,
            "total_btc_moved": round(total_btc, 2),
            "transactions": txs[:5]
        }


class FuturesCalculator:
    """
    Futures position calculator with leverage
    """
    
    @staticmethod
    def calculate_pnl(
        entry_price: float,
        exit_price: float,
        position_size: float,  # in USD or coin amount
        leverage: int = 1,
        direction: str = "LONG",
        is_coin_size: bool = False
    ) -> Dict:
        """
        Calculate profit/loss for a futures position
        
        Args:
            entry_price: Entry price
            exit_price: Exit price (or current price)
            position_size: Position size in USD or coins
            leverage: Leverage multiplier (1-125)
            direction: LONG or SHORT
            is_coin_size: If True, position_size is in coins, not USD
        """
        # Calculate position value
        if is_coin_size:
            position_value_usd = position_size * entry_price
            coins = position_size
        else:
            position_value_usd = position_size
            coins = position_size / entry_price
        
        # Calculate price change percentage
        if direction.upper() == "LONG":
            price_change_pct = ((exit_price - entry_price) / entry_price) * 100
        else:  # SHORT
            price_change_pct = ((entry_price - exit_price) / entry_price) * 100
        
        # Apply leverage
        pnl_pct = price_change_pct * leverage
        pnl_usd = (position_value_usd * pnl_pct) / 100
        
        # Calculate liquidation price
        # Liquidation when loss = 100% of margin (position_value / leverage)
        margin = position_value_usd / leverage
        
        if direction.upper() == "LONG":
            liq_price = entry_price * (1 - (1 / leverage) + 0.005)  # 0.5% buffer
        else:
            liq_price = entry_price * (1 + (1 / leverage) - 0.005)
        
        # ROI based on margin (actual capital used)
        roi_pct = (pnl_usd / margin) * 100 if margin > 0 else 0
        
        return {
            "direction": direction.upper(),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "leverage": leverage,
            "position_size_usd": round(position_value_usd, 2),
            "margin_required": round(margin, 2),
            "coins": round(coins, 6),
            "price_change_pct": round(price_change_pct, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_usd": round(pnl_usd, 2),
            "roi_on_margin": round(roi_pct, 2),
            "liquidation_price": round(liq_price, 2),
            "status": "PROFIT" if pnl_usd > 0 else "LOSS" if pnl_usd < 0 else "BREAKEVEN"
        }
    
    @staticmethod
    def calculate_position_size(
        account_balance: float,
        risk_pct: float,
        entry_price: float,
        stop_loss_price: float,
        leverage: int = 1
    ) -> Dict:
        """
        Calculate safe position size based on risk management
        
        Args:
            account_balance: Total account balance in USD
            risk_pct: Percentage of account willing to risk (e.g., 2 for 2%)
            entry_price: Entry price
            stop_loss_price: Stop loss price
            leverage: Leverage to use
        """
        risk_amount = account_balance * (risk_pct / 100)
        
        # Calculate price distance to stop loss
        stop_distance_pct = abs((entry_price - stop_loss_price) / entry_price) * 100
        
        # With leverage, the effective stop distance
        effective_stop_pct = stop_distance_pct * leverage
        
        # Position size where stop loss = risk amount
        if effective_stop_pct > 0:
            position_size = (risk_amount / effective_stop_pct) * 100
        else:
            position_size = 0
        
        margin_required = position_size / leverage
        coins = position_size / entry_price if entry_price > 0 else 0
        
        return {
            "account_balance": account_balance,
            "risk_pct": risk_pct,
            "risk_amount_usd": round(risk_amount, 2),
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "stop_distance_pct": round(stop_distance_pct, 2),
            "leverage": leverage,
            "recommended_position_size": round(position_size, 2),
            "margin_required": round(margin_required, 2),
            "coins_to_buy": round(coins, 6),
            "max_loss_at_stop": round(risk_amount, 2)
        }
    
    @staticmethod
    def generate_scenarios(
        entry_price: float,
        position_size: float,
        leverage: int,
        direction: str = "LONG"
    ) -> List[Dict]:
        """Generate PnL scenarios at different price levels"""
        scenarios = []
        
        # Calculate at various price changes
        changes = [-20, -15, -10, -5, -3, -1, 0, 1, 3, 5, 10, 15, 20]
        
        for change in changes:
            if direction.upper() == "LONG":
                exit_price = entry_price * (1 + change/100)
            else:
                exit_price = entry_price * (1 - change/100)
            
            result = FuturesCalculator.calculate_pnl(
                entry_price=entry_price,
                exit_price=exit_price,
                position_size=position_size,
                leverage=leverage,
                direction=direction
            )
            
            scenarios.append({
                "price_change": f"{change:+d}%",
                "exit_price": round(exit_price, 2),
                "pnl_usd": result["pnl_usd"],
                "pnl_pct": result["pnl_pct"],
                "status": result["status"]
            })
        
        return scenarios


# Global instances
news_intel = NewsIntel()
futures_calc = FuturesCalculator()
