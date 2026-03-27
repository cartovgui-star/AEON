"""
Background tasks for Aeon - funding alerts, trading loop, Free Will scanner
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Callable

logger = logging.getLogger(__name__)


class BackgroundTasks:
    """Manages all background tasks for Aeon"""
    
    def __init__(
        self,
        db,
        market_intel,
        autonomous_trader,
        learning_system,
        free_will,
        send_message: Callable,
        get_user_settings: Callable,
        chat_ids: Set[int]
    ):
        self.db = db
        self.market_intel = market_intel
        self.autonomous_trader = autonomous_trader
        self.learning_system = learning_system
        self.free_will = free_will
        self.send_message = send_message
        self.get_user_settings = get_user_settings
        self.chat_ids = chat_ids
        
        # Track last alerts to avoid spam
        self.last_funding_alert: Dict[str, datetime] = {}
    
    async def check_funding_rate_alerts(self):
        """Check for extreme funding rates and alert users."""
        now = datetime.now()
        
        for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
            try:
                # Skip if alerted recently (1 hour cooldown)
                if symbol in self.last_funding_alert and (now - self.last_funding_alert[symbol]).total_seconds() < 3600:
                    continue
                
                funding = await self.market_intel.get_current_funding_rate(symbol)
                rate = funding.get("funding_rate", 0)
                
                # Alert on extreme funding rates
                if abs(rate) > 0.0008:  # >0.08% is significant
                    self.last_funding_alert[symbol] = now
                    
                    if rate > 0:
                        alert_type = "🔴 HIGH POSITIVE"
                        warning = "Longs paying shorts heavily - potential long squeeze incoming"
                    else:
                        alert_type = "🟢 HIGH NEGATIVE"
                        warning = "Shorts paying longs heavily - potential short squeeze incoming"
                    
                    alert = f"""⚡ FUNDING RATE ALERT

{alert_type} FUNDING: {symbol}
Rate: {funding.get('funding_rate_pct', 'N/A')}

{warning}

Price: ${funding.get('mark_price', 0):,.2f}

👁️ «The leverage winds shift. Prepare accordingly.»"""
                    
                    for chat_id in list(self.chat_ids):
                        settings = await self.get_user_settings(chat_id)
                        if settings.get("free_will", True):
                            await self.send_message(chat_id, alert)
                            
            except Exception as e:
                logger.error(f"Funding alert error for {symbol}: {e}")
    
    async def autonomous_trading_loop(self):
        """
        Aeon's autonomous trading brain - runs continuously.
        - Scans all trading pairs for high-probability setups
        - Takes paper trades when high-confidence setups appear
        - Evaluates open positions every 5 minutes
        - Learns from outcomes and adjusts strategy weights
        - Monitors funding rates for alerts
        """
        # Load existing strategy weights
        await self.autonomous_trader.load_strategy_weights()
        
        while True:
            try:
                if self.autonomous_trader.active:
                    # Scan for new opportunities
                    opportunities = await self.autonomous_trader.scan_all_markets()
                    
                    # Take high-confidence trades
                    for opp in opportunities:
                        if opp.get("confidence", 0) >= 75:
                            await self.autonomous_trader.take_trade(opp)
                            
                            # Notify users
                            for chat_id in list(self.chat_ids):
                                settings = await self.get_user_settings(chat_id)
                                if settings.get("free_will", True):
                                    msg = f"""🎯 NEW TRADE SIGNAL

{opp.get('symbol')} - {opp.get('signal')}
Confidence: {opp.get('confidence')}%

Entry: ${opp.get('entry', 0):,.2f}
Target: ${opp.get('target', 0):,.2f}
Stop: ${opp.get('stop', 0):,.2f}

Reasoning: {opp.get('reasoning', '')}

👁️ «The pattern emerges. Position taken.»"""
                                    await self.send_message(chat_id, msg)
                    
                    # Check and close positions
                    closed = await self.autonomous_trader.evaluate_positions(self.market_intel)
                    
                    for result in closed:
                        if result.get("pnl_pct") is not None:
                            pnl = result.get("pnl_pct", 0)
                            emoji = "✅" if pnl > 0 else "❌"
                            
                            # Get updated stats
                            stats = await self.learning_system.get_prediction_stats()
                            
                            for chat_id in list(self.chat_ids):
                                settings = await self.get_user_settings(chat_id)
                                if settings.get("free_will", True):
                                    msg = f"""{emoji} TRADE CLOSED

PnL: {pnl:+.2f}%
Entry: ${result.get('entry', 0):,.2f}
Exit: ${result.get('exit', 0):,.2f}

📊 RUNNING STATS:
Win Rate: {stats.get('win_rate', 0)}%
Total PnL: {stats.get('total_pnl_pct', 0):+.2f}%
Record: {stats.get('wins', 0)}W / {stats.get('losses', 0)}L

👁️ «Every trade teaches. The Great Work continues.»"""
                                    await self.send_message(chat_id, msg)
                    
                    # Check for funding rate alerts
                    await self.check_funding_rate_alerts()
                
                # Run every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Autonomous trading error: {e}")
                await asyncio.sleep(60)
    
    async def free_will_scanner(self, derivatives_intel, enhanced_intel):
        """
        TRUE 24/7 FREE WILL - Scans ALL 44 pairs across ALL timeframes
        Sends IMMEDIATE alerts for high-probability setups (>65%)
        """
        # Set dependencies
        self.free_will.set_dependencies(
            market_intel=self.market_intel,
            derivatives_intel=derivatives_intel,
            enhanced_intel=enhanced_intel,
            send_telegram=self.send_message,
            get_user_settings=self.get_user_settings,
            chat_ids=self.chat_ids
        )
        
        scan_count = 0
        MAX_ALERTS_PER_SCAN = 5  # Limit alerts per scan to avoid spam
        
        while True:
            try:
                if self.free_will.active:
                    scan_count += 1
                    
                    # Priority scan every 30 seconds (top 20 pairs, key timeframes)
                    setups = await self.free_will.scan_all()
                    
                    # Extended scan every 5 minutes (all 44 pairs, all timeframes)
                    if scan_count % 10 == 0:
                        extended = await self.free_will.scan_extended()
                        setups.extend(extended)
                    
                    # Sort by confidence and limit alerts
                    setups.sort(key=lambda x: x["confidence"], reverse=True)
                    alerts_sent = 0
                    
                    # Send alerts for valid setups
                    for setup in setups:
                        if alerts_sent >= MAX_ALERTS_PER_SCAN:
                            break
                            
                        if setup["confidence"] >= self.free_will.min_confidence:
                            alert_msg = self.free_will.format_alert(setup)
                            
                            # Send to all users with free_will enabled
                            for chat_id in list(self.chat_ids):
                                settings = await self.get_user_settings(chat_id)
                                if settings.get("free_will", True):
                                    await self.send_message(chat_id, alert_msg)
                                    
                                    # Log the alert
                                    await self.db.free_will_alerts.insert_one({
                                        "chat_id": chat_id,
                                        "setup": setup,
                                        "timestamp": datetime.now(timezone.utc)
                                    })
                                
                                # Small delay between users to avoid rate limiting
                                await asyncio.sleep(0.5)
                            
                            # Mark symbol as alerted (consolidated per symbol)
                            self.free_will._mark_alerted(setup["symbol"])
                            alerts_sent += 1
                            
                            logger.info(f"🚨 FREE WILL ALERT: {setup['symbol']} {setup['timeframe']} {setup['direction']}")
                
                # Scan every 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Free Will scanner error: {e}")
                await asyncio.sleep(30)
