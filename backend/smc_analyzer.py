"""
SMART MONEY CONCEPTS (SMC) TRADING MODULE
Implementation of institutional trading concepts:

1. Order Blocks (OB) - Areas where institutions placed large orders
2. Fair Value Gaps (FVG) - Imbalances in price action
3. Break of Structure (BOS) - Trend change confirmation
4. Change of Character (CHoCH) - Early reversal signal
5. Liquidity Zones - Areas where stop losses cluster
6. Premium/Discount Zones - Fibonacci retracement levels
7. Inducement - Fake breakouts to trap retail traders
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import ccxt

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2)

mexc = ccxt.mexc()


class SMCAnalyzer:
    """Smart Money Concepts Analysis Engine"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60
    
    async def get_ohlcv(self, symbol: str, timeframe: str = "4h", limit: int = 100) -> List:
        """Fetch OHLCV data"""
        cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}"
        if cache_key in self.cache:
            data, ts = self.cache[cache_key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        
        try:
            loop = asyncio.get_event_loop()
            ohlcv = await loop.run_in_executor(
                executor,
                lambda: mexc.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
            self.cache[cache_key] = (ohlcv, datetime.now())
            return ohlcv
        except Exception as e:
            logger.error(f"SMC OHLCV error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # MARKET STRUCTURE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def find_swing_points(self, ohlcv: List, lookback: int = 5) -> Dict:
        """
        Find swing highs and swing lows
        A swing high = high > lookback highs on both sides
        A swing low = low < lookback lows on both sides
        """
        if len(ohlcv) < lookback * 2 + 1:
            return {"swing_highs": [], "swing_lows": []}
        
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(ohlcv) - lookback):
            # Check swing high
            is_swing_high = True
            current_high = ohlcv[i][2]
            for j in range(i - lookback, i + lookback + 1):
                if j != i and ohlcv[j][2] >= current_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs.append({
                    "index": i,
                    "price": current_high,
                    "timestamp": ohlcv[i][0],
                    "type": "swing_high"
                })
            
            # Check swing low
            is_swing_low = True
            current_low = ohlcv[i][3]
            for j in range(i - lookback, i + lookback + 1):
                if j != i and ohlcv[j][3] <= current_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows.append({
                    "index": i,
                    "price": current_low,
                    "timestamp": ohlcv[i][0],
                    "type": "swing_low"
                })
        
        return {"swing_highs": swing_highs, "swing_lows": swing_lows}
    
    def analyze_market_structure(self, ohlcv: List) -> Dict:
        """
        Determine market structure: Bullish, Bearish, or Ranging
        Based on Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), Lower Lows (LL)
        """
        swings = self.find_swing_points(ohlcv)
        
        highs = swings["swing_highs"][-4:] if len(swings["swing_highs"]) >= 4 else swings["swing_highs"]
        lows = swings["swing_lows"][-4:] if len(swings["swing_lows"]) >= 4 else swings["swing_lows"]
        
        structure = {
            "trend": "RANGING",
            "hh_count": 0,
            "hl_count": 0,
            "lh_count": 0,
            "ll_count": 0,
            "last_swing_high": highs[-1] if highs else None,
            "last_swing_low": lows[-1] if lows else None,
            "bos_detected": False,
            "choch_detected": False
        }
        
        # Count HH, HL, LH, LL
        for i in range(1, len(highs)):
            if highs[i]["price"] > highs[i-1]["price"]:
                structure["hh_count"] += 1
            else:
                structure["lh_count"] += 1
        
        for i in range(1, len(lows)):
            if lows[i]["price"] > lows[i-1]["price"]:
                structure["hl_count"] += 1
            else:
                structure["ll_count"] += 1
        
        # Determine trend
        if structure["hh_count"] >= 2 and structure["hl_count"] >= 2:
            structure["trend"] = "BULLISH"
        elif structure["lh_count"] >= 2 and structure["ll_count"] >= 2:
            structure["trend"] = "BEARISH"
        
        # Detect Break of Structure (BOS)
        current_price = ohlcv[-1][4]
        if structure["last_swing_high"] and current_price > structure["last_swing_high"]["price"]:
            structure["bos_detected"] = True
            structure["bos_type"] = "BULLISH_BOS"
        elif structure["last_swing_low"] and current_price < structure["last_swing_low"]["price"]:
            structure["bos_detected"] = True
            structure["bos_type"] = "BEARISH_BOS"
        
        # Detect Change of Character (CHoCH)
        if structure["trend"] == "BULLISH" and structure["ll_count"] > 0:
            structure["choch_detected"] = True
            structure["choch_type"] = "BEARISH_CHOCH"
        elif structure["trend"] == "BEARISH" and structure["hh_count"] > 0:
            structure["choch_detected"] = True
            structure["choch_type"] = "BULLISH_CHOCH"
        
        return structure
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ORDER BLOCKS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def find_order_blocks(self, ohlcv: List, lookback: int = 50) -> List[Dict]:
        """
        Find Order Blocks - last candle before impulsive move
        Bullish OB: Last bearish candle before bullish impulse
        Bearish OB: Last bullish candle before bearish impulse
        """
        order_blocks = []
        
        if len(ohlcv) < lookback:
            return order_blocks
        
        for i in range(5, len(ohlcv) - 1):
            current = ohlcv[i]
            prev = ohlcv[i-1]
            
            # Check for impulsive move (candle body > 1.5x average)
            avg_body = sum(abs(c[4] - c[1]) for c in ohlcv[i-10:i]) / 10
            current_body = abs(current[4] - current[1])
            
            if current_body > avg_body * 1.5:
                # Bullish impulse
                if current[4] > current[1]:
                    # Look for last bearish candle before impulse
                    for j in range(i-1, max(i-5, 0), -1):
                        if ohlcv[j][4] < ohlcv[j][1]:  # Bearish candle
                            order_blocks.append({
                                "type": "BULLISH_OB",
                                "index": j,
                                "high": ohlcv[j][2],
                                "low": ohlcv[j][3],
                                "timestamp": ohlcv[j][0],
                                "strength": round(current_body / avg_body, 2),
                                "mitigated": False
                            })
                            break
                
                # Bearish impulse
                elif current[4] < current[1]:
                    # Look for last bullish candle before impulse
                    for j in range(i-1, max(i-5, 0), -1):
                        if ohlcv[j][4] > ohlcv[j][1]:  # Bullish candle
                            order_blocks.append({
                                "type": "BEARISH_OB",
                                "index": j,
                                "high": ohlcv[j][2],
                                "low": ohlcv[j][3],
                                "timestamp": ohlcv[j][0],
                                "strength": round(current_body / avg_body, 2),
                                "mitigated": False
                            })
                            break
        
        # Check if order blocks have been mitigated (price returned to the zone)
        current_price = ohlcv[-1][4]
        for ob in order_blocks:
            if ob["type"] == "BULLISH_OB":
                if current_price >= ob["low"] and current_price <= ob["high"]:
                    ob["mitigated"] = True
            else:
                if current_price >= ob["low"] and current_price <= ob["high"]:
                    ob["mitigated"] = True
        
        # Return most recent unmitigated order blocks
        return [ob for ob in order_blocks if not ob["mitigated"]][-5:]
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # FAIR VALUE GAPS (FVG)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def find_fair_value_gaps(self, ohlcv: List) -> List[Dict]:
        """
        Find Fair Value Gaps - price imbalances
        Bullish FVG: Gap between candle 1 high and candle 3 low
        Bearish FVG: Gap between candle 1 low and candle 3 high
        """
        fvgs = []
        
        if len(ohlcv) < 10:
            return fvgs
        
        for i in range(2, len(ohlcv)):
            candle_1 = ohlcv[i-2]
            candle_3 = ohlcv[i]
            
            # Bullish FVG
            if candle_3[3] > candle_1[2]:  # Candle 3 low > Candle 1 high
                fvgs.append({
                    "type": "BULLISH_FVG",
                    "index": i-1,
                    "upper": candle_3[3],
                    "lower": candle_1[2],
                    "size_pct": round(((candle_3[3] - candle_1[2]) / candle_1[2]) * 100, 3),
                    "timestamp": ohlcv[i-1][0],
                    "filled": False
                })
            
            # Bearish FVG
            elif candle_3[2] < candle_1[3]:  # Candle 3 high < Candle 1 low
                fvgs.append({
                    "type": "BEARISH_FVG",
                    "index": i-1,
                    "upper": candle_1[3],
                    "lower": candle_3[2],
                    "size_pct": round(((candle_1[3] - candle_3[2]) / candle_3[2]) * 100, 3),
                    "timestamp": ohlcv[i-1][0],
                    "filled": False
                })
        
        # Check if FVGs have been filled
        current_price = ohlcv[-1][4]
        for fvg in fvgs:
            if fvg["type"] == "BULLISH_FVG":
                # FVG filled if price went back below the gap
                for c in ohlcv[fvg["index"]+1:]:
                    if c[3] <= fvg["lower"]:
                        fvg["filled"] = True
                        break
            else:
                for c in ohlcv[fvg["index"]+1:]:
                    if c[2] >= fvg["upper"]:
                        fvg["filled"] = True
                        break
        
        # Return unfilled FVGs
        return [fvg for fvg in fvgs if not fvg["filled"]][-5:]
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # LIQUIDITY ZONES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def find_liquidity_zones(self, ohlcv: List) -> Dict:
        """
        Find liquidity zones where stop losses likely cluster:
        - Above swing highs (buy-side liquidity)
        - Below swing lows (sell-side liquidity)
        - Equal highs/lows (trapped traders)
        """
        swings = self.find_swing_points(ohlcv)
        
        buy_side_liquidity = []
        sell_side_liquidity = []
        
        # Buy-side liquidity above swing highs
        for sh in swings["swing_highs"]:
            buy_side_liquidity.append({
                "type": "BUY_SIDE",
                "price": sh["price"],
                "timestamp": sh["timestamp"],
                "description": "Stop losses above swing high"
            })
        
        # Sell-side liquidity below swing lows
        for sl in swings["swing_lows"]:
            sell_side_liquidity.append({
                "type": "SELL_SIDE",
                "price": sl["price"],
                "timestamp": sl["timestamp"],
                "description": "Stop losses below swing low"
            })
        
        # Find equal highs/lows (liquidity pools)
        equal_highs = []
        equal_lows = []
        tolerance = 0.002  # 0.2% tolerance
        
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        
        for i in range(len(highs)):
            for j in range(i+1, min(i+20, len(highs))):
                if abs(highs[i] - highs[j]) / highs[i] < tolerance:
                    equal_highs.append({
                        "price": (highs[i] + highs[j]) / 2,
                        "type": "EQUAL_HIGHS",
                        "description": "Liquidity pool - likely to be swept"
                    })
                    break
        
        for i in range(len(lows)):
            for j in range(i+1, min(i+20, len(lows))):
                if abs(lows[i] - lows[j]) / lows[i] < tolerance:
                    equal_lows.append({
                        "price": (lows[i] + lows[j]) / 2,
                        "type": "EQUAL_LOWS",
                        "description": "Liquidity pool - likely to be swept"
                    })
                    break
        
        current_price = ohlcv[-1][4]
        
        # Find nearest liquidity
        nearest_buy_side = None
        nearest_sell_side = None
        
        for bl in sorted(buy_side_liquidity, key=lambda x: x["price"]):
            if bl["price"] > current_price:
                nearest_buy_side = bl
                break
        
        for sl in sorted(sell_side_liquidity, key=lambda x: x["price"], reverse=True):
            if sl["price"] < current_price:
                nearest_sell_side = sl
                break
        
        return {
            "buy_side_liquidity": buy_side_liquidity[-5:],
            "sell_side_liquidity": sell_side_liquidity[-5:],
            "equal_highs": equal_highs[-3:],
            "equal_lows": equal_lows[-3:],
            "nearest_buy_side": nearest_buy_side,
            "nearest_sell_side": nearest_sell_side
        }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PREMIUM/DISCOUNT ZONES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def calculate_premium_discount(self, ohlcv: List, lookback: int = 50) -> Dict:
        """
        Calculate premium and discount zones based on swing range
        - Premium Zone: Above 50% of range (sell area)
        - Discount Zone: Below 50% of range (buy area)
        - Equilibrium: 50% level
        """
        if len(ohlcv) < lookback:
            return {}
        
        recent = ohlcv[-lookback:]
        
        swing_high = max(c[2] for c in recent)
        swing_low = min(c[3] for c in recent)
        
        range_size = swing_high - swing_low
        equilibrium = swing_low + (range_size * 0.5)
        
        current_price = ohlcv[-1][4]
        
        # Calculate Fibonacci levels
        fib_levels = {
            "0.0": swing_low,
            "0.236": swing_low + (range_size * 0.236),
            "0.382": swing_low + (range_size * 0.382),
            "0.5": equilibrium,
            "0.618": swing_low + (range_size * 0.618),
            "0.786": swing_low + (range_size * 0.786),
            "1.0": swing_high
        }
        
        # Determine zone
        position_pct = ((current_price - swing_low) / range_size) * 100 if range_size > 0 else 50
        
        if position_pct > 70:
            zone = "EXTREME_PREMIUM"
            bias = "BEARISH"
        elif position_pct > 50:
            zone = "PREMIUM"
            bias = "BEARISH"
        elif position_pct < 30:
            zone = "EXTREME_DISCOUNT"
            bias = "BULLISH"
        elif position_pct < 50:
            zone = "DISCOUNT"
            bias = "BULLISH"
        else:
            zone = "EQUILIBRIUM"
            bias = "NEUTRAL"
        
        return {
            "swing_high": round(swing_high, 2),
            "swing_low": round(swing_low, 2),
            "equilibrium": round(equilibrium, 2),
            "current_price": round(current_price, 2),
            "position_pct": round(position_pct, 1),
            "zone": zone,
            "bias": bias,
            "fib_levels": {k: round(v, 2) for k, v in fib_levels.items()}
        }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # FULL SMC ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def full_analysis(self, symbol: str, timeframe: str = "4h") -> Dict:
        """Run complete SMC analysis"""
        ohlcv = await self.get_ohlcv(symbol, timeframe, 100)
        
        if len(ohlcv) < 20:
            return {"error": "Insufficient data for SMC analysis"}
        
        current_price = ohlcv[-1][4]
        
        # Run all analyses
        structure = self.analyze_market_structure(ohlcv)
        order_blocks = self.find_order_blocks(ohlcv)
        fvgs = self.find_fair_value_gaps(ohlcv)
        liquidity = self.find_liquidity_zones(ohlcv)
        premium_discount = self.calculate_premium_discount(ohlcv)
        
        # Determine trading bias
        bullish_factors = 0
        bearish_factors = 0
        
        if structure["trend"] == "BULLISH":
            bullish_factors += 2
        elif structure["trend"] == "BEARISH":
            bearish_factors += 2
        
        if structure["bos_detected"]:
            if "BULLISH" in structure.get("bos_type", ""):
                bullish_factors += 2
            else:
                bearish_factors += 2
        
        if premium_discount.get("bias") == "BULLISH":
            bullish_factors += 1
        elif premium_discount.get("bias") == "BEARISH":
            bearish_factors += 1
        
        # Check for active bullish/bearish OBs
        bullish_obs = [ob for ob in order_blocks if ob["type"] == "BULLISH_OB"]
        bearish_obs = [ob for ob in order_blocks if ob["type"] == "BEARISH_OB"]
        
        if bullish_obs:
            bullish_factors += 1
        if bearish_obs:
            bearish_factors += 1
        
        # Overall signal
        if bullish_factors >= 4:
            overall_signal = "STRONG_BUY"
            confidence = 80
        elif bullish_factors > bearish_factors:
            overall_signal = "BUY"
            confidence = 65
        elif bearish_factors >= 4:
            overall_signal = "STRONG_SELL"
            confidence = 80
        elif bearish_factors > bullish_factors:
            overall_signal = "SELL"
            confidence = 65
        else:
            overall_signal = "NEUTRAL"
            confidence = 50
        
        # Find entry points
        entry_points = []
        
        # Entry at bullish order blocks in discount zone
        if premium_discount.get("zone") in ["DISCOUNT", "EXTREME_DISCOUNT"]:
            for ob in bullish_obs:
                entry_points.append({
                    "type": "BULLISH_OB_ENTRY",
                    "zone": f"${ob['low']:,.2f} - ${ob['high']:,.2f}",
                    "strength": ob["strength"]
                })
        
        # Entry at bearish order blocks in premium zone
        if premium_discount.get("zone") in ["PREMIUM", "EXTREME_PREMIUM"]:
            for ob in bearish_obs:
                entry_points.append({
                    "type": "BEARISH_OB_ENTRY",
                    "zone": f"${ob['low']:,.2f} - ${ob['high']:,.2f}",
                    "strength": ob["strength"]
                })
        
        # Entry at FVGs
        for fvg in fvgs:
            entry_points.append({
                "type": f"{fvg['type']}_ENTRY",
                "zone": f"${fvg['lower']:,.2f} - ${fvg['upper']:,.2f}",
                "size": f"{fvg['size_pct']}%"
            })
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),
            "overall_signal": overall_signal,
            "confidence": confidence,
            "bullish_factors": bullish_factors,
            "bearish_factors": bearish_factors,
            "market_structure": {
                "trend": structure["trend"],
                "hh_hl": f"HH:{structure['hh_count']} HL:{structure['hl_count']}",
                "lh_ll": f"LH:{structure['lh_count']} LL:{structure['ll_count']}",
                "bos": structure.get("bos_type") if structure["bos_detected"] else None,
                "choch": structure.get("choch_type") if structure["choch_detected"] else None
            },
            "premium_discount": {
                "zone": premium_discount.get("zone"),
                "position": f"{premium_discount.get('position_pct', 50)}%",
                "equilibrium": premium_discount.get("equilibrium"),
                "bias": premium_discount.get("bias")
            },
            "order_blocks": {
                "bullish": len(bullish_obs),
                "bearish": len(bearish_obs),
                "nearest_bullish": bullish_obs[0] if bullish_obs else None,
                "nearest_bearish": bearish_obs[0] if bearish_obs else None
            },
            "fvgs": {
                "bullish": len([f for f in fvgs if "BULLISH" in f["type"]]),
                "bearish": len([f for f in fvgs if "BEARISH" in f["type"]]),
                "list": fvgs[:3]
            },
            "liquidity": {
                "nearest_buy_side": liquidity.get("nearest_buy_side"),
                "nearest_sell_side": liquidity.get("nearest_sell_side")
            },
            "entry_points": entry_points[:5],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
smc_analyzer = SMCAnalyzer()
