"""
AEON MULTI-TIMEFRAME ANALYSIS
Confluence detection across 1h, 4h, and daily timeframes
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from market_intelligence import market_intel

logger = logging.getLogger(__name__)


class MultiTimeframeAnalysis:
    """
    Analyzes multiple timeframes for confluence:
    - 1h: Short-term momentum
    - 4h: Medium-term trend
    - 1d: Major trend direction
    
    Confluence = all timeframes agree = stronger signal
    """
    
    def __init__(self):
        self.timeframes = ["1h", "4h", "1d"]
    
    async def analyze_timeframe(self, symbol: str, timeframe: str) -> Dict:
        """Analyze a single timeframe"""
        try:
            ta = await market_intel.get_technical_analysis(symbol, timeframe)
            
            if "error" in ta:
                return {"timeframe": timeframe, "error": ta["error"]}
            
            indicators = ta.get("indicators", {})
            price = ta.get("price", 0)
            
            # Score the timeframe
            score = 0
            signals = []
            
            # RSI
            rsi = indicators.get("rsi", 50)
            if rsi < 30:
                score += 2
                signals.append(f"RSI oversold ({rsi:.0f})")
            elif rsi < 40:
                score += 1
                signals.append(f"RSI low ({rsi:.0f})")
            elif rsi > 70:
                score -= 2
                signals.append(f"RSI overbought ({rsi:.0f})")
            elif rsi > 60:
                score -= 1
                signals.append(f"RSI high ({rsi:.0f})")
            
            # MACD
            macd = indicators.get("macd", 0)
            macd_signal = indicators.get("macd_signal", 0)
            macd_hist = indicators.get("macd_histogram", 0)
            
            if macd > macd_signal and macd_hist > 0:
                score += 1.5
                signals.append("MACD bullish")
            elif macd < macd_signal and macd_hist < 0:
                score -= 1.5
                signals.append("MACD bearish")
            
            # EMA Stack
            ema_9 = indicators.get("ema_9", 0)
            ema_21 = indicators.get("ema_21", 0)
            ema_50 = indicators.get("ema_50", 0)
            
            if ema_9 and ema_21 and ema_50:
                if ema_9 > ema_21 > ema_50:
                    score += 1.5
                    signals.append("Bullish EMA stack")
                elif ema_9 < ema_21 < ema_50:
                    score -= 1.5
                    signals.append("Bearish EMA stack")
            
            # Price vs EMAs
            if price and ema_21:
                if price > ema_21 * 1.02:
                    score += 0.5
                    signals.append("Price above EMA21")
                elif price < ema_21 * 0.98:
                    score -= 0.5
                    signals.append("Price below EMA21")
            
            # Bollinger Bands
            bb_lower = indicators.get("bb_lower", 0)
            bb_upper = indicators.get("bb_upper", 0)
            
            if price and bb_lower and price < bb_lower:
                score += 1
                signals.append("Below BB lower")
            elif price and bb_upper and price > bb_upper:
                score -= 1
                signals.append("Above BB upper")
            
            # Determine bias
            if score >= 2:
                bias = "BULLISH"
                emoji = "🟢"
            elif score <= -2:
                bias = "BEARISH"
                emoji = "🔴"
            elif score >= 0.5:
                bias = "LEAN BULLISH"
                emoji = "🟡"
            elif score <= -0.5:
                bias = "LEAN BEARISH"
                emoji = "🟠"
            else:
                bias = "NEUTRAL"
                emoji = "⚪"
            
            return {
                "timeframe": timeframe,
                "price": price,
                "bias": bias,
                "emoji": emoji,
                "score": round(score, 2),
                "signals": signals,
                "indicators": {
                    "rsi": round(rsi, 1),
                    "macd": round(macd, 4) if macd else None,
                    "ema_9": round(ema_9, 2) if ema_9 else None,
                    "ema_21": round(ema_21, 2) if ema_21 else None,
                    "ema_50": round(ema_50, 2) if ema_50 else None,
                }
            }
            
        except Exception as e:
            logger.error(f"Timeframe analysis error: {e}")
            return {"timeframe": timeframe, "error": str(e)}
    
    async def get_multi_timeframe_analysis(self, symbol: str) -> Dict:
        """
        Analyze all timeframes and determine confluence
        """
        # Analyze all timeframes concurrently
        tasks = [self.analyze_timeframe(symbol, tf) for tf in self.timeframes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analyses = {}
        scores = []
        biases = []
        
        for r in results:
            if isinstance(r, dict) and "error" not in r:
                tf = r["timeframe"]
                analyses[tf] = r
                scores.append(r["score"])
                biases.append(r["bias"])
        
        # Calculate confluence
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Check alignment
        bullish_count = sum(1 for b in biases if "BULLISH" in b)
        bearish_count = sum(1 for b in biases if "BEARISH" in b)
        
        if bullish_count == len(biases) and len(biases) == 3:
            confluence = "STRONG BULLISH"
            confluence_emoji = "🟢🟢🟢"
            confidence = 85
        elif bearish_count == len(biases) and len(biases) == 3:
            confluence = "STRONG BEARISH"
            confluence_emoji = "🔴🔴🔴"
            confidence = 85
        elif bullish_count >= 2:
            confluence = "BULLISH CONFLUENCE"
            confluence_emoji = "🟢🟢"
            confidence = 70
        elif bearish_count >= 2:
            confluence = "BEARISH CONFLUENCE"
            confluence_emoji = "🔴🔴"
            confidence = 70
        else:
            confluence = "MIXED / NO CONFLUENCE"
            confluence_emoji = "⚪"
            confidence = 40
        
        # Generate recommendation
        if confidence >= 70:
            if "BULLISH" in confluence:
                recommendation = "Consider LONG positions with tight stops"
            else:
                recommendation = "Consider SHORT positions with tight stops"
        else:
            recommendation = "Wait for clearer confluence before entering"
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confluence": confluence,
            "confluence_emoji": confluence_emoji,
            "confidence": confidence,
            "average_score": round(avg_score, 2),
            "recommendation": recommendation,
            "timeframes": analyses,
            "summary": self._generate_summary(analyses)
        }
    
    def _generate_summary(self, analyses: Dict) -> str:
        """Generate human-readable summary"""
        lines = []
        
        for tf in ["1h", "4h", "1d"]:
            if tf in analyses:
                a = analyses[tf]
                lines.append(f"{tf}: {a['emoji']} {a['bias']} (score: {a['score']:+.1f})")
        
        return "\n".join(lines)
    
    async def get_trend_alignment(self, symbol: str) -> Dict:
        """
        Quick check if lower timeframes align with higher
        """
        mtf = await self.get_multi_timeframe_analysis(symbol)
        
        analyses = mtf.get("timeframes", {})
        
        # Check if 1h aligns with 4h and daily
        h1 = analyses.get("1h", {})
        h4 = analyses.get("4h", {})
        d1 = analyses.get("1d", {})
        
        alignment = {
            "1h_vs_4h": "ALIGNED" if h1.get("bias") == h4.get("bias") else "CONFLICT",
            "1h_vs_daily": "ALIGNED" if h1.get("bias") == d1.get("bias") else "CONFLICT",
            "4h_vs_daily": "ALIGNED" if h4.get("bias") == d1.get("bias") else "CONFLICT",
        }
        
        aligned_count = sum(1 for v in alignment.values() if v == "ALIGNED")
        
        if aligned_count == 3:
            status = "FULL ALIGNMENT"
            trade_quality = "HIGH"
        elif aligned_count == 2:
            status = "PARTIAL ALIGNMENT"
            trade_quality = "MEDIUM"
        else:
            status = "NO ALIGNMENT"
            trade_quality = "LOW"
        
        return {
            "symbol": symbol,
            "status": status,
            "trade_quality": trade_quality,
            "alignment_details": alignment,
            "daily_bias": d1.get("bias", "UNKNOWN"),
            "recommendation": f"Daily trend is {d1.get('bias', 'UNKNOWN')}. Trade {'WITH' if h1.get('bias') == d1.get('bias') else 'AGAINST'} the trend."
        }


# Global instance
mtf_analysis = MultiTimeframeAnalysis()
