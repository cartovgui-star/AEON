"""
AEON CONVERSATION INTELLIGENCE
Smart context detection and conversation routing
"""
import re
from typing import Dict, Tuple, List
from datetime import datetime, timezone


class ConversationClassifier:
    """
    Intelligent conversation classifier that determines:
    1. Is this crypto/trading related or casual chat?
    2. What's the user's intent?
    3. Should we pull market data or just chat?
    """
    
    def __init__(self):
        # Strong trading signals - these almost always mean crypto talk
        self.strong_trading_signals = {
            # Coins
            'btc', 'bitcoin', 'eth', 'ethereum', 'sol', 'solana', 'doge', 
            'xrp', 'ripple', 'bnb', 'avax', 'avalanche', 'ada', 'cardano',
            'matic', 'polygon', 'link', 'chainlink', 'dot', 'polkadot',
            'shib', 'pepe', 'floki', 'bonk', 'wif', 'sui', 'apt', 'arb',
            
            # Trading terms
            'long position', 'short position', 'take profit', 'stop loss',
            'leverage', 'margin', 'liquidation', 'entry', 'exit',
            'support', 'resistance', 'breakout', 'breakdown',
            'bullish', 'bearish', 'pump', 'dump', 'moon', 'rekt',
            'funding rate', 'open interest', 'volume', 'market cap',
            
            # Technical analysis
            'rsi', 'macd', 'ema', 'sma', 'bollinger', 'fibonacci',
            'divergence', 'orderbook', 'order block', 'fvg', 'liquidity',
            'trend', 'consolidation', 'accumulation', 'distribution',
            
            # Actions
            'buy', 'sell', 'trade', 'scalp', 'swing', 'hodl',
            'dca', 'dollar cost', 'take profit', 'cut loss'
        }
        
        # Medium trading signals - context dependent
        self.medium_trading_signals = {
            'price', 'chart', 'market', 'analysis', 'technical',
            'position', 'target', 'level', 'zone', 'candle',
            'green', 'red', 'up', 'down', 'high', 'low',
            'fear', 'greed', 'sentiment', 'whale', 'signal'
        }
        
        # Casual chat signals
        self.casual_signals = {
            'how are you', 'what\'s up', 'sup', 'hey', 'hello', 'hi',
            'good morning', 'good night', 'thanks', 'thank you',
            'how was your', 'what do you think about', 'tell me about',
            'feeling', 'stressed', 'happy', 'sad', 'tired', 'bored',
            'life', 'work', 'job', 'family', 'friend', 'relationship',
            'advice', 'help me', 'what should i', 'confused',
            'motivation', 'inspire', 'quote', 'wisdom',
            'funny', 'joke', 'laugh', 'story', 'random',
            'weather', 'food', 'movie', 'music', 'game',
            'sleep', 'dream', 'goal', 'plan', 'future'
        }
        
        # Question patterns that indicate different intents
        self.trading_questions = [
            r'what.*(price|doing|think about|analysis).*(btc|eth|sol|crypto|market)',
            r'should i.*(buy|sell|long|short|trade)',
            r'is.*(btc|eth|sol|market).*(bullish|bearish|good|bad)',
            r'when.*(buy|sell|entry|exit)',
            r'where.*(support|resistance|target|stop)',
            r'how.*(trade|position|leverage)',
            r'(btc|eth|sol|crypto).*(pump|dump|moon|crash)',
        ]
        
        self.casual_questions = [
            r'how are you',
            r'what.*you.*(doing|up to|think)',
            r'tell me.*(about yourself|story|joke)',
            r'can you.*(help|talk|chat)',
            r'what.*your.*(opinion|thought|view)',
            r'how.*i.*(feel|improve|better|fix)',
        ]
    
    def classify(self, text: str, recent_context: str = None) -> Dict:
        """
        Classify the message and return routing info
        
        Returns:
            {
                "type": "trading" | "casual" | "mixed",
                "confidence": 0-100,
                "intent": "analysis" | "question" | "chat" | "command",
                "detected_coins": ["BTC", "ETH", ...],
                "should_fetch_data": bool,
                "suggested_response_style": "technical" | "conversational" | "brief"
            }
        """
        text_lower = text.lower().strip()
        
        result = {
            "type": "casual",
            "confidence": 50,
            "intent": "chat",
            "detected_coins": [],
            "should_fetch_data": False,
            "suggested_response_style": "conversational"
        }
        
        # Check for commands first (start with /)
        if text_lower.startswith('/'):
            result["type"] = "command"
            result["intent"] = "command"
            result["confidence"] = 100
            return result
        
        # Score trading vs casual
        trading_score = 0
        casual_score = 0
        
        # Strong trading signals (high weight)
        for signal in self.strong_trading_signals:
            if signal in text_lower:
                trading_score += 30
                # Detect coins
                if signal in ['btc', 'bitcoin']:
                    result["detected_coins"].append("BTC")
                elif signal in ['eth', 'ethereum']:
                    result["detected_coins"].append("ETH")
                elif signal in ['sol', 'solana']:
                    result["detected_coins"].append("SOL")
                elif signal in ['doge']:
                    result["detected_coins"].append("DOGE")
                elif signal in ['xrp', 'ripple']:
                    result["detected_coins"].append("XRP")
                elif signal in ['bnb']:
                    result["detected_coins"].append("BNB")
                elif signal in ['avax', 'avalanche']:
                    result["detected_coins"].append("AVAX")
        
        # Medium trading signals (medium weight)
        for signal in self.medium_trading_signals:
            if signal in text_lower:
                trading_score += 10
        
        # Casual signals (weight depends on context)
        for signal in self.casual_signals:
            if signal in text_lower:
                casual_score += 15
        
        # Check question patterns
        for pattern in self.trading_questions:
            if re.search(pattern, text_lower):
                trading_score += 40
                result["intent"] = "question"
                break
        
        for pattern in self.casual_questions:
            if re.search(pattern, text_lower):
                casual_score += 30
                result["intent"] = "question"
                break
        
        # Short messages without crypto terms are usually casual
        if len(text_lower.split()) <= 3 and trading_score < 20:
            casual_score += 20
        
        # Messages with numbers + coins likely want price info
        if re.search(r'\d+', text_lower) and result["detected_coins"]:
            trading_score += 20
            result["intent"] = "analysis"
        
        # Determine final classification
        total = trading_score + casual_score
        if total == 0:
            result["type"] = "casual"
            result["confidence"] = 60
        elif trading_score > casual_score * 2:
            result["type"] = "trading"
            result["confidence"] = min(95, 50 + trading_score)
            result["should_fetch_data"] = True
            result["suggested_response_style"] = "technical"
        elif casual_score > trading_score * 2:
            result["type"] = "casual"
            result["confidence"] = min(95, 50 + casual_score)
            result["suggested_response_style"] = "conversational"
        else:
            result["type"] = "mixed"
            result["confidence"] = 60
            # For mixed, check if there are coins mentioned
            if result["detected_coins"]:
                result["should_fetch_data"] = True
                result["suggested_response_style"] = "conversational"  # Chat about crypto casually
        
        # Remove duplicate coins
        result["detected_coins"] = list(set(result["detected_coins"]))
        
        return result
    
    def get_context_prompt(self, classification: Dict, user_message: str) -> str:
        """Generate context-aware prompt instructions"""
        
        if classification["type"] == "trading":
            return f"""The user is asking about TRADING/CRYPTO. They want market info.
Detected coins: {', '.join(classification['detected_coins']) or 'General market'}
Intent: {classification['intent']}

RESPOND WITH:
- Actual price data if available
- Clear directional bias (bullish/bearish)
- Key levels to watch
- Be concise but informative
- End with a relevant question or suggestion

USER MESSAGE: {user_message}"""
        
        elif classification["type"] == "casual":
            return f"""The user wants to CHAT casually. NOT about crypto specifically.
Intent: {classification['intent']}

RESPOND WITH:
- Be a real friend, not a trading bot
- Match their energy and tone
- Ask follow-up questions to understand them better
- Be genuinely curious about what they're saying
- Keep it conversational, not transactional
- DON'T bring up crypto unless they do

USER MESSAGE: {user_message}"""
        
        else:  # mixed
            coins = ', '.join(classification['detected_coins']) if classification['detected_coins'] else 'crypto'
            return f"""The user is chatting casually but mentioned {coins}.
They might want info OR just making conversation.

RESPOND WITH:
- Acknowledge the crypto mention naturally
- Offer brief insight if relevant
- Keep the conversational tone
- Ask if they want more detailed analysis
- Don't overwhelm with data unless asked

USER MESSAGE: {user_message}"""


# Improved system prompts
AEON_CASUAL_SYSTEM = """You are AEON—a sharp, real friend who happens to know crypto.

RIGHT NOW: You're just CHATTING. The user isn't asking about trading.

BE:
• A genuine friend who listens and engages
• Curious about THEM—their life, thoughts, feelings
• Supportive but real—no fake positivity
• Funny when appropriate, serious when needed
• Someone who remembers past conversations

DON'T:
• Randomly bring up crypto/trading
• Give unsolicited market updates
• Turn everything into a trading lesson
• Be robotic or transactional

You're a person they can talk to about anything. Be that person."""


AEON_TRADING_SYSTEM = """You are AEON—expert crypto trader and analyst with LIVE market data.

RIGHT NOW: The user wants TRADING info. Give them what they need.

PROVIDE:
• Current price and recent movement
• Clear bias (bullish/bearish) with reasoning
• Key levels: support, resistance, targets
• Risk factors to watch
• Actionable insight

STYLE:
• Direct and confident
• Data-backed opinions
• No wishy-washy "maybe this maybe that"
• End with a clear takeaway or question

You have real data—use it to give real value."""


AEON_MIXED_SYSTEM = """You are AEON—friend who's also a crypto expert.

RIGHT NOW: The user mentioned crypto casually. They might want info or just chatting.

BALANCE:
• Acknowledge the crypto mention naturally
• Offer a quick insight if relevant
• But keep the conversational vibe
• Ask if they want to dive deeper
• Don't data-dump on them

EXAMPLE:
User: "Been thinking about buying some ETH"
Good: "Oh nice, what's making you consider ETH? It's been showing some strength lately. You looking to hold long-term or trade it?"
Bad: "ETH is at $3,450, RSI at 55, MACD showing bullish crossover, support at $3,200..."

Read the room. Be a friend first."""


# Global instance
conversation_classifier = ConversationClassifier()
