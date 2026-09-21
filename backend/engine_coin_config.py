"""
ENGINE COIN CONFIG — Dynamic Coin Selection
=============================================
All engines read their trading pairs from here instead of hardcoded lists.
Configure per-engine or globally.
"""

import asyncio
import logging
from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default top 20 coins (by market cap)
DEFAULT_TOP_20 = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "NEAR/USDT", "TRX/USDT", "UNI/USDT", "LTC/USDT", "ATOM/USDT",
    "POL/USDT", "OP/USDT", "FIL/USDT", "SUI/USDT", "INJ/USDT",
]

class EngineCoinConfig:
    """Manage per-engine coin lists via MongoDB"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.cache = {}
        self.cache_ts = {}
        self.CACHE_TTL = 300  # 5 minutes

    async def get_coins(self, engine_name: str) -> List[str]:
        """Get coins for engine (from cache or DB)"""
        # Check cache
        if engine_name in self.cache:
            age = (datetime.now(timezone.utc) - self.cache_ts[engine_name]).total_seconds()
            if age < self.CACHE_TTL:
                return self.cache[engine_name]

        # Fetch from DB
        doc = await self.db.engine_coin_config.find_one({"_id": engine_name})
        if doc and "coins" in doc:
            coins = doc["coins"]
        else:
            coins = DEFAULT_TOP_20

        # Cache it
        self.cache[engine_name] = coins
        self.cache_ts[engine_name] = datetime.now(timezone.utc)

        return coins

    async def set_coins(self, engine_name: str, coins: List[str]) -> bool:
        """Replace engine's coin list"""
        await self.db.engine_coin_config.update_one(
            {"_id": engine_name},
            {
                "$set": {
                    "coins": coins,
                    "updated_at": datetime.now(timezone.utc),
                    "count": len(coins),
                }
            },
            upsert=True
        )
        # Clear cache
        self.cache.pop(engine_name, None)
        logger.info(f"[CONFIG] {engine_name}: coins set to {coins}")
        return True

    async def add_coin(self, engine_name: str, coin: str) -> bool:
        """Add single coin to engine"""
        coins = await self.get_coins(engine_name)
        if coin not in coins:
            coins.append(coin)
            await self.set_coins(engine_name, coins)
            logger.info(f"[CONFIG] {engine_name}: added {coin}")
            return True
        return False

    async def remove_coin(self, engine_name: str, coin: str) -> bool:
        """Remove single coin from engine"""
        coins = await self.get_coins(engine_name)
        if coin in coins:
            coins.remove(coin)
            await self.set_coins(engine_name, coins)
            logger.info(f"[CONFIG] {engine_name}: removed {coin}")
            return True
        return False

    async def reset_to_default(self, engine_name: str) -> bool:
        """Reset engine to default top 20"""
        await self.set_coins(engine_name, DEFAULT_TOP_20)
        logger.info(f"[CONFIG] {engine_name}: reset to DEFAULT_TOP_20")
        return True

    async def get_status(self, engine_name: str) -> Dict:
        """Get current config status"""
        coins = await self.get_coins(engine_name)
        return {
            "engine": engine_name,
            "coins": coins,
            "count": len(coins),
            "is_default": coins == DEFAULT_TOP_20,
        }

    async def get_all_status(self) -> Dict[str, Dict]:
        """Get status for all engines"""
        engines = [
            "autonomous_trader_v2",
            "free_will_v2",
            "elite_strategy_v3",
            "vwap_scalper",
            "yolo_engine",
            "dual_trading_engine",
            "institutional_scalper_v1",
            "tcn_neural_engine",
        ]

        result = {}
        for engine in engines:
            result[engine] = await self.get_status(engine)

        return result


# Module-level singleton
_config_instance: Optional[EngineCoinConfig] = None

def init_coin_config(db: AsyncIOMotorDatabase) -> EngineCoinConfig:
    global _config_instance
    _config_instance = EngineCoinConfig(db)
    return _config_instance

def get_coin_config() -> Optional[EngineCoinConfig]:
    return _config_instance
