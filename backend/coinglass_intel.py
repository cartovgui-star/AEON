"""
COINGLASS DATA MODULE
Real liquidation heatmaps, open interest, and funding data

NOTE: As of 2025, Coinglass requires an API key for ALL endpoints.
Free tier is available with limited calls.

To get API key:
1. Go to https://www.coinglass.com/api
2. Sign up for an account
3. Navigate to API section
4. Generate your API key
5. Add COINGLASS_API_KEY to backend/.env

Pricing: Free tier available (limited calls), paid plans start ~$30-50/month
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Coinglass API base URL
COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"

# API Key (optional for free endpoints)
COINGLASS_API_KEY = os.environ.get('COINGLASS_API_KEY', '')


class CoinglassIntel:
    """
    Real derivatives data from Coinglass
    
    Free endpoints (no key):
    - funding_rates
    - open_interest
    - long_short_ratio
    
    Paid endpoints (key required):
    - liquidation_heatmap
    - liquidation_history
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60  # 1 minute cache
        self.has_api_key = bool(COINGLASS_API_KEY)
    
    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None
    
    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())
    
    async def _request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make request to Coinglass API"""
        try:
            headers = {}
            if COINGLASS_API_KEY:
                headers["coinglassSecret"] = COINGLASS_API_KEY
            
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{COINGLASS_BASE}/{endpoint}",
                    params=params,
                    headers=headers
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        return data.get("data", {})
                    return {"error": data.get("msg", "Unknown error")}
                
                return {"error": f"HTTP {resp.status_code}"}
                
        except Exception as e:
            logger.error(f"Coinglass API error: {e}")
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FREE ENDPOINTS (No API Key Required)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_funding_rates(self, symbol: str = "BTC") -> Dict:
        """
        Get funding rates across exchanges
        Requires API key (free tier available)
        """
        if not self.has_api_key:
            return {
                "error": "API key required",
                "how_to_get_key": "Visit https://www.coinglass.com/api to get your API key (free tier available)",
                "pricing": "Free tier available with limited calls, paid plans start ~$30-50/month"
            }
        
        cache_key = f"cg_funding_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        data = await self._request("funding", {"symbol": symbol})
        
        if "error" in data:
            return data
        
        # Parse response
        rates = []
        for exchange_data in data if isinstance(data, list) else []:
            rates.append({
                "exchange": exchange_data.get("exchangeName", "Unknown"),
                "rate": exchange_data.get("rate", 0),
                "rate_pct": f"{exchange_data.get('rate', 0) * 100:.4f}%",
                "predicted_rate": exchange_data.get("predictedRate", 0),
                "next_funding_time": exchange_data.get("nextFundingTime", 0)
            })
        
        # Calculate average
        if rates:
            avg_rate = sum(r["rate"] for r in rates) / len(rates)
        else:
            avg_rate = 0
        
        result = {
            "symbol": symbol,
            "exchanges": rates,
            "average_rate": avg_rate,
            "average_rate_pct": f"{avg_rate * 100:.4f}%",
            "data_source": "Coinglass",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._cache_set(cache_key, result)
        return result
    
    async def get_open_interest(self, symbol: str = "BTC") -> Dict:
        """
        Get aggregated open interest across exchanges
        FREE - No API key required
        """
        cache_key = f"cg_oi_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        data = await self._request("open_interest", {"symbol": symbol})
        
        if "error" in data:
            return data
        
        exchanges = []
        total_oi = 0
        
        for ex in data if isinstance(data, list) else []:
            oi_value = ex.get("openInterest", 0)
            total_oi += oi_value
            exchanges.append({
                "exchange": ex.get("exchangeName", "Unknown"),
                "open_interest": oi_value,
                "open_interest_str": f"${oi_value:,.0f}",
                "change_1h": ex.get("h1OIChangePercent", 0),
                "change_24h": ex.get("h24OIChangePercent", 0)
            })
        
        result = {
            "symbol": symbol,
            "total_open_interest": total_oi,
            "total_open_interest_str": f"${total_oi:,.0f}",
            "exchanges": exchanges,
            "data_source": "Coinglass",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._cache_set(cache_key, result)
        return result
    
    async def get_long_short_ratio(self, symbol: str = "BTC") -> Dict:
        """
        Get global long/short ratio
        FREE - No API key required
        """
        cache_key = f"cg_ls_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        data = await self._request("long_short", {"symbol": symbol})
        
        if "error" in data:
            return data
        
        exchanges = []
        total_long = 0
        total_short = 0
        
        for ex in data if isinstance(data, list) else []:
            long_ratio = ex.get("longRatio", 0.5)
            short_ratio = ex.get("shortRatio", 0.5)
            
            total_long += long_ratio
            total_short += short_ratio
            
            exchanges.append({
                "exchange": ex.get("exchangeName", "Unknown"),
                "long_pct": round(long_ratio * 100, 1),
                "short_pct": round(short_ratio * 100, 1),
                "long_short_ratio": round(long_ratio / short_ratio, 2) if short_ratio > 0 else 0
            })
        
        # Global average
        count = len(exchanges) or 1
        avg_long = (total_long / count) * 100
        avg_short = (total_short / count) * 100
        
        # Interpretation
        if avg_long > 60:
            interpretation = "⚠️ Longs crowded - potential long squeeze"
            bias = "BEARISH"
        elif avg_long < 40:
            interpretation = "⚠️ Shorts crowded - potential short squeeze"
            bias = "BULLISH"
        else:
            interpretation = "Balanced positioning"
            bias = "NEUTRAL"
        
        result = {
            "symbol": symbol,
            "global": {
                "long_pct": round(avg_long, 1),
                "short_pct": round(avg_short, 1),
                "ratio": round(avg_long / avg_short, 2) if avg_short > 0 else 0
            },
            "exchanges": exchanges,
            "interpretation": interpretation,
            "bias": bias,
            "data_source": "Coinglass",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._cache_set(cache_key, result)
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PAID ENDPOINTS (API Key Required)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_liquidation_heatmap(self, symbol: str = "BTC") -> Dict:
        """
        Get liquidation heatmap data
        PAID - Requires API key
        """
        if not self.has_api_key:
            return {
                "error": "API key required",
                "how_to_get_key": "Visit https://www.coinglass.com/api to get your API key",
                "pricing": "Free tier available, paid plans start ~$30-50/month"
            }
        
        cache_key = f"cg_liq_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        data = await self._request("liquidation_map", {"symbol": symbol})
        
        if "error" in data:
            return data
        
        # Parse liquidation levels
        long_liquidations = []
        short_liquidations = []
        
        for level in data.get("liqHeatMap", []):
            price = level.get("price", 0)
            long_liq = level.get("longLiquidation", 0)
            short_liq = level.get("shortLiquidation", 0)
            
            if long_liq > 0:
                long_liquidations.append({"price": price, "value": long_liq})
            if short_liq > 0:
                short_liquidations.append({"price": price, "value": short_liq})
        
        # Find biggest liquidation clusters
        long_liquidations.sort(key=lambda x: x["value"], reverse=True)
        short_liquidations.sort(key=lambda x: x["value"], reverse=True)
        
        result = {
            "symbol": symbol,
            "top_long_liquidation_levels": long_liquidations[:5],
            "top_short_liquidation_levels": short_liquidations[:5],
            "total_long_liq_value": sum(l["value"] for l in long_liquidations),
            "total_short_liq_value": sum(s["value"] for s in short_liquidations),
            "data_source": "Coinglass",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._cache_set(cache_key, result)
        return result
    
    async def get_liquidation_history(self, symbol: str = "BTC", hours: int = 24) -> Dict:
        """
        Get liquidation history
        PAID - Requires API key
        """
        if not self.has_api_key:
            return {
                "error": "API key required",
                "how_to_get_key": "Visit https://www.coinglass.com/api to get your API key"
            }
        
        data = await self._request("liquidation_history", {
            "symbol": symbol,
            "timeType": "h24" if hours <= 24 else "h48"
        })
        
        if "error" in data:
            return data
        
        total_long_liq = 0
        total_short_liq = 0
        
        for item in data if isinstance(data, list) else []:
            total_long_liq += item.get("longLiquidationUsd", 0)
            total_short_liq += item.get("shortLiquidationUsd", 0)
        
        # Interpretation
        total = total_long_liq + total_short_liq
        if total > 0:
            long_pct = (total_long_liq / total) * 100
            if long_pct > 70:
                interpretation = f"🔴 Heavy long liquidations ({long_pct:.0f}%) - price dropped"
            elif long_pct < 30:
                interpretation = f"🟢 Heavy short liquidations ({100-long_pct:.0f}%) - price pumped"
            else:
                interpretation = "Balanced liquidations"
        else:
            interpretation = "No significant liquidations"
        
        return {
            "symbol": symbol,
            "period": f"{hours}h",
            "total_liquidations": total,
            "total_liquidations_str": f"${total:,.0f}",
            "long_liquidations": total_long_liq,
            "short_liquidations": total_short_liq,
            "long_pct": round((total_long_liq / total) * 100, 1) if total > 0 else 0,
            "interpretation": interpretation,
            "data_source": "Coinglass",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMBINED ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_full_report(self, symbol: str = "BTC") -> Dict:
        """Get comprehensive Coinglass report"""
        funding = await self.get_funding_rates(symbol)
        oi = await self.get_open_interest(symbol)
        ls = await self.get_long_short_ratio(symbol)
        
        # Combine signals
        signals = []
        overall_bias = "NEUTRAL"
        
        # Funding analysis
        if "error" not in funding:
            avg_rate = funding.get("average_rate", 0)
            if avg_rate > 0.0005:
                signals.append("🔴 High funding - longs paying")
                overall_bias = "BEARISH"
            elif avg_rate < -0.0003:
                signals.append("🟢 Negative funding - shorts paying")
                overall_bias = "BULLISH"
        
        # L/S analysis
        if "error" not in ls:
            if ls.get("bias") == "BULLISH":
                signals.append("🟢 Shorts crowded")
                if overall_bias == "NEUTRAL":
                    overall_bias = "BULLISH"
            elif ls.get("bias") == "BEARISH":
                signals.append("🔴 Longs crowded")
                if overall_bias == "NEUTRAL":
                    overall_bias = "BEARISH"
        
        return {
            "symbol": symbol,
            "funding": funding,
            "open_interest": oi,
            "long_short": ls,
            "signals": signals,
            "overall_bias": overall_bias,
            "has_api_key": self.has_api_key,
            "data_source": "Coinglass",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
coinglass_intel = CoinglassIntel()
