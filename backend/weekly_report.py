"""
AEON WEEKLY PERFORMANCE REPORT
Sends comprehensive trading performance summary every Sunday at 8 PM Central Time

Features:
- Win rate by strategy (V2.1, Scalper, Day Trader, Long Term)
- Best and worst performing coins
- Total PnL breakdown
- Weekly highlights and lowlights
- Strategy recommendations based on performance
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Set
import pytz

logger = logging.getLogger(__name__)

# Austin, Texas timezone
AUSTIN_TZ = pytz.timezone('America/Chicago')
REPORT_DAY = 6  # Sunday (0=Monday, 6=Sunday)
REPORT_HOUR = 20  # 8 PM


class WeeklyPerformanceReport:
    """
    Weekly performance report system for Aeon
    Runs every Sunday at 8 PM Central Time
    """
    
    def __init__(self):
        self.last_report_date = None
        self.db = None
        self.send_message: Optional[Callable] = None
        self.get_user_settings: Optional[Callable] = None
        self.chat_ids: Set[int] = set()
        self.is_active = True
        
    def set_dependencies(
        self,
        db,
        send_message: Callable,
        get_user_settings: Callable,
        chat_ids: Set[int]
    ):
        """Set external dependencies"""
        self.db = db
        self.send_message = send_message
        self.get_user_settings = get_user_settings
        self.chat_ids = chat_ids
        
    def _get_austin_time(self) -> datetime:
        """Get current time in Austin, Texas"""
        return datetime.now(AUSTIN_TZ)
    
    def _should_send_report(self) -> bool:
        """Check if it's time to send the weekly report (Sunday 8 PM CT)"""
        austin_now = self._get_austin_time()
        
        # Check if it's Sunday at 8 PM (within 5 minute window)
        if austin_now.weekday() == REPORT_DAY and austin_now.hour == REPORT_HOUR and austin_now.minute < 5:
            # Check if we already sent this week
            if self.last_report_date:
                days_since = (austin_now.date() - self.last_report_date).days
                if days_since < 7:
                    return False
            return True
        
        return False
    
    def _get_week_range(self) -> tuple:
        """Get the start and end dates for the current week (Mon-Sun)"""
        austin_now = self._get_austin_time()
        # Find last Monday
        days_since_monday = austin_now.weekday()
        week_start = austin_now - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = austin_now
        return week_start, week_end
    
    async def get_closed_trades(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all closed trades within the date range"""
        trades = []
        
        if self.db is None:
            return trades
        
        try:
            # Get from v2_closed_trades collection
            cursor = self.db.v2_closed_trades.find({
                "closed_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            })
            async for trade in cursor:
                trade_data = {k: v for k, v in trade.items() if k != '_id'}
                trades.append(trade_data)
            
            # Also get from paper_trades collection
            cursor2 = self.db.paper_trades.find({
                "closed_at": {
                    "$gte": start_date,
                    "$lte": end_date
                },
                "status": "closed"
            })
            async for trade in cursor2:
                trade_data = {k: v for k, v in trade.items() if k != '_id'}
                trades.append(trade_data)
                
        except Exception as e:
            logger.error(f"Error fetching closed trades: {e}")
        
        return trades
    
    async def calculate_strategy_stats(self, trades: List[Dict]) -> Dict:
        """Calculate win rate and PnL by strategy"""
        strategies = {
            "V2.1 Autonomous": {"trades": [], "source": "v2"},
            "Aggressive Scalper": {"trades": [], "source": "scalper"},
            "Day Trader": {"trades": [], "source": "day_trader"},
            "Long Term": {"trades": [], "source": "long_term"}
        }
        
        for trade in trades:
            source = trade.get("source", trade.get("style", "v2")).lower()
            
            if "scalp" in source:
                strategies["Aggressive Scalper"]["trades"].append(trade)
            elif "day" in source:
                strategies["Day Trader"]["trades"].append(trade)
            elif "long" in source:
                strategies["Long Term"]["trades"].append(trade)
            else:
                strategies["V2.1 Autonomous"]["trades"].append(trade)
        
        stats = {}
        for name, data in strategies.items():
            strategy_trades = data["trades"]
            if not strategy_trades:
                continue
            
            wins = len([t for t in strategy_trades if (t.get("pnl_pct") or t.get("pnl", 0)) > 0])
            losses = len([t for t in strategy_trades if (t.get("pnl_pct") or t.get("pnl", 0)) <= 0])
            total = wins + losses
            
            total_pnl = sum(t.get("pnl_pct") or t.get("pnl", 0) for t in strategy_trades)
            avg_pnl = total_pnl / total if total > 0 else 0
            
            stats[name] = {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / total) * 100, 1) if total > 0 else 0,
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(avg_pnl, 2)
            }
        
        return stats
    
    async def get_coin_performance(self, trades: List[Dict]) -> Dict:
        """Get best and worst performing coins"""
        coin_stats = {}
        
        for trade in trades:
            symbol = trade.get("symbol", "").replace("/USDT", "").replace("USDT", "")
            if not symbol:
                continue
            
            if symbol not in coin_stats:
                coin_stats[symbol] = {"trades": 0, "wins": 0, "total_pnl": 0}
            
            coin_stats[symbol]["trades"] += 1
            pnl = trade.get("pnl_pct") or trade.get("pnl", 0)
            coin_stats[symbol]["total_pnl"] += pnl
            if pnl > 0:
                coin_stats[symbol]["wins"] += 1
        
        # Calculate win rates
        for symbol, data in coin_stats.items():
            data["win_rate"] = round((data["wins"] / data["trades"]) * 100, 1) if data["trades"] > 0 else 0
            data["avg_pnl"] = round(data["total_pnl"] / data["trades"], 2) if data["trades"] > 0 else 0
        
        # Sort by total PnL
        sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]["total_pnl"], reverse=True)
        
        best = sorted_coins[:3] if len(sorted_coins) >= 3 else sorted_coins
        worst = sorted_coins[-3:][::-1] if len(sorted_coins) >= 3 else []
        
        return {
            "best_performers": [{"symbol": s, **d} for s, d in best],
            "worst_performers": [{"symbol": s, **d} for s, d in worst],
            "all_coins": coin_stats
        }
    
    async def get_weekly_highlights(self, trades: List[Dict]) -> Dict:
        """Get notable events from the week"""
        highlights = {
            "biggest_win": None,
            "biggest_loss": None,
            "longest_hold": None,
            "quickest_trade": None,
            "most_traded_coin": None,
            "total_trading_days": 0
        }
        
        if not trades:
            return highlights
        
        # Find biggest win and loss
        sorted_by_pnl = sorted(trades, key=lambda x: x.get("pnl_pct") or x.get("pnl", 0), reverse=True)
        if sorted_by_pnl:
            highlights["biggest_win"] = {
                "symbol": sorted_by_pnl[0].get("symbol", "").replace("/USDT", ""),
                "pnl": round(sorted_by_pnl[0].get("pnl_pct") or sorted_by_pnl[0].get("pnl", 0), 2),
                "direction": sorted_by_pnl[0].get("direction", "")
            }
            highlights["biggest_loss"] = {
                "symbol": sorted_by_pnl[-1].get("symbol", "").replace("/USDT", ""),
                "pnl": round(sorted_by_pnl[-1].get("pnl_pct") or sorted_by_pnl[-1].get("pnl", 0), 2),
                "direction": sorted_by_pnl[-1].get("direction", "")
            }
        
        # Most traded coin
        coin_counts = {}
        trading_days = set()
        for trade in trades:
            symbol = trade.get("symbol", "").replace("/USDT", "")
            if symbol:
                coin_counts[symbol] = coin_counts.get(symbol, 0) + 1
            
            # Track trading days
            closed_at = trade.get("closed_at")
            if closed_at:
                if isinstance(closed_at, str):
                    try:
                        closed_at = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    except Exception as e:
                        logger.debug(f"Date parse error: {e}")
                if isinstance(closed_at, datetime):
                    trading_days.add(closed_at.date())
        
        if coin_counts:
            most_traded = max(coin_counts.items(), key=lambda x: x[1])
            highlights["most_traded_coin"] = {"symbol": most_traded[0], "count": most_traded[1]}
        
        highlights["total_trading_days"] = len(trading_days)
        
        return highlights
    
    async def generate_recommendations(self, strategy_stats: Dict, coin_performance: Dict) -> List[str]:
        """Generate strategy recommendations based on performance"""
        recommendations = []
        
        # Check overall win rate
        total_trades = sum(s["total_trades"] for s in strategy_stats.values())
        total_wins = sum(s["wins"] for s in strategy_stats.values())
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        if overall_win_rate < 40:
            recommendations.append("Consider raising confidence thresholds to improve win rate")
        elif overall_win_rate > 60:
            recommendations.append("Strong win rate! Consider slightly more aggressive entries")
        
        # Check by strategy
        for name, stats in strategy_stats.items():
            if stats["total_trades"] >= 5:
                if stats["win_rate"] < 35:
                    recommendations.append(f"Review {name} strategy - win rate below optimal")
                if stats["win_rate"] > 70:
                    recommendations.append(f"{name} performing excellently - maintain current settings")
        
        # Check worst performing coins
        worst = coin_performance.get("worst_performers", [])
        if worst:
            bad_coins = [c["symbol"] for c in worst if c.get("total_pnl", 0) < -5]
            if bad_coins:
                recommendations.append(f"Consider avoiding or reducing size on: {', '.join(bad_coins[:3])}")
        
        # Check best performing coins
        best = coin_performance.get("best_performers", [])
        if best:
            good_coins = [c["symbol"] for c in best if c.get("total_pnl", 0) > 5]
            if good_coins:
                recommendations.append(f"Top performers this week: {', '.join(good_coins[:3])}")
        
        if not recommendations:
            recommendations.append("Trading performance is stable - maintain current approach")
        
        return recommendations[:5]  # Max 5 recommendations
    
    async def generate_report(self) -> str:
        """Generate the full weekly performance report"""
        austin_now = self._get_austin_time()
        week_start, week_end = self._get_week_range()
        
        # Get trades for the week
        trades = await self.get_closed_trades(week_start, week_end)
        
        # Calculate stats
        strategy_stats = await self.calculate_strategy_stats(trades)
        coin_performance = await self.get_coin_performance(trades)
        highlights = await self.get_weekly_highlights(trades)
        recommendations = await self.generate_recommendations(strategy_stats, coin_performance)
        
        # Calculate totals
        total_trades = len(trades)
        total_pnl = sum(t.get("pnl_pct") or t.get("pnl", 0) for t in trades)
        total_wins = len([t for t in trades if (t.get("pnl_pct") or t.get("pnl", 0)) > 0])
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        # Format dates
        week_start_str = week_start.strftime("%b %d")
        week_end_str = week_end.strftime("%b %d, %Y")
        
        # Build the report
        msg_parts = []
        
        # Header
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        msg_parts.append(f"""📊 AEON WEEKLY PERFORMANCE REPORT
{week_start_str} - {week_end_str}
━━━━━━━━━━━━━━━━━━━━━━""")
        
        # Overall Summary
        pnl_color = "+" if total_pnl >= 0 else ""
        wr_status = "🟢" if overall_win_rate >= 50 else "🟡" if overall_win_rate >= 40 else "🔴"
        
        msg_parts.append(f"""
{pnl_emoji} OVERALL SUMMARY
Total Trades: {total_trades}
Win Rate: {wr_status} {overall_win_rate:.1f}%
Total PnL: {pnl_color}{total_pnl:.2f}%
Trading Days: {highlights.get('total_trading_days', 0)}/7""")
        
        # Strategy Breakdown
        if strategy_stats:
            msg_parts.append("\n🎯 STRATEGY PERFORMANCE")
            for name, stats in strategy_stats.items():
                if stats["total_trades"] > 0:
                    wr_indicator = "✅" if stats["win_rate"] >= 50 else "⚠️"
                    pnl_sign = "+" if stats["total_pnl"] >= 0 else ""
                    msg_parts.append(f"""
{name}:
  {wr_indicator} {stats['win_rate']}% WR ({stats['wins']}W/{stats['losses']}L)
  PnL: {pnl_sign}{stats['total_pnl']}% ({pnl_sign}{stats['avg_pnl']}% avg)""")
        
        # Best/Worst Coins
        best = coin_performance.get("best_performers", [])
        worst = coin_performance.get("worst_performers", [])
        
        if best:
            msg_parts.append("\n🏆 TOP PERFORMERS")
            for coin in best[:3]:
                if coin.get("total_pnl", 0) > 0:
                    msg_parts.append(f"  🟢 {coin['symbol']}: +{coin['total_pnl']:.2f}% ({coin['win_rate']}% WR)")
        
        if worst:
            msg_parts.append("\n📉 UNDERPERFORMERS")
            for coin in worst[:3]:
                if coin.get("total_pnl", 0) < 0:
                    msg_parts.append(f"  🔴 {coin['symbol']}: {coin['total_pnl']:.2f}% ({coin['win_rate']}% WR)")
        
        # Weekly Highlights
        msg_parts.append("\n⚡ HIGHLIGHTS")
        if highlights.get("biggest_win"):
            bw = highlights["biggest_win"]
            msg_parts.append(f"  Best Trade: {bw['symbol']} {bw['direction']} +{bw['pnl']}%")
        if highlights.get("biggest_loss") and highlights["biggest_loss"]["pnl"] < 0:
            bl = highlights["biggest_loss"]
            msg_parts.append(f"  Worst Trade: {bl['symbol']} {bl['direction']} {bl['pnl']}%")
        if highlights.get("most_traded_coin"):
            mtc = highlights["most_traded_coin"]
            msg_parts.append(f"  Most Active: {mtc['symbol']} ({mtc['count']} trades)")
        
        # Recommendations
        if recommendations:
            msg_parts.append("\n💡 RECOMMENDATIONS")
            for rec in recommendations:
                msg_parts.append(f"  • {rec}")
        
        # Footer
        msg_parts.append(f"""
━━━━━━━━━━━━━━━━━━━━━━
👁️ «The week reveals its lessons. Adapt, improve, prosper.»""")
        
        return "\n".join(msg_parts)
    
    async def send_report(self):
        """Send the weekly report to all users"""
        if not self.send_message or not self.chat_ids:
            logger.warning("Weekly report: No message sender or chat IDs configured")
            return
        
        try:
            report = await self.generate_report()
            
            # Send to all users
            for chat_id in list(self.chat_ids):
                try:
                    settings = await self.get_user_settings(chat_id)
                    if settings.get("free_will", True):
                        await self.send_message(chat_id, report)
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending report to {chat_id}: {e}")
            
            # Store in database
            if self.db is not None:
                try:
                    await self.db.weekly_reports.insert_one({
                        "content": report,
                        "sent_at": datetime.now(timezone.utc),
                        "recipients": len(self.chat_ids)
                    })
                except Exception as e:
                    logger.warning(f"Failed to log weekly report to DB: {e}")
            
            # Update last report date
            self.last_report_date = self._get_austin_time().date()
            logger.info(f"📊 Weekly performance report sent to {len(self.chat_ids)} users")
            
        except Exception as e:
            logger.error(f"Error generating/sending weekly report: {e}")
    
    async def run_scheduler(self):
        """Main scheduler loop - checks every minute for report time"""
        logger.info("📊 Weekly Performance Report Scheduler started (Sunday 8 PM Central Time)")
        
        while self.is_active:
            try:
                if self._should_send_report():
                    await self.send_report()

                from self_healer import self_healer
                self_healer.heartbeat("weekly_report")

                # Check every minute
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Weekly report scheduler error: {e}")
                await asyncio.sleep(60)
    
    async def send_test_report(self):
        """Send a test report immediately (for testing)"""
        logger.info("Sending test weekly report...")
        await self.send_report()
        return {"success": True, "message": "Test report sent"}
    
    async def get_preview(self) -> str:
        """Generate preview of current week's report"""
        return await self.generate_report()
    
    async def get_status(self) -> Dict:
        """Get report scheduler status"""
        austin_now = self._get_austin_time()
        
        # Calculate next Sunday 8 PM
        days_until_sunday = (6 - austin_now.weekday()) % 7
        if days_until_sunday == 0 and austin_now.hour >= REPORT_HOUR:
            days_until_sunday = 7
        
        next_report = austin_now + timedelta(days=days_until_sunday)
        next_report = next_report.replace(hour=REPORT_HOUR, minute=0, second=0, microsecond=0)
        
        week_start, week_end = self._get_week_range()
        trades = await self.get_closed_trades(week_start, week_end)
        
        return {
            "enabled": self.is_active,
            "scheduled_day": "Sunday",
            "scheduled_time": "8:00 PM CT",
            "timezone": "America/Chicago (Central Time)",
            "current_time_ct": austin_now.strftime("%Y-%m-%d %H:%M:%S"),
            "next_report": next_report.strftime("%Y-%m-%d %H:%M:%S"),
            "last_sent": self.last_report_date.isoformat() if self.last_report_date else None,
            "active_users": len(self.chat_ids),
            "trades_this_week": len(trades)
        }


# Global instance
weekly_report = WeeklyPerformanceReport()
