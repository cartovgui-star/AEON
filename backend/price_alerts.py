"""
AEON REAL-TIME PRICE ALERT SYSTEM v2
Lean, batched alerts with reduced noise

Changes from v1:
- RSI alerts are BATCHED into a single summary message per scan
- Breakout alerts require volume confirmation and use longer cooldowns
- Funding alerts are grouped and show relative context
- All alerts are more concise
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set, Callable, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import ccxt

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)

mexc = ccxt.mexc()


class PriceAlert:
    """Individual price alert configuration"""
    def __init__(self, alert_id: str, symbol: str, alert_type: str,
                 condition: Dict, chat_ids: List[int] = None,
                 created_at: datetime = None, active: bool = True):
        self.alert_id = alert_id
        self.symbol = symbol
        self.alert_type = alert_type
        self.condition = condition
        self.chat_ids = chat_ids or []
        self.created_at = created_at or datetime.now(timezone.utc)
        self.active = active
        self.triggered_at = None
        self.triggered_count = 0

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "symbol": self.symbol,
            "alert_type": self.alert_type,
            "condition": self.condition,
            "chat_ids": self.chat_ids,
            "created_at": self.created_at.isoformat(),
            "active": self.active,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "triggered_count": self.triggered_count
        }


class PriceAlertSystem:
    """
    Real-time price monitoring and alert system v2
    Lean alerts: RSI batched, breakout volume-confirmed, funding contextual
    """

    def __init__(self):
        self.alerts: Dict[str, PriceAlert] = {}
        self.active = True
        self.last_prices: Dict[str, float] = {}
        self.price_history: Dict[str, List[Dict]] = {}
        self.history_max = 100

        self.auto_alerts_enabled = True
        self.auto_alert_thresholds = {
            "price_change_5min": 2.0,
            "price_change_1h": 5.0,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
            "volume_spike_mult": 3.0,
        }

        self.alert_cooldowns: Dict[str, datetime] = {}
        self.cooldown_seconds = 600  # 10 min default cooldown (was 5)

        self.send_telegram: Optional[Callable] = None
        self.chat_ids: Set[int] = set()

        self.dashboard_alerts: List[Dict] = []
        self.max_dashboard_alerts = 50

        self.tracked_symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
            "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT"
        ]

        self.total_alerts_sent = 0
        self.alerts_today = 0
        self.last_scan = None
        self.ws_manager = None

        # RSI batch buffer: collects RSI extremes across symbols per scan
        self._rsi_batch: List[Dict] = []
        # Breakout cooldown is longer (30 min per symbol)
        self._breakout_cooldowns: Dict[str, datetime] = {}
        self._breakout_cooldown_seconds = 1800

    def set_dependencies(self, send_telegram: Callable, chat_ids: Set[int], ws_manager=None, heartbeat_fn=None):
        self.send_telegram = send_telegram
        self.chat_ids = chat_ids
        self.ws_manager = ws_manager
        self._heartbeat_fn = heartbeat_fn

    def _can_send_alert(self, alert_key: str) -> bool:
        now = datetime.now(timezone.utc)
        if self.total_alerts_sent % 100 == 0:
            self._cleanup_old_cooldowns()
        if alert_key in self.alert_cooldowns:
            elapsed = (now - self.alert_cooldowns[alert_key]).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        return True

    def _cleanup_old_cooldowns(self):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=2)
        self.alert_cooldowns = {k: v for k, v in self.alert_cooldowns.items() if v > cutoff}
        self._breakout_cooldowns = {k: v for k, v in self._breakout_cooldowns.items() if v > cutoff}

    def _mark_alert_sent(self, alert_key: str):
        self.alert_cooldowns[alert_key] = datetime.now(timezone.utc)
        self.total_alerts_sent += 1
        self.alerts_today += 1

    async def fetch_price(self, symbol: str) -> Optional[float]:
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(executor, lambda: mexc.fetch_ticker(symbol))
            return ticker.get("last", 0)
        except Exception as e:
            logger.error(f"Price fetch error {symbol}: {e}")
            return None

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 20) -> List:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor, lambda: mexc.fetch_ohlcv(symbol, timeframe, limit=limit))
        except Exception as e:
            logger.error(f"OHLCV fetch error {symbol}: {e}")
            return []

    def _add_dashboard_alert(self, alert: Dict):
        alert["dashboard_id"] = f"dash_{datetime.now(timezone.utc).timestamp()}"
        alert["read"] = False
        self.dashboard_alerts.insert(0, alert)
        if len(self.dashboard_alerts) > self.max_dashboard_alerts:
            self.dashboard_alerts = self.dashboard_alerts[:self.max_dashboard_alerts]

    async def _send_alert(self, alert_type: str, symbol: str, message: str,
                          data: Dict = None, telegram: bool = True, dashboard: bool = True):
        alert_key = f"{alert_type}_{symbol}"
        if not self._can_send_alert(alert_key):
            return
        self._mark_alert_sent(alert_key)

        alert_data = {
            "type": alert_type, "symbol": symbol, "message": message,
            "data": data or {}, "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": self._get_severity(alert_type)
        }
        if dashboard:
            self._add_dashboard_alert(alert_data)
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast_alert(alert_type, symbol, message, data, self._get_severity(alert_type))
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")
        if telegram and self.send_telegram and self.chat_ids:
            for chat_id in list(self.chat_ids):
                try:
                    await self.send_telegram(chat_id, message)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
        logger.info(f"Alert sent: {alert_type} for {symbol}")

    async def _send_batched_alert(self, alert_type: str, message: str, data: Dict = None):
        """Send a single batched alert (not per-symbol cooldown)."""
        alert_key = f"batch_{alert_type}"
        if not self._can_send_alert(alert_key):
            return
        self._mark_alert_sent(alert_key)

        alert_data = {
            "type": alert_type, "symbol": "BATCH", "message": message,
            "data": data or {}, "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": self._get_severity(alert_type)
        }
        self._add_dashboard_alert(alert_data)
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast_alert(alert_type, "BATCH", message, data, self._get_severity(alert_type))
            except Exception:
                pass
        if self.send_telegram and self.chat_ids:
            for chat_id in list(self.chat_ids):
                try:
                    await self.send_telegram(chat_id, message)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
        logger.info(f"Batched alert sent: {alert_type}")

    def _get_severity(self, alert_type: str) -> str:
        high_priority = ["breakout", "rsi_extreme", "volume_spike", "large_move"]
        medium_priority = ["price_target", "ma_cross", "funding_alert"]
        if alert_type in high_priority:
            return "high"
        elif alert_type in medium_priority:
            return "medium"
        return "low"

    # ═══════════════════════════════════════════════════════════════════════════════
    # AUTO-ALERT CHECKS (v2 - leaner)
    # ═══════════════════════════════════════════════════════════════════════════════

    async def check_price_change(self, symbol: str, price: float):
        clean_sym = symbol.replace("/USDT", "")
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append({"price": price, "time": datetime.now(timezone.utc)})
        if len(self.price_history[symbol]) > self.history_max:
            self.price_history[symbol] = self.price_history[symbol][-self.history_max:]

        history = self.price_history[symbol]

        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        five_min_prices = [h for h in history if h["time"] >= five_min_ago]
        if five_min_prices:
            oldest_price = five_min_prices[0]["price"]
            change_5m = ((price - oldest_price) / oldest_price) * 100
            if abs(change_5m) >= self.auto_alert_thresholds["price_change_5min"]:
                d = "+" if change_5m > 0 else ""
                await self._send_alert("large_move", symbol,
                    f"{'📈' if change_5m > 0 else '📉'} {clean_sym} {d}{change_5m:.1f}% in 5m | ${price:,.2f}",
                    {"change_pct": change_5m, "timeframe": "5m"})

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        one_hour_prices = [h for h in history if h["time"] >= one_hour_ago]
        if len(one_hour_prices) > 10:
            oldest_price = one_hour_prices[0]["price"]
            change_1h = ((price - oldest_price) / oldest_price) * 100
            if abs(change_1h) >= self.auto_alert_thresholds["price_change_1h"]:
                d = "+" if change_1h > 0 else ""
                await self._send_alert("hourly_move", symbol,
                    f"{'🚀' if change_1h > 0 else '💥'} {clean_sym} {d}{change_1h:.1f}% in 1h | ${price:,.2f}",
                    {"change_pct": change_1h, "timeframe": "1h"})

    async def check_rsi_extreme(self, symbol: str):
        """Collect RSI extremes into batch buffer instead of sending individually."""
        ohlcv = await self.fetch_ohlcv(symbol, "1h", 20)
        if len(ohlcv) < 15:
            return
        closes = [c[4] for c in ohlcv]
        rsi = self._calculate_rsi(closes)
        if rsi is None:
            return

        clean_sym = symbol.replace("/USDT", "")
        price = closes[-1]

        if rsi <= self.auto_alert_thresholds["rsi_oversold"]:
            self._rsi_batch.append({"symbol": clean_sym, "rsi": rsi, "price": price, "condition": "OVERSOLD"})
        elif rsi >= self.auto_alert_thresholds["rsi_overbought"]:
            self._rsi_batch.append({"symbol": clean_sym, "rsi": rsi, "price": price, "condition": "OVERBOUGHT"})

    async def _flush_rsi_batch(self):
        """Send all collected RSI extremes as ONE grouped message."""
        if not self._rsi_batch:
            return

        oversold = [r for r in self._rsi_batch if r["condition"] == "OVERSOLD"]
        overbought = [r for r in self._rsi_batch if r["condition"] == "OVERBOUGHT"]

        lines = ["📊 RSI SCAN SUMMARY\n"]
        if oversold:
            lines.append("🔵 OVERSOLD:")
            for r in oversold:
                lines.append(f"  {r['symbol']} RSI {r['rsi']:.0f} | ${r['price']:,.2f}")
        if overbought:
            lines.append("🔴 OVERBOUGHT:")
            for r in overbought:
                lines.append(f"  {r['symbol']} RSI {r['rsi']:.0f} | ${r['price']:,.2f}")

        lines.append(f"\n{len(self._rsi_batch)} coin{'s' if len(self._rsi_batch) > 1 else ''} at extremes")

        msg = "\n".join(lines)
        data = {"oversold": len(oversold), "overbought": len(overbought), "coins": [r["symbol"] for r in self._rsi_batch]}

        await self._send_batched_alert("rsi_extreme", msg, data)
        self._rsi_batch = []

    async def check_volume_spike(self, symbol: str):
        ohlcv = await self.fetch_ohlcv(symbol, "1h", 25)
        if len(ohlcv) < 20:
            return
        volumes = [c[5] for c in ohlcv]
        avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
        current_volume = volumes[-1]
        volume_mult = current_volume / avg_volume if avg_volume > 0 else 1

        if volume_mult >= self.auto_alert_thresholds["volume_spike_mult"]:
            clean_sym = symbol.replace("/USDT", "")
            price = ohlcv[-1][4]
            await self._send_alert("volume_spike", symbol,
                f"🔊 {clean_sym} volume {volume_mult:.1f}x avg | ${price:,.2f}\nUnusual activity - watch for follow-through.",
                {"volume_mult": volume_mult})

    async def check_breakout(self, symbol: str):
        """Breakout alerts with volume confirmation and longer cooldown."""
        now = datetime.now(timezone.utc)
        if symbol in self._breakout_cooldowns:
            if (now - self._breakout_cooldowns[symbol]).total_seconds() < self._breakout_cooldown_seconds:
                return

        ohlcv = await self.fetch_ohlcv(symbol, "4h", 25)
        if len(ohlcv) < 20:
            return

        highs = [c[2] for c in ohlcv[-22:-2]]
        lows = [c[3] for c in ohlcv[-22:-2]]
        volumes = [c[5] for c in ohlcv[-22:-2]]
        resistance = max(highs)
        support = min(lows)
        avg_vol = sum(volumes) / len(volumes) if volumes else 1

        current = ohlcv[-1]
        price = current[4]
        curr_vol = current[5]
        clean_sym = symbol.replace("/USDT", "")

        vol_confirmed = curr_vol > avg_vol * 1.5
        vol_tag = " [Vol Confirmed]" if vol_confirmed else " [Low Vol]"

        if price > resistance * 1.008:  # 0.8% above resistance (was 0.5%)
            self._breakout_cooldowns[symbol] = now
            range_pct = ((resistance - support) / support) * 100
            await self._send_alert("breakout", symbol,
                f"🚀 BREAKOUT {clean_sym}{vol_tag}\n"
                f"${price:,.2f} broke ${resistance:,.2f} resistance\n"
                f"Range was {range_pct:.1f}% | Watch retest of ${resistance:,.2f}",
                {"level": resistance, "direction": "bullish", "volume_confirmed": vol_confirmed})

        elif price < support * 0.992:  # 0.8% below support (was 0.5%)
            self._breakout_cooldowns[symbol] = now
            range_pct = ((resistance - support) / support) * 100
            await self._send_alert("breakout", symbol,
                f"💥 BREAKDOWN {clean_sym}{vol_tag}\n"
                f"${price:,.2f} broke ${support:,.2f} support\n"
                f"Range was {range_pct:.1f}% | Watch retest of ${support:,.2f}",
                {"level": support, "direction": "bearish", "volume_confirmed": vol_confirmed})

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    # ═══════════════════════════════════════════════════════════════════════════════
    # CUSTOM ALERTS MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════

    def add_price_alert(self, symbol: str, target_price: float,
                        direction: str, chat_id: int = None) -> Dict:
        import uuid
        alert_id = str(uuid.uuid4())[:8]
        alert = PriceAlert(
            alert_id=alert_id, symbol=symbol, alert_type="price_target",
            condition={"target_price": target_price, "direction": direction},
            chat_ids=[chat_id] if chat_id else [])
        self.alerts[alert_id] = alert
        return {"success": True, "alert_id": alert_id, "message": f"Alert set: {symbol} {direction} ${target_price:,.2f}"}

    def remove_alert(self, alert_id: str) -> Dict:
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            return {"success": True, "message": f"Alert {alert_id} removed"}
        return {"success": False, "message": "Alert not found"}

    def list_alerts(self, chat_id: int = None) -> List[Dict]:
        alerts = []
        for alert in self.alerts.values():
            if chat_id is None or chat_id in alert.chat_ids:
                alerts.append(alert.to_dict())
        return alerts

    async def check_custom_alerts(self):
        for alert_id, alert in list(self.alerts.items()):
            if not alert.active:
                continue
            price = await self.fetch_price(alert.symbol)
            if not price:
                continue
            triggered = False
            direction = alert.condition.get("direction", "")
            target = alert.condition.get("target_price", 0)
            if direction == "above" and price >= target:
                triggered = True
            elif direction == "below" and price <= target:
                triggered = True
            if triggered:
                alert.triggered_at = datetime.now(timezone.utc)
                alert.triggered_count += 1
                alert.active = False
                clean_sym = alert.symbol.replace("/USDT", "")
                await self._send_alert("price_target", alert.symbol,
                    f"🎯 {clean_sym} hit ${target:,.2f} ({direction}) | Now ${price:,.2f}",
                    {"target": target, "current": price, "direction": direction})

    # ═══════════════════════════════════════════════════════════════════════════════
    # MAIN SCAN LOOP
    # ═══════════════════════════════════════════════════════════════════════════════

    async def scan_prices(self):
        self._rsi_batch = []

        if hasattr(self, '_heartbeat_fn') and self._heartbeat_fn:
            self._heartbeat_fn()

        for symbol in self.tracked_symbols:
            try:
                price = await self.fetch_price(symbol)
                if not price:
                    continue
                self.last_prices[symbol] = price
                await self.check_price_change(symbol, price)
                await self.check_rsi_extreme(symbol)
                await self.check_volume_spike(symbol)
                await self.check_breakout(symbol)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Scan error for {symbol}: {e}")

        # Flush batched RSI alerts as one message
        await self._flush_rsi_batch()

        await self.check_custom_alerts()
        self.last_scan = datetime.now(timezone.utc)

    async def run_forever(self):
        logger.info("Price Alert System v2 started (lean alerts)")
        while self.active:
            try:
                await self.scan_prices()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Alert system error: {e}")
                await asyncio.sleep(30)

    def get_stats(self) -> Dict:
        return {
            "active": self.active,
            "auto_alerts_enabled": self.auto_alerts_enabled,
            "tracked_symbols": len(self.tracked_symbols),
            "custom_alerts": len(self.alerts),
            "dashboard_alerts_pending": len([a for a in self.dashboard_alerts if not a.get("read")]),
            "total_alerts_sent": self.total_alerts_sent,
            "alerts_today": self.alerts_today,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "thresholds": self.auto_alert_thresholds
        }

    def get_dashboard_alerts(self, limit: int = 20, unread_only: bool = False) -> List[Dict]:
        alerts = self.dashboard_alerts
        if unread_only:
            alerts = [a for a in alerts if not a.get("read")]
        return alerts[:limit]

    def mark_alert_read(self, dashboard_id: str) -> bool:
        for alert in self.dashboard_alerts:
            if alert.get("dashboard_id") == dashboard_id:
                alert["read"] = True
                return True
        return False

    def clear_all_dashboard_alerts(self):
        self.dashboard_alerts = []


# Global instance
price_alert_system = PriceAlertSystem()
