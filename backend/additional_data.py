"""
AEON ADDITIONAL FREE DATA SOURCES
Integrates free APIs for more market intelligence:
- CryptoCompare (social stats, news sentiment)
- Messari (on-chain metrics)
- Blockchain.com (BTC on-chain data)
- Alternative.me (Fear & Greed - already have)
- CoinGecko (already integrated via enhanced_intel)
"""

import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AdditionalDataSources:
    """
    Additional free data sources for market intelligence
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache
    
    def _is_cached(self, key: str) -> bool:
        """Check if data is cached and still valid"""
        if key not in self.cache:
            return False
        cached_at = self.cache[key].get("cached_at", 0)
        return (datetime.now(timezone.utc).timestamp() - cached_at) < self.cache_ttl
    
    def _get_cached(self, key: str) -> Optional[Dict]:
        """Get cached data if valid"""
        if self._is_cached(key):
            return self.cache[key].get("data")
        return None
    
    def _set_cache(self, key: str, data: Dict):
        """Cache data"""
        self.cache[key] = {
            "data": data,
            "cached_at": datetime.now(timezone.utc).timestamp()
        }
    
    async def get_crypto_compare_social(self, symbol: str = "BTC") -> Dict:
        """
        Get social stats from CryptoCompare (FREE)
        Includes: Reddit, Twitter, Facebook activity
        """
        cache_key = f"cc_social_{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Social stats endpoint (free)
                url = f"https://min-api.cryptocompare.com/data/social/coin/latest?coinId={self._get_coin_id(symbol)}"
                resp = await client.get(url)
                
                if resp.status_code == 200:
                    data = resp.json()
                    social_data = data.get("Data", {})
                    
                    result = {
                        "symbol": symbol,
                        "reddit": {
                            "subscribers": social_data.get("Reddit", {}).get("subscribers", 0),
                            "active_users": social_data.get("Reddit", {}).get("active_users", 0),
                            "posts_per_day": social_data.get("Reddit", {}).get("posts_per_day", 0)
                        },
                        "twitter": {
                            "followers": social_data.get("Twitter", {}).get("followers", 0),
                            "statuses": social_data.get("Twitter", {}).get("statuses", 0)
                        },
                        "github": {
                            "stars": social_data.get("CodeRepository", {}).get("List", [{}])[0].get("stars", 0) if social_data.get("CodeRepository", {}).get("List") else 0,
                            "forks": social_data.get("CodeRepository", {}).get("List", [{}])[0].get("forks", 0) if social_data.get("CodeRepository", {}).get("List") else 0
                        },
                        "source": "CryptoCompare"
                    }
                    
                    self._set_cache(cache_key, result)
                    return result
                    
        except Exception as e:
            logger.error(f"CryptoCompare social error: {e}")
        
        return {"error": "Failed to fetch social data", "symbol": symbol}
    
    def _get_coin_id(self, symbol: str) -> int:
        """Map symbol to CryptoCompare coin ID"""
        coin_ids = {
            "BTC": 1182, "ETH": 7605, "SOL": 934443, "BNB": 204788,
            "XRP": 5031, "DOGE": 4432, "ADA": 321992, "AVAX": 935778,
            "DOT": 891618, "LINK": 243641, "ATOM": 507426
        }
        return coin_ids.get(symbol.upper(), 1182)  # Default to BTC
    
    async def get_blockchain_btc_stats(self) -> Dict:
        """
        Get BTC on-chain stats from Blockchain.com (FREE)
        Includes: Hash rate, difficulty, mempool, blocks
        """
        cache_key = "blockchain_btc"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Multiple free endpoints
                stats_url = "https://api.blockchain.info/stats"
                resp = await client.get(stats_url)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    result = {
                        "hash_rate": f"{data.get('hash_rate', 0) / 1e18:.2f} EH/s",
                        "difficulty": data.get("difficulty", 0),
                        "blocks_mined_24h": data.get("n_blocks_mined", 0),
                        "btc_mined_24h": data.get("n_btc_mined", 0) / 1e8,
                        "total_btc_sent_24h": data.get("total_btc_sent", 0) / 1e8,
                        "market_price_usd": data.get("market_price_usd", 0),
                        "mempool_size": data.get("mempool_size", 0),
                        "total_fees_btc": data.get("total_fees_btc", 0) / 1e8,
                        "miners_revenue_usd": data.get("miners_revenue_usd", 0),
                        "next_retarget": data.get("nextretarget", 0),
                        "source": "Blockchain.com"
                    }
                    
                    self._set_cache(cache_key, result)
                    return result
                    
        except Exception as e:
            logger.error(f"Blockchain.com stats error: {e}")
        
        return {"error": "Failed to fetch BTC on-chain data"}
    
    async def get_mempool_fees(self) -> Dict:
        """
        Get BTC mempool fee estimates from mempool.space (FREE)
        """
        cache_key = "mempool_fees"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = "https://mempool.space/api/v1/fees/recommended"
                resp = await client.get(url)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    result = {
                        "fastest_fee": data.get("fastestFee", 0),
                        "half_hour_fee": data.get("halfHourFee", 0),
                        "hour_fee": data.get("hourFee", 0),
                        "economy_fee": data.get("economyFee", 0),
                        "minimum_fee": data.get("minimumFee", 0),
                        "unit": "sat/vB",
                        "source": "mempool.space"
                    }
                    
                    self._set_cache(cache_key, result)
                    return result
                    
        except Exception as e:
            logger.error(f"Mempool.space error: {e}")
        
        return {"error": "Failed to fetch mempool fees"}
    
    async def get_eth_gas(self) -> Dict:
        """
        Get ETH gas prices from public API (FREE)
        """
        cache_key = "eth_gas"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Using Etherscan free endpoint alternative
                url = "https://api.gasprice.io/v1/estimates"
                resp = await client.get(url)
                
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get("result", {})
                    
                    return {
                        "instant": result.get("instant", {}).get("feeCap", 0),
                        "fast": result.get("fast", {}).get("feeCap", 0),
                        "standard": result.get("standard", {}).get("feeCap", 0),
                        "slow": result.get("eco", {}).get("feeCap", 0),
                        "unit": "gwei",
                        "source": "gasprice.io"
                    }
                    
        except Exception as e:
            logger.error(f"ETH gas error: {e}")
        
        # Fallback - try alternative
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = "https://api.blocknative.com/gasprices/blockprices"
                resp = await client.get(url)
                
                if resp.status_code == 200:
                    data = resp.json()
                    block = data.get("blockPrices", [{}])[0]
                    prices = block.get("estimatedPrices", [])
                    
                    result = {
                        "instant": prices[0].get("maxFeePerGas", 0) if len(prices) > 0 else 0,
                        "fast": prices[1].get("maxFeePerGas", 0) if len(prices) > 1 else 0,
                        "standard": prices[2].get("maxFeePerGas", 0) if len(prices) > 2 else 0,
                        "slow": prices[3].get("maxFeePerGas", 0) if len(prices) > 3 else 0,
                        "unit": "gwei",
                        "source": "blocknative"
                    }
                    
                    self._set_cache(cache_key, result)
                    return result
                    
        except:
            pass
        
        return {"error": "Failed to fetch ETH gas prices"}
    
    async def get_defi_llama_tvl(self, protocol: str = None) -> Dict:
        """
        Get DeFi TVL data from DefiLlama (FREE)
        """
        cache_key = f"defillama_{protocol or 'global'}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if protocol:
                    url = f"https://api.llama.fi/protocol/{protocol}"
                else:
                    url = "https://api.llama.fi/protocols"
                
                resp = await client.get(url)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if protocol:
                        result = {
                            "name": data.get("name"),
                            "tvl": data.get("tvl", 0),
                            "chain_tvls": data.get("chainTvls", {}),
                            "category": data.get("category"),
                            "source": "DefiLlama"
                        }
                    else:
                        # Top 10 protocols by TVL
                        top_protocols = sorted(data, key=lambda x: x.get("tvl", 0), reverse=True)[:10]
                        result = {
                            "top_protocols": [
                                {"name": p.get("name"), "tvl": p.get("tvl", 0), "category": p.get("category")}
                                for p in top_protocols
                            ],
                            "total_protocols": len(data),
                            "source": "DefiLlama"
                        }
                    
                    self._set_cache(cache_key, result)
                    return result
                    
        except Exception as e:
            logger.error(f"DefiLlama error: {e}")
        
        return {"error": "Failed to fetch DeFi data"}
    
    async def get_full_additional_data(self, symbol: str = "BTC") -> Dict:
        """Get all additional data sources combined"""
        results = {}
        
        # Run all fetches in parallel
        import asyncio
        tasks = [
            self.get_crypto_compare_social(symbol),
            self.get_blockchain_btc_stats(),
            self.get_mempool_fees(),
            self.get_eth_gas(),
            self.get_defi_llama_tvl()
        ]
        
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        
        results["social"] = fetched[0] if not isinstance(fetched[0], Exception) else {"error": str(fetched[0])}
        results["btc_onchain"] = fetched[1] if not isinstance(fetched[1], Exception) else {"error": str(fetched[1])}
        results["btc_fees"] = fetched[2] if not isinstance(fetched[2], Exception) else {"error": str(fetched[2])}
        results["eth_gas"] = fetched[3] if not isinstance(fetched[3], Exception) else {"error": str(fetched[3])}
        results["defi_tvl"] = fetched[4] if not isinstance(fetched[4], Exception) else {"error": str(fetched[4])}
        
        return results


# Global instance
additional_data = AdditionalDataSources()
