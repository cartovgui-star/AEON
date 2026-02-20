"""
Trade Outcome Tracking System
Tracks alert accuracy and learns from outcomes
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class TradeOutcomeTracker:
    """Track alert outcomes to measure Aeon's accuracy"""
    
    def __init__(self):
        # Track all alerts sent
        self.alerts_history: List[Dict] = []
        
        # Stats by source
        self.stats = {
            "total_alerts": 0,
            "total_resolved": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "pending": 0,
            "expired": 0,  # No outcome within timeframe
        }
        
        # Stats by direction
        self.direction_stats = {
            "LONG": {"total": 0, "wins": 0, "losses": 0},
            "SHORT": {"total": 0, "wins": 0, "losses": 0},
        }
        
        # Stats by symbol
        self.symbol_stats: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})
        
        # Stats by confidence range
        self.confidence_stats = {
            "80-85": {"total": 0, "wins": 0},
            "85-90": {"total": 0, "wins": 0},
            "90-95": {"total": 0, "wins": 0},
        }
    
    def record_alert(self, alert_data: Dict) -> str:
        """Record a new alert sent to user"""
        alert_id = f"alert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{len(self.alerts_history)}"
        
        record = {
            "id": alert_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": alert_data.get("symbol", ""),
            "direction": alert_data.get("direction", ""),
            "confidence": alert_data.get("confidence", 0),
            "entry": alert_data.get("entry", 0),
            "stop": alert_data.get("stop", 0),
            "target": alert_data.get("target", 0),
            "source": alert_data.get("source", "unknown"),  # freewill, dual, autonomous
            "outcome": "PENDING",
            "outcome_price": None,
            "outcome_time": None,
            "pnl_pct": None,
        }
        
        self.alerts_history.append(record)
        self.stats["total_alerts"] += 1
        self.stats["pending"] += 1
        
        # Track by direction
        direction = record["direction"]
        if direction in self.direction_stats:
            self.direction_stats[direction]["total"] += 1
        
        # Track by symbol
        symbol = record["symbol"].replace("/USDT", "")
        self.symbol_stats[symbol]["total"] += 1
        
        logger.info(f"Alert recorded: {alert_id} - {direction} {symbol}")
        return alert_id
    
    def update_outcome(self, alert_id: str, outcome: str, exit_price: float) -> Dict:
        """Update alert with outcome (WIN/LOSS/BREAKEVEN/EXPIRED)"""
        for alert in self.alerts_history:
            if alert["id"] == alert_id:
                entry = alert["entry"]
                direction = alert["direction"]
                
                # Calculate PnL %
                if direction == "LONG":
                    pnl_pct = ((exit_price - entry) / entry) * 100
                else:  # SHORT
                    pnl_pct = ((entry - exit_price) / entry) * 100
                
                alert["outcome"] = outcome
                alert["outcome_price"] = exit_price
                alert["outcome_time"] = datetime.now(timezone.utc).isoformat()
                alert["pnl_pct"] = round(pnl_pct, 2)
                
                # Update stats
                self.stats["pending"] -= 1
                self.stats["total_resolved"] += 1
                
                if outcome == "WIN":
                    self.stats["wins"] += 1
                    self.direction_stats[direction]["wins"] += 1
                    symbol = alert["symbol"].replace("/USDT", "")
                    self.symbol_stats[symbol]["wins"] += 1
                elif outcome == "LOSS":
                    self.stats["losses"] += 1
                    self.direction_stats[direction]["losses"] += 1
                    symbol = alert["symbol"].replace("/USDT", "")
                    self.symbol_stats[symbol]["losses"] += 1
                elif outcome == "BREAKEVEN":
                    self.stats["breakeven"] += 1
                elif outcome == "EXPIRED":
                    self.stats["expired"] += 1
                
                # Track confidence accuracy
                conf = alert["confidence"]
                if 80 <= conf < 85:
                    self.confidence_stats["80-85"]["total"] += 1
                    if outcome == "WIN":
                        self.confidence_stats["80-85"]["wins"] += 1
                elif 85 <= conf < 90:
                    self.confidence_stats["85-90"]["total"] += 1
                    if outcome == "WIN":
                        self.confidence_stats["85-90"]["wins"] += 1
                elif conf >= 90:
                    self.confidence_stats["90-95"]["total"] += 1
                    if outcome == "WIN":
                        self.confidence_stats["90-95"]["wins"] += 1
                
                logger.info(f"Alert {alert_id} resolved: {outcome} ({pnl_pct:+.2f}%)")
                return alert
        
        return {"error": f"Alert {alert_id} not found"}
    
    def get_accuracy_report(self) -> Dict:
        """Get full accuracy report"""
        total = self.stats["total_alerts"]
        resolved = self.stats["total_resolved"]
        wins = self.stats["wins"]
        losses = self.stats["losses"]
        
        win_rate = (wins / resolved * 100) if resolved > 0 else 0
        
        # Confidence accuracy
        conf_accuracy = {}
        for range_name, data in self.confidence_stats.items():
            if data["total"] > 0:
                conf_accuracy[range_name] = f"{data['wins']}/{data['total']} ({data['wins']/data['total']*100:.1f}%)"
            else:
                conf_accuracy[range_name] = "0/0"
        
        # Symbol accuracy (top 5)
        symbol_accuracy = {}
        for symbol, data in sorted(self.symbol_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:5]:
            if data["total"] > 0:
                symbol_accuracy[symbol] = {
                    "total": data["total"],
                    "win_rate": f"{data['wins']/data['total']*100:.1f}%" if data["total"] > 0 else "N/A"
                }
        
        return {
            "overview": {
                "total_alerts": total,
                "resolved": resolved,
                "pending": self.stats["pending"],
                "wins": wins,
                "losses": losses,
                "breakeven": self.stats["breakeven"],
                "win_rate": f"{win_rate:.1f}%",
            },
            "by_direction": {
                "LONG": {
                    "total": self.direction_stats["LONG"]["total"],
                    "wins": self.direction_stats["LONG"]["wins"],
                    "win_rate": f"{self.direction_stats['LONG']['wins']/self.direction_stats['LONG']['total']*100:.1f}%" if self.direction_stats["LONG"]["total"] > 0 else "N/A"
                },
                "SHORT": {
                    "total": self.direction_stats["SHORT"]["total"],
                    "wins": self.direction_stats["SHORT"]["wins"],
                    "win_rate": f"{self.direction_stats['SHORT']['wins']/self.direction_stats['SHORT']['total']*100:.1f}%" if self.direction_stats["SHORT"]["total"] > 0 else "N/A"
                }
            },
            "by_confidence": conf_accuracy,
            "by_symbol": symbol_accuracy,
            "recent_alerts": self.get_recent_alerts(5),
        }
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get most recent alerts with outcomes"""
        return [
            {
                "id": a["id"],
                "symbol": a["symbol"].replace("/USDT", ""),
                "direction": a["direction"],
                "confidence": a["confidence"],
                "outcome": a["outcome"],
                "pnl_pct": a["pnl_pct"],
            }
            for a in sorted(self.alerts_history, key=lambda x: x["timestamp"], reverse=True)[:limit]
        ]
    
    def get_pending_alerts(self) -> List[Dict]:
        """Get all pending alerts that need outcome tracking"""
        return [a for a in self.alerts_history if a["outcome"] == "PENDING"]
    
    def format_accuracy_message(self) -> str:
        """Format accuracy report for Telegram"""
        report = self.get_accuracy_report()
        ov = report["overview"]
        
        if ov["total_alerts"] == 0:
            return """📊 AEON ACCURACY TRACKER

No alerts sent yet. Accuracy tracking begins when alerts are sent.

This will show:
• Overall win rate
• Accuracy by confidence level
• Best/worst performing coins
• LONG vs SHORT performance"""
        
        msg = f"""📊 AEON ACCURACY REPORT

📈 OVERALL ({ov['resolved']} resolved / {ov['pending']} pending)
Win Rate: {ov['win_rate']}
Wins: {ov['wins']} | Losses: {ov['losses']} | BE: {ov['breakeven']}

📍 BY DIRECTION
LONG: {report['by_direction']['LONG']['win_rate']} ({report['by_direction']['LONG']['wins']}/{report['by_direction']['LONG']['total']})
SHORT: {report['by_direction']['SHORT']['win_rate']} ({report['by_direction']['SHORT']['wins']}/{report['by_direction']['SHORT']['total']})

📊 BY CONFIDENCE
80-85%: {report['by_confidence'].get('80-85', 'N/A')}
85-90%: {report['by_confidence'].get('85-90', 'N/A')}
90-95%: {report['by_confidence'].get('90-95', 'N/A')}

🪙 TOP SYMBOLS"""
        
        for symbol, data in report.get("by_symbol", {}).items():
            msg += f"\n{symbol}: {data['win_rate']} ({data['total']} alerts)"
        
        if report.get("recent_alerts"):
            msg += "\n\n📋 RECENT"
            for a in report["recent_alerts"][:3]:
                emoji = "✅" if a["outcome"] == "WIN" else "❌" if a["outcome"] == "LOSS" else "⏳"
                pnl = f"{a['pnl_pct']:+.1f}%" if a["pnl_pct"] else ""
                msg += f"\n{emoji} {a['direction']} {a['symbol']} {a['confidence']}% {pnl}"
        
        return msg


# Global instance
trade_outcome_tracker = TradeOutcomeTracker()
