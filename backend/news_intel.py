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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
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
    
    async def get_latest_news(self, limit: int = 10, filter_coin: str = None) -> List[Dict]:
        """Get latest crypto news from multiple sources"""
        try:
            news = []
            
            # Use multiple RSS feeds for fresh content
            rss_urls = [
                "https://cointelegraph.com/rss",
                "https://blockworks.co/feed/",
                "https://decrypt.co/feed",
            ]
            
            for url in rss_urls:
                try:
                    content = await self._fetch(url, f"news_{url[:30]}", timeout=5)
                    if content and "<?xml" in content[:100]:
                        soup = BeautifulSoup(content, 'xml')
                        items = soup.find_all('item')
                        
                        for item in items[:3]:  # Only top 3 from each source
                            title = item.find('title')
                            link = item.find('link')
                            pub_date = item.find('pubDate')
                            
                            if title:
                                title_text = title.text.strip()
                                sentiment = self._analyze_sentiment(title_text)
                                
                                # Filter by coin if specified
                                if filter_coin:
                                    if filter_coin.lower() not in title_text.lower():
                                        continue
                                
                                news.append({
                                    "title": title_text[:80] + "..." if len(title_text) > 80 else title_text,
                                    "url": link.text if link else "",
                                    "published": pub_date.text if pub_date else "",
                                    "sentiment": sentiment,
                                    "source": "news"
                                })
                except Exception as e:
                    logger.warning(f"RSS fetch error: {e}")
                    continue
            
            # Deduplicate by title similarity
            seen_titles = set()
            unique_news = []
            for n in news:
                title_key = n["title"][:40].lower()
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    unique_news.append(n)
            
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
        """Get crypto social media highlights from Reddit and aggregators"""
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
                        
                        for entry in entries[:2]:  # Top 2 from each sub
                            title = entry.find('title')
                            link = entry.find('link')
                            
                            if title:
                                title_text = title.text.strip()
                                # Skip pinned/meta posts
                                if any(skip in title_text.lower() for skip in ['daily discussion', 'weekly', 'monthly', 'megathread']):
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
    
    async def get_full_news_feed(self) -> Dict:
        """Get comprehensive news feed with news, videos, and social"""
        news = await self.get_latest_news(limit=3)
        videos = await self.get_crypto_videos(limit=2)
        social = await self.get_crypto_social(limit=2)
        
        # Calculate overall sentiment
        all_items = news + social
        bullish = sum(1 for n in all_items if n.get("sentiment", {}).get("label") == "BULLISH")
        bearish = sum(1 for n in all_items if n.get("sentiment", {}).get("label") == "BEARISH")
        
        if bullish > bearish + 1:
            overall = "BULLISH"
        elif bearish > bullish + 1:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        return {
            "news": news,
            "videos": videos,
            "social": social,
            "overall_sentiment": overall,
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
