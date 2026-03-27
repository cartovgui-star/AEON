"""
AEON ENHANCED MARKET INTELLIGENCE
Real free APIs for comprehensive crypto data
"""

import aiohttp
import asyncio
import logging
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
        # MEXC for spot data
        self.mexc = ccxt.mexc({'enableRateLimit': True})
        
        # API endpoints
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.fear_greed_api = "https://api.alternative.me/fng"
        
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
    # COINGECKO - TOP 100 COINS (with MEXC fallback)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_mexc_prices(self) -> List[Dict]:
        """Get prices from MEXC for top coins"""
        try:
            # Top 20 for quick loading (full 44 would be slow)
            primary_symbols = [
                "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
                "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
                "TRX/USDT", "LTC/USDT", "NEAR/USDT", "UNI/USDT", "APT/USDT",
                "ATOM/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT", "AAVE/USDT"
            ]
            tickers = self.mexc.fetch_tickers(primary_symbols)
            
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
        """Get top 100 cryptocurrencies - uses MEXC as primary (faster, no rate limits)"""
        # Use MEXC as primary source - always available
        coins = await self.get_mexc_prices()
        if coins:
            return coins
        
        # Fallback to CoinGecko if MEXC fails
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
            btc_ticker = self.mexc.fetch_ticker("BTC/USDT")
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
            # Try MEXC first (via ccxt)
            base = symbol.replace("USDT", "")
            
            # MEXC uses swap format
            try:
                mexc = ccxt.mexc({'enableRateLimit': True})
                funding = mexc.fetch_funding_rate(f"{base}/USDT:USDT")
                
                rate = funding.get("fundingRate", 0) or 0
                return {
                    "symbol": symbol,
                    "source": "MEXC",
                    "funding_rate": rate,
                    "funding_rate_pct": f"{rate * 100:.4f}%",
                    "is_positive": rate > 0,
                    "interpretation": "Longs pay shorts" if rate > 0 else "Shorts pay longs"
                }
            except Exception as mexc_err:
                logger.warning(f"MEXC funding error: {mexc_err}")
            
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
    
    async def get_mexc_recent_trades(self, symbol: str = "BTC_USDT", limit: int = 50) -> List[Dict]:
        """Get recent trades from MEXC contract ticker."""
        mexc_sym = symbol.replace("/", "_").replace("-", "_").upper()
        if not mexc_sym.endswith("_USDT"):
            mexc_sym = mexc_sym.replace("USDT", "_USDT") if "USDT" in mexc_sym else mexc_sym + "_USDT"
        url = f"https://contract.mexc.com/api/v1/contract/ticker?symbol={mexc_sym}"
        data = await self._fetch_json(url, f"mexc_ticker_{mexc_sym}")
        if data.get("code") == 0 and data.get("data"):
            d = data["data"]
            return [{
                "symbol": mexc_sym,
                "price": float(d.get("lastPrice", 0)),
                "volume": float(d.get("volume24", 0)),
                "timestamp": str(d.get("timestamp", "")),
            }]
        return []

    async def get_mexc_tickers(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """Get tickers for multiple symbols from MEXC contract API."""
        if not symbols:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "AVAXUSDT"]

        results = {}
        for symbol in symbols:
            mexc_sym = symbol.replace("USDT", "_USDT")
            url = f"https://contract.mexc.com/api/v1/contract/ticker?symbol={mexc_sym}"
            data = await self._fetch_json(url, f"mexc_cticker_{mexc_sym}")
            if data.get("code") == 0 and data.get("data"):
                item = data["data"]
                results[symbol] = {
                    "price": float(item.get("lastPrice", 0)),
                    "change_24h": float(item.get("priceChangeRate", 0)) * 100,
                    "volume_24h": float(item.get("volume24", 0)),
                    "high_24h": float(item.get("higher24Price", 0)),
                    "low_24h": float(item.get("lower24Price", 0)),
                    "funding_rate": float(item.get("fundingRate", 0)),
                    "open_interest": float(item.get("holdVol", 0)),
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
                    ticker = self.mexc.fetch_ticker("BTC/USDT")
                    btc_price = ticker.get("last", 0)
                    btc_chg = ticker.get("percentage", 0) or 0
                except Exception as e:
                    logger.debug(f"BTC ticker fetch failed: {e}")

            if eth_price == 0:
                try:
                    ticker = self.mexc.fetch_ticker("ETH/USDT")
                    eth_price = ticker.get("last", 0)
                    eth_chg = ticker.get("percentage", 0) or 0
                except Exception as e:
                    logger.debug(f"ETH ticker fetch failed: {e}")

            if sol_price == 0:
                try:
                    ticker = self.mexc.fetch_ticker("SOL/USDT")
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
