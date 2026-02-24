"""
AEON AGGRESSIVE SCALPER
Hybrid Scalping Strategy: Volume Breakout + Order Flow + Momentum

Runs alongside V2.1 strategy for additional high-frequency trades.
Uses MEXC live data across 5m, 15m, 30m timeframes.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import ccxt
import numpy as np

logger = logging.getLogger(__name__)

# Initialize MEXC
try:
    mexc = ccxt.mexc({'enableRateLimit': True})
except Exception as e:
    logger.error(f"Failed to init MEXC for scalper: {e}")
    mexc = None

executor = ThreadPoolExecutor(max_workers=5)

# All tracked symbols
SCALP_SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT',
    'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ARB/USDT', 'OP/USDT'
]

# Timeframes for multi-TF analysis
SCALP_TIMEFRAMES = ['5m', '15m', '30m']

# Default scalper settings
SCALPER_SETTINGS = {
    'lookback_vol': 20,
    'momentum_period': 14,
    'profit_target_pct': 1.5,
    'stop_loss_pct': 0.5,
    'volume_threshold': 1.5,
    'rsi_overbought': 70,
    'rsi_oversold': 30,
    'roc_threshold': 0.5,
    'max_hold_bars': 50,
    'enabled': True,
}


class AggressiveScalper:
    """
    Hybrid Scalping Strategy for AEON
    
    Combines:
    1. Volume Breakout - Entry on breakouts with above-avg volume
    2. Order Flow/Support-Resistance - Quick bounces off key levels
    3. Momentum - Price spikes/drops with directional confirmation
    
    Targets: 0.5-3% per trade with tight stops and fast exits
    """
    
    def __init__(self):
        self.settings = SCALPER_SETTINGS.copy()
        self.active_signals = {}  # symbol -> signal data
        self.signal_history = []
        self.is_scanning = False
        
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> List:
        """Fetch OHLCV data from MEXC"""
        if not mexc:
            return []
        
        try:
            loop = asyncio.get_event_loop()
            ohlcv = await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
            return ohlcv
        except Exception as e:
            logger.error(f"Scalper OHLCV fetch error {symbol}: {e}")
            return []
    
    def calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI from close prices"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    
    def calculate_volume_ratio(self, volumes: List[float], lookback: int = 20) -> float:
        """Calculate current volume vs moving average"""
        if len(volumes) < lookback + 1:
            return 1.0
        
        vol_ma = np.mean(volumes[-lookback-1:-1])
        current_vol = volumes[-1]
        
        if vol_ma == 0:
            return 1.0
        
        return current_vol / vol_ma
    
    def calculate_roc(self, closes: List[float], period: int = 5) -> Tuple[float, float]:
        """Calculate Rate of Change and its moving average"""
        if len(closes) < period + 1:
            return 0.0, 0.0
        
        rocs = []
        for i in range(period, len(closes)):
            if closes[i-1] != 0:
                roc = ((closes[i] / closes[i-1]) - 1) * 100
                rocs.append(roc)
        
        if not rocs:
            return 0.0, 0.0
        
        current_roc = rocs[-1] if rocs else 0.0
        roc_ma = np.mean(rocs[-5:]) if len(rocs) >= 5 else np.mean(rocs)
        
        return current_roc, roc_ma
    
    async def analyze_symbol(self, symbol: str, timeframe: str = '5m') -> Dict:
        """
        Analyze a single symbol for scalp signals
        Returns signal with direction and strength
        """
        ohlcv = await self.fetch_ohlcv(symbol, timeframe, limit=100)
        
        if len(ohlcv) < 30:
            return {'symbol': symbol, 'timeframe': timeframe, 'signal': 0, 'strength': 0}
        
        # Extract OHLCV arrays
        opens = [c[1] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        
        # Current values
        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]
        prev_high = highs[-2]
        prev_low = lows[-2]
        
        # Calculate indicators
        rsi = self.calculate_rsi(closes, self.settings['momentum_period'])
        volume_ratio = self.calculate_volume_ratio(volumes, self.settings['lookback_vol'])
        roc, roc_ma = self.calculate_roc(closes)
        
        high_volume = volume_ratio > self.settings['volume_threshold']
        overbought = rsi > self.settings['rsi_overbought']
        oversold = rsi < self.settings['rsi_oversold']
        
        # Support/Resistance proximity
        near_prev_high = abs(current_close - prev_high) / prev_high < 0.01
        near_prev_low = abs(current_close - prev_low) / prev_low < 0.01
        
        # Strong momentum conditions
        strong_up = overbought and roc > roc_ma
        strong_down = oversold and roc < roc_ma
        
        signal = 0
        strength = 0
        reason = ""
        
        # ===== BUY SIGNAL LOGIC =====
        
        # Strength 3: Volume Breakout + Momentum (Bullish)
        if high_volume and strong_up and current_close > prev_high:
            signal = 1
            strength = 3
            reason = "Volume breakout + strong momentum UP"
        
        # Strength 2: Volume + Oversold Bounce
        elif high_volume and near_prev_low and rsi < 40:
            signal = 1
            strength = 2
            reason = "Volume + support bounce (oversold)"
        
        # Strength 1: Pure Momentum (Aggressive)
        elif strong_up and roc > self.settings['roc_threshold']:
            signal = 1
            strength = 1
            reason = "Momentum spike UP"
        
        # ===== SELL SIGNAL LOGIC =====
        
        # Strength 3: Volume Breakout + Momentum (Bearish)
        elif high_volume and strong_down and current_close < prev_low:
            signal = -1
            strength = 3
            reason = "Volume breakout + strong momentum DOWN"
        
        # Strength 2: Volume + Overbought Rejection
        elif high_volume and near_prev_high and rsi > 60:
            signal = -1
            strength = 2
            reason = "Volume + resistance rejection (overbought)"
        
        # Strength 1: Pure Momentum (Aggressive)
        elif strong_down and roc < -self.settings['roc_threshold']:
            signal = -1
            strength = 1
            reason = "Momentum spike DOWN"
        
        # Calculate targets
        stop_loss = current_close * (1 - self.settings['stop_loss_pct']/100) if signal == 1 else \
                    current_close * (1 + self.settings['stop_loss_pct']/100) if signal == -1 else 0
        
        target = current_close * (1 + self.settings['profit_target_pct']/100) if signal == 1 else \
                 current_close * (1 - self.settings['profit_target_pct']/100) if signal == -1 else 0
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': signal,  # 1=BUY, -1=SELL, 0=HOLD
            'strength': strength,  # 1-3
            'reason': reason,
            'price': current_close,
            'rsi': round(rsi, 1),
            'volume_ratio': round(volume_ratio, 2),
            'roc': round(roc, 2),
            'stop_loss': round(stop_loss, 4) if stop_loss else None,
            'target': round(target, 4) if target else None,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    
    async def scan_all_symbols(self, timeframe: str = '5m') -> List[Dict]:
        """Scan all symbols for scalp signals on a specific timeframe"""
        if not self.settings['enabled']:
            return []
        
        self.is_scanning = True
        signals = []
        
        for symbol in SCALP_SYMBOLS:
            try:
                result = await self.analyze_symbol(symbol, timeframe)
                if result['signal'] != 0:
                    signals.append(result)
                    self.active_signals[f"{symbol}_{timeframe}"] = result
            except Exception as e:
                logger.error(f"Scalper scan error {symbol}: {e}")
        
        self.is_scanning = False
        
        # Sort by strength (highest first)
        signals.sort(key=lambda x: x['strength'], reverse=True)
        
        return signals
    
    async def scan_all_timeframes(self) -> Dict[str, List[Dict]]:
        """Scan all symbols across all timeframes"""
        if not self.settings['enabled']:
            return {}
        
        results = {}
        
        for tf in SCALP_TIMEFRAMES:
            signals = await self.scan_all_symbols(tf)
            results[tf] = signals
            logger.info(f"Scalper {tf}: Found {len(signals)} signals")
        
        return results
    
    async def get_best_opportunities(self, min_strength: int = 2) -> List[Dict]:
        """Get the best scalp opportunities across all timeframes"""
        all_signals = await self.scan_all_timeframes()
        
        best = []
        for tf, signals in all_signals.items():
            for sig in signals:
                if sig['strength'] >= min_strength:
                    best.append(sig)
        
        # Sort by strength, then by volume ratio
        best.sort(key=lambda x: (x['strength'], x['volume_ratio']), reverse=True)
        
        return best[:10]  # Top 10 opportunities
    
    async def backtest_symbol(self, symbol: str, timeframe: str = '5m', 
                              days: int = 7) -> Dict:
        """
        Backtest the scalping strategy on historical data
        """
        # Fetch more data for backtest
        limit = {
            '5m': min(1000, days * 288),   # 288 5m candles per day
            '15m': min(1000, days * 96),   # 96 15m candles per day
            '30m': min(1000, days * 48),   # 48 30m candles per day
        }.get(timeframe, 500)
        
        ohlcv = await self.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if len(ohlcv) < 50:
            return {'error': 'Insufficient data'}
        
        trades = []
        position = 0
        entry_price = 0
        entry_idx = 0
        
        # Extract arrays
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        timestamps = [c[0] for c in ohlcv]
        
        for i in range(30, len(ohlcv)):
            # Calculate indicators at this point
            rsi = self.calculate_rsi(closes[:i+1], self.settings['momentum_period'])
            vol_ratio = self.calculate_volume_ratio(volumes[:i+1], self.settings['lookback_vol'])
            roc, roc_ma = self.calculate_roc(closes[:i+1])
            
            current_close = closes[i]
            current_high = highs[i]
            current_low = lows[i]
            prev_high = highs[i-1]
            prev_low = lows[i-1]
            
            high_volume = vol_ratio > self.settings['volume_threshold']
            overbought = rsi > self.settings['rsi_overbought']
            oversold = rsi < self.settings['rsi_oversold']
            strong_up = overbought and roc > roc_ma
            strong_down = oversold and roc < roc_ma
            
            # Position management
            if position != 0:
                bars_held = i - entry_idx
                
                if position == 1:  # Long position
                    target_price = entry_price * (1 + self.settings['profit_target_pct']/100)
                    stop_price = entry_price * (1 - self.settings['stop_loss_pct']/100)
                    
                    if current_high >= target_price:
                        pnl_pct = self.settings['profit_target_pct']
                        trades.append({
                            'type': 'LONG', 'entry': entry_price, 'exit': target_price,
                            'pnl_pct': pnl_pct, 'bars': bars_held, 'reason': 'Target Hit'
                        })
                        position = 0
                    elif current_low <= stop_price:
                        pnl_pct = -self.settings['stop_loss_pct']
                        trades.append({
                            'type': 'LONG', 'entry': entry_price, 'exit': stop_price,
                            'pnl_pct': pnl_pct, 'bars': bars_held, 'reason': 'Stop Loss'
                        })
                        position = 0
                    elif bars_held >= self.settings['max_hold_bars']:
                        pnl_pct = ((current_close - entry_price) / entry_price) * 100
                        trades.append({
                            'type': 'LONG', 'entry': entry_price, 'exit': current_close,
                            'pnl_pct': pnl_pct, 'bars': bars_held, 'reason': 'Max Hold'
                        })
                        position = 0
                
                elif position == -1:  # Short position
                    target_price = entry_price * (1 - self.settings['profit_target_pct']/100)
                    stop_price = entry_price * (1 + self.settings['stop_loss_pct']/100)
                    
                    if current_low <= target_price:
                        pnl_pct = self.settings['profit_target_pct']
                        trades.append({
                            'type': 'SHORT', 'entry': entry_price, 'exit': target_price,
                            'pnl_pct': pnl_pct, 'bars': bars_held, 'reason': 'Target Hit'
                        })
                        position = 0
                    elif current_high >= stop_price:
                        pnl_pct = -self.settings['stop_loss_pct']
                        trades.append({
                            'type': 'SHORT', 'entry': entry_price, 'exit': stop_price,
                            'pnl_pct': pnl_pct, 'bars': bars_held, 'reason': 'Stop Loss'
                        })
                        position = 0
                    elif bars_held >= self.settings['max_hold_bars']:
                        pnl_pct = ((entry_price - current_close) / entry_price) * 100
                        trades.append({
                            'type': 'SHORT', 'entry': entry_price, 'exit': current_close,
                            'pnl_pct': pnl_pct, 'bars': bars_held, 'reason': 'Max Hold'
                        })
                        position = 0
            
            # Entry logic
            if position == 0:
                signal = 0
                
                # Buy signals
                if high_volume and strong_up and current_close > prev_high:
                    signal = 1
                elif high_volume and current_close < prev_low * 1.01 and rsi < 40:
                    signal = 1
                elif strong_up and roc > self.settings['roc_threshold']:
                    signal = 1
                
                # Sell signals
                elif high_volume and strong_down and current_close < prev_low:
                    signal = -1
                elif high_volume and current_close > prev_high * 0.99 and rsi > 60:
                    signal = -1
                elif strong_down and roc < -self.settings['roc_threshold']:
                    signal = -1
                
                if signal != 0:
                    position = signal
                    entry_price = current_close
                    entry_idx = i
        
        # Calculate statistics
        if not trades:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
            }
        
        wins = sum(1 for t in trades if t['pnl_pct'] > 0)
        losses = len(trades) - wins
        total_pnl = sum(t['pnl_pct'] for t in trades)
        avg_bars = sum(t['bars'] for t in trades) / len(trades)
        
        target_hits = sum(1 for t in trades if t['reason'] == 'Target Hit')
        stop_hits = sum(1 for t in trades if t['reason'] == 'Stop Loss')
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'total_trades': len(trades),
            'wins': wins,
            'losses': losses,
            'win_rate': round((wins / len(trades)) * 100, 1),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(total_pnl / len(trades), 2),
            'avg_bars': round(avg_bars, 1),
            'target_hits': target_hits,
            'stop_hits': stop_hits,
            'longs': sum(1 for t in trades if t['type'] == 'LONG'),
            'shorts': sum(1 for t in trades if t['type'] == 'SHORT'),
            'trades': trades[-20:],  # Last 20 trades
        }
    
    async def backtest_all(self, timeframe: str = '5m', days: int = 7) -> Dict:
        """Backtest all symbols"""
        results = []
        
        for symbol in SCALP_SYMBOLS:
            try:
                result = await self.backtest_symbol(symbol, timeframe, days)
                if result.get('total_trades', 0) > 0:
                    results.append(result)
            except Exception as e:
                logger.error(f"Backtest error {symbol}: {e}")
        
        # Aggregate stats
        total_trades = sum(r['total_trades'] for r in results)
        total_wins = sum(r['wins'] for r in results)
        total_pnl = sum(r['total_pnl'] for r in results)
        
        return {
            'timeframe': timeframe,
            'days': days,
            'symbols_tested': len(results),
            'total_trades': total_trades,
            'total_wins': total_wins,
            'win_rate': round((total_wins / total_trades * 100), 1) if total_trades > 0 else 0,
            'total_pnl': round(total_pnl, 2),
            'by_symbol': sorted(results, key=lambda x: x['total_pnl'], reverse=True),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    
    def get_settings(self) -> Dict:
        """Get current scalper settings"""
        return self.settings.copy()
    
    def update_settings(self, new_settings: Dict) -> Dict:
        """Update scalper settings"""
        for key, value in new_settings.items():
            if key in self.settings:
                self.settings[key] = value
        return self.settings.copy()


# Global scalper instance
scalper = AggressiveScalper()
