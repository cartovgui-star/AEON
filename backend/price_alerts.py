"""
AEON REAL-TIME PRICE ALERT SYSTEM
Monitors prices and sends alerts to Dashboard and Telegram

Alert Types:
1. Price Target Alerts - When price hits specific level
2. Percentage Move Alerts - When price moves X% in Y time
3. Breakout Alerts - When price breaks key levels
4. RSI Extreme Alerts - When RSI hits extremes
5. Volume Spike Alerts - Unusual volume detection
6. Funding Rate Alerts - Extreme funding rate changes
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
    Real-time price monitoring and alert system
    
    Monitors:
    - Custom price targets
    - Percentage moves
    - Key level breakouts
    - Technical indicator extremes
    - Volume anomalies
    """
    
    def __init__(self):
        self.alerts: Dict[str, PriceAlert] = {}
        self.active = True
        self.last_prices: Dict[str, float] = {}
        self.price_history: Dict[str, List[Dict]] = {}  # symbol -> [{price, time}, ...]
        self.history_max = 100  # Keep last 100 price points
        
        # Auto-alerts (always on)
        self.auto_alerts_enabled = True
        self.auto_alert_thresholds = {
            "price_change_5min": 2.0,    # Alert on 2%+ move in 5 min
            "price_change_1h": 5.0,       # Alert on 5%+ move in 1 hour
            "rsi_oversold": 25,           # RSI below 25
            "rsi_overbought": 75,         # RSI above 75
            "volume_spike_mult": 3.0,     # Volume 3x average
        }
        
        # Cooldowns to prevent spam
        self.alert_cooldowns: Dict[str, datetime] = {}
        self.cooldown_seconds = 300  # 5 minutes between same alerts
        
        # External dependencies
        self.send_telegram: Optional[Callable] = None
        self.chat_ids: Set[int] = set()
        
        # Dashboard alerts (in-memory queue for WebSocket/polling)
        self.dashboard_alerts: List[Dict] = []
        self.max_dashboard_alerts = 50
        
        # Tracked symbols
        self.tracked_symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
            "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT"
        ]
        
        # Stats
        self.total_alerts_sent = 0
        self.alerts_today = 0
        self.last_scan = None
        
        # WebSocket manager reference
        self.ws_manager = None
    
    def set_dependencies(self, send_telegram: Callable, chat_ids: Set[int], ws_manager=None):
        """Set external dependencies"""
        self.send_telegram = send_telegram
        self.chat_ids = chat_ids
        self.ws_manager = ws_manager
    
    def _can_send_alert(self, alert_key: str) -> bool:
        """Check if alert is not in cooldown"""
        now = datetime.now(timezone.utc)
        
        # Periodic cleanup of old cooldowns (every 100 checks)
        if self.total_alerts_sent % 100 == 0:
            self._cleanup_old_cooldowns()
        
        if alert_key in self.alert_cooldowns:
            elapsed = (now - self.alert_cooldowns[alert_key]).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        return True
    
    def _cleanup_old_cooldowns(self):
        """Remove stale cooldown entries to prevent memory growth"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=2)
        self.alert_cooldowns = {
            k: v for k, v in self.alert_cooldowns.items()
            if v > cutoff
        }
    
    def _mark_alert_sent(self, alert_key: str):
        """Mark alert as sent"""
        self.alert_cooldowns[alert_key] = datetime.now(timezone.utc)
        self.total_alerts_sent += 1
        self.alerts_today += 1
    
    async def fetch_price(self, symbol: str) -> Optional[float]:
        """Fetch current price"""
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ticker(symbol)
            )
            return ticker.get("last", 0)
        except Exception as e:
            logger.error(f"Price fetch error {symbol}: {e}")
            return None
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 20) -> List:
        """Fetch OHLCV data"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
        except Exception as e:
            logger.error(f"OHLCV fetch error {symbol}: {e}")
            return []
    
    def _add_dashboard_alert(self, alert: Dict):
        """Add alert to dashboard queue"""
        alert["dashboard_id"] = f"dash_{datetime.now(timezone.utc).timestamp()}"
        alert["read"] = False
        self.dashboard_alerts.insert(0, alert)
        
        # Trim to max size
        if len(self.dashboard_alerts) > self.max_dashboard_alerts:
            self.dashboard_alerts = self.dashboard_alerts[:self.max_dashboard_alerts]
    
    async def _send_alert(self, alert_type: str, symbol: str, message: str, 
                          data: Dict = None, telegram: bool = True, dashboard: bool = True):
        """Send alert to both Telegram and Dashboard (and WebSocket)"""
        alert_key = f"{alert_type}_{symbol}"
        
        if not self._can_send_alert(alert_key):
            return
        
        self._mark_alert_sent(alert_key)
        
        alert_data = {
            "type": alert_type,
            "symbol": symbol,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": self._get_severity(alert_type)
        }
        
        # Send to dashboard
        if dashboard:
            self._add_dashboard_alert(alert_data)
        
        # Send via WebSocket (real-time push)
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast_alert(
                    alert_type, symbol, message, data, self._get_severity(alert_type)
                )
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")
        
        # Send to Telegram
        if telegram and self.send_telegram and self.chat_ids:
            for chat_id in list(self.chat_ids):
                try:
                    await self.send_telegram(chat_id, message)
                    await asyncio.sleep(0.3)  # Rate limiting
                except:
                    pass
        
        logger.info(f"Alert sent: {alert_type} for {symbol}")
    
    def _get_severity(self, alert_type: str) -> str:
        """Get alert severity level"""
        high_priority = ["breakout", "rsi_extreme", "volume_spike", "large_move"]
        medium_priority = ["price_target", "ma_cross", "funding_alert"]
        
        if alert_type in high_priority:
            return "high"
        elif alert_type in medium_priority:
            return "medium"
        return "low"
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # AUTO-ALERT CHECKS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def check_price_change(self, symbol: str, price: float):
        """Check for significant price changes"""
        clean_sym = symbol.replace("/USDT", "")
        
        # Update history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append({
            "price": price,
            "time": datetime.now(timezone.utc)
        })
        
        # Trim history
        if len(self.price_history[symbol]) > self.history_max:
            self.price_history[symbol] = self.price_history[symbol][-self.history_max:]
        
        history = self.price_history[symbol]
        
        # Check 5-minute move
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        five_min_prices = [h for h in history if h["time"] >= five_min_ago]
        
        if five_min_prices:
            oldest_price = five_min_prices[0]["price"]
            change_5m = ((price - oldest_price) / oldest_price) * 100
            
            if abs(change_5m) >= self.auto_alert_thresholds["price_change_5min"]:
                direction = "📈" if change_5m > 0 else "📉"
                await self._send_alert(
                    "large_move",
                    symbol,
                    f"""{direction} RAPID MOVE: {clean_sym}
                    
Price: ${price:,.2f}
Change (5m): {change_5m:+.2f}%

This is a significant short-term move.
Check volume for confirmation.""",
                    {"change_pct": change_5m, "timeframe": "5m"}
                )
        
        # Check 1-hour move
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        one_hour_prices = [h for h in history if h["time"] >= one_hour_ago]
        
        if len(one_hour_prices) > 10:
            oldest_price = one_hour_prices[0]["price"]
            change_1h = ((price - oldest_price) / oldest_price) * 100
            
            if abs(change_1h) >= self.auto_alert_thresholds["price_change_1h"]:
                direction = "🚀" if change_1h > 0 else "💥"
                await self._send_alert(
                    "hourly_move",
                    symbol,
                    f"""{direction} HOURLY ALERT: {clean_sym}
                    
Price: ${price:,.2f}
Change (1h): {change_1h:+.2f}%

Significant hourly movement detected.""",
                    {"change_pct": change_1h, "timeframe": "1h"}
                )
    
    async def check_rsi_extreme(self, symbol: str):
        """Check for RSI extremes"""
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
            await self._send_alert(
                "rsi_extreme",
                symbol,
                f"""🔵 RSI OVERSOLD: {clean_sym}

RSI: {rsi:.0f}
Price: ${price:,.2f}

RSI below {self.auto_alert_thresholds['rsi_oversold']} suggests oversold conditions.
Watch for reversal signals.""",
                {"rsi": rsi, "condition": "oversold"}
            )
        
        elif rsi >= self.auto_alert_thresholds["rsi_overbought"]:
            await self._send_alert(
                "rsi_extreme",
                symbol,
                f"""🔴 RSI OVERBOUGHT: {clean_sym}

RSI: {rsi:.0f}
Price: ${price:,.2f}

RSI above {self.auto_alert_thresholds['rsi_overbought']} suggests overbought conditions.
Watch for reversal signals.""",
                {"rsi": rsi, "condition": "overbought"}
            )
    
    async def check_volume_spike(self, symbol: str):
        """Check for unusual volume"""
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
            
            await self._send_alert(
                "volume_spike",
                symbol,
                f"""🔊 VOLUME SPIKE: {clean_sym}

Price: ${price:,.2f}
Volume: {volume_mult:.1f}x average

Unusual volume detected ({volume_mult:.1f}x normal).
This often precedes significant price moves.""",
                {"volume_mult": volume_mult}
            )
    
    async def check_breakout(self, symbol: str):
        """Check for breakout patterns"""
        ohlcv = await self.fetch_ohlcv(symbol, "4h", 25)
        if len(ohlcv) < 20:
            return
        
        # Get recent range (excluding last 2 candles)
        highs = [c[2] for c in ohlcv[-22:-2]]
        lows = [c[3] for c in ohlcv[-22:-2]]
        
        resistance = max(highs)
        support = min(lows)
        
        current = ohlcv[-1]
        price = current[4]
        clean_sym = symbol.replace("/USDT", "")
        
        # Bullish breakout
        if price > resistance * 1.005:  # 0.5% above resistance
            await self._send_alert(
                "breakout",
                symbol,
                f"""🚀 BREAKOUT: {clean_sym}

Price: ${price:,.2f}
Broke above: ${resistance:,.2f}

Price has broken above recent resistance.
This could signal the start of an upward move.

Watch for:
• Volume confirmation
• Retest of broken level as support""",
                {"level": resistance, "direction": "bullish"}
            )
        
        # Bearish breakdown
        elif price < support * 0.995:  # 0.5% below support
            await self._send_alert(
                "breakout",
                symbol,
                f"""💥 BREAKDOWN: {clean_sym}

Price: ${price:,.2f}
Broke below: ${support:,.2f}

Price has broken below recent support.
This could signal the start of a downward move.

Watch for:
• Volume confirmation
• Retest of broken level as resistance""",
                {"level": support, "direction": "bearish"}
            )
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate current RSI"""
        if len(closes) < period + 1:
            return None
        
        gains = []
        losses = []
        
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
        """Add custom price target alert"""
        import uuid
        alert_id = str(uuid.uuid4())[:8]
        
        alert = PriceAlert(
            alert_id=alert_id,
            symbol=symbol,
            alert_type="price_target",
            condition={
                "target_price": target_price,
                "direction": direction  # "above" or "below"
            },
            chat_ids=[chat_id] if chat_id else []
        )
        
        self.alerts[alert_id] = alert
        
        return {
            "success": True,
            "alert_id": alert_id,
            "message": f"Alert set: {symbol} {direction} ${target_price:,.2f}"
        }
    
    def remove_alert(self, alert_id: str) -> Dict:
        """Remove custom alert"""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            return {"success": True, "message": f"Alert {alert_id} removed"}
        return {"success": False, "message": "Alert not found"}
    
    def list_alerts(self, chat_id: int = None) -> List[Dict]:
        """List all alerts"""
        alerts = []
        for alert in self.alerts.values():
            if chat_id is None or chat_id in alert.chat_ids:
                alerts.append(alert.to_dict())
        return alerts
    
    async def check_custom_alerts(self):
        """Check all custom price alerts"""
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
                alert.active = False  # Deactivate after trigger
                
                clean_sym = alert.symbol.replace("/USDT", "")
                
                await self._send_alert(
                    "price_target",
                    alert.symbol,
                    f"""🎯 PRICE ALERT TRIGGERED: {clean_sym}

Target: ${target:,.2f}
Current: ${price:,.2f}
Direction: {direction.upper()}

Your custom price alert has been triggered!""",
                    {"target": target, "current": price, "direction": direction}
                )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # MAIN SCAN LOOP
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def scan_prices(self):
        """Main scan loop for all tracked symbols"""
        for symbol in self.tracked_symbols:
            try:
                price = await self.fetch_price(symbol)
                if not price:
                    continue
                
                self.last_prices[symbol] = price
                
                # Run all checks
                await self.check_price_change(symbol, price)
                await self.check_rsi_extreme(symbol)
                await self.check_volume_spike(symbol)
                await self.check_breakout(symbol)
                
                await asyncio.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Scan error for {symbol}: {e}")
        
        # Check custom alerts
        await self.check_custom_alerts()
        
        self.last_scan = datetime.now(timezone.utc)
    
    async def run_forever(self):
        """Run the alert system continuously"""
        logger.info("🔔 Price Alert System started")
        
        while self.active:
            try:
                await self.scan_prices()
                await asyncio.sleep(60)  # Scan every 60 seconds
                
            except Exception as e:
                logger.error(f"Alert system error: {e}")
                await asyncio.sleep(30)
    
    def get_stats(self) -> Dict:
        """Get alert system statistics"""
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
        """Get dashboard alerts"""
        alerts = self.dashboard_alerts
        if unread_only:
            alerts = [a for a in alerts if not a.get("read")]
        return alerts[:limit]
    
    def mark_alert_read(self, dashboard_id: str) -> bool:
        """Mark dashboard alert as read"""
        for alert in self.dashboard_alerts:
            if alert.get("dashboard_id") == dashboard_id:
                alert["read"] = True
                return True
        return False
    
    def clear_all_dashboard_alerts(self):
        """Clear all dashboard alerts"""
        self.dashboard_alerts = []


# Global instance
price_alert_system = PriceAlertSystem()
