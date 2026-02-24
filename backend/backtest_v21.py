"""
AEON V2.1 Backtest Engine
Tests the new HIGH WIN RATE filters against historical MEXC data
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import statistics
import logging
from concurrent.futures import ThreadPoolExecutor
import ccxt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread executor for MEXC API calls
executor = ThreadPoolExecutor(max_workers=3)

# Initialize MEXC exchange
try:
    mexc = ccxt.mexc({'enableRateLimit': True})
except Exception as e:
    logger.error(f"Failed to init MEXC: {e}")
    mexc = None

# V2.1 Filter Settings (Default - can be overridden in backtest)
V21_SETTINGS = {
    "min_confidence": 90,
    "min_confirmations": 5,
    "min_rr_ratio": 3.0,
    "ema_no_trade_zone_pct": 0.5,
    "min_adx": 25,
    "min_volume_multiplier": 1.5,
    "session_filter": True,  # Only trade London/NY
}

# Confidence levels to test (65% to 90%)
CONFIDENCE_LEVELS = [65, 70, 75, 80, 85, 90]

# Timeframes for multi-timeframe testing
MTF_TIMEFRAMES = ["15m", "1h", "4h"]

class BacktestV21Engine:
    """
    V2.1 Backtest Engine using MEXC historical data
    Tests the HIGH WIN RATE filters against real market data
    """
    
    def __init__(self):
        self.results = {
            "total_candles": 0,
            "signals_generated": 0,
            "filters": {
                "ema_200_filtered": 0,
                "adx_filtered": 0,
                "volume_filtered": 0,
                "session_filtered": 0,
                "confidence_filtered": 0,
                "rr_filtered": 0,
                "rsi_counter_trend": 0,
            },
            "passed_filters": 0,
            "simulated_trades": [],
            "win_rate_old": 0,
            "win_rate_new": 0,
        }
        self.is_running = False
        self.progress = 0
        self.current_symbol = ""
    
    async def fetch_klines(self, symbol: str, interval: str = "1h", days: int = 30) -> List[Dict]:
        """Fetch historical klines from MEXC"""
        if not mexc:
            logger.error("MEXC not initialized")
            return []
        
        try:
            loop = asyncio.get_event_loop()
            
            # Calculate limit based on days and interval
            interval_minutes = {
                "1m": 1, "5m": 5, "15m": 15, "30m": 30,
                "1h": 60, "4h": 240, "1d": 1440
            }
            mins_per_candle = interval_minutes.get(interval, 60)
            candles_needed = min(1000, (days * 24 * 60) // mins_per_candle)
            
            # Fetch OHLCV data from MEXC
            ohlcv = await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ohlcv(symbol, interval, limit=int(candles_needed))
            )
            
            if not ohlcv:
                return []
            
            klines = []
            for k in ohlcv:
                klines.append({
                    "timestamp": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": k[0] + (mins_per_candle * 60 * 1000),
                })
            
            logger.info(f"Fetched {len(klines)} candles for {symbol} from MEXC")
            return klines
            
        except Exception as e:
            logger.error(f"MEXC fetch error for {symbol}: {e}")
            return []
    
    def calculate_indicators(self, klines: List[Dict], index: int) -> Dict:
        """Calculate technical indicators at a specific candle"""
        if index < 200:  # Need enough data for 200 EMA
            return {}
        
        closes = [k["close"] for k in klines[:index+1]]
        volumes = [k["volume"] for k in klines[:index+1]]
        highs = [k["high"] for k in klines[:index+1]]
        lows = [k["low"] for k in klines[:index+1]]
        
        # EMAs
        ema_9 = self.calculate_ema(closes, 9)
        ema_21 = self.calculate_ema(closes, 21)
        ema_50 = self.calculate_ema(closes, 50)
        ema_200 = self.calculate_ema(closes, 200)
        
        # RSI
        rsi = self.calculate_rsi(closes, 14)
        
        # ATR
        atr = self.calculate_atr(highs, lows, closes, 14)
        
        # ADX
        adx = self.calculate_adx(highs, lows, closes, 14)
        
        # Volume
        volume_sma = statistics.mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1]
        current_volume = volumes[-1]
        
        # Bollinger Bands
        bb_middle = statistics.mean(closes[-20:])
        bb_std = statistics.stdev(closes[-20:]) if len(closes) >= 20 else 0
        bb_upper = bb_middle + (2 * bb_std)
        bb_lower = bb_middle - (2 * bb_std)
        
        # Support/Resistance (simple pivot)
        support = min(lows[-20:])
        resistance = max(highs[-20:])
        
        return {
            "price": closes[-1],
            "ema_9": ema_9,
            "ema_21": ema_21,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "rsi": rsi,
            "atr": atr,
            "adx": adx,
            "volume": current_volume,
            "volume_sma": volume_sma,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "support": support,
            "resistance": resistance,
        }
    
    def calculate_ema(self, data: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return data[-1] if data else 0
        
        multiplier = 2 / (period + 1)
        ema = statistics.mean(data[:period])  # Start with SMA
        
        for price in data[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(closes) < period + 1:
            return 50
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = statistics.mean(gains[-period:])
        avg_loss = statistics.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(closes) < period + 1:
            return (highs[-1] - lows[-1]) if highs else 0
        
        tr_values = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr_values.append(max(high_low, high_close, low_close))
        
        return statistics.mean(tr_values[-period:])
    
    def calculate_adx(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate Average Directional Index (simplified)"""
        if len(closes) < period * 2:
            return 25  # Default neutral
        
        # Simplified ADX calculation
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(highs)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        atr = self.calculate_atr(highs, lows, closes, period)
        if atr == 0:
            return 25
        
        plus_di = (statistics.mean(plus_dm[-period:]) / atr) * 100
        minus_di = (statistics.mean(minus_dm[-period:]) / atr) * 100
        
        dx_sum = plus_di + minus_di
        if dx_sum == 0:
            return 25
        
        dx = abs(plus_di - minus_di) / dx_sum * 100
        return dx
    
    def get_session(self, timestamp: int) -> str:
        """Get trading session from timestamp"""
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        # Convert to EST (UTC-5)
        est_hour = (dt.hour - 5) % 24
        
        if 8 <= est_hour < 12:
            return "LONDON_NY_OVERLAP"
        elif 3 <= est_hour < 8:
            return "LONDON"
        elif 12 <= est_hour < 17:
            return "NEW_YORK"
        else:
            return "OFF_HOURS"
    
    def apply_v21_filters(self, indicators: Dict, timestamp: int, min_confidence: int = None) -> Dict:
        """Apply all V2.1 filters and return result
        
        Args:
            indicators: Technical indicators dict
            timestamp: Candle timestamp
            min_confidence: Override minimum confidence (default: V21_SETTINGS value)
        """
        # Use provided min_confidence or default from settings
        conf_threshold = min_confidence if min_confidence is not None else V21_SETTINGS["min_confidence"]
        
        result = {
            "passed": False,
            "direction": None,
            "filtered_by": None,
            "confidence": 0,
            "details": {}
        }
        
        price = indicators.get("price", 0)
        ema_200 = indicators.get("ema_200", price)
        adx = indicators.get("adx", 25)
        volume = indicators.get("volume", 0)
        volume_sma = indicators.get("volume_sma", volume)
        rsi = indicators.get("rsi", 50)
        
        # 1. 200 EMA TREND FILTER (FIRST)
        ema_distance_pct = ((price - ema_200) / ema_200) * 100 if ema_200 > 0 else 0
        
        if abs(ema_distance_pct) < V21_SETTINGS["ema_no_trade_zone_pct"]:
            result["filtered_by"] = "ema_200_no_trade_zone"
            self.results["filters"]["ema_200_filtered"] += 1
            return result
        
        # Determine allowed direction
        if ema_distance_pct > 0:
            ema_trend = "BULLISH"  # LONG only
        else:
            ema_trend = "BEARISH"  # SHORT only
        
        # 2. ADX FILTER (Trending market)
        if adx < V21_SETTINGS["min_adx"]:
            result["filtered_by"] = "adx_ranging"
            self.results["filters"]["adx_filtered"] += 1
            return result
        
        # 3. VOLUME FILTER
        volume_ratio = volume / volume_sma if volume_sma > 0 else 1
        if volume_ratio < V21_SETTINGS["min_volume_multiplier"]:
            result["filtered_by"] = "low_volume"
            self.results["filters"]["volume_filtered"] += 1
            return result
        
        # 4. SESSION FILTER
        session = self.get_session(timestamp)
        if V21_SETTINGS["session_filter"] and session == "OFF_HOURS":
            result["filtered_by"] = "bad_session"
            self.results["filters"]["session_filtered"] += 1
            return result
        
        # 5. RSI TREND AGREEMENT
        # RSI signals must agree with 200 EMA trend
        rsi_signal = None
        if rsi < 30:
            if ema_trend == "BULLISH":
                rsi_signal = "BUY"  # Valid
            else:
                result["filtered_by"] = "rsi_counter_trend"
                self.results["filters"]["rsi_counter_trend"] += 1
                return result
        elif rsi > 70:
            if ema_trend == "BEARISH":
                rsi_signal = "SELL"  # Valid
            else:
                result["filtered_by"] = "rsi_counter_trend"
                self.results["filters"]["rsi_counter_trend"] += 1
                return result
        
        # 6. CONFLUENCE SCORING
        confirmations = []
        tech_buy = 0
        tech_sell = 0
        
        # RSI
        if rsi < 30 and ema_trend == "BULLISH":
            tech_buy += 2
            confirmations.append("RSI<30 in uptrend")
        elif rsi > 70 and ema_trend == "BEARISH":
            tech_sell += 2
            confirmations.append("RSI>70 in downtrend")
        
        # EMA Stack
        ema_9 = indicators.get("ema_9", price)
        ema_21 = indicators.get("ema_21", price)
        ema_50 = indicators.get("ema_50", price)
        
        if ema_9 > ema_21 > ema_50 and ema_trend == "BULLISH":
            tech_buy += 2
            confirmations.append("Bullish EMA stack")
        elif ema_9 < ema_21 < ema_50 and ema_trend == "BEARISH":
            tech_sell += 2
            confirmations.append("Bearish EMA stack")
        
        # Bollinger Bands
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_upper = indicators.get("bb_upper", price * 1.02)
        
        if price <= bb_lower and ema_trend == "BULLISH":
            tech_buy += 2
            confirmations.append("BB lower touch")
        elif price >= bb_upper and ema_trend == "BEARISH":
            tech_sell += 2
            confirmations.append("BB upper touch")
        
        # ADX strong trend
        if adx > 30:
            if ema_trend == "BULLISH":
                tech_buy += 1
                confirmations.append("Strong ADX trend")
            else:
                tech_sell += 1
                confirmations.append("Strong ADX trend")
        
        # Volume spike
        if volume_ratio > 2.0:
            if ema_trend == "BULLISH":
                tech_buy += 1
                confirmations.append("Volume spike")
            else:
                tech_sell += 1
                confirmations.append("Volume spike")
        
        # Determine direction
        if ema_trend == "BULLISH" and tech_buy >= 4:
            direction = "LONG"
            signal_strength = tech_buy
        elif ema_trend == "BEARISH" and tech_sell >= 4:
            direction = "SHORT"
            signal_strength = tech_sell
        else:
            result["filtered_by"] = "insufficient_confluence"
            self.results["filters"]["confidence_filtered"] += 1
            return result
        
        # Calculate confidence
        confidence = min(98, 60 + (signal_strength * 6))
        
        # 7. CONFIDENCE CHECK (90% min)
        if confidence < V21_SETTINGS["min_confidence"]:
            result["filtered_by"] = "low_confidence"
            self.results["filters"]["confidence_filtered"] += 1
            return result
        
        # 8. R:R CHECK
        atr = indicators.get("atr", price * 0.02)
        support = indicators.get("support", price * 0.97)
        resistance = indicators.get("resistance", price * 1.03)
        
        if direction == "LONG":
            stop = max(support - (atr * 0.2), price - (atr * 2))
            target = price + (abs(price - stop) * V21_SETTINGS["min_rr_ratio"])
        else:
            stop = min(resistance + (atr * 0.2), price + (atr * 2))
            target = price - (abs(stop - price) * V21_SETTINGS["min_rr_ratio"])
        
        risk = abs(price - stop)
        reward = abs(target - price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if rr_ratio < V21_SETTINGS["min_rr_ratio"]:
            result["filtered_by"] = "poor_rr"
            self.results["filters"]["rr_filtered"] += 1
            return result
        
        # ALL FILTERS PASSED
        result["passed"] = True
        result["direction"] = direction
        result["confidence"] = confidence
        result["details"] = {
            "entry": price,
            "stop": stop,
            "target": target,
            "rr_ratio": rr_ratio,
            "confirmations": confirmations,
            "adx": adx,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
            "session": session,
        }
        
        return result
    
    def simulate_trade_outcome(self, entry: float, stop: float, target: float, direction: str, future_klines: List[Dict]) -> Dict:
        """Simulate trade outcome using future candles"""
        for i, candle in enumerate(future_klines[:50]):  # Check next 50 candles
            high = candle["high"]
            low = candle["low"]
            
            if direction == "LONG":
                # Check if stop hit
                if low <= stop:
                    return {"outcome": "LOSS", "exit_price": stop, "candles": i+1}
                # Check if target hit
                if high >= target:
                    return {"outcome": "WIN", "exit_price": target, "candles": i+1}
            else:  # SHORT
                # Check if stop hit
                if high >= stop:
                    return {"outcome": "LOSS", "exit_price": stop, "candles": i+1}
                # Check if target hit
                if low <= target:
                    return {"outcome": "WIN", "exit_price": target, "candles": i+1}
        
        # Trade still open after 50 candles, close at last price
        last_price = future_klines[-1]["close"] if future_klines else entry
        if direction == "LONG":
            outcome = "WIN" if last_price > entry else "LOSS"
        else:
            outcome = "WIN" if last_price < entry else "LOSS"
        
        return {"outcome": outcome, "exit_price": last_price, "candles": len(future_klines)}
    
    async def run_backtest(self, symbol: str, interval: str = "1h", days: int = 30) -> Dict:
        """Run backtest for a single symbol using MEXC data"""
        self.current_symbol = symbol
        logger.info(f"Fetching {days} days of {interval} data for {symbol} from MEXC...")
        
        # Convert symbol format for MEXC (e.g., BTCUSDT -> BTC/USDT)
        mexc_symbol = symbol.replace("USDT", "/USDT")
        klines = await self.fetch_klines(mexc_symbol, interval, days)
        
        if not klines:
            logger.error(f"Failed to fetch data for {symbol} from MEXC")
            return {"symbol": symbol, "error": "No data from MEXC"}
        
        logger.info(f"Got {len(klines)} candles for {symbol} from MEXC")
        
        symbol_results = {
            "symbol": symbol,
            "total_candles": len(klines),
            "signals_checked": 0,
            "old_signals": 0,  # Signals that would pass OLD rules
            "new_signals": 0,  # Signals that pass V2.1 rules
            "trades": [],
            "filter_breakdown": {
                "ema_200": 0,
                "adx": 0,
                "volume": 0,
                "session": 0,
                "rsi_counter_trend": 0,
                "confidence": 0,
                "rr": 0,
            }
        }
        
        # Scan through candles (skip first 200 for indicator warmup)
        for i in range(200, len(klines) - 50):  # Leave 50 candles for outcome simulation
            indicators = self.calculate_indicators(klines, i)
            if not indicators:
                continue
            
            symbol_results["signals_checked"] += 1
            
            # Check if this would generate a signal under OLD rules (80% conf, 4/5, 2:1 R:R)
            rsi = indicators.get("rsi", 50)
            if rsi < 30 or rsi > 70:  # Simple old rule
                symbol_results["old_signals"] += 1
            
            # Apply V2.1 filters
            result = self.apply_v21_filters(indicators, klines[i]["timestamp"])
            
            if result.get("filtered_by"):
                filter_name = result["filtered_by"]
                if "ema" in filter_name:
                    symbol_results["filter_breakdown"]["ema_200"] += 1
                elif "adx" in filter_name:
                    symbol_results["filter_breakdown"]["adx"] += 1
                elif "volume" in filter_name:
                    symbol_results["filter_breakdown"]["volume"] += 1
                elif "session" in filter_name:
                    symbol_results["filter_breakdown"]["session"] += 1
                elif "rsi" in filter_name:
                    symbol_results["filter_breakdown"]["rsi_counter_trend"] += 1
                elif "confidence" in filter_name or "confluence" in filter_name:
                    symbol_results["filter_breakdown"]["confidence"] += 1
                elif "rr" in filter_name:
                    symbol_results["filter_breakdown"]["rr"] += 1
            
            if result["passed"]:
                symbol_results["new_signals"] += 1
                
                # Simulate trade outcome
                details = result["details"]
                future_klines = klines[i+1:i+51]
                outcome = self.simulate_trade_outcome(
                    details["entry"],
                    details["stop"],
                    details["target"],
                    result["direction"],
                    future_klines
                )
                
                trade = {
                    "timestamp": klines[i]["timestamp"],
                    "direction": result["direction"],
                    "entry": details["entry"],
                    "stop": details["stop"],
                    "target": details["target"],
                    "rr_ratio": details["rr_ratio"],
                    "confidence": result["confidence"],
                    "outcome": outcome["outcome"],
                    "exit_price": outcome["exit_price"],
                    "candles_to_exit": outcome["candles"],
                    "confirmations": details["confirmations"],
                }
                symbol_results["trades"].append(trade)
        
        return symbol_results
    
    async def run_full_backtest(self, symbols: List[str] = None, interval: str = "1h", days: int = 30) -> Dict:
        """Run backtest for multiple symbols using MEXC data"""
        if symbols is None:
            symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        self.is_running = True
        self.progress = 0
        
        print("=" * 70)
        print("AEON V2.1 HIGH WIN RATE BACKTEST (MEXC Data)")
        print("=" * 70)
        print(f"Testing {len(symbols)} symbols over {days} days")
        print(f"Interval: {interval} candles")
        print("Data Source: MEXC Exchange")
        print()
        print("V2.1 Settings:")
        for key, value in V21_SETTINGS.items():
            print(f"  {key}: {value}")
        print("=" * 70)
        
        all_results = []
        total_old_signals = 0
        total_new_signals = 0
        total_wins = 0
        total_losses = 0
        all_filter_breakdown = {
            "ema_200": 0,
            "adx": 0,
            "volume": 0,
            "session": 0,
            "rsi_counter_trend": 0,
            "confidence": 0,
            "rr": 0,
        }
        all_trades = []
        
        for idx, symbol in enumerate(symbols):
            self.progress = int((idx / len(symbols)) * 100)
            
            # Convert symbol to format without slash for internal processing
            internal_symbol = symbol.replace("/", "")
            result = await self.run_backtest(internal_symbol, interval, days)
            
            if result and "error" not in result:
                all_results.append(result)
                total_old_signals += result.get("old_signals", 0)
                total_new_signals += result.get("new_signals", 0)
                
                for trade in result.get("trades", []):
                    if trade["outcome"] == "WIN":
                        total_wins += 1
                    else:
                        total_losses += 1
                    all_trades.append({**trade, "symbol": symbol})
                
                for key in all_filter_breakdown:
                    all_filter_breakdown[key] += result.get("filter_breakdown", {}).get(key, 0)
        
        self.progress = 100
        self.is_running = False
        
        # Print results
        print("\n" + "=" * 70)
        print("BACKTEST RESULTS (MEXC DATA)")
        print("=" * 70)
        
        for result in all_results:
            print(f"\n{result.get('symbol', 'Unknown')}:")
            print(f"  Candles analyzed: {result.get('total_candles', 0)}")
            print(f"  Signals checked: {result.get('signals_checked', 0)}")
            print(f"  Old rules signals: {result.get('old_signals', 0)}")
            print(f"  V2.1 signals (passed): {result.get('new_signals', 0)}")
            
            wins = sum(1 for t in result.get("trades", []) if t["outcome"] == "WIN")
            losses = sum(1 for t in result.get("trades", []) if t["outcome"] == "LOSS")
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
            
            print(f"  Simulated trades: {total}")
            print(f"  Wins: {wins}, Losses: {losses}")
            print(f"  Win Rate: {win_rate:.1f}%")
            
            print("  Filter breakdown:")
            for key, value in result.get("filter_breakdown", {}).items():
                if value > 0:
                    print(f"    - {key}: {value}")
        
        print("\n" + "=" * 70)
        print("AGGREGATE RESULTS")
        print("=" * 70)
        
        total_trades = total_wins + total_losses
        new_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        old_win_rate = 19  # Known from user
        
        print(f"\nTotal signals under OLD rules: {total_old_signals}")
        print(f"Total signals under V2.1 rules: {total_new_signals}")
        if total_old_signals > 0:
            print(f"Reduction: {((total_old_signals - total_new_signals) / total_old_signals * 100):.1f}% fewer trades")
        
        print("\nSimulated Trade Results (V2.1):")
        print(f"  Total trades: {total_trades}")
        print(f"  Wins: {total_wins}")
        print(f"  Losses: {total_losses}")
        print(f"  WIN RATE: {new_win_rate:.1f}%")
        
        print("\nComparison:")
        print(f"  OLD win rate (actual): {old_win_rate}%")
        print(f"  NEW win rate (simulated): {new_win_rate:.1f}%")
        print(f"  IMPROVEMENT: +{new_win_rate - old_win_rate:.1f}%")
        
        print("\nFilter Effectiveness (total filtered):")
        total_filtered = sum(all_filter_breakdown.values())
        for key, value in sorted(all_filter_breakdown.items(), key=lambda x: x[1], reverse=True):
            pct = (value / total_filtered * 100) if total_filtered > 0 else 0
            print(f"  {key}: {value} ({pct:.1f}%)")
        
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        
        recommendations = []
        if total_trades > 0:
            if new_win_rate >= 50:
                recommendations.append("✅ V2.1 filters are working well!")
                recommendations.append("   Win rate significantly improved from 19% baseline.")
            elif new_win_rate >= 35:
                recommendations.append("⚠️ Moderate improvement. Consider:")
                recommendations.append("   - Increasing min_confidence to 92%")
                recommendations.append("   - Requiring 6/6 confirmations")
            else:
                recommendations.append("❌ Win rate still low. Consider:")
                recommendations.append("   - More aggressive filtering")
                recommendations.append("   - Adding multi-timeframe confirmation")
        
        for rec in recommendations:
            print(rec)
        
        return {
            "data_source": "MEXC",
            "symbols": symbols,
            "interval": interval,
            "days": days,
            "settings": V21_SETTINGS,
            "old_signals": total_old_signals,
            "new_signals": total_new_signals,
            "signal_reduction_pct": round(((total_old_signals - total_new_signals) / max(1, total_old_signals)) * 100, 1),
            "total_trades": total_trades,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": round(new_win_rate, 1),
            "old_win_rate": old_win_rate,
            "improvement": round(new_win_rate - old_win_rate, 1),
            "filter_breakdown": all_filter_breakdown,
            "results_by_symbol": all_results,
            "recent_trades": all_trades[-20:],  # Last 20 trades
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def main():
    engine = BacktestV21Engine()
    results = await engine.run_full_backtest(
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        interval="1h",
        days=30
    )
    return results


# Global instance for API access
backtest_v21_engine = BacktestV21Engine()


if __name__ == "__main__":
    asyncio.run(main())
