"""
Options Data Module - Deribit API (Free)
- Max Pain calculation
- Put/Call Ratio
- Gamma Exposure
- Options Flow
"""
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class OptionsAnalyzer:
    """
    Analyzes crypto options data from Deribit
    
    Key Metrics:
    - Max Pain: Price where most options expire worthless (market tends to gravitate here)
    - Put/Call Ratio: >1 = bearish sentiment, <1 = bullish sentiment
    - Open Interest by Strike: Shows where big positions are
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minute cache for options data
        self.base_url = "https://www.deribit.com/api/v2"
    
    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None
    
    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())
    
    async def _api_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make request to Deribit API"""
        try:
            url = f"{self.base_url}/{endpoint}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result", data)
                    else:
                        logger.warning(f"Deribit API returned {resp.status}")
                        return {}
        except Exception as e:
            logger.error(f"Deribit API error: {e}")
            return {}
    
    async def get_instruments(self, currency: str = "BTC", kind: str = "option") -> List[Dict]:
        """Get all available options instruments"""
        cache_key = f"instruments_{currency}_{kind}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        result = await self._api_request("public/get_instruments", {
            "currency": currency,
            "kind": kind,
            "expired": "false"
        })
        
        if result:
            self._cache_set(cache_key, result)
        return result if isinstance(result, list) else []
    
    async def get_book_summary(self, currency: str = "BTC", kind: str = "option") -> List[Dict]:
        """Get summary of all options order books"""
        cache_key = f"book_summary_{currency}_{kind}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        result = await self._api_request("public/get_book_summary_by_currency", {
            "currency": currency,
            "kind": kind
        })
        
        if result:
            self._cache_set(cache_key, result)
        return result if isinstance(result, list) else []
    
    async def get_index_price(self, index_name: str = "btc_usd") -> float:
        """Get current index price"""
        result = await self._api_request("public/get_index_price", {
            "index_name": index_name
        })
        return result.get("index_price", 0) if result else 0
    
    async def calculate_max_pain(self, currency: str = "BTC") -> Dict:
        """
        Calculate Max Pain for nearest expiry
        
        Max Pain = Price where total value of puts + calls is minimized
        Market makers profit most when price settles at max pain
        Price tends to gravitate towards max pain near expiry
        """
        cache_key = f"max_pain_{currency}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            # Get all options
            instruments = await self.get_instruments(currency, "option")
            book_summary = await self.get_book_summary(currency, "option")
            current_price = await self.get_index_price(f"{currency.lower()}_usd")
            
            if not instruments or not book_summary or not current_price:
                return {"error": "Could not fetch options data"}
            
            # Create lookup for open interest
            oi_lookup = {item["instrument_name"]: item.get("open_interest", 0) for item in book_summary}
            
            # Group by expiry
            expiries = defaultdict(list)
            for inst in instruments:
                expiry = inst.get("expiration_timestamp", 0)
                expiries[expiry].append(inst)
            
            # Find nearest expiry with sufficient data
            now = datetime.now(timezone.utc).timestamp() * 1000
            future_expiries = {k: v for k, v in expiries.items() if k > now}
            
            if not future_expiries:
                return {"error": "No future expiries found"}
            
            nearest_expiry = min(future_expiries.keys())
            nearest_options = future_expiries[nearest_expiry]
            
            # Collect strikes and OI
            strikes = set()
            calls_oi = defaultdict(float)
            puts_oi = defaultdict(float)
            
            for opt in nearest_options:
                strike = opt.get("strike", 0)
                name = opt.get("instrument_name", "")
                oi = oi_lookup.get(name, 0)
                
                strikes.add(strike)
                
                if "-C" in name:
                    calls_oi[strike] = oi
                elif "-P" in name:
                    puts_oi[strike] = oi
            
            if not strikes:
                return {"error": "No strike data found"}
            
            # Calculate pain at each strike
            # Pain = Sum of (ITM value * OI) for all options
            strike_pain = {}
            
            for settlement_price in sorted(strikes):
                total_pain = 0
                
                # For each call: if settlement > strike, call is ITM
                for strike, oi in calls_oi.items():
                    if settlement_price > strike:
                        # Call is ITM, pain = (settlement - strike) * OI
                        total_pain += (settlement_price - strike) * oi
                
                # For each put: if settlement < strike, put is ITM
                for strike, oi in puts_oi.items():
                    if settlement_price < strike:
                        # Put is ITM, pain = (strike - settlement) * OI
                        total_pain += (strike - settlement_price) * oi
                
                strike_pain[settlement_price] = total_pain
            
            # Max pain = strike with minimum total pain
            max_pain_strike = min(strike_pain, key=strike_pain.get)
            
            # Calculate distance from current price
            distance = max_pain_strike - current_price
            distance_pct = (distance / current_price) * 100 if current_price > 0 else 0
            
            # Determine bias
            if distance_pct > 3:
                bias = "BULLISH"
                signal = f"Max pain ${max_pain_strike:,.0f} is {distance_pct:.1f}% above - price may rise"
            elif distance_pct < -3:
                bias = "BEARISH"
                signal = f"Max pain ${max_pain_strike:,.0f} is {abs(distance_pct):.1f}% below - price may fall"
            else:
                bias = "NEUTRAL"
                signal = f"Price near max pain - expect consolidation"
            
            # Expiry info
            expiry_dt = datetime.fromtimestamp(nearest_expiry / 1000, tz=timezone.utc)
            days_to_expiry = (expiry_dt - datetime.now(timezone.utc)).days
            
            result = {
                "currency": currency,
                "max_pain": max_pain_strike,
                "current_price": round(current_price, 2),
                "distance": round(distance, 2),
                "distance_pct": round(distance_pct, 2),
                "bias": bias,
                "signal": signal,
                "expiry": expiry_dt.strftime("%Y-%m-%d"),
                "days_to_expiry": days_to_expiry,
                "total_strikes": len(strikes),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self._cache_set(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Max pain calculation error: {e}")
            return {"error": str(e)}
    
    async def calculate_put_call_ratio(self, currency: str = "BTC") -> Dict:
        """
        Calculate Put/Call Ratio
        
        PCR = Total Put OI / Total Call OI
        - PCR > 1: More puts than calls = Bearish sentiment / hedging
        - PCR < 1: More calls than puts = Bullish sentiment
        - PCR > 1.2: Extreme bearish (often contrarian bullish)
        - PCR < 0.5: Extreme bullish (often contrarian bearish)
        """
        cache_key = f"pcr_{currency}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            book_summary = await self.get_book_summary(currency, "option")
            
            if not book_summary:
                return {"error": "Could not fetch options data"}
            
            total_call_oi = 0
            total_put_oi = 0
            total_call_volume = 0
            total_put_volume = 0
            
            for item in book_summary:
                name = item.get("instrument_name", "")
                oi = item.get("open_interest", 0)
                volume = item.get("volume", 0)
                
                if "-C" in name:
                    total_call_oi += oi
                    total_call_volume += volume
                elif "-P" in name:
                    total_put_oi += oi
                    total_put_volume += volume
            
            # Calculate ratios
            pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            pcr_volume = total_put_volume / total_call_volume if total_call_volume > 0 else 0
            
            # Determine sentiment
            if pcr_oi > 1.2:
                sentiment = "EXTREME_BEARISH"
                signal = "High put/call ratio - could be contrarian bullish"
            elif pcr_oi > 1.0:
                sentiment = "BEARISH"
                signal = "More puts than calls - hedging/bearish bets"
            elif pcr_oi < 0.5:
                sentiment = "EXTREME_BULLISH"
                signal = "Low put/call ratio - could be contrarian bearish"
            elif pcr_oi < 0.8:
                sentiment = "BULLISH"
                signal = "More calls than puts - bullish speculation"
            else:
                sentiment = "NEUTRAL"
                signal = "Balanced put/call ratio"
            
            result = {
                "currency": currency,
                "put_call_ratio_oi": round(pcr_oi, 3),
                "put_call_ratio_volume": round(pcr_volume, 3),
                "total_put_oi": round(total_put_oi, 2),
                "total_call_oi": round(total_call_oi, 2),
                "total_put_volume": round(total_put_volume, 2),
                "total_call_volume": round(total_call_volume, 2),
                "sentiment": sentiment,
                "signal": signal,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self._cache_set(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Put/Call ratio error: {e}")
            return {"error": str(e)}
    
    async def get_oi_by_strike(self, currency: str = "BTC") -> Dict:
        """Get Open Interest distribution by strike price"""
        try:
            instruments = await self.get_instruments(currency, "option")
            book_summary = await self.get_book_summary(currency, "option")
            current_price = await self.get_index_price(f"{currency.lower()}_usd")
            
            if not instruments or not book_summary:
                return {"error": "Could not fetch options data"}
            
            oi_lookup = {item["instrument_name"]: item.get("open_interest", 0) for item in book_summary}
            
            # Find nearest expiry
            now = datetime.now(timezone.utc).timestamp() * 1000
            expiries = set(inst.get("expiration_timestamp", 0) for inst in instruments)
            future_expiries = [e for e in expiries if e > now]
            
            if not future_expiries:
                return {"error": "No future expiries"}
            
            nearest_expiry = min(future_expiries)
            
            # Collect OI by strike
            strikes_data = defaultdict(lambda: {"calls": 0, "puts": 0})
            
            for inst in instruments:
                if inst.get("expiration_timestamp") != nearest_expiry:
                    continue
                
                strike = inst.get("strike", 0)
                name = inst.get("instrument_name", "")
                oi = oi_lookup.get(name, 0)
                
                if "-C" in name:
                    strikes_data[strike]["calls"] = oi
                elif "-P" in name:
                    strikes_data[strike]["puts"] = oi
            
            # Find significant strikes (high OI)
            all_oi = [(s, d["calls"] + d["puts"]) for s, d in strikes_data.items()]
            all_oi.sort(key=lambda x: x[1], reverse=True)
            
            significant_strikes = all_oi[:10]
            
            # Identify walls (high OI that may act as support/resistance)
            call_wall = max(strikes_data.items(), key=lambda x: x[1]["calls"])[0] if strikes_data else 0
            put_wall = max(strikes_data.items(), key=lambda x: x[1]["puts"])[0] if strikes_data else 0
            
            return {
                "currency": currency,
                "current_price": round(current_price, 2),
                "call_wall": call_wall,
                "put_wall": put_wall,
                "significant_strikes": [{"strike": s, "total_oi": round(oi, 2)} for s, oi in significant_strikes],
                "interpretation": f"Call wall at ${call_wall:,.0f} (resistance), Put wall at ${put_wall:,.0f} (support)",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"OI by strike error: {e}")
            return {"error": str(e)}
    
    async def get_full_options_analysis(self, currency: str = "BTC") -> Dict:
        """Get comprehensive options analysis"""
        tasks = [
            self.calculate_max_pain(currency),
            self.calculate_put_call_ratio(currency),
            self.get_oi_by_strike(currency),
        ]
        
        max_pain, pcr, oi_strikes = await asyncio.gather(*tasks, return_exceptions=True)
        
        if isinstance(max_pain, Exception):
            max_pain = {"error": str(max_pain)}
        if isinstance(pcr, Exception):
            pcr = {"error": str(pcr)}
        if isinstance(oi_strikes, Exception):
            oi_strikes = {"error": str(oi_strikes)}
        
        # Combine signals
        signals = []
        
        if max_pain.get("bias") in ["BULLISH"]:
            signals.append("BUY")
        elif max_pain.get("bias") in ["BEARISH"]:
            signals.append("SELL")
        
        if pcr.get("sentiment") in ["BULLISH", "EXTREME_BEARISH"]:  # Extreme bearish = contrarian bullish
            signals.append("BUY")
        elif pcr.get("sentiment") in ["BEARISH", "EXTREME_BULLISH"]:  # Extreme bullish = contrarian bearish
            signals.append("SELL")
        
        buy_count = signals.count("BUY")
        sell_count = signals.count("SELL")
        
        if buy_count > sell_count:
            overall = "BULLISH"
        elif sell_count > buy_count:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        return {
            "currency": currency,
            "overall_bias": overall,
            "max_pain": max_pain,
            "put_call_ratio": pcr,
            "oi_distribution": oi_strikes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
options_analyzer = OptionsAnalyzer()
