"""
AEON ENHANCED MARKET INTELLIGENCE
Real free APIs for comprehensive crypto data
"""

import aiohttp
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import ccxt

logger = logging.getLogger(__name__)


class EnhancedMarketIntel:
    """
    Aggregates data from multiple FREE APIs:
    - CoinGecko: Top 100 coins, prices, market data
    - Alternative.me: Fear & Greed Index
    - MEXC: Orderbook, prices, funding rates, open interest (via ccxt + contract API)
    """
    
    def __init__(self):
        # OKX for spot data
        self.okx = ccxt.okx({'enableRateLimit': True})
        
        # API endpoints
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.fear_greed_api = "https://api.alternative.me/fng"
        self.livecoinwatch_base = "https://api.livecoinwatch.com"
        self.livecoinwatch_key = os.environ.get("LIVECOINWATCH_API_KEY", "")
        self.coinbase_base = "https://api.coinbase.com/v2"
        
        # Cache for rate limiting
        self._cache = {}
        self._cache_ttl = 120  # 2 minute cache to avoid rate limits
        
        # Top coins list
        self.tracked_symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", 
            "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "TRX/USDT",
            "UNI/USDT", "ATOM/USDT", "LTC/USDT", "BCH/USDT", "NEAR/USDT",
            "APT/USDT", "ARB/USDT", "OP/USDT", "FIL/USDT", "INJ/USDT"
        ]
    
    async def _fetch_json(self, url: str, cache_key: str = None) -> Dict:
        """Fetch JSON with caching"""
        if cache_key and cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if cache_key:
                            self._cache[cache_key] = (data, datetime.now())
                        return data
                    else:
                        logger.error(f"API error {resp.status}: {url}")
                        return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LIVECOINWATCH - PRIMARY PRICE SOURCE
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_livecoinwatch_prices(self) -> List[Dict]:
        """Get top 50 coin prices from LiveCoinWatch API (ranked by market cap)"""
        if not self.livecoinwatch_key:
            logger.warning("LCW: no API key configured")
            return []
        try:
            payload = {
                "currency": "USD",
                "sort": "rank",
                "order": "ascending",
                "offset": 0,
                "limit": 50,
                "meta": True
            }
            headers = {
                "x-api-key": self.livecoinwatch_key,
                "content-type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.livecoinwatch_base}/coins/list",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"LCW error {resp.status}")
                        return []
                    data = await resp.json()

            results = []
            for i, coin in enumerate(data):
                delta = coin.get("delta", {})
                results.append({
                    "symbol": (coin.get("code") or "").lower().lstrip("_"),
                    "name": coin.get("name", ""),
                    "current_price": coin.get("rate", 0),
                    "price_change_percentage_1h": round((delta.get("hour", 1) - 1) * 100, 2),
                    "price_change_percentage_24h": round((delta.get("day", 1) - 1) * 100, 2),
                    "price_change_percentage_7d": round((delta.get("week", 1) - 1) * 100, 2),
                    "market_cap": coin.get("cap", 0),
                    "market_cap_rank": coin.get("rank", i + 1),
                    "total_volume": coin.get("volume", 0),
                    "high_24h": 0,
                    "low_24h": 0,
                    "source": "livecoinwatch"
                })
            logger.info(f"LCW: fetched {len(results)} coins")
            return results
        except Exception as e:
            logger.error(f"LCW prices error: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # COINBASE - PUBLIC SPOT PRICE CHECK (no auth required)
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_coinbase_spot_prices(self) -> Dict[str, float]:
        """Get spot prices for BTC/ETH/SOL from Coinbase public API (no key needed)"""
        pairs = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD"]
        prices = {}
        try:
            async with aiohttp.ClientSession() as session:
                for pair in pairs:
                    try:
                        async with session.get(
                            f"{self.coinbase_base}/prices/{pair}/spot",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                d = await resp.json()
                                coin = pair.split("-")[0]
                                prices[coin] = float(d.get("data", {}).get("amount", 0))
                    except Exception:
                        pass
            return prices
        except Exception as e:
            logger.error(f"Coinbase spot error: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # COINGECKO - TOP 100 COINS (with OKX fallback)
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_mexc_prices(self) -> List[Dict]:
        """Get prices from OKX for top coins"""
        try:
            # Top 20 for quick loading (full 44 would be slow)
            primary_symbols = [
                "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
                "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
                "TRX/USDT", "LTC/USDT", "NEAR/USDT", "UNI/USDT", "APT/USDT",
                "ATOM/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT", "AAVE/USDT"
            ]
            tickers = self.okx.fetch_tickers(primary_symbols)
            
            results = []
            for i, symbol in enumerate(primary_symbols):
                if symbol in tickers:
                    t = tickers[symbol]
                    coin = symbol.split('/')[0]
                    results.append({
                        "symbol": coin.lower(),
                        "name": coin,
                        "current_price": t.get("last", 0),
                        "price_change_percentage_24h": t.get("percentage", 0),
                        "market_cap_rank": i + 1,
                        "high_24h": t.get("high", 0),
                        "low_24h": t.get("low", 0),
                        "total_volume": t.get("quoteVolume", 0),
                    })
            return results
        except Exception as e:
            logger.error(f"MEXC prices error: {e}")
            return []
    
    async def get_top_100_coins(self) -> List[Dict]:
        """Get top coins — priority: LiveCoinWatch → MEXC → CoinGecko"""
        # 1. LiveCoinWatch (best data: rank, market cap, 1h/24h/7d deltas)
        coins = await self.get_livecoinwatch_prices()
        if coins:
            return coins

        # 2. MEXC fallback (fast but no market cap data)
        coins = await self.get_mexc_prices()
        if coins:
            return coins

        # 3. CoinGecko last resort (rate-limited)
        url = f"{self.coingecko_base}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h,24h,7d"
        data = await self._fetch_json(url, "top100")
        if isinstance(data, list) and len(data) > 0:
            return data
        return []
    
    async def get_coin_data(self, coin_id: str) -> Dict:
        """Get detailed data for a specific coin"""
        url = f"{self.coingecko_base}/coins/{coin_id}?localization=false&tickers=false&community_data=false&developer_data=false"
        return await self._fetch_json(url, f"coin_{coin_id}")
    
    async def get_trending_coins(self) -> List[Dict]:
        """Get trending coins (searched most in last 24h)"""
        url = f"{self.coingecko_base}/search/trending"
        data = await self._fetch_json(url, "trending")
        if "coins" in data:
            return [c.get("item", {}) for c in data["coins"]]
        return []
    
    async def get_global_market_data(self) -> Dict:
        """Get global crypto market stats - with MEXC fallback for BTC dominance"""
        url = f"{self.coingecko_base}/global"
        data = await self._fetch_json(url, "global")
        
        if "data" in data:
            d = data["data"]
            return {
                "total_market_cap": d.get("total_market_cap", {}).get("usd", 0),
                "total_volume_24h": d.get("total_volume", {}).get("usd", 0),
                "btc_dominance": d.get("market_cap_percentage", {}).get("btc", 0),
                "eth_dominance": d.get("market_cap_percentage", {}).get("eth", 0),
                "active_cryptos": d.get("active_cryptocurrencies", 0),
                "markets": d.get("markets", 0),
                "market_cap_change_24h": d.get("market_cap_change_percentage_24h_usd", 0),
            }
        
        # Fallback: try to get BTC price at minimum
        try:
            btc_ticker = self.okx.fetch_ticker("BTC/USDT")
            btc_price = btc_ticker.get("last", 0)
            # Estimate market cap based on BTC price (rough approximation)
            # BTC typically represents ~50% of crypto market
            estimated_btc_mcap = btc_price * 19_700_000  # ~19.7M BTC supply
            estimated_total = estimated_btc_mcap / 0.55  # Assume 55% dominance
            
            return {
                "total_market_cap": estimated_total,
                "total_volume_24h": 0,
                "btc_dominance": 55.0,
                "eth_dominance": 15.0,
                "active_cryptos": 0,
                "markets": 0,
                "market_cap_change_24h": 0,
                "estimated": True
            }
        except Exception as e:
            logger.warning(f"Global market fallback failed: {e}")
            return {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FEAR & GREED INDEX
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_fear_greed_index(self, days: int = 1) -> Dict:
        """Get Fear & Greed Index (0=Extreme Fear, 100=Extreme Greed)"""
        url = f"{self.fear_greed_api}/?limit={days}"
        data = await self._fetch_json(url, f"fng_{days}")
        
        if "data" in data and data["data"]:
            latest = data["data"][0]
            return {
                "value": int(latest.get("value", 50)),
                "classification": latest.get("value_classification", "Neutral"),
                "timestamp": datetime.fromtimestamp(int(latest.get("timestamp", 0)), tz=timezone.utc).isoformat(),
                "history": data["data"] if days > 1 else None
            }
        return {"value": 50, "classification": "Neutral"}
    
    def interpret_fear_greed(self, value: int) -> str:
        """Get trading interpretation of Fear & Greed"""
        if value <= 20:
            return "EXTREME FEAR - Historically good buying opportunity"
        elif value <= 40:
            return "FEAR - Market is worried, potential accumulation zone"
        elif value <= 60:
            return "NEUTRAL - No strong sentiment either way"
        elif value <= 80:
            return "GREED - Market is getting overconfident, be cautious"
        else:
            return "EXTREME GREED - Market euphoria, high risk of correction"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DERIVATIVES DATA - Using available sources
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict:
        """Get funding rate from available sources"""
        try:
            # Try OKX first (via ccxt)
            base = symbol.replace("USDT", "")

            # OKX uses swap format
            try:
                okx_ex = ccxt.okx({'enableRateLimit': True})
                funding = okx_ex.fetch_funding_rate(f"{base}/USDT:USDT")

                rate = funding.get("fundingRate", 0) or 0
                return {
                    "symbol": symbol,
                    "source": "OKX",
                    "funding_rate": rate,
                    "funding_rate_pct": f"{rate * 100:.4f}%",
                    "is_positive": rate > 0,
                    "interpretation": "Longs pay shorts" if rate > 0 else "Shorts pay longs"
                }
            except Exception as okx_err:
                logger.warning(f"OKX funding error: {okx_err}")
            
            # Fallback: use estimate based on market conditions
            fng = await self.get_fear_greed_index()
            fg_value = fng.get("value", 50)
            
            # Estimate funding based on sentiment
            if fg_value < 25:
                est_rate = -0.0001  # Slight negative in extreme fear
            elif fg_value < 40:
                est_rate = 0.0001
            elif fg_value > 75:
                est_rate = 0.0005  # Positive in extreme greed
            elif fg_value > 60:
                est_rate = 0.0003
            else:
                est_rate = 0.0001
            
            return {
                "symbol": symbol,
                "source": "ESTIMATED",
                "funding_rate": est_rate,
                "funding_rate_pct": f"{est_rate * 100:.4f}%",
                "is_positive": est_rate > 0,
                "interpretation": "Longs pay shorts" if est_rate > 0 else "Shorts pay longs",
                "note": "Estimated based on market sentiment"
            }
            
        except Exception as e:
            logger.error(f"Funding error: {e}")
            return {"symbol": symbol, "error": str(e)}
    
    async def get_open_interest_estimate(self, symbol: str = "BTCUSDT") -> Dict:
        """Get open interest estimate"""
        try:
            # Use market data to estimate OI trends
            global_data = await self.get_global_market_data()
            
            return {
                "symbol": symbol,
                "note": "OI data requires exchange API access",
                "market_volume_24h": global_data.get("total_volume_24h", 0),
                "market_trend": "HIGH" if global_data.get("market_cap_change_24h", 0) > 5 else "LOW" if global_data.get("market_cap_change_24h", 0) < -5 else "NEUTRAL"
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}
    
    async def get_mexc_recent_trades(self, symbol: str = "BTC-USDT", limit: int = 50) -> List[Dict]:
        """Get recent ticker from OKX (replaces MEXC contract ticker)."""
        okx_inst = symbol.replace("/", "-").replace("_", "-").upper()
        if not okx_inst.endswith("-USDT"):
            okx_inst = okx_inst.replace("USDT", "-USDT") if "USDT" in okx_inst else okx_inst + "-USDT"
        url = f"https://www.okx.com/api/v5/market/ticker?instId={okx_inst}-SWAP"
        data = await self._fetch_json(url, f"okx_ticker_{okx_inst}")
        items = data.get("data", [])
        if items:
            d = items[0]
            return [{
                "symbol": okx_inst,
                "price": float(d.get("last", 0)),
                "volume": float(d.get("vol24h", 0)),
                "timestamp": str(d.get("ts", "")),
            }]
        return []

    async def get_mexc_tickers(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """Get tickers for multiple symbols from OKX (replaces MEXC contract API)."""
        if not symbols:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "AVAXUSDT"]

        results = {}
        for symbol in symbols:
            base = symbol.replace("USDT", "")
            okx_inst = f"{base}-USDT-SWAP"
            url = f"https://www.okx.com/api/v5/market/ticker?instId={okx_inst}"
            data = await self._fetch_json(url, f"okx_cticker_{okx_inst}")
            items = data.get("data", [])
            if items:
                item = items[0]
                results[symbol] = {
                    "price": float(item.get("last", 0)),
                    "change_24h": 0.0,  # OKX doesn't return % change in this endpoint
                    "volume_24h": float(item.get("volCcy24h", 0)),
                    "high_24h": float(item.get("high24h", 0)),
                    "low_24h": float(item.get("low24h", 0)),
                    "funding_rate": 0.0,
                    "open_interest": float(item.get("oi", 0)),
                }
        return results
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AGGREGATED INTELLIGENCE
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_market_intelligence(self, symbol: str = "BTCUSDT") -> Dict:
        """Get comprehensive market intelligence for a symbol"""
        try:
            # Fetch all data concurrently
            funding_task = self.get_funding_rate(symbol)
            oi_task = self.get_open_interest_estimate(symbol)
            fng_task = self.get_fear_greed_index()
            global_task = self.get_global_market_data()
            
            funding, oi, fng, global_data = await asyncio.gather(
                funding_task, oi_task, fng_task, global_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(funding, Exception):
                funding = {"error": str(funding)}
            if isinstance(oi, Exception):
                oi = {"error": str(oi)}
            if isinstance(fng, Exception):
                fng = {"value": 50, "classification": "Unknown"}
            if isinstance(global_data, Exception):
                global_data = {}
            
            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "funding": funding,
                "open_interest": oi,
                "fear_greed": {
                    "value": fng.get("value", 50),
                    "classification": fng.get("classification", "Neutral"),
                    "interpretation": self.interpret_fear_greed(fng.get("value", 50))
                },
                "global_market": global_data,
            }
        except Exception as e:
            logger.error(f"Market intelligence error: {e}")
            return {"error": str(e)}
    
    async def get_market_summary(self) -> str:
        """Generate a human-readable market summary with MEXC fallbacks"""
        try:
            # Get all data from working APIs
            fng = await self.get_fear_greed_index()
            global_data = await self.get_global_market_data()
            top_coins = await self.get_top_100_coins()
            trending = await self.get_trending_coins()
            
            # If CoinGecko fails, try MEXC prices
            if not top_coins:
                top_coins = await self.get_mexc_prices()
            
            # Extract BTC, ETH, SOL from top coins
            btc = next((c for c in top_coins if str(c.get("symbol", "")).lower() == "btc"), {})
            eth = next((c for c in top_coins if str(c.get("symbol", "")).lower() == "eth"), {})
            sol = next((c for c in top_coins if str(c.get("symbol", "")).lower() == "sol"), {})
            
            # Format market cap - show N/A if zero
            mcap = global_data.get('total_market_cap', 0)
            mcap_str = f"${mcap/1e12:.2f}T" if mcap > 0 else "N/A (API rate limited)"
            
            vol = global_data.get('total_volume_24h', 0)
            vol_str = f"${vol/1e9:.1f}B" if vol > 0 else "N/A"
            
            btc_dom = global_data.get('btc_dominance', 0)
            btc_dom_str = f"{btc_dom:.1f}%" if btc_dom > 0 else "~55%"
            
            mcap_chg = global_data.get('market_cap_change_24h', 0)
            mcap_chg_str = f"{mcap_chg:+.2f}%" if mcap_chg != 0 else "N/A"
            
            # Get prices - try multiple sources
            btc_price = btc.get('current_price', 0) or btc.get('price', 0)
            eth_price = eth.get('current_price', 0) or eth.get('price', 0)
            sol_price = sol.get('current_price', 0) or sol.get('price', 0)
            
            btc_chg = btc.get('price_change_percentage_24h', 0) or btc.get('change_24h', 0) or 0
            eth_chg = eth.get('price_change_percentage_24h', 0) or eth.get('change_24h', 0) or 0
            sol_chg = sol.get('price_change_percentage_24h', 0) or sol.get('change_24h', 0) or 0
            
            # If prices still zero, fetch from MEXC directly
            if btc_price == 0:
                try:
                    ticker = self.okx.fetch_ticker("BTC/USDT")
                    btc_price = ticker.get("last", 0)
                    btc_chg = ticker.get("percentage", 0) or 0
                except Exception as e:
                    logger.debug(f"BTC ticker fetch failed: {e}")

            if eth_price == 0:
                try:
                    ticker = self.okx.fetch_ticker("ETH/USDT")
                    eth_price = ticker.get("last", 0)
                    eth_chg = ticker.get("percentage", 0) or 0
                except Exception as e:
                    logger.debug(f"ETH ticker fetch failed: {e}")

            if sol_price == 0:
                try:
                    ticker = self.okx.fetch_ticker("SOL/USDT")
                    sol_price = ticker.get("last", 0)
                    sol_chg = ticker.get("percentage", 0) or 0
                except Exception as e:
                    logger.debug(f"SOL ticker fetch failed: {e}")
            
            summary = f"""📊 MARKET INTELLIGENCE REPORT

🎭 SENTIMENT
Fear & Greed: {fng.get('value', '?')} ({fng.get('classification', '?')})
{self.interpret_fear_greed(fng.get('value', 50))}

📈 GLOBAL MARKET
Total Market Cap: {mcap_str}
24h Volume: {vol_str}
BTC Dominance: {btc_dom_str}
Market Cap Change 24h: {mcap_chg_str}

💰 KEY PRICES (Live)
BTC: ${btc_price:,.2f} ({btc_chg:+.2f}%)
ETH: ${eth_price:,.2f} ({eth_chg:+.2f}%)
SOL: ${sol_price:,.2f} ({sol_chg:+.2f}%)
"""
            
            if trending:
                summary += "\n🔥 TRENDING\n"
                for coin in trending[:5]:
                    summary += f"• {coin.get('name', '?')} ({coin.get('symbol', '?').upper()})\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"Summary error: {e}")
            return f"⚠️ Error generating summary: {e}"
    
    async def get_top_movers(self, limit: int = 10) -> Dict[str, List]:
        """Get top gainers and losers from top 100"""
        coins = await self.get_top_100_coins()
        
        if not coins:
            return {"gainers": [], "losers": []}
        
        # Sort by 24h change
        sorted_coins = sorted(coins, key=lambda x: x.get("price_change_percentage_24h", 0) or 0, reverse=True)
        
        gainers = []
        for c in sorted_coins[:limit]:
            gainers.append({
                "symbol": c.get("symbol", "").upper(),
                "name": c.get("name", ""),
                "price": c.get("current_price", 0),
                "change_24h": c.get("price_change_percentage_24h", 0),
                "market_cap_rank": c.get("market_cap_rank", 0)
            })
        
        losers = []
        for c in sorted_coins[-limit:]:
            losers.append({
                "symbol": c.get("symbol", "").upper(),
                "name": c.get("name", ""),
                "price": c.get("current_price", 0),
                "change_24h": c.get("price_change_percentage_24h", 0),
                "market_cap_rank": c.get("market_cap_rank", 0)
            })
        
        return {"gainers": gainers, "losers": list(reversed(losers))}
    
    async def analyze_symbol_sentiment(self, symbol: str) -> Dict:
        """Comprehensive sentiment analysis for a symbol"""
        # Get all relevant data
        funding = await self.get_funding_rate(symbol)
        oi = await self.get_open_interest_estimate(symbol)
        fng = await self.get_fear_greed_index()
        
        # Score calculation
        score = 0
        signals = []
        
        # Fear & Greed
        fg_value = fng.get("value", 50)
        if fg_value <= 25:
            score += 2
            signals.append(f"✅ Extreme fear ({fg_value}) - contrarian buy signal")
        elif fg_value <= 40:
            score += 1
            signals.append(f"✅ Fear ({fg_value}) - potential accumulation")
        elif fg_value >= 75:
            score -= 2
            signals.append(f"🔴 Extreme greed ({fg_value}) - high risk of correction")
        elif fg_value >= 60:
            score -= 1
            signals.append(f"🔴 Greed ({fg_value}) - caution advised")
        
        # Funding rate
        if "funding_rate" in funding:
            rate = funding["funding_rate"]
            if rate > 0.0005:  # >0.05%
                score -= 1
                signals.append(f"🔴 High funding ({rate*100:.3f}%) - longs crowded")
            elif rate < -0.0001:
                score += 1
                signals.append(f"✅ Negative funding ({rate*100:.3f}%) - shorts crowded")
        
        # Determine overall sentiment
        if score >= 2:
            sentiment = "BULLISH"
        elif score <= -2:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
        
        return {
            "symbol": symbol,
            "sentiment": sentiment,
            "score": score,
            "signals": signals,
            "fear_greed": fng,
            "funding": funding,
            "open_interest": oi
        }


# Global instance
enhanced_intel = EnhancedMarketIntel()
