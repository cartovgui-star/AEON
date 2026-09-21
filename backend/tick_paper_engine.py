"""
AEON Tick Paper Engine
======================
Replaces 30s REST polling with a per-tick OKX WebSocket feed for intrabar-accurate
TP/SL fills on paper positions — matching TradingView paper trading behaviour.

Realism layers (each independently togglable):
  • SLIPPAGE_BPS     — SL/trail-stop fills worse than trigger (default 5 bps)
  • FUNDING_ENABLED  — OKX 8h funding costs applied to open perp positions
  • Spread on entry  — handled upstream by ORIA spread_adjusted_entry(); NOT doubled here

Toggle:  set TICK_MODE=1 in backend/.env  (or export it before starting PM2)
         TICK_MODE=0  → original 30s REST polling, this module is a no-op

OKX public WebSocket docs:
  https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-trades-channel
  Endpoint: wss://ws.okx.com:8443/ws/v5/public
  Channel:  trades
  instId:   BTC-USDT-SWAP  (perpetual swap format)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

# ── Config — edit these or set via env vars ───────────────────────────────────
TICK_MODE_ENABLED = os.getenv("TICK_MODE", "0") == "1"
SLIPPAGE_BPS      = int(os.getenv("TICK_SLIPPAGE_BPS", "5"))    # bps applied on SL/trail fills
FUNDING_ENABLED   = os.getenv("TICK_FUNDING", "1") == "1"       # apply OKX funding every 8h
FALLBACK_SECS     = 60      # if no tick for this long, run REST fallback
SYNC_INTERVAL     = 30      # seconds between subscription sync (catches newly opened positions)
LOG_TICK_EVERY    = 500     # log tick count every N ticks per symbol (reduces noise)

_OKX_WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
TRADE_FEE_PCT   = 0.0020   # must match paper_trading.py TRADE_FEE_PCT


# ── Symbol format helpers ─────────────────────────────────────────────────────

def _to_instid(symbol: str) -> str:
    """'BTC/USDT' → 'BTC-USDT-SWAP'"""
    base, quote = symbol.split("/")
    return f"{base}-{quote}-SWAP"


def _from_instid(instid: str) -> Optional[str]:
    """'BTC-USDT-SWAP' → 'BTC/USDT', None for non-SWAP instIds"""
    parts = instid.split("-")
    if len(parts) == 3 and parts[2] == "SWAP":
        return f"{parts[0]}/{parts[1]}"
    return None


# ── Main class ────────────────────────────────────────────────────────────────

class TickPaperEngine:
    """
    Connects to OKX public trades WebSocket, subscribes dynamically to all symbols
    that have open paper positions, and fires intrabar-accurate fills.

    Usage (from server.py):
        engine = TickPaperEngine(db, market_intel)
        asyncio.create_task(engine.run_forever())
    """

    def __init__(self, db, market_intel):
        self.db           = db
        self.market_intel = market_intel

        self._subscribed: Set[str] = set()     # OKX instIds currently subscribed
        self._last_tick_ts: float  = 0.0       # unix ts of last received trade tick
        self._connected            = False
        self._active               = False
        self._reconnect_delay      = 2.0
        self._max_delay            = 64.0

        # Counters for stats/logging
        self._tick_count: Dict[str, int] = {}  # symbol → tick count
        self._fill_count  = 0
        self._funding_payments_applied = 0
        self._session_start = time.time()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_stats(self) -> Dict:
        return {
            "connected":             self._connected,
            "mode":                  "tick" if TICK_MODE_ENABLED else "polling",
            "slippage_bps":          SLIPPAGE_BPS,
            "funding_enabled":       FUNDING_ENABLED,
            "subscribed_count":      len(self._subscribed),
            "subscribed_symbols":    [_from_instid(i) or i for i in sorted(self._subscribed)],
            "tick_counts":           {_from_instid(k) or k: v for k, v in self._tick_count.items()},
            "fills_this_session":    self._fill_count,
            "funding_applied":       self._funding_payments_applied,
            "last_tick_age_s":       round(time.time() - self._last_tick_ts, 1) if self._last_tick_ts else None,
            "uptime_s":              round(time.time() - self._session_start),
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def run_forever(self):
        """Entry point — runs forever with exponential-backoff reconnect."""
        self._active = True
        delay = self._reconnect_delay
        while self._active:
            try:
                await self._connect_and_stream()
                delay = self._reconnect_delay   # reset on clean exit
            except asyncio.CancelledError:
                logger.info("[TICK] Cancelled — shutting down")
                break
            except Exception as e:
                logger.warning(f"[TICK] Disconnected ({type(e).__name__}: {e}), reconnecting in {delay:.0f}s")
            finally:
                self._connected = False
            if not self._active:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._max_delay)

    def stop(self):
        self._active = False

    # ── WebSocket session ─────────────────────────────────────────────────────

    async def _connect_and_stream(self):
        logger.info(f"[TICK] Connecting → {_OKX_WS_PUBLIC}")
        async with websockets.connect(
            _OKX_WS_PUBLIC,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
        ) as ws:
            self._connected = True
            logger.info("[TICK] Connected to OKX public WS")

            # Subscribe immediately to all currently open symbols
            await self._sync_subscriptions(ws)

            # Spawn sub-tasks that run for the life of this connection
            sub_tasks = [
                asyncio.create_task(self._subscription_sync_loop(ws)),
                asyncio.create_task(self._fallback_loop()),
            ]
            if FUNDING_ENABLED:
                sub_tasks.append(asyncio.create_task(self._funding_loop()))

            try:
                async for raw in ws:
                    if not self._active:
                        break
                    try:
                        await self._handle_message(raw)
                    except Exception as e:
                        logger.debug(f"[TICK] Message handler error: {e}")
            finally:
                for t in sub_tasks:
                    t.cancel()

    # ── Subscription management ───────────────────────────────────────────────

    async def _sync_subscriptions(self, ws):
        """Subscribe to any new symbols that have open positions."""
        needed = await self._get_open_instids()
        new = needed - self._subscribed
        if not new:
            return
        args = [{"channel": "trades", "instId": iid} for iid in sorted(new)]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))
        self._subscribed |= new
        symbols = [_from_instid(i) or i for i in new]
        logger.info(f"[TICK] Subscribed to {len(new)} new symbol(s): {symbols}")

    async def _subscription_sync_loop(self, ws):
        """Re-sync subscriptions every SYNC_INTERVAL seconds (catches newly opened positions)."""
        while True:
            await asyncio.sleep(SYNC_INTERVAL)
            try:
                await self._sync_subscriptions(ws)
            except ConnectionClosed:
                break
            except Exception as e:
                logger.debug(f"[TICK] Sync loop error: {e}")

    async def _get_open_instids(self) -> Set[str]:
        """Query DB for all symbols with currently open positions → OKX instIds."""
        instids: Set[str] = set()
        from paper_trading import ACCOUNTS
        for acc_id in ACCOUNTS:
            try:
                acc = await self.db.paper_accounts.find_one(
                    {"_id": acc_id}, {"positions": 1}
                )
                if not acc:
                    continue
                for pos in acc.get("positions", []):
                    if pos.get("status") == "open":
                        sym = pos.get("symbol", "")
                        if "/" in sym:
                            instids.add(_to_instid(sym))
            except Exception as e:
                logger.debug(f"[TICK] get_open_instids error for {acc_id}: {e}")
        return instids

    # ── Message handling ──────────────────────────────────────────────────────

    async def _handle_message(self, raw: str):
        msg = json.loads(raw)

        # WS control events
        event = msg.get("event")
        if event == "subscribe":
            logger.debug(f"[TICK] Subscribe confirmed: {msg.get('arg', {}).get('instId')}")
            return
        if event == "error":
            logger.warning(f"[TICK] OKX WS error: {msg.get('msg')} (code {msg.get('code')})")
            return

        # Trade data
        arg    = msg.get("arg", {})
        instid = arg.get("instId", "")
        symbol = _from_instid(instid)
        if not symbol:
            return

        data = msg.get("data", [])
        if not data:
            return

        self._last_tick_ts = time.time()

        # Each message may carry multiple trade prints — process all
        for trade in data:
            try:
                price = float(trade["px"])
            except (KeyError, ValueError, TypeError):
                continue

            # Count ticks per symbol for stats, log occasionally
            self._tick_count[instid] = self._tick_count.get(instid, 0) + 1
            if self._tick_count[instid] % LOG_TICK_EVERY == 0:
                logger.debug(
                    f"[TICK] {symbol} ${price:,.2f} "
                    f"| ticks={self._tick_count[instid]} fills={self._fill_count}"
                )

            await self._check_fills(symbol, price)

    # ── Fill handler ──────────────────────────────────────────────────────────

    async def _check_fills(self, symbol: str, price: float):
        """
        On each tick, call update_position_price for all accounts holding symbol.
        Slippage is passed through so SL/trail fills are priced realistically.
        Engine manager is notified on close for win-rate tracking.
        """
        from paper_trading import paper_trading, ACCOUNTS
        if not paper_trading:
            return

        for acc_id in ACCOUNTS:
            try:
                result = await paper_trading.update_position_price(
                    acc_id, symbol, price, slippage_bps=SLIPPAGE_BPS
                )
                if result is None:
                    continue  # no open position or still open, nothing to report

                self._fill_count += 1
                reason    = result.get("close_reason", "closed")
                pnl       = result.get("realized_pnl", 0)
                exit_p    = result.get("exit_price", price)
                direction = result.get("direction", "")
                lev       = result.get("leverage", 1)
                strategy  = result.get("strategy", "")
                pnl_sign  = "+" if pnl >= 0 else ""

                logger.info(
                    f"[TICK-FILL] {symbol} {direction}{lev}x | {reason} @ ${exit_p:,.4f} "
                    f"| PnL {pnl_sign}${pnl:,.2f} | {acc_id} | {strategy} "
                    f"| slippage={SLIPPAGE_BPS}bps"
                )

                # Notify engine manager so win rates and trade records update
                unified_id = result.get("signal_data", {}).get("unified_trade_id")
                if unified_id:
                    try:
                        from aeon_engine_system import get_engine_manager
                        get_engine_manager().close_trade_by_id(unified_id, exit_p, pnl)
                    except Exception as em_err:
                        logger.debug(f"[TICK] Engine manager notify failed: {em_err}")

            except Exception as e:
                logger.debug(f"[TICK] check_fills error [{acc_id}/{symbol}]: {e}")

    # ── Fallback polling ──────────────────────────────────────────────────────

    async def _fallback_loop(self):
        """
        If no tick arrives for FALLBACK_SECS, fall back to REST price fetch.
        Handles WS silence gaps so positions aren't stranded.
        """
        while True:
            await asyncio.sleep(FALLBACK_SECS)
            age = time.time() - self._last_tick_ts if self._last_tick_ts else FALLBACK_SECS + 1
            if age < FALLBACK_SECS:
                continue  # ticks are fresh, nothing to do

            logger.warning(f"[TICK] No ticks for {age:.0f}s — activating REST fallback")
            try:
                from paper_trading import paper_trading, ACCOUNTS
                if not paper_trading:
                    continue

                # Collect all open symbols
                symbols: Set[str] = set()
                for acc_id in ACCOUNTS:
                    acc = await self.db.paper_accounts.find_one(
                        {"_id": acc_id}, {"positions": 1}
                    )
                    if acc:
                        for pos in acc.get("positions", []):
                            if pos.get("status") == "open":
                                sym = pos.get("symbol")
                                if sym:
                                    symbols.add(sym)

                for sym in symbols:
                    try:
                        ticker = await self.market_intel.get_ticker(sym)
                        price  = ticker.get("price") or ticker.get("last") if ticker else None
                        if price:
                            await self._check_fills(sym, float(price))
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"[TICK] Fallback loop error: {e}")

    # ── Funding ───────────────────────────────────────────────────────────────

    async def _funding_loop(self):
        """
        Apply OKX perpetual funding costs at each 8h settlement window.
        OKX settles at 00:00, 08:00, 16:00 UTC.

        Sign convention (verified against OKX docs):
          positive funding rate → longs pay shorts
          negative funding rate → shorts pay longs
          funding_payment = position_size_usd × |rate|
          LONG  position: delta = -position_size_usd × rate  (negative = pay)
          SHORT position: delta = +position_size_usd × rate  (positive = receive)
        """
        while True:
            # Sleep until 1 minute past the next OKX settlement
            now = datetime.now(timezone.utc)
            current_window = (now.hour // 8) * 8
            next_window_h  = current_window + 8
            if next_window_h >= 24:
                next_dt = (now + timedelta(days=1)).replace(
                    hour=0, minute=1, second=0, microsecond=0
                )
            else:
                next_dt = now.replace(
                    hour=next_window_h, minute=1, second=0, microsecond=0
                )
            wait = (next_dt - now).total_seconds()
            logger.info(
                f"[FUNDING] Next settlement at {next_dt.strftime('%H:%M UTC')} "
                f"({wait/3600:.1f}h from now)"
            )
            await asyncio.sleep(max(wait, 60))
            await self._apply_funding_all()

    async def _apply_funding_all(self):
        """Fetch current OKX funding rates and apply to all open positions."""
        from paper_trading import paper_trading, ACCOUNTS
        if not paper_trading:
            return

        # Group open positions by symbol so we only fetch rate once per symbol
        by_symbol: Dict[str, List[tuple]] = {}  # symbol → [(acc_id, pos), ...]
        for acc_id in ACCOUNTS:
            try:
                acc = await self.db.paper_accounts.find_one(
                    {"_id": acc_id}, {"positions": 1}
                )
                if not acc:
                    continue
                for pos in acc.get("positions", []):
                    if pos.get("status") == "open":
                        sym = pos.get("symbol")
                        if sym:
                            by_symbol.setdefault(sym, []).append((acc_id, pos))
            except Exception as e:
                logger.debug(f"[FUNDING] Position fetch error for {acc_id}: {e}")

        if not by_symbol:
            return

        logger.info(f"[FUNDING] Applying funding for {len(by_symbol)} symbol(s)")

        for symbol, pos_list in by_symbol.items():
            try:
                rate_data = await self.market_intel.get_current_funding_rate(symbol)
                rate = float(rate_data.get("funding_rate", 0.0))
                if rate == 0.0:
                    continue

                for acc_id, pos in pos_list:
                    size      = float(pos.get("position_size_usd", 0))
                    direction = pos.get("direction", "LONG")
                    pos_id    = pos.get("id")
                    if not size or not pos_id:
                        continue

                    # Positive rate: longs pay, shorts receive
                    delta = round(size * rate * (1.0 if direction == "SHORT" else -1.0), 6)
                    sign  = "+" if delta >= 0 else ""

                    # Apply atomically: balance and running funding_pnl on the position
                    await self.db.paper_accounts.update_one(
                        {"_id": acc_id, "positions.id": pos_id},
                        {
                            "$inc": {
                                "balance":                 delta,
                                "total_pnl":               delta,
                                "positions.$.funding_pnl": delta,
                            }
                        }
                    )
                    self._funding_payments_applied += 1
                    logger.info(
                        f"[FUNDING] {symbol} {direction} [{acc_id}] "
                        f"rate {rate*100:+.4f}% "
                        f"size ${size:,.0f} → {sign}${delta:.4f}"
                    )

            except Exception as e:
                logger.warning(f"[FUNDING] Error for {symbol}: {e}")


# ── Module-level singleton ────────────────────────────────────────────────────

_tick_engine: Optional[TickPaperEngine] = None


def get_tick_engine() -> Optional[TickPaperEngine]:
    return _tick_engine


def init_tick_engine(db, market_intel) -> TickPaperEngine:
    global _tick_engine
    _tick_engine = TickPaperEngine(db, market_intel)
    return _tick_engine
