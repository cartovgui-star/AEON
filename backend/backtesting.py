"""
AEON BACKTESTING FRAMEWORK
Test trading strategies against historical data
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import ccxt

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)

# Initialize exchange
mexc = ccxt.mexc()


class BacktestEngine:
    """
    Backtesting engine for strategy validation
    
    Features:
    - Test strategies on historical data
    - Calculate win rate, profit factor, max drawdown
    - Compare different entry/exit strategies
    - Generate performance reports
    """
    
    def __init__(self):
        self.cache = {}
    
    async def get_historical_data(self, symbol: str, timeframe: str, 
                                   days: int = 30, limit: int = 500) -> List:
        """Fetch historical OHLCV data"""
        try:
            loop = asyncio.get_running_loop()
            ohlcv = await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
            return ohlcv
        except Exception as e:
            logger.error(f"Historical data error: {e}")
            return []
    
    def calculate_rsi(self, closes: List[float], period: int = 14) -> List[float]:
        """Calculate RSI"""
        if len(closes) < period + 1:
            return [50] * len(closes)
        
        rsi_values = [50] * period  # Pad beginning
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        for i in range(period - 1, len(gains)):
            avg_gain = sum(gains[i-period+1:i+1]) / period
            avg_loss = sum(losses[i-period+1:i+1]) / period
            
            if avg_loss == 0:
                rsi_values.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))
        
        return rsi_values
    
    def calculate_ema(self, data: List[float], period: int) -> List[float]:
        """Calculate EMA"""
        if len(data) < period:
            return data
        
        ema_values = [sum(data[:period]) / period]
        multiplier = 2 / (period + 1)
        
        for price in data[period:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        
        # Pad beginning
        return [ema_values[0]] * (len(data) - len(ema_values)) + ema_values
    
    def calculate_bb(self, closes: List[float], period: int = 20, 
                     std_mult: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
        """Calculate Bollinger Bands"""
        if len(closes) < period:
            return closes, closes, closes
        
        middle = []
        upper = []
        lower = []
        
        for i in range(len(closes)):
            if i < period - 1:
                middle.append(closes[i])
                upper.append(closes[i])
                lower.append(closes[i])
            else:
                window = closes[i-period+1:i+1]
                sma = sum(window) / period
                std = (sum((x - sma) ** 2 for x in window) / period) ** 0.5
                
                middle.append(sma)
                upper.append(sma + std * std_mult)
                lower.append(sma - std * std_mult)
        
        return upper, middle, lower
    
    async def backtest_rsi_strategy(self, symbol: str, timeframe: str = "1h",
                                     rsi_oversold: int = 30, rsi_overbought: int = 70,
                                     stop_pct: float = 2.0, target_pct: float = 4.0,
                                     days: int = 30) -> Dict:
        """
        Backtest RSI mean reversion strategy
        
        Entry: RSI < oversold (LONG) or RSI > overbought (SHORT)
        Exit: Target hit, Stop hit, or opposite RSI extreme
        """
        ohlcv = await self.get_historical_data(symbol, timeframe, days)
        
        if len(ohlcv) < 50:
            return {"error": "Insufficient data"}
        
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        
        rsi = self.calculate_rsi(closes)
        
        trades = []
        position = None
        
        for i in range(20, len(closes)):
            current_rsi = rsi[i]
            price = closes[i]
            high = highs[i]
            low = lows[i]
            
            # Check if in position
            if position:
                entry = position["entry"]
                direction = position["direction"]
                stop = position["stop"]
                target = position["target"]
                
                # Check stop/target
                if direction == "LONG":
                    if low <= stop:
                        # Stop hit
                        pnl_pct = ((stop - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": stop,
                            "pnl_pct": pnl_pct,
                            "result": "STOP",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif high >= target:
                        # Target hit
                        pnl_pct = ((target - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": target,
                            "pnl_pct": pnl_pct,
                            "result": "TARGET",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif current_rsi > rsi_overbought:
                        # Exit on overbought
                        pnl_pct = ((price - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": price,
                            "pnl_pct": pnl_pct,
                            "result": "RSI_EXIT",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                
                else:  # SHORT
                    if high >= stop:
                        pnl_pct = ((entry - stop) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": stop,
                            "pnl_pct": pnl_pct,
                            "result": "STOP",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif low <= target:
                        pnl_pct = ((entry - target) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": target,
                            "pnl_pct": pnl_pct,
                            "result": "TARGET",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif current_rsi < rsi_oversold:
                        pnl_pct = ((entry - price) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": price,
                            "pnl_pct": pnl_pct,
                            "result": "RSI_EXIT",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
            
            # Look for entry
            if not position:
                if current_rsi < rsi_oversold:
                    # LONG entry
                    position = {
                        "direction": "LONG",
                        "entry": price,
                        "stop": price * (1 - stop_pct / 100),
                        "target": price * (1 + target_pct / 100),
                        "entry_bar": i
                    }
                elif current_rsi > rsi_overbought:
                    # SHORT entry
                    position = {
                        "direction": "SHORT",
                        "entry": price,
                        "stop": price * (1 + stop_pct / 100),
                        "target": price * (1 - target_pct / 100),
                        "entry_bar": i
                    }
        
        # Calculate stats
        return self._calculate_stats(trades, symbol, timeframe, "RSI Mean Reversion")
    
    async def backtest_bb_strategy(self, symbol: str, timeframe: str = "1h",
                                    stop_pct: float = 2.0, target_pct: float = 4.0,
                                    days: int = 30) -> Dict:
        """
        Backtest Bollinger Band strategy
        
        Entry: Price touches lower band (LONG) or upper band (SHORT)
        Exit: Price reaches middle band, or stop/target hit
        """
        ohlcv = await self.get_historical_data(symbol, timeframe, days)
        
        if len(ohlcv) < 50:
            return {"error": "Insufficient data"}
        
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        
        upper, middle, lower = self.calculate_bb(closes)
        
        trades = []
        position = None
        
        for i in range(25, len(closes)):
            price = closes[i]
            high = highs[i]
            low = lows[i]
            
            bb_upper = upper[i]
            bb_middle = middle[i]
            bb_lower = lower[i]
            
            if position:
                entry = position["entry"]
                direction = position["direction"]
                stop = position["stop"]
                target = position["target"]
                
                if direction == "LONG":
                    if low <= stop:
                        pnl_pct = ((stop - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": stop,
                            "pnl_pct": pnl_pct,
                            "result": "STOP",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif high >= bb_middle:
                        pnl_pct = ((bb_middle - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": bb_middle,
                            "pnl_pct": pnl_pct,
                            "result": "MIDDLE_BAND",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                
                else:  # SHORT
                    if high >= stop:
                        pnl_pct = ((entry - stop) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": stop,
                            "pnl_pct": pnl_pct,
                            "result": "STOP",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif low <= bb_middle:
                        pnl_pct = ((entry - bb_middle) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": bb_middle,
                            "pnl_pct": pnl_pct,
                            "result": "MIDDLE_BAND",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
            
            if not position:
                if low <= bb_lower:
                    position = {
                        "direction": "LONG",
                        "entry": price,
                        "stop": price * (1 - stop_pct / 100),
                        "target": bb_middle,
                        "entry_bar": i
                    }
                elif high >= bb_upper:
                    position = {
                        "direction": "SHORT",
                        "entry": price,
                        "stop": price * (1 + stop_pct / 100),
                        "target": bb_middle,
                        "entry_bar": i
                    }
        
        return self._calculate_stats(trades, symbol, timeframe, "Bollinger Band")
    
    async def backtest_ema_cross_strategy(self, symbol: str, timeframe: str = "1h",
                                           fast_period: int = 9, slow_period: int = 21,
                                           stop_pct: float = 2.0, days: int = 30) -> Dict:
        """
        Backtest EMA crossover strategy
        
        Entry: Fast EMA crosses above slow (LONG) or below (SHORT)
        Exit: Opposite cross or stop hit
        """
        ohlcv = await self.get_historical_data(symbol, timeframe, days)
        
        if len(ohlcv) < 50:
            return {"error": "Insufficient data"}
        
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        
        ema_fast = self.calculate_ema(closes, fast_period)
        ema_slow = self.calculate_ema(closes, slow_period)
        
        trades = []
        position = None
        
        for i in range(slow_period + 1, len(closes)):
            price = closes[i]
            high = highs[i]
            low = lows[i]
            
            fast_curr = ema_fast[i]
            fast_prev = ema_fast[i-1]
            slow_curr = ema_slow[i]
            slow_prev = ema_slow[i-1]
            
            # Detect crossover
            bullish_cross = fast_prev <= slow_prev and fast_curr > slow_curr
            bearish_cross = fast_prev >= slow_prev and fast_curr < slow_curr
            
            if position:
                entry = position["entry"]
                direction = position["direction"]
                stop = position["stop"]
                
                if direction == "LONG":
                    if low <= stop:
                        pnl_pct = ((stop - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": stop,
                            "pnl_pct": pnl_pct,
                            "result": "STOP",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif bearish_cross:
                        pnl_pct = ((price - entry) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": price,
                            "pnl_pct": pnl_pct,
                            "result": "CROSS_EXIT",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                
                else:  # SHORT
                    if high >= stop:
                        pnl_pct = ((entry - stop) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": stop,
                            "pnl_pct": pnl_pct,
                            "result": "STOP",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
                    elif bullish_cross:
                        pnl_pct = ((entry - price) / entry) * 100
                        trades.append({
                            "direction": direction,
                            "entry": entry,
                            "exit": price,
                            "pnl_pct": pnl_pct,
                            "result": "CROSS_EXIT",
                            "bars_held": i - position["entry_bar"]
                        })
                        position = None
            
            if not position:
                if bullish_cross:
                    position = {
                        "direction": "LONG",
                        "entry": price,
                        "stop": price * (1 - stop_pct / 100),
                        "entry_bar": i
                    }
                elif bearish_cross:
                    position = {
                        "direction": "SHORT",
                        "entry": price,
                        "stop": price * (1 + stop_pct / 100),
                        "entry_bar": i
                    }
        
        return self._calculate_stats(trades, symbol, timeframe, "EMA Crossover")
    
    def _calculate_stats(self, trades: List[Dict], symbol: str, 
                         timeframe: str, strategy: str) -> Dict:
        """Calculate backtest statistics"""
        if not trades:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy": strategy,
                "total_trades": 0,
                "error": "No trades generated"
            }
        
        wins = [t for t in trades if t["pnl_pct"] > 0]
        losses = [t for t in trades if t["pnl_pct"] <= 0]
        
        total_pnl = sum(t["pnl_pct"] for t in trades)
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
        
        # Profit factor
        gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0
        gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in trades:
            cumulative += t["pnl_pct"]
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        # Average bars held
        avg_bars = sum(t.get("bars_held", 0) for t in trades) / len(trades)
        
        # Best/Worst trade
        best = max(trades, key=lambda x: x["pnl_pct"])
        worst = min(trades, key=lambda x: x["pnl_pct"])
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "total_pnl_pct": round(total_pnl, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "avg_bars_held": round(avg_bars, 1),
            "best_trade_pct": round(best["pnl_pct"], 2),
            "worst_trade_pct": round(worst["pnl_pct"], 2),
            "trades": trades[-10:],  # Last 10 trades
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def compare_strategies(self, symbol: str, timeframe: str = "1h", 
                                  days: int = 30) -> Dict:
        """Compare all strategies on same data"""
        tasks = [
            self.backtest_rsi_strategy(symbol, timeframe, days=days),
            self.backtest_bb_strategy(symbol, timeframe, days=days),
            self.backtest_ema_cross_strategy(symbol, timeframe, days=days),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        strategies = []
        for r in results:
            if isinstance(r, Exception):
                strategies.append({"error": str(r)})
            else:
                strategies.append(r)
        
        # Rank by profit factor
        valid = [s for s in strategies if "error" not in s and s.get("total_trades", 0) > 0]
        valid.sort(key=lambda x: x.get("profit_factor", 0), reverse=True)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "strategies": strategies,
            "best_strategy": valid[0].get("strategy") if valid else "None",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
backtest_engine = BacktestEngine()
