"""
AEON ARBITRAGE DETECTOR (Moltbot-inspired)
Scans price differences across exchanges for arbitrage opportunities.
Uses ccxt to check multiple exchanges in parallel.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
import ccxt

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=5)

EXCHANGES_CONFIG = [
    {"id": "mexc", "name": "MEXC"},
    {"id": "binance", "name": "Binance"},
    {"id": "bybit", "name": "Bybit"},
    {"id": "okx", "name": "OKX"},
    {"id": "kucoin", "name": "KuCoin"},
]

ARBI_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT"
]


class ArbitrageDetector:
    def __init__(self):
        self.exchanges = {}
        self.cache = {}
        self.cache_ttl = 30
        self.opportunities: List[Dict] = []
        self.max_opportunities = 50
        self.min_spread_pct = 0.3
        self._init_exchanges()

    def _init_exchanges(self):
        for ex in EXCHANGES_CONFIG:
            try:
                exchange_class = getattr(ccxt, ex["id"])
                self.exchanges[ex["id"]] = {
                    "instance": exchange_class({"enableRateLimit": True, "timeout": 8000}),
                    "name": ex["name"]
                }
            except Exception as e:
                logger.warning(f"Could not init {ex['id']}: {e}")

    async def _fetch_ticker(self, exchange_id: str, symbol: str) -> Dict:
        try:
            ex = self.exchanges.get(exchange_id)
            if not ex:
                return {}
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                executor,
                lambda: ex["instance"].fetch_ticker(symbol)
            )
            return {
                "exchange": exchange_id,
                "exchange_name": ex["name"],
                "symbol": symbol,
                "bid": ticker.get("bid", 0),
                "ask": ticker.get("ask", 0),
                "last": ticker.get("last", 0),
                "volume": ticker.get("baseVolume", 0)
            }
        except Exception as e:
            return {}

    async def scan_symbol(self, symbol: str) -> Dict:
        tasks = [self._fetch_ticker(ex_id, symbol) for ex_id in self.exchanges]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        prices = []
        for r in results:
            if isinstance(r, dict) and r.get("last", 0) > 0:
                prices.append(r)

        if len(prices) < 2:
            return {"symbol": symbol, "opportunities": [], "exchanges_checked": len(prices)}

        opportunities = []
        for i, buy_ex in enumerate(prices):
            for j, sell_ex in enumerate(prices):
                if i == j:
                    continue
                buy_price = buy_ex.get("ask", buy_ex["last"])
                sell_price = sell_ex.get("bid", sell_ex["last"])

                if buy_price <= 0:
                    continue

                spread_pct = ((sell_price - buy_price) / buy_price) * 100

                if spread_pct >= self.min_spread_pct:
                    opportunities.append({
                        "buy_exchange": buy_ex["exchange_name"],
                        "sell_exchange": sell_ex["exchange_name"],
                        "buy_price": round(buy_price, 6),
                        "sell_price": round(sell_price, 6),
                        "spread_pct": round(spread_pct, 3),
                        "est_profit_per_1k": round(10 * spread_pct, 2),
                        "symbol": symbol
                    })

        opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)

        return {
            "symbol": symbol,
            "opportunities": opportunities[:5],
            "prices": [{
                "exchange": p["exchange_name"],
                "price": p["last"],
                "bid": p.get("bid", 0),
                "ask": p.get("ask", 0)
            } for p in prices],
            "exchanges_checked": len(prices),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def scan_all(self) -> Dict:
        cache_key = "scan_all"
        if cache_key in self.cache:
            ts = self.cache[cache_key].get("ts", 0)
            if (datetime.now(timezone.utc).timestamp() - ts) < self.cache_ttl:
                return self.cache[cache_key]["data"]

        all_opps = []
        all_prices = {}

        for symbol in ARBI_SYMBOLS:
            try:
                result = await self.scan_symbol(symbol)
                for opp in result.get("opportunities", []):
                    all_opps.append(opp)
                all_prices[symbol] = result.get("prices", [])
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Arbitrage scan error {symbol}: {e}")

        all_opps.sort(key=lambda x: x["spread_pct"], reverse=True)

        result = {
            "total_opportunities": len(all_opps),
            "best_opportunities": all_opps[:10],
            "prices": all_prices,
            "exchanges": [ex["name"] for ex in EXCHANGES_CONFIG if ex["id"] in self.exchanges],
            "symbols_scanned": len(ARBI_SYMBOLS),
            "min_spread": self.min_spread_pct,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.cache[cache_key] = {"data": result, "ts": datetime.now(timezone.utc).timestamp()}

        for opp in all_opps[:5]:
            self.opportunities.insert(0, {**opp, "found_at": datetime.now(timezone.utc).isoformat()})
        if len(self.opportunities) > self.max_opportunities:
            self.opportunities = self.opportunities[:self.max_opportunities]

        return result

    def get_recent_opportunities(self, limit: int = 20) -> List[Dict]:
        return self.opportunities[:limit]


arbitrage_detector = ArbitrageDetector()
