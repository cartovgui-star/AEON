"""
AEON AGGRESSIVE SCALPER
Hybrid Scalping Strategy: Volume Breakout + Order Flow + Momentum

Features:
- Runs alongside V2.1 strategy for additional high-frequency trades
- Uses MEXC live data across 5m, 15m, 30m timeframes
- Auto-learning parameter optimization
- Reversal pattern detection for smart exits
- Integration with V2.1 autonomous trader
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import ccxt
import numpy as np

# Import learning and reversal systems
from scalper_learning import (
    ReversalPatternDetector, AutoLearningSystem, ScalperV2Integration,
    auto_learner, v2_integration, reversal_detector
)

# Import paper trading for signal routing
try:
    from paper_trading import route_engine_signal
except ImportError:
    route_engine_signal = None

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
    'auto_learn': True,  # Enable auto-learning
    'use_reversal_exits': True,  # Use reversal patterns for exits
    'send_to_v2': True,  # Send signals to V2.1
}


class AggressiveScalper:
    """
    Hybrid Scalping Strategy for AEON
    
    Combines:
    1. Volume Breakout - Entry on breakouts with above-avg volume
    2. Order Flow/Support-Resistance - Quick bounces off key levels
    3. Momentum - Price spikes/drops with directional confirmation
    
    Advanced Features:
    - Auto-learning parameter optimization
    - Reversal pattern detection for smart exits
    - V2.1 integration for unified trading
    
    Targets: 0.5-3% per trade with tight stops and fast exits
    """
    
    def __init__(self):
        self.settings = SCALPER_SETTINGS.copy()
        self.active_signals = {}  # symbol -> signal data
        self.signal_history = []
        self.is_scanning = False
        self.last_auto_learn = None
        self.learning_interval = 3600  # 1 hour
        
        # Initialize learning system
        asyncio.create_task(self._init_learning())
    
    async def _init_learning(self):
        """Initialize learning from database"""
        try:
            await auto_learner.load_from_db()
            if auto_learner.current_params:
                # Apply learned parameters
                for key, value in auto_learner.current_params.items():
                    if key in self.settings:
                        self.settings[key] = value
                logger.info(f"Applied learned parameters: {auto_learner.current_params}")
        except Exception as e:
            logger.error(f"Error initializing learning: {e}")
    
    async def auto_optimize(self):
        """Run auto-optimization if enabled and due"""
        if not self.settings.get('auto_learn', True):
            return
        
        if await auto_learner.should_optimize():
            new_settings = await auto_learner.optimize_parameters(self.settings)
            
            # Apply optimized settings
            for key, value in new_settings.items():
                if key in self.settings and key not in ['enabled', 'auto_learn', 'use_reversal_exits', 'send_to_v2']:
                    self.settings[key] = value
            
            self.last_auto_learn = datetime.now(timezone.utc)
            logger.info("Auto-optimization completed")
        
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> List:
        """Fetch OHLCV data from MEXC"""
        if not mexc:
            return []
        
        try:
            loop = asyncio.get_running_loop()
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
        
        # Check for reversal patterns (for exit recommendations)
        reversal_exit = None
        if self.settings.get('use_reversal_exits', True) and len(ohlcv) >= 10:
            candles = [{'open': o[1], 'high': o[2], 'low': o[3], 'close': o[4]} for o in ohlcv[-10:]]
            rsi_values = [self.calculate_rsi(closes[:i+1], self.settings['momentum_period']) for i in range(len(closes)-10, len(closes))]
            
            # Check if we should exit based on reversal patterns
            if signal != 0:
                position_type = "LONG" if signal == 1 else "SHORT"
                reversal_exit = reversal_detector.analyze_exit_signals(candles, rsi_values, position_type)
        
        result = {
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
            'reversal_warning': reversal_exit if reversal_exit and reversal_exit.get('should_exit') else None,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        
        # Send to V2.1 if enabled and signal is strong
        if signal != 0 and self.settings.get('send_to_v2', True):
            await v2_integration.queue_signal(result)
        
        return result
    
    async def scan_all_symbols(self, timeframe: str = '5m') -> List[Dict]:
        """Scan all symbols for scalp signals on a specific timeframe"""
        if not self.settings['enabled']:
            return []
        
        self.is_scanning = True
        signals = []
        
        # Run auto-optimization if due
        await self.auto_optimize()
        
        for symbol in SCALP_SYMBOLS:
            try:
                result = await self.analyze_symbol(symbol, timeframe)
                if result['signal'] != 0:
                    signals.append(result)
                    self.active_signals[f"{symbol}_{timeframe}"] = result
                    
                    # Route to paper trading
                    if route_engine_signal and result['strength'] >= 3:
                        try:
                            direction = "LONG" if result['signal'] > 0 else "SHORT"
                            entry_price = result.get('current_price', 0)
                            
                            # Calculate scalper-style SL/TP (tight)
                            if direction == "LONG":
                                stop_loss = entry_price * (1 - self.settings['stop_loss_pct'] / 100)
                                take_profit = entry_price * (1 + self.settings['profit_target_pct'] / 100)
                            else:
                                stop_loss = entry_price * (1 + self.settings['stop_loss_pct'] / 100)
                                take_profit = entry_price * (1 - self.settings['profit_target_pct'] / 100)
                            
                            paper_signal = {
                                "symbol": symbol,
                                "direction": direction,
                                "entry_price": entry_price,
                                "stop_loss": stop_loss,
                                "take_profit": take_profit,
                                "confidence": 75 + (result['strength'] * 5),  # 80-95 based on strength
                                "confirmations": result.get('indicators', []),
                                "timeframe": timeframe,
                                "risk_pct": 1.0  # Scalper uses smaller risk
                            }
                            await route_engine_signal(paper_signal, "SCALPER")
                        except Exception as e:
                            logger.warning(f"Scalper paper trade routing error: {e}")
                    
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
    
    async def get_learning_status(self) -> Dict:
        """Get auto-learning system status"""
        performance = await auto_learner.analyze_performance(24)
        return {
            "auto_learn_enabled": self.settings.get('auto_learn', True),
            "last_optimization": self.last_auto_learn.isoformat() if self.last_auto_learn else None,
            "learning_interval_hours": self.learning_interval / 3600,
            "current_learned_params": auto_learner.current_params,
            "recent_performance": performance,
            "learning_summary": auto_learner.get_learning_summary()
        }
    
    async def get_v2_integration_status(self) -> Dict:
        """Get V2.1 integration status"""
        return {
            "v2_integration_enabled": self.settings.get('send_to_v2', True),
            "min_strength_for_v2": v2_integration.min_strength_for_v2,
            "queued_signals": len(v2_integration.signal_queue),
            "signals_in_queue": v2_integration.signal_queue[:5]  # Show first 5
        }
    
    async def force_optimize(self) -> Dict:
        """Force run auto-optimization now"""
        old_settings = self.settings.copy()
        new_settings = await auto_learner.optimize_parameters(self.settings)
        
        changes = {}
        for key, value in new_settings.items():
            if key in old_settings and old_settings[key] != value:
                changes[key] = {"old": old_settings[key], "new": value}
                self.settings[key] = value
        
        self.last_auto_learn = datetime.now(timezone.utc)
        
        return {
            "success": True,
            "changes": changes,
            "new_settings": self.settings,
            "optimized_at": datetime.now(timezone.utc).isoformat()
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # MULTI-TIMEFRAME CONFLUENCE ANALYSIS
    # Find high-probability setups when signals align across 5m, 15m, 30m timeframes
    # ═══════════════════════════════════════════════════════════════════════════════

    async def analyze_mtf_confluence(self, symbol: str) -> Dict:
        """
        Analyze a symbol across all timeframes (5m, 15m, 30m) for confluence.
        Higher confluence = higher probability trade.
        
        Confluence Levels:
        - STRONG (3/3): All timeframes agree - highest probability
        - MODERATE (2/3): Two timeframes agree - good setup
        - WEAK (1/3): Only one timeframe has signal - low probability
        - NONE (0/3): No signals - stay out
        """
        if "/" not in symbol:
            symbol = symbol.upper() + "/USDT"
        
        signals_by_tf = {}
        confluence_score = 0
        direction_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        total_strength = 0
        
        # Analyze all timeframes
        for tf in SCALP_TIMEFRAMES:
            try:
                analysis = await self.analyze_symbol(symbol, tf)
                signals_by_tf[tf] = analysis
                
                signal = analysis.get('signal', 0)
                strength = analysis.get('strength', 0)
                
                if signal == 1:  # BUY
                    direction_votes["LONG"] += 1
                    confluence_score += strength
                    total_strength += strength
                elif signal == -1:  # SELL
                    direction_votes["SHORT"] += 1
                    confluence_score += strength
                    total_strength += strength
                else:
                    direction_votes["NEUTRAL"] += 1
                    
            except Exception as e:
                logger.error(f"MTF confluence error {symbol} {tf}: {e}")
                signals_by_tf[tf] = {"error": str(e)}
        
        # Determine consensus direction
        if direction_votes["LONG"] > direction_votes["SHORT"] and direction_votes["LONG"] >= 2:
            consensus_direction = "LONG"
            confluence_count = direction_votes["LONG"]
        elif direction_votes["SHORT"] > direction_votes["LONG"] and direction_votes["SHORT"] >= 2:
            consensus_direction = "SHORT"
            confluence_count = direction_votes["SHORT"]
        elif direction_votes["LONG"] == direction_votes["SHORT"] and direction_votes["LONG"] >= 1:
            consensus_direction = "MIXED"
            confluence_count = max(direction_votes["LONG"], direction_votes["SHORT"])
        else:
            consensus_direction = "NEUTRAL"
            confluence_count = 0
        
        # Determine confluence level
        if confluence_count == 3:
            confluence_level = "STRONG"
            probability = "HIGH (75-85%)"
            recommendation = f"Strong {consensus_direction} - All timeframes aligned"
        elif confluence_count == 2:
            confluence_level = "MODERATE"
            probability = "MEDIUM (60-70%)"
            recommendation = f"Good {consensus_direction} setup - 2/3 timeframes agree"
        elif confluence_count == 1:
            confluence_level = "WEAK"
            probability = "LOW (45-55%)"
            recommendation = "Consider waiting for more confirmation"
        else:
            confluence_level = "NONE"
            probability = "N/A"
            recommendation = "No clear setup - stay out"
        
        # Calculate weighted confidence
        avg_strength = total_strength / 3 if total_strength > 0 else 0
        weighted_confidence = min(95, 50 + (confluence_count * 15) + (avg_strength * 5))
        
        return {
            "symbol": symbol,
            "confluence_level": confluence_level,
            "confluence_count": f"{confluence_count}/3",
            "consensus_direction": consensus_direction,
            "weighted_confidence": round(weighted_confidence, 1),
            "probability": probability,
            "recommendation": recommendation,
            "total_strength": total_strength,
            "direction_votes": direction_votes,
            "timeframes": signals_by_tf,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

    async def scan_mtf_confluence(self, min_confluence: int = 2) -> Dict:
        """
        Scan all symbols for MTF confluence setups.
        Returns symbols with signals on at least `min_confluence` timeframes.
        """
        results = {
            "strong": [],      # 3/3 confluence
            "moderate": [],    # 2/3 confluence
            "weak": [],        # 1/3 confluence
        }
        
        for symbol in SCALP_SYMBOLS:
            try:
                analysis = await self.analyze_mtf_confluence(symbol)
                
                level = analysis.get("confluence_level", "NONE")
                if level == "STRONG":
                    results["strong"].append(analysis)
                elif level == "MODERATE":
                    results["moderate"].append(analysis)
                elif level == "WEAK" and min_confluence <= 1:
                    results["weak"].append(analysis)
                    
            except Exception as e:
                logger.error(f"MTF scan error {symbol}: {e}")
        
        # Sort by weighted confidence
        for key in results:
            results[key] = sorted(results[key], 
                                  key=lambda x: x.get("weighted_confidence", 0), 
                                  reverse=True)
        
        # Summary stats
        total_strong = len(results["strong"])
        total_moderate = len(results["moderate"])
        
        return {
            "summary": {
                "strong_setups": total_strong,
                "moderate_setups": total_moderate,
                "total_actionable": total_strong + total_moderate,
                "scanned_symbols": len(SCALP_SYMBOLS),
            },
            "best_setup": results["strong"][0] if results["strong"] else 
                         (results["moderate"][0] if results["moderate"] else None),
            "strong_confluence": results["strong"],
            "moderate_confluence": results["moderate"],
            "weak_confluence": results["weak"][:5] if min_confluence <= 1 else [],
            "scanned_at": datetime.now(timezone.utc).isoformat()
        }

    async def get_mtf_correlation_report(self) -> Dict:
        """
        Generate a comprehensive MTF correlation analysis report.
        Shows which timeframes tend to agree and historical performance by confluence level.
        """
        confluence_data = await self.scan_mtf_confluence(min_confluence=1)
        
        # Analyze correlation patterns
        tf_agreement = {
            "5m_15m": 0,
            "5m_30m": 0,
            "15m_30m": 0,
            "all_three": 0,
        }
        
        direction_stats = {
            "LONG": {"strong": 0, "moderate": 0, "weak": 0},
            "SHORT": {"strong": 0, "moderate": 0, "weak": 0},
        }
        
        for setup in confluence_data["strong_confluence"]:
            direction = setup.get("consensus_direction")
            if direction in direction_stats:
                direction_stats[direction]["strong"] += 1
            tf_agreement["all_three"] += 1
            
        for setup in confluence_data["moderate_confluence"]:
            direction = setup.get("consensus_direction")
            if direction in direction_stats:
                direction_stats[direction]["moderate"] += 1
            
            # Check which TFs agree
            tfs = setup.get("timeframes", {})
            signals = {tf: tfs.get(tf, {}).get("signal", 0) for tf in SCALP_TIMEFRAMES}
            
            if signals.get("5m") == signals.get("15m") and signals.get("5m") != 0:
                tf_agreement["5m_15m"] += 1
            if signals.get("5m") == signals.get("30m") and signals.get("5m") != 0:
                tf_agreement["5m_30m"] += 1
            if signals.get("15m") == signals.get("30m") and signals.get("15m") != 0:
                tf_agreement["15m_30m"] += 1
        
        # Best performing correlations
        correlation_insights = []
        if tf_agreement["all_three"] > 0:
            correlation_insights.append(f"🎯 {tf_agreement['all_three']} symbols have PERFECT alignment (5m+15m+30m)")
        if tf_agreement["15m_30m"] > tf_agreement["5m_15m"]:
            correlation_insights.append("📊 15m+30m correlation is strongest - consider prioritizing these")
        elif tf_agreement["5m_15m"] > tf_agreement["15m_30m"]:
            correlation_insights.append("📊 5m+15m correlation is strongest - good for quick scalps")
        
        return {
            "summary": confluence_data["summary"],
            "best_setup": confluence_data["best_setup"],
            "timeframe_correlation": tf_agreement,
            "direction_breakdown": direction_stats,
            "insights": correlation_insights,
            "recommendations": [
                "Trade STRONG confluence (3/3) with higher position size",
                "Trade MODERATE confluence (2/3) with standard position size",
                "Avoid WEAK confluence (1/3) unless other factors confirm",
                "Best setups often occur when 15m and 30m align first, then 5m confirms"
            ],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


# Global scalper instance
scalper = AggressiveScalper()
