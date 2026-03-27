"""
SMC + Strategy Confluence Analyzer
Combines Smart Money Concepts with Technical Strategies for higher confidence signals
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ConfluenceAnalyzer:
    """
    Combines SMC analysis with strategy signals to find high-probability setups
    
    Confluence factors:
    1. SMC Market Structure alignment
    2. Price in optimal zone (discount for longs, premium for shorts)
    3. Order block / FVG entry zone
    4. Technical strategy signal
    5. Liquidity target
    """
    
    def __init__(self, smc_analyzer, strategy_engine):
        self.smc = smc_analyzer
        self.strategy = strategy_engine
    
    async def analyze_confluence(self, symbol: str, timeframe: str = "4h") -> Dict:
        """
        Run confluence analysis combining SMC and strategies
        Returns high-probability setups with multiple confirmations
        """
        # Run both analyses in parallel
        smc_task = self.smc.full_analysis(symbol, timeframe)
        strategy_task = self.strategy.scan_all_strategies(symbol, timeframe)
        
        smc_result, strategy_result = await asyncio.gather(smc_task, strategy_task)
        
        if "error" in smc_result or "error" in strategy_result:
            return {
                "error": smc_result.get("error") or strategy_result.get("error"),
                "symbol": symbol
            }
        
        # Calculate confluence score
        confluence = self._calculate_confluence(smc_result, strategy_result)
        
        # Determine final signal
        final_signal = self._determine_signal(confluence, smc_result, strategy_result)
        
        # Generate trade setup
        trade_setup = self._generate_trade_setup(confluence, smc_result, strategy_result, final_signal)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": smc_result.get("current_price", 0),
            "final_signal": final_signal["signal"],
            "confidence": final_signal["confidence"],
            "confluence_score": confluence["total_score"],
            "confluence_factors": confluence["factors"],
            "smc_summary": {
                "trend": smc_result.get("market_structure", {}).get("trend"),
                "zone": smc_result.get("premium_discount", {}).get("zone"),
                "signal": smc_result.get("overall_signal"),
                "order_blocks": smc_result.get("order_blocks", {}),
                "fvgs": smc_result.get("fvgs", {})
            },
            "strategy_summary": {
                "overall": strategy_result.get("overall_signal"),
                "buy_signals": strategy_result.get("buy_signals", 0),
                "sell_signals": strategy_result.get("sell_signals", 0),
                "best_strategy": strategy_result.get("best_strategy", {}).get("strategy") if strategy_result.get("best_strategy") else None
            },
            "trade_setup": trade_setup,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _calculate_confluence(self, smc: Dict, strategy: Dict) -> Dict:
        """Calculate confluence score from multiple factors"""
        factors = []
        total_score = 0
        max_score = 0
        
        # Factor 1: SMC Trend Alignment (0-20 points)
        max_score += 20
        smc_trend = smc.get("market_structure", {}).get("trend", "RANGING")
        smc_signal = smc.get("overall_signal", "NEUTRAL")
        
        if "BUY" in smc_signal:
            if smc_trend == "BULLISH":
                total_score += 20
                factors.append({"factor": "SMC Trend", "status": "ALIGNED", "score": 20, "detail": "Bullish structure + Buy signal"})
            else:
                total_score += 10
                factors.append({"factor": "SMC Trend", "status": "PARTIAL", "score": 10, "detail": f"Buy signal but {smc_trend} structure"})
        elif "SELL" in smc_signal:
            if smc_trend == "BEARISH":
                total_score += 20
                factors.append({"factor": "SMC Trend", "status": "ALIGNED", "score": 20, "detail": "Bearish structure + Sell signal"})
            else:
                total_score += 10
                factors.append({"factor": "SMC Trend", "status": "PARTIAL", "score": 10, "detail": f"Sell signal but {smc_trend} structure"})
        else:
            factors.append({"factor": "SMC Trend", "status": "NEUTRAL", "score": 0, "detail": "No clear SMC direction"})
        
        # Factor 2: Optimal Zone (0-20 points)
        max_score += 20
        zone = smc.get("premium_discount", {}).get("zone", "EQUILIBRIUM")
        
        if "BUY" in smc_signal and "DISCOUNT" in zone:
            score = 20 if "EXTREME" in zone else 15
            total_score += score
            factors.append({"factor": "Price Zone", "status": "OPTIMAL", "score": score, "detail": f"Buy in {zone}"})
        elif "SELL" in smc_signal and "PREMIUM" in zone:
            score = 20 if "EXTREME" in zone else 15
            total_score += score
            factors.append({"factor": "Price Zone", "status": "OPTIMAL", "score": score, "detail": f"Sell in {zone}"})
        elif zone == "EQUILIBRIUM":
            total_score += 5
            factors.append({"factor": "Price Zone", "status": "NEUTRAL", "score": 5, "detail": "Price at equilibrium"})
        else:
            factors.append({"factor": "Price Zone", "status": "SUBOPTIMAL", "score": 0, "detail": f"Signal opposite to zone ({zone})"})
        
        # Factor 3: Order Block Entry (0-15 points)
        max_score += 15
        obs = smc.get("order_blocks", {})
        bullish_obs = obs.get("bullish", 0)
        bearish_obs = obs.get("bearish", 0)
        
        if "BUY" in smc_signal and bullish_obs > 0:
            total_score += 15
            factors.append({"factor": "Order Blocks", "status": "PRESENT", "score": 15, "detail": f"{bullish_obs} bullish OBs available"})
        elif "SELL" in smc_signal and bearish_obs > 0:
            total_score += 15
            factors.append({"factor": "Order Blocks", "status": "PRESENT", "score": 15, "detail": f"{bearish_obs} bearish OBs available"})
        elif bullish_obs > 0 or bearish_obs > 0:
            total_score += 5
            factors.append({"factor": "Order Blocks", "status": "PARTIAL", "score": 5, "detail": "OBs present but opposite direction"})
        else:
            factors.append({"factor": "Order Blocks", "status": "ABSENT", "score": 0, "detail": "No active order blocks"})
        
        # Factor 4: Fair Value Gap (0-15 points)
        max_score += 15
        fvgs = smc.get("fvgs", {})
        bullish_fvgs = fvgs.get("bullish", 0)
        bearish_fvgs = fvgs.get("bearish", 0)
        
        if "BUY" in smc_signal and bullish_fvgs > 0:
            total_score += 15
            factors.append({"factor": "Fair Value Gaps", "status": "PRESENT", "score": 15, "detail": f"{bullish_fvgs} bullish FVGs"})
        elif "SELL" in smc_signal and bearish_fvgs > 0:
            total_score += 15
            factors.append({"factor": "Fair Value Gaps", "status": "PRESENT", "score": 15, "detail": f"{bearish_fvgs} bearish FVGs"})
        elif bullish_fvgs > 0 or bearish_fvgs > 0:
            total_score += 5
            factors.append({"factor": "Fair Value Gaps", "status": "PARTIAL", "score": 5, "detail": "FVGs present but opposite"})
        else:
            factors.append({"factor": "Fair Value Gaps", "status": "ABSENT", "score": 0, "detail": "No unfilled FVGs"})
        
        # Factor 5: Strategy Alignment (0-20 points)
        max_score += 20
        strategy_signal = strategy.get("overall_signal", "NEUTRAL")
        strategy_buys = strategy.get("buy_signals", 0)
        strategy_sells = strategy.get("sell_signals", 0)
        
        if "BUY" in smc_signal and "BUY" in strategy_signal:
            score = 20 if "STRONG" in strategy_signal else 15
            total_score += score
            factors.append({"factor": "Strategy Signals", "status": "ALIGNED", "score": score, "detail": f"{strategy_buys} strategies confirm buy"})
        elif "SELL" in smc_signal and "SELL" in strategy_signal:
            score = 20 if "STRONG" in strategy_signal else 15
            total_score += score
            factors.append({"factor": "Strategy Signals", "status": "ALIGNED", "score": score, "detail": f"{strategy_sells} strategies confirm sell"})
        elif strategy_signal == "NEUTRAL":
            total_score += 5
            factors.append({"factor": "Strategy Signals", "status": "NEUTRAL", "score": 5, "detail": "No strategy consensus"})
        else:
            factors.append({"factor": "Strategy Signals", "status": "CONFLICTING", "score": 0, "detail": f"SMC and strategies disagree"})
        
        # Factor 6: Liquidity Target (0-10 points)
        max_score += 10
        liquidity = smc.get("liquidity", {})
        nearest_buy = liquidity.get("nearest_buy_side")
        nearest_sell = liquidity.get("nearest_sell_side")
        
        if "BUY" in smc_signal and nearest_buy:
            total_score += 10
            factors.append({"factor": "Liquidity Target", "status": "PRESENT", "score": 10, "detail": f"Buy-side liquidity at ${nearest_buy.get('price', 0):,.0f}"})
        elif "SELL" in smc_signal and nearest_sell:
            total_score += 10
            factors.append({"factor": "Liquidity Target", "status": "PRESENT", "score": 10, "detail": f"Sell-side liquidity at ${nearest_sell.get('price', 0):,.0f}"})
        else:
            factors.append({"factor": "Liquidity Target", "status": "UNCLEAR", "score": 0, "detail": "No clear liquidity target"})
        
        return {
            "total_score": total_score,
            "max_score": max_score,
            "percentage": round((total_score / max_score) * 100, 1) if max_score > 0 else 0,
            "factors": factors
        }
    
    def _determine_signal(self, confluence: Dict, smc: Dict, strategy: Dict) -> Dict:
        """Determine final signal based on confluence"""
        score_pct = confluence.get("percentage", 0)
        smc_signal = smc.get("overall_signal", "NEUTRAL")
        
        # High confluence = Strong signal
        if score_pct >= 75:
            if "BUY" in smc_signal:
                return {"signal": "STRONG_BUY", "confidence": min(95, 70 + int(score_pct * 0.3))}
            elif "SELL" in smc_signal:
                return {"signal": "STRONG_SELL", "confidence": min(95, 70 + int(score_pct * 0.3))}
        
        # Medium confluence = Normal signal
        elif score_pct >= 50:
            if "BUY" in smc_signal:
                return {"signal": "BUY", "confidence": 60 + int(score_pct * 0.2)}
            elif "SELL" in smc_signal:
                return {"signal": "SELL", "confidence": 60 + int(score_pct * 0.2)}
        
        # Low confluence = Weak/No signal
        elif score_pct >= 30:
            if "BUY" in smc_signal:
                return {"signal": "WEAK_BUY", "confidence": 50}
            elif "SELL" in smc_signal:
                return {"signal": "WEAK_SELL", "confidence": 50}
        
        return {"signal": "NEUTRAL", "confidence": 40}
    
    def _generate_trade_setup(self, confluence: Dict, smc: Dict, strategy: Dict, final_signal: Dict) -> Dict:
        """Generate actionable trade setup"""
        if final_signal["signal"] == "NEUTRAL":
            return {"action": "WAIT", "reason": "Low confluence - no clear setup"}
        
        price = smc.get("current_price", 0)
        pd = smc.get("premium_discount", {})
        obs = smc.get("order_blocks", {})
        liquidity = smc.get("liquidity", {})
        best_strat = strategy.get("best_strategy", {})
        
        is_long = "BUY" in final_signal["signal"]
        
        # Determine entry zone
        entry_zone = None
        if is_long:
            nearest_ob = obs.get("nearest_bullish")
            if nearest_ob:
                entry_zone = f"${nearest_ob.get('low', 0):,.2f} - ${nearest_ob.get('high', 0):,.2f}"
        else:
            nearest_ob = obs.get("nearest_bearish")
            if nearest_ob:
                entry_zone = f"${nearest_ob.get('low', 0):,.2f} - ${nearest_ob.get('high', 0):,.2f}"
        
        # Use strategy's entry if no OB
        if not entry_zone and best_strat:
            entry_zone = f"${best_strat.get('entry', price):,.2f}"
        
        # Determine stop loss (below/above OB or use strategy's stop)
        stop_loss = best_strat.get("stop", price * (0.97 if is_long else 1.03)) if best_strat else price * (0.97 if is_long else 1.03)
        
        # Determine target (liquidity zone or strategy target)
        target = None
        if is_long and liquidity.get("nearest_buy_side"):
            target = liquidity["nearest_buy_side"].get("price", price * 1.05)
        elif not is_long and liquidity.get("nearest_sell_side"):
            target = liquidity["nearest_sell_side"].get("price", price * 0.95)
        elif best_strat:
            target = best_strat.get("target", price * (1.05 if is_long else 0.95))
        else:
            target = price * (1.05 if is_long else 0.95)
        
        # Calculate risk/reward
        risk = abs(price - stop_loss)
        reward = abs(target - price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        return {
            "action": "LONG" if is_long else "SHORT",
            "entry_zone": entry_zone or f"${price:,.2f}",
            "stop_loss": f"${stop_loss:,.2f}",
            "target": f"${target:,.2f}",
            "risk_reward": f"1:{rr_ratio:.1f}",
            "confluence_score": f"{confluence.get('percentage', 0)}%",
            "aligned_factors": len([f for f in confluence.get("factors", []) if f.get("status") in ["ALIGNED", "OPTIMAL", "PRESENT"]]),
            "total_factors": len(confluence.get("factors", [])),
            "reason": f"{len([f for f in confluence.get('factors', []) if f.get('score', 0) > 0])}/6 factors aligned"
        }


# Factory function
def create_confluence_analyzer(smc_analyzer, strategy_engine):
    return ConfluenceAnalyzer(smc_analyzer, strategy_engine)
