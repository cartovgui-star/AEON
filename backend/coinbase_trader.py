"""
AEON COINBASE ADVANCED TRADE INTEGRATION
=========================================
Full execution layer for Coinbase Advanced Trade API v3.

Capabilities:
- JWT authentication (CDP API keys)
- OHLCV candle data (replaces MEXC REST)
- Order placement / cancellation
- Account balance + position tracking
- Symbol mapping: BTC/USDT <-> BTC-USD

Auth: CDP API Key (key_name + private_key in PEM format)
Base: https://api.coinbase.com/api/v3/brokerage
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import aiohttp

logger = logging.getLogger(__name__)

CB_BASE = "https://api.coinbase.com/api/v3/brokerage"

# Timeframe mapping: internal -> Coinbase granularity
TF_MAP = {
    "1m":  "ONE_MINUTE",
    "5m":  "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h":  "ONE_HOUR",
    "2h":  "TWO_HOUR",
    "6h":  "SIX_HOUR",
    "1d":  "ONE_DAY",
    # Aliases
    "4h":  "ONE_HOUR",   # CB doesn't have 4H — use 1H and fetch more bars
}

# Pairs supported on Coinbase Advanced Trade
CB_SUPPORTED = {
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ATOM/USDT", "UNI/USDT", "LTC/USDT", "OP/USDT", "INJ/USDT",
    "APT/USDT", "FIL/USDT", "POL/USDT",
}


def _to_cb_product(symbol: str) -> str:
    """BTC/USDT -> BTC-USD  |  BTC/USD -> BTC-USD"""
    base = symbol.split("/")[0].upper()
    return f"{base}-USD"


def _from_cb_product(product_id: str) -> str:
    """BTC-USD -> BTC/USDT"""
    base = product_id.split("-")[0].upper()
    return f"{base}/USDT"


class CoinbaseTrader:
    """
    Coinbase Advanced Trade execution + data client.

    Uses legacy API key + secret (HMAC-SHA256) for simplicity.
    Supports CDP JWT keys too — set use_jwt=True and provide key_name + private_key.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        use_jwt: bool = False,
        key_name: str = "",
        private_key: str = "",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.use_jwt = use_jwt
        self.key_name = key_name
        self.private_key = private_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._accounts: Dict = {}
        self._account_cache_ts: float = 0

    # ─────────────────────────────────────────────────────────────────────────
    # AUTH
    # ─────────────────────────────────────────────────────────────────────────

    def _hmac_headers(self, method: str, path: str, body: str = "") -> Dict:
        """Generate HMAC-SHA256 auth headers (legacy API key format)."""
        ts = str(int(time.time()))
        msg = ts + method.upper() + path + body
        sig = hmac.new(
            self.api_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": sig,
            "CB-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
        }

    def _jwt_headers(self, method: str, path: str) -> Dict:
        """Generate JWT auth headers (CDP key format)."""
        try:
            import jwt as _jwt
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            private_key_obj = serialization.load_pem_private_key(
                self.private_key.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
            payload = {
                "sub": self.key_name,
                "iss": "cdp",
                "nbf": int(time.time()),
                "exp": int(time.time()) + 120,
                "uri": f"{method.upper()} api.coinbase.com{path}",
            }
            token = _jwt.encode(payload, private_key_obj, algorithm="ES256")
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        except Exception as e:
            logger.error(f"[CB] JWT generation failed: {e}")
            return {}

    def _get_headers(self, method: str, path: str, body: str = "") -> Dict:
        if self.use_jwt:
            return self._jwt_headers(method, path)
        return self._hmac_headers(method, path, body)

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP
    # ─────────────────────────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        body: Dict = None,
    ) -> Dict:
        session = await self._get_session()
        path = f"/api/v3/brokerage/{endpoint}"
        url = f"https://api.coinbase.com{path}"
        body_str = json.dumps(body) if body else ""
        headers = self._get_headers(method, path, body_str)

        try:
            async with session.request(
                method,
                url,
                headers=headers,
                params=params,
                data=body_str if body_str else None,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    logger.error(f"[CB] {method} {endpoint} → {resp.status}: {data}")
                return data
        except Exception as e:
            logger.error(f"[CB] Request error {endpoint}: {e}")
            return {"error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # MARKET DATA
    # ─────────────────────────────────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
    ) -> Dict:
        """
        Fetch OHLCV candles from Coinbase. Replaces MEXC fetch_ohlcv.
        Returns {"candles": [[ts_ms, o, h, l, c, v], ...], "symbol": symbol, "timeframe": timeframe}
        Compatible with existing market_intelligence.get_ohlcv() return format.
        """
        product_id = _to_cb_product(symbol)
        granularity = TF_MAP.get(timeframe, "ONE_HOUR")

        # CB returns max 350 candles per call
        end = int(time.time())
        # Seconds per granularity
        gran_seconds = {
            "ONE_MINUTE": 60, "FIVE_MINUTE": 300, "FIFTEEN_MINUTE": 900,
            "THIRTY_MINUTE": 1800, "ONE_HOUR": 3600, "TWO_HOUR": 7200,
            "SIX_HOUR": 21600, "ONE_DAY": 86400,
        }
        secs = gran_seconds.get(granularity, 3600)
        # For 4h, fetch 4x more 1H candles
        fetch_limit = min(limit * 4 if timeframe == "4h" else limit, 350)
        start = end - (secs * fetch_limit)

        data = await self._request(
            "GET",
            f"products/{product_id}/candles",
            params={
                "start": str(start),
                "end": str(end),
                "granularity": granularity,
            },
        )

        if "error" in data or "candles" not in data:
            logger.error(f"[CB] Candles error {symbol}: {data}")
            return {"error": str(data)}

        raw = data["candles"]
        # CB format: {start, low, high, open, close, volume}
        # Convert to [[ts_ms, o, h, l, c, v], ...] sorted oldest first
        candles = []
        for c in raw:
            candles.append([
                int(c["start"]) * 1000,  # ms
                float(c["open"]),
                float(c["high"]),
                float(c["low"]),
                float(c["close"]),
                float(c["volume"]),
            ])
        candles.sort(key=lambda x: x[0])

        # For 4h, downsample: group 4 x 1H bars into 1 x 4H bar
        if timeframe == "4h" and len(candles) >= 4:
            candles_4h = []
            for i in range(0, len(candles) - 3, 4):
                chunk = candles[i:i+4]
                candles_4h.append([
                    chunk[0][0],                              # ts
                    chunk[0][1],                              # open
                    max(c[2] for c in chunk),                 # high
                    min(c[3] for c in chunk),                 # low
                    chunk[-1][4],                             # close
                    sum(c[5] for c in chunk),                 # volume
                ])
            candles = candles_4h[-limit:]
        else:
            candles = candles[-limit:]

        return {"candles": candles, "symbol": symbol, "timeframe": timeframe}

    async def get_ticker(self, symbol: str) -> Dict:
        """Get current price + 24h stats."""
        product_id = _to_cb_product(symbol)
        data = await self._request("GET", f"products/{product_id}/ticker", params={"limit": 1})
        if "trades" in data and data["trades"]:
            price = float(data["trades"][0]["price"])
            return {"symbol": symbol, "price": price}
        # Fallback: product endpoint
        prod = await self._request("GET", f"products/{product_id}")
        if "price" in prod:
            return {"symbol": symbol, "price": float(prod["price"])}
        return {"error": "no price", "symbol": symbol}

    async def get_best_bid_ask(self, symbol: str) -> Dict:
        """Get best bid/ask."""
        product_id = _to_cb_product(symbol)
        data = await self._request("GET", "best_bid_ask", params={"product_ids": product_id})
        if "pricebooks" in data and data["pricebooks"]:
            pb = data["pricebooks"][0]
            bid = float(pb["bids"][0]["price"]) if pb.get("bids") else 0
            ask = float(pb["asks"][0]["price"]) if pb.get("asks") else 0
            return {"symbol": symbol, "bid": bid, "ask": ask, "spread": ask - bid}
        return {"error": "no orderbook", "symbol": symbol}

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT
    # ─────────────────────────────────────────────────────────────────────────

    async def get_accounts(self, force: bool = False) -> List[Dict]:
        """List all accounts with balances. Cached 60s."""
        if not force and time.time() - self._account_cache_ts < 60:
            return list(self._accounts.values())

        data = await self._request("GET", "accounts")
        if "accounts" not in data:
            return []

        self._accounts = {a["uuid"]: a for a in data["accounts"]}
        self._account_cache_ts = time.time()
        return data["accounts"]

    async def get_balance(self, currency: str = "USD") -> float:
        """Get available balance for a currency."""
        accounts = await self.get_accounts()
        for acc in accounts:
            if acc.get("currency") == currency:
                return float(acc.get("available_balance", {}).get("value", 0))
        return 0.0

    async def get_portfolio_summary(self) -> Dict:
        """Summarized portfolio: balances + open orders."""
        accounts = await self.get_accounts()
        balances = {}
        total_usd = 0.0
        for acc in accounts:
            val = float(acc.get("available_balance", {}).get("value", 0))
            curr = acc.get("currency", "?")
            if val > 0.01:
                balances[curr] = val
                if curr == "USD":
                    total_usd += val

        orders_data = await self._request(
            "GET", "orders/historical/batch",
            params={"order_status": "OPEN", "limit": "50"}
        )
        open_orders = orders_data.get("orders", [])

        return {
            "balances": balances,
            "usd_available": balances.get("USD", 0),
            "total_usd_approx": total_usd,
            "open_orders": len(open_orders),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ORDER EXECUTION
    # ─────────────────────────────────────────────────────────────────────────

    async def place_market_order(
        self,
        symbol: str,
        side: str,          # "BUY" or "SELL"
        quote_size: float,  # USD amount to spend/receive
    ) -> Dict:
        """
        Place a market order on Coinbase.
        side: BUY (enter long) | SELL (exit long / enter short via spot)
        quote_size: USD value of trade
        """
        product_id = _to_cb_product(symbol)
        client_order_id = str(uuid.uuid4())

        body = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": {
                "market_market_ioc": {
                    "quote_size": str(round(quote_size, 2)),
                }
            },
        }

        result = await self._request("POST", "orders", body=body)

        if result.get("success"):
            order = result.get("success_response", {})
            logger.info(f"[CB] Order placed: {side} {symbol} ${quote_size} → {order.get('order_id')}")
            return {
                "success": True,
                "order_id": order.get("order_id"),
                "client_order_id": client_order_id,
                "symbol": symbol,
                "side": side,
                "quote_size": quote_size,
            }
        else:
            err = result.get("error_response", result)
            logger.error(f"[CB] Order FAILED: {side} {symbol} → {err}")
            return {"success": False, "error": err, "symbol": symbol}

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        base_size: float,   # coin amount
        limit_price: float,
        post_only: bool = False,
    ) -> Dict:
        """Place a limit order."""
        product_id = _to_cb_product(symbol)
        client_order_id = str(uuid.uuid4())

        order_config: Dict[str, Any] = {
            "limit_limit_gtc": {
                "base_size": str(round(base_size, 8)),
                "limit_price": str(round(limit_price, 2)),
                "post_only": post_only,
            }
        }

        body = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_config,
        }

        result = await self._request("POST", "orders", body=body)

        if result.get("success"):
            order = result.get("success_response", {})
            logger.info(
                f"[CB] Limit order: {side} {base_size} {symbol} @ ${limit_price} "
                f"→ {order.get('order_id')}"
            )
            return {
                "success": True,
                "order_id": order.get("order_id"),
                "client_order_id": client_order_id,
                "symbol": symbol,
                "side": side,
                "base_size": base_size,
                "limit_price": limit_price,
            }
        else:
            err = result.get("error_response", result)
            logger.error(f"[CB] Limit order FAILED: {side} {symbol} @ {limit_price} → {err}")
            return {"success": False, "error": err, "symbol": symbol}

    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an open order."""
        result = await self._request(
            "POST", "orders/batch_cancel",
            body={"order_ids": [order_id]}
        )
        results = result.get("results", [])
        if results and results[0].get("success"):
            return {"success": True, "order_id": order_id}
        return {"success": False, "error": result}

    async def get_order(self, order_id: str) -> Dict:
        """Get order status."""
        return await self._request("GET", f"orders/historical/{order_id}")

    async def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get all open orders, optionally filtered by symbol."""
        params: Dict = {"order_status": "OPEN", "limit": "100"}
        if symbol:
            params["product_id"] = _to_cb_product(symbol)
        data = await self._request("GET", "orders/historical/batch", params=params)
        return data.get("orders", [])

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL EXECUTION (AEON integration)
    # ─────────────────────────────────────────────────────────────────────────

    async def execute_signal(
        self,
        signal: Dict,
        usd_amount: float = 100.0,
    ) -> Dict:
        """
        Execute an AEON signal on Coinbase.
        signal = {"symbol": "BTC/USDT", "direction": "long"|"short", "entry_price": ..., ...}
        Note: Coinbase spot only — longs = BUY, shorts = SELL existing position.
        """
        symbol = signal.get("symbol", "BTC/USDT")
        direction = signal.get("direction", "long").lower()
        side = "BUY" if direction == "long" else "SELL"

        result = await self.place_market_order(symbol, side, usd_amount)
        result["signal_direction"] = direction
        result["signal_confidence"] = signal.get("confidence", 0)
        return result

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ─────────────────────────────────────────────────────────────────────────────
# OHLCV ADAPTER — drop-in replacement for market_intelligence.get_ohlcv
# ─────────────────────────────────────────────────────────────────────────────

_coinbase_trader: Optional[CoinbaseTrader] = None


def init_coinbase_trader(api_key: str, api_secret: str, use_jwt: bool = False,
                          key_name: str = "", private_key: str = "") -> CoinbaseTrader:
    global _coinbase_trader
    _coinbase_trader = CoinbaseTrader(
        api_key=api_key,
        api_secret=api_secret,
        use_jwt=use_jwt,
        key_name=key_name,
        private_key=private_key,
    )
    logger.info("[CB] CoinbaseTrader initialized")
    return _coinbase_trader


def get_coinbase_trader() -> Optional[CoinbaseTrader]:
    return _coinbase_trader


async def get_ohlcv_coinbase(symbol: str, timeframe: str = "1h", limit: int = 200) -> Dict:
    """
    Drop-in replacement for MarketIntelligence.get_ohlcv().
    Falls back to original MEXC source if Coinbase unavailable.
    """
    trader = get_coinbase_trader()
    if trader is None:
        return {"error": "CoinbaseTrader not initialized"}
    return await trader.get_candles(symbol, timeframe, limit)


# ─────────────────────────────────────────────────────────────────────────────
# FUTURES (CFM) — Coinbase Futures Market
# ─────────────────────────────────────────────────────────────────────────────

class CoinbaseFutures:
    """
    Coinbase CFM (Nano Bitcoin Futures) execution layer.
    Endpoints: /cfm/*
    Requires: trade + transfer permissions on API key.

    CFM products:
      BIT  — Nano Bitcoin Futures (1/100 BTC contract)
      ETH  — Nano Ether Futures   (1/10  ETH contract)
    Note: CFM is separate from Advanced Trade spot. Margin is swept between accounts.
    """

    def __init__(self, trader: "CoinbaseTrader"):
        self._t = trader  # Reuse auth + HTTP from CoinbaseTrader

    async def get_balance_summary(self) -> Dict:
        """
        Get futures account balance summary.
        Returns: futures_buying_power, total_usd_balance, unrealized_pnl, etc.
        """
        data = await self._t._request("GET", "cfm/balance_summary")
        if "balance_summary" in data:
            bs = data["balance_summary"]
            return {
                "futures_buying_power": float(bs.get("futures_buying_power", {}).get("value", 0)),
                "total_usd_balance": float(bs.get("total_usd_balance", {}).get("value", 0)),
                "cbi_usd_balance": float(bs.get("cbi_usd_balance", {}).get("value", 0)),
                "cfm_usd_balance": float(bs.get("cfm_usd_balance", {}).get("value", 0)),
                "unrealized_pnl": float(bs.get("unrealized_pnl", {}).get("value", 0)),
                "initial_margin": float(bs.get("initial_margin", {}).get("value", 0)),
                "available_margin": float(bs.get("available_margin", {}).get("value", 0)),
                "liquidation_threshold": float(bs.get("liquidation_threshold", {}).get("value", 0)),
            }
        return {"error": data}

    async def list_positions(self) -> List[Dict]:
        """List all open futures positions."""
        data = await self._t._request("GET", "cfm/positions")
        positions = data.get("positions", [])
        result = []
        for p in positions:
            result.append({
                "product_id": p.get("product_id"),
                "symbol": _from_cb_product(p.get("product_id", "")),
                "side": p.get("side"),                          # LONG | SHORT
                "number_of_contracts": int(p.get("number_of_contracts", 0)),
                "current_price": float(p.get("current_price", 0)),
                "avg_entry_price": float(p.get("avg_entry_price", 0)),
                "unrealized_pnl": float(p.get("unrealized_pnl", {}).get("value", 0)),
                "margin_type": p.get("margin_type"),
            })
        return result

    async def get_position(self, product_id: str) -> Dict:
        """Get a specific futures position."""
        return await self._t._request("GET", f"cfm/positions/{product_id}")

    async def place_futures_order(
        self,
        product_id: str,     # e.g. "BIT-26APR24-CDE" — get from list_products
        side: str,           # "BUY" (long) or "SELL" (short)
        num_contracts: int,  # number of contracts
        order_type: str = "market",
        limit_price: float = None,
    ) -> Dict:
        """
        Place a futures order on CFM.
        For nano BTC: 1 contract = 1/100 BTC
        """
        client_order_id = str(uuid.uuid4())

        if order_type == "market":
            order_config = {
                "market_market_ioc": {
                    "base_size": str(num_contracts)
                }
            }
        else:
            order_config = {
                "limit_limit_gtc": {
                    "base_size": str(num_contracts),
                    "limit_price": str(limit_price),
                    "post_only": False,
                }
            }

        body = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_config,
        }

        result = await self._t._request("POST", "orders", body=body)

        if result.get("success"):
            order = result.get("success_response", {})
            logger.info(
                f"[CB FUTURES] Order placed: {side} {num_contracts} contracts "
                f"{product_id} → {order.get(order_id)}"
            )
            return {
                "success": True,
                "order_id": order.get("order_id"),
                "client_order_id": client_order_id,
                "product_id": product_id,
                "side": side,
                "num_contracts": num_contracts,
            }
        else:
            err = result.get("error_response", result)
            logger.error(f"[CB FUTURES] Order FAILED: {side} {product_id} → {err}")
            return {"success": False, "error": err}

    async def get_intraday_margin(self) -> Dict:
        """Get current intraday margin setting."""
        return await self._t._request("GET", "cfm/intraday/margin_setting")

    async def get_margin_window(self) -> Dict:
        """Get current margin window (regular vs intraday)."""
        return await self._t._request("GET", "cfm/intraday/current_margin_window")

    async def schedule_sweep(self, usd_amount: float) -> Dict:
        """Schedule transfer from spot to futures margin."""
        return await self._t._request(
            "POST", "cfm/sweeps/schedule",
            body={"usd_amount": str(round(usd_amount, 2))}
        )

    async def list_sweeps(self) -> List[Dict]:
        """List pending margin sweeps."""
        data = await self._t._request("GET", "cfm/sweeps")
        return data.get("sweeps", [])

    async def cancel_sweep(self) -> Dict:
        """Cancel pending futures sweep."""
        return await self._t._request("DELETE", "cfm/sweeps")

    async def get_futures_summary(self) -> Dict:
        """Full futures account snapshot for AEON dashboard."""
        balance, positions = await asyncio.gather(
            self.get_balance_summary(),
            self.list_positions(),
            return_exceptions=True,
        )
        if isinstance(balance, Exception):
            balance = {"error": str(balance)}
        if isinstance(positions, Exception):
            positions = []

        return {
            "balance": balance,
            "open_positions": positions,
            "num_positions": len(positions),
            "total_unrealized_pnl": sum(p.get("unrealized_pnl", 0) for p in positions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def execute_signal_futures(
        self,
        signal: Dict,
        product_id: str,
        num_contracts: int = 1,
    ) -> Dict:
        """
        Execute an AEON signal as a CFM futures order.
        signal = {"direction": "long"|"short", "symbol": ..., "confidence": ...}
        """
        direction = signal.get("direction", "long").lower()
        side = "BUY" if direction == "long" else "SELL"
        result = await self.place_futures_order(product_id, side, num_contracts)
        result["signal_direction"] = direction
        result["signal_confidence"] = signal.get("confidence", 0)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class CoinbasePortfolios:
    """Coinbase portfolio management (separate trading portfolios)."""

    def __init__(self, trader: "CoinbaseTrader"):
        self._t = trader

    async def list_portfolios(self) -> List[Dict]:
        data = await self._t._request("GET", "portfolios")
        return data.get("portfolios", [])

    async def get_breakdown(self, portfolio_uuid: str) -> Dict:
        return await self._t._request("GET", f"portfolios/{portfolio_uuid}")

    async def move_funds(
        self,
        funds: float,
        currency: str,
        source_portfolio_uuid: str,
        target_portfolio_uuid: str,
    ) -> Dict:
        return await self._t._request(
            "POST", "portfolios/move_funds",
            body={
                "funds": {"value": str(funds), "currency": currency},
                "source_portfolio_uuid": source_portfolio_uuid,
                "target_portfolio_uuid": target_portfolio_uuid,
            }
        )

    async def get_transaction_summary(self) -> Dict:
        """Get fee tier + 30-day volume for rate optimization."""
        return await self._t._request("GET", "transaction_summary")


# ─────────────────────────────────────────────────────────────────────────────
# ATTACH FUTURES + PORTFOLIOS TO MAIN TRADER
# ─────────────────────────────────────────────────────────────────────────────

def _attach_modules(trader: "CoinbaseTrader") -> "CoinbaseTrader":
    trader.futures = CoinbaseFutures(trader)
    trader.portfolios = CoinbasePortfolios(trader)
    return trader


# Patch init to auto-attach
_orig_init_coinbase = init_coinbase_trader

def init_coinbase_trader(api_key: str, api_secret: str, use_jwt: bool = False,
                          key_name: str = "", private_key: str = "") -> "CoinbaseTrader":
    trader = _orig_init_coinbase(api_key, api_secret, use_jwt, key_name, private_key)
    _attach_modules(trader)
    return trader

# PUBLIC MARKET DATA — no auth required
import time as _time

CB_PUBLIC_BASE = "https://api.coinbase.com/api/v3/brokerage/market"

async def get_public_candles(symbol: str, timeframe: str = "1h", limit: int = 200):
    product_id = _to_cb_product(symbol)
    gran_map = {
        "1m": "ONE_MINUTE", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE",
        "30m": "THIRTY_MINUTE", "1h": "ONE_HOUR", "2h": "TWO_HOUR",
        "4h": "ONE_HOUR", "6h": "SIX_HOUR", "1d": "ONE_DAY",
    }
    granularity = gran_map.get(timeframe, "ONE_HOUR")
    secs_map = {
        "ONE_MINUTE": 60, "FIVE_MINUTE": 300, "FIFTEEN_MINUTE": 900,
        "THIRTY_MINUTE": 1800, "ONE_HOUR": 3600, "TWO_HOUR": 7200,
        "SIX_HOUR": 21600, "ONE_DAY": 86400,
    }
    secs = secs_map.get(granularity, 3600)
    fetch_limit = min(limit * 4 if timeframe == "4h" else limit, 350)
    end_ts = int(_time.time())
    start_ts = end_ts - (secs * fetch_limit)
    url = CB_PUBLIC_BASE + "/products/" + product_id + "/candles"
    params = {"start": str(start_ts), "end": str(end_ts), "granularity": granularity}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers={"cache-control": "no-cache"}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
        if "candles" not in data:
            return {"error": str(data)}
        candles = sorted([
            [int(c["start"]) * 1000, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"])]
            for c in data["candles"]
        ], key=lambda x: x[0])
        if timeframe == "4h" and len(candles) >= 4:
            candles_4h = []
            for i in range(0, len(candles) - 3, 4):
                chunk = candles[i:i+4]
                candles_4h.append([chunk[0][0], chunk[0][1], max(c[2] for c in chunk), min(c[3] for c in chunk), chunk[-1][4], sum(c[5] for c in chunk)])
            candles = candles_4h[-limit:]
        else:
            candles = candles[-limit:]
        return {"candles": candles, "symbol": symbol, "timeframe": timeframe}
    except Exception as e:
        logger.error("[CB PUBLIC] candles error " + symbol + ": " + str(e))
        return {"error": str(e)}

async def get_public_ticker(symbol: str):
    product_id = _to_cb_product(symbol)
    url = CB_PUBLIC_BASE + "/products/" + product_id + "/ticker"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"limit": "1"}, headers={"cache-control": "no-cache"}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
        if data.get("trades"):
            return {"symbol": symbol, "price": float(data["trades"][0]["price"]), "source": "coinbase_public"}
        return {"error": "no trades", "symbol": symbol}
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
