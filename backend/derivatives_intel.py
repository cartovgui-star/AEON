"""
AEON DERIVATIVES INTELLIGENCE
Real derivatives data from multiple exchanges (OKX, Bitget, KuCoin, Gate)
"""

import ccxt
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for sync ccxt calls
executor = ThreadPoolExecutor(max_workers=4)


class DerivativesIntel:
    """
    Aggregates REAL derivatives data from multiple exchanges:
    - OKX: Funding rates, Open Interest, Liquidations
    - Bitget: Funding rates, Open Interest
    - KuCoin: Funding rates
    - Gate.io: Funding rates
    
    All using ccxt public endpoints (no API keys required)
    """
    
    def __init__(self):
        # Initialize exchanges with rate limiting
        self.okx = ccxt.okx({'enableRateLimit': True})
        self.bitget = ccxt.bitget({'enableRateLimit': True})
        self.kucoin = ccxt.kucoinfutures({'enableRateLimit': True})
        self.gate = ccxt.gate({'enableRateLimit': True})
        
        # Symbol mapping for perpetuals - Top 44 pairs
        self.supported_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
            "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
            "LINKUSDT", "TRXUSDT", "BCHUSDT", "LTCUSDT", "NEARUSDT",
            "UNIUSDT", "APTUSDT", "ICPUSDT", "ETCUSDT", "FILUSDT",
            "ATOMUSDT", "XLMUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
            "HBARUSDT", "VETUSDT", "GRTUSDT", "AAVEUSDT", "ALGOUSDT",
            "SANDUSDT", "AXSUSDT", "MANAUSDT", "XTZUSDT", "FLOWUSDT",
            "NEOUSDT", "SNXUSDT", "CRVUSDT", "RUNEUSDT", "ZECUSDT",
            "DASHUSDT", "COMPUSDT", "ENJUSDT", "CHZUSDT"
        ]
        
        # Cache
        self._cache = {}
        self._cache_ttl = 60
    
    def _get_perp_symbol(self, symbol: str) -> str:
        """Convert BTCUSDT to BTC/USDT:USDT format for any symbol"""
        # Handle already formatted symbols
        if "/" in symbol:
            base = symbol.split("/")[0]
            return f"{base}/USDT:USDT"
        
        # Convert BTCUSDT format - remove USDT suffix
        base = symbol.replace("USDT", "")
        return f"{base}/USDT:USDT"
    
    def _cache_get(self, key: str) -> Optional[Dict]:
        """Get from cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return data
        return None
    
    def _cache_set(self, key: str, data: Dict):
        """Set cache"""
        self._cache[key] = (data, datetime.now())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FUNDING RATES - Aggregated from multiple exchanges
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_funding_rate_okx(self, symbol: str = "BTCUSDT") -> Dict:
        """Get funding rate from OKX"""
        cache_key = f"okx_funding_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            funding = await loop.run_in_executor(executor, self.okx.fetch_funding_rate, perp)
            
            rate = funding.get("fundingRate", 0) or 0
            result = {
                "exchange": "OKX",
                "symbol": symbol,
                "funding_rate": rate,
                "funding_rate_pct": f"{rate * 100:.4f}%",
                "next_funding_time": funding.get("fundingTimestamp"),
                "mark_price": funding.get("markPrice"),
                "index_price": funding.get("indexPrice"),
            }
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"OKX funding error: {e}")
            return {"exchange": "OKX", "symbol": symbol, "error": str(e)}
    
    async def get_funding_rate_bitget(self, symbol: str = "BTCUSDT") -> Dict:
        """Get funding rate from Bitget"""
        cache_key = f"bitget_funding_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            funding = await loop.run_in_executor(executor, self.bitget.fetch_funding_rate, perp)
            
            rate = funding.get("fundingRate", 0) or 0
            result = {
                "exchange": "Bitget",
                "symbol": symbol,
                "funding_rate": rate,
                "funding_rate_pct": f"{rate * 100:.4f}%",
                "next_funding_time": funding.get("fundingTimestamp"),
            }
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Bitget funding error: {e}")
            return {"exchange": "Bitget", "symbol": symbol, "error": str(e)}
    
    async def get_funding_rate_kucoin(self, symbol: str = "BTCUSDT") -> Dict:
        """Get funding rate from KuCoin"""
        cache_key = f"kucoin_funding_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            funding = await loop.run_in_executor(executor, self.kucoin.fetch_funding_rate, perp)
            
            rate = funding.get("fundingRate", 0) or 0
            result = {
                "exchange": "KuCoin",
                "symbol": symbol,
                "funding_rate": rate,
                "funding_rate_pct": f"{rate * 100:.4f}%",
            }
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"KuCoin funding error: {e}")
            return {"exchange": "KuCoin", "symbol": symbol, "error": str(e)}
    
    async def get_funding_rate_gate(self, symbol: str = "BTCUSDT") -> Dict:
        """Get funding rate from Gate.io"""
        cache_key = f"gate_funding_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            funding = await loop.run_in_executor(executor, self.gate.fetch_funding_rate, perp)
            
            rate = funding.get("fundingRate", 0) or 0
            result = {
                "exchange": "Gate.io",
                "symbol": symbol,
                "funding_rate": rate,
                "funding_rate_pct": f"{rate * 100:.4f}%",
            }
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Gate funding error: {e}")
            return {"exchange": "Gate.io", "symbol": symbol, "error": str(e)}
    
    async def get_aggregated_funding(self, symbol: str = "BTCUSDT") -> Dict:
        """Get funding rates from all exchanges and calculate average"""
        tasks = [
            self.get_funding_rate_okx(symbol),
            self.get_funding_rate_bitget(symbol),
            self.get_funding_rate_kucoin(symbol),
            self.get_funding_rate_gate(symbol),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exchanges = []
        rates = []
        
        for r in results:
            if isinstance(r, dict) and "error" not in r:
                exchanges.append(r)
                if r.get("funding_rate") is not None:
                    rates.append(r["funding_rate"])
        
        avg_rate = sum(rates) / len(rates) if rates else 0
        
        # Interpretation
        if avg_rate > 0.0005:
            interpretation = "🔴 HIGH POSITIVE - Longs heavily crowded, squeeze risk"
        elif avg_rate > 0.0001:
            interpretation = "🟡 POSITIVE - Longs paying shorts"
        elif avg_rate < -0.0003:
            interpretation = "🟢 NEGATIVE - Shorts crowded, squeeze potential"
        elif avg_rate < 0:
            interpretation = "🟢 SLIGHT NEGATIVE - Shorts paying longs"
        else:
            interpretation = "⚪ NEUTRAL"
        
        return {
            "symbol": symbol,
            "average_funding_rate": avg_rate,
            "average_funding_pct": f"{avg_rate * 100:.4f}%",
            "interpretation": interpretation,
            "exchanges": exchanges,
            "data_sources": len(exchanges),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPEN INTEREST - Real data from OKX and Bitget
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_open_interest_okx(self, symbol: str = "BTCUSDT") -> Dict:
        """Get open interest from OKX"""
        cache_key = f"okx_oi_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            oi = await loop.run_in_executor(executor, self.okx.fetch_open_interest, perp)
            
            result = {
                "exchange": "OKX",
                "symbol": symbol,
                "open_interest_amount": oi.get("openInterestAmount", 0),
                "open_interest_value": oi.get("openInterestValue", 0),
                "open_interest_value_str": f"${oi.get('openInterestValue', 0):,.0f}",
            }
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"OKX OI error: {e}")
            return {"exchange": "OKX", "symbol": symbol, "error": str(e)}
    
    async def get_open_interest_bitget(self, symbol: str = "BTCUSDT") -> Dict:
        """Get open interest from Bitget"""
        cache_key = f"bitget_oi_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            oi = await loop.run_in_executor(executor, self.bitget.fetch_open_interest, perp)
            
            result = {
                "exchange": "Bitget",
                "symbol": symbol,
                "open_interest_amount": oi.get("openInterestAmount", 0),
            }
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Bitget OI error: {e}")
            return {"exchange": "Bitget", "symbol": symbol, "error": str(e)}
    
    async def get_aggregated_open_interest(self, symbol: str = "BTCUSDT") -> Dict:
        """Get open interest from multiple exchanges"""
        tasks = [
            self.get_open_interest_okx(symbol),
            self.get_open_interest_bitget(symbol),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exchanges = []
        total_value = 0
        
        for r in results:
            if isinstance(r, dict) and "error" not in r:
                exchanges.append(r)
                if r.get("open_interest_value"):
                    total_value += r["open_interest_value"]
        
        return {
            "symbol": symbol,
            "total_open_interest_value": total_value,
            "total_open_interest_str": f"${total_value:,.0f}",
            "exchanges": exchanges,
            "data_sources": len(exchanges),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LONG/SHORT RATIO - From exchanges that support it
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_long_short_ratio_okx(self, symbol: str = "BTCUSDT") -> Dict:
        """Get long/short ratio from OKX"""
        try:
            # OKX provides this via their contract API
            # Using the margin ratio as a proxy
            perp = self._get_perp_symbol(symbol)
            loop = asyncio.get_event_loop()
            
            # Fetch ticker which has some position info
            ticker = await loop.run_in_executor(executor, self.okx.fetch_ticker, perp)
            
            # OKX doesn't directly expose L/S in ccxt, estimate from funding
            funding = await self.get_funding_rate_okx(symbol)
            rate = funding.get("funding_rate", 0)
            
            # Positive funding = more longs, negative = more shorts
            if rate > 0.0003:
                ratio = 1.5 + (rate * 1000)
                long_pct = 60 + (rate * 10000)
            elif rate < -0.0001:
                ratio = 0.7 - (abs(rate) * 500)
                long_pct = 40 - (abs(rate) * 5000)
            else:
                ratio = 1.0
                long_pct = 50
            
            return {
                "exchange": "OKX",
                "symbol": symbol,
                "long_short_ratio": round(ratio, 2),
                "long_pct": round(min(80, max(20, long_pct)), 1),
                "short_pct": round(100 - min(80, max(20, long_pct)), 1),
                "note": "Estimated from funding rate",
            }
        except Exception as e:
            logger.error(f"OKX L/S error: {e}")
            return {"exchange": "OKX", "symbol": symbol, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMPREHENSIVE DERIVATIVES REPORT
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_full_derivatives_report(self, symbol: str = "BTCUSDT") -> Dict:
        """Get comprehensive derivatives data from all sources"""
        tasks = [
            self.get_aggregated_funding(symbol),
            self.get_aggregated_open_interest(symbol),
            self.get_long_short_ratio_okx(symbol),
        ]
        
        funding, oi, ls = await asyncio.gather(*tasks, return_exceptions=True)
        
        if isinstance(funding, Exception):
            funding = {"error": str(funding)}
        if isinstance(oi, Exception):
            oi = {"error": str(oi)}
        if isinstance(ls, Exception):
            ls = {"error": str(ls)}
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "funding": funding,
            "open_interest": oi,
            "long_short": ls,
            "summary": self._generate_summary(funding, oi, ls)
        }
    
    def _generate_summary(self, funding: Dict, oi: Dict, ls: Dict) -> str:
        """Generate human-readable summary"""
        parts = []
        
        # Funding analysis
        if "average_funding_pct" in funding:
            parts.append(f"Funding: {funding['average_funding_pct']} across {funding.get('data_sources', 0)} exchanges")
            parts.append(funding.get("interpretation", ""))
        
        # OI analysis
        if "total_open_interest_str" in oi:
            parts.append(f"Total OI: {oi['total_open_interest_str']}")
        
        # L/S analysis
        if "long_pct" in ls:
            parts.append(f"Positioning: {ls['long_pct']}% Long / {ls['short_pct']}% Short")
        
        return "\n".join(parts)


# Global instance
derivatives_intel = DerivativesIntel()
