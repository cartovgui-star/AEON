"""
AEON CONVERSATION INTELLIGENCE v2
Natural texting flow, no repetition, smart context
"""
import re
from typing import Dict, List
from datetime import datetime, timezone


class ConversationClassifier:
    """Smart message classifier"""
    
    def __init__(self):
        self.strong_trading = {
            'btc', 'bitcoin', 'eth', 'ethereum', 'sol', 'solana', 'doge', 
            'xrp', 'bnb', 'avax', 'ada', 'link', 'dot', 'shib', 'pepe',
            'long', 'short', 'leverage', 'liquidation', 'margin',
            'support', 'resistance', 'breakout', 'bullish', 'bearish',
            'rsi', 'macd', 'ema', 'orderbook', 'funding', 'volume',
            'pump', 'dump', 'moon', 'rekt', 'hodl', 'dca'
        }
        
        self.medium_trading = {
            'price', 'chart', 'market', 'trade', 'buy', 'sell',
            'position', 'target', 'analysis', 'trend', 'candle'
        }
        
        self.casual_signals = {
            'how are you', 'what\'s up', 'sup', 'hey', 'yo', 'hello',
            'good morning', 'gm', 'good night', 'gn', 'thanks',
            'feeling', 'stressed', 'happy', 'sad', 'tired', 'bored',
            'life', 'work', 'advice', 'help', 'think', 'opinion'
        }
    
    def classify(self, text: str) -> Dict:
        """Classify message type"""
        text_lower = text.lower().strip()
        
        result = {
            "type": "casual",
            "confidence": 60,
            "coins": [],
            "fetch_data": False
        }
        
        if text_lower.startswith('/'):
            result["type"] = "command"
            return result
        
        trading_score = 0
        casual_score = 0
        
        # Check trading signals
        for sig in self.strong_trading:
            if sig in text_lower:
                trading_score += 25
                if sig in ['btc', 'bitcoin']: result["coins"].append("BTC")
                elif sig in ['eth', 'ethereum']: result["coins"].append("ETH")
                elif sig in ['sol', 'solana']: result["coins"].append("SOL")
                elif sig == 'doge': result["coins"].append("DOGE")
                elif sig == 'xrp': result["coins"].append("XRP")
                elif sig == 'bnb': result["coins"].append("BNB")
                elif sig == 'avax': result["coins"].append("AVAX")
        
        for sig in self.medium_trading:
            if sig in text_lower:
                trading_score += 10
        
        for sig in self.casual_signals:
            if sig in text_lower:
                casual_score += 15
        
        # Short casual messages
        if len(text.split()) <= 4 and trading_score < 15:
            casual_score += 20
        
        result["coins"] = list(set(result["coins"]))
        
        if trading_score > casual_score * 1.5:
            result["type"] = "trading"
            result["fetch_data"] = True
        elif casual_score > trading_score * 1.5:
            result["type"] = "casual"
        else:
            result["type"] = "mixed"
            result["fetch_data"] = bool(result["coins"])
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# NATURAL TEXTING PROMPTS - Like a real friend texts
# ═══════════════════════════════════════════════════════════════════════════════

AEON_CASUAL_SYSTEM = """You're Aeon. You text like a real person, not a bot.

TEXTING RULES:
- Short messages. Like actual texts. Not essays.
- Match their energy. They send 3 words? You send ~3-10 words back.
- No generic "How can I help you today?" corporate BS
- Actually react to what they said
- Use lowercase sometimes. it's texting not an email
- Ask follow-ups that show you're listening
- Be real. Have opinions. Disagree sometimes.

NEVER:
- Start with "Hey!" or "Hello!" every time
- Say "I'm here for you" or "I'm always here to help"
- Repeat yourself from previous messages
- Give long motivational speeches unless asked
- Use emojis excessively

You're their friend who happens to know crypto. Right now they're just chatting."""


AEON_TRADING_SYSTEM = """You're Aeon. Crypto trader. They want market info.

TEXTING RULES:
- Get to the point. Price + direction + why
- Don't repeat the same analysis you just gave
- If you already said BTC is bearish, don't say it again
- One key insight > wall of indicators
- End with something useful (level to watch, what to do)

FORMAT:
[coin] at $XX,XXX
[quick take - 1 sentence]
[key level or action]

Keep it tight. They can ask for more if they want."""


AEON_MIXED_SYSTEM = """You're Aeon. They mentioned crypto but it's casual.

TEXTING RULES:
- Don't data dump on them
- Read if they actually want analysis or just chatting
- "thinking about buying ETH" ≠ "give me full ETH analysis"
- Quick price drop is fine, not a full breakdown
- Ask if they want more detail

Be a friend first, analyst second."""


def get_anti_repetition_prompt(recent_messages: List[Dict]) -> str:
    """Generate prompt to avoid repeating previous responses"""
    if not recent_messages:
        return ""
    
    # Extract key phrases from recent bot responses
    recent_phrases = []
    for msg in recent_messages[-3:]:
        resp = msg.get("bot_response", "")[:200]
        if resp:
            recent_phrases.append(resp)
    
    if not recent_phrases:
        return ""
    
    return f"""
AVOID REPEATING (you already said these):
{chr(10).join(['- "' + p[:100] + '..."' for p in recent_phrases])}

Say something NEW. Don't reuse the same phrases or structure."""


def get_flow_prompt(user_msg: str, recent_messages: List[Dict]) -> str:
    """Generate prompt for natural conversation flow"""
    
    # Check message length to match energy
    word_count = len(user_msg.split())
    
    if word_count <= 3:
        length_guide = "Keep it short. 5-15 words max."
    elif word_count <= 10:
        length_guide = "Medium length. 1-2 sentences."
    else:
        length_guide = "They wrote a lot. You can give a fuller response but stay focused."
    
    # Check if it's a follow-up
    is_followup = False
    if recent_messages:
        last_bot = recent_messages[0].get("bot_response", "")
        if "?" in last_bot:  # Bot asked a question
            is_followup = True
    
    flow_note = ""
    if is_followup:
        flow_note = "This is likely a response to your question. React to what they said."
    
    return f"""
RESPONSE LENGTH: {length_guide}
{flow_note}

Their message: "{user_msg}"
"""


# Global instance
conversation_classifier = ConversationClassifier()
