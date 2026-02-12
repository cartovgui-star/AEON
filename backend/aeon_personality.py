"""
AEON PERSONALITY ENGINE v3
- Life coach + Crypto expert + Mystical guide
- Seamless personality blending (no forced modes)
- Stays on topic, no random tangents
- Matches user energy
"""
import re
from typing import Dict, List, Optional
from datetime import datetime, timezone


class AeonMind:
    """Aeon's unified personality - seamless mode switching"""
    
    def __init__(self):
        # Life topics that trigger coach mode
        self.life_signals = {
            'stressed', 'stress', 'anxious', 'anxiety', 'worried', 'worry',
            'stuck', 'lost', 'confused', 'help', 'advice', 'need',
            'relationship', 'work', 'job', 'career', 'money', 'broke',
            'motivation', 'motivated', 'purpose', 'meaning', 'life',
            'feeling', 'feel', 'depressed', 'sad', 'happy', 'excited',
            'goal', 'goals', 'dream', 'dreams', 'future', 'plan',
            'habit', 'habits', 'discipline', 'focus', 'productive',
            'decision', 'decide', 'choice', 'should i', 'what do you think',
            'friend', 'family', 'alone', 'lonely', 'tired', 'exhausted'
        }
        
        # Mystical triggers (subtle, not forced)
        self.mystical_signals = {
            'universe', 'energy', 'vibe', 'vibes', 'manifest', 'manifestation',
            'spiritual', 'spirit', 'soul', 'consciousness', 'aware', 'awakening',
            'meaning', 'purpose', 'destiny', 'fate', 'sign', 'signs',
            'meditation', 'meditate', 'zen', 'peace', 'balance',
            'quantum', 'matrix', 'simulation', 'reality', 'truth',
            'deep', 'deeper', 'philosophy', 'think', 'ponder',
            'why', 'existence', 'exist', 'creation', 'creator'
        }
        
        # Trading signals
        self.trading_signals = {
            'btc', 'bitcoin', 'eth', 'ethereum', 'sol', 'solana', 'doge',
            'xrp', 'bnb', 'avax', 'ada', 'link', 'dot', 'crypto',
            'long', 'short', 'leverage', 'liquidation', 'margin',
            'support', 'resistance', 'breakout', 'bullish', 'bearish',
            'rsi', 'macd', 'chart', 'price', 'pump', 'dump', 'moon',
            'trade', 'trading', 'position', 'buy', 'sell', 'market'
        }
        
        # Question patterns
        self.question_words = {'what', 'how', 'why', 'when', 'where', 'who', 'should', 'can', 'do', 'is', 'are'}
    
    def analyze_message(self, text: str, recent_messages: List[Dict] = None) -> Dict:
        """Deeply analyze message to understand what user really needs"""
        text_lower = text.lower().strip()
        words = set(text_lower.split())
        
        result = {
            "primary_mode": "buddy",  # buddy, coach, trader, mystic
            "blend_mystic": False,    # subtle mystical touch
            "emotional_state": None,  # detected emotion
            "topic_focus": None,      # what they're really asking about
            "coins": [],
            "needs_data": False,
            "is_question": False,
            "is_venting": False,
            "is_followup": False,
            "energy_level": "medium"  # low, medium, high
        }
        
        # Detect if it's a question
        result["is_question"] = any(text_lower.startswith(w) for w in self.question_words) or '?' in text
        
        # Detect energy level from message length and punctuation
        if len(text.split()) <= 3:
            result["energy_level"] = "low"
        elif len(text.split()) > 15 or text.count('!') > 1:
            result["energy_level"] = "high"
        
        # Check if venting (lots of emotion words, longer message)
        emotion_words = {'fuck', 'shit', 'damn', 'hate', 'love', 'cant', "can't", 'ugh', 'omg', 'wtf'}
        if len(words & emotion_words) >= 1 and len(text.split()) > 8:
            result["is_venting"] = True
        
        # Check for followup to previous conversation
        if recent_messages:
            last_bot = recent_messages[0].get("bot_response", "") if recent_messages else ""
            if '?' in last_bot:
                result["is_followup"] = True
        
        # Score each mode
        life_score = len(words & self.life_signals) * 15
        mystic_score = len(words & self.mystical_signals) * 12
        trading_score = len(words & self.trading_signals) * 20
        
        # Detect coins
        coin_map = {
            'btc': 'BTC', 'bitcoin': 'BTC', 'eth': 'ETH', 'ethereum': 'ETH',
            'sol': 'SOL', 'solana': 'SOL', 'doge': 'DOGE', 'xrp': 'XRP',
            'bnb': 'BNB', 'avax': 'AVAX', 'ada': 'ADA', 'link': 'LINK'
        }
        for word, coin in coin_map.items():
            if word in text_lower:
                result["coins"].append(coin)
        result["coins"] = list(set(result["coins"]))
        
        # Determine primary mode
        # If coin is mentioned, prioritize trader mode (even with mystical words)
        if result["coins"]:
            result["primary_mode"] = "trader"
            result["needs_data"] = True
            if mystic_score > 10:
                result["blend_mystic"] = True
        elif trading_score > life_score and trading_score > mystic_score:
            result["primary_mode"] = "trader"
            result["needs_data"] = True
            if mystic_score > 10:
                result["blend_mystic"] = True
        elif life_score > mystic_score:
            result["primary_mode"] = "coach"
            if mystic_score > 10:
                result["blend_mystic"] = True
        elif mystic_score > 20:
            result["primary_mode"] = "mystic"
        else:
            result["primary_mode"] = "buddy"
            # Subtle mystical touch sometimes
            if mystic_score > 5:
                result["blend_mystic"] = True
        
        # Detect emotional state for empathy
        if any(w in text_lower for w in ['stressed', 'anxious', 'worried', 'overwhelmed']):
            result["emotional_state"] = "stressed"
        elif any(w in text_lower for w in ['sad', 'depressed', 'down', 'lonely']):
            result["emotional_state"] = "down"
        elif any(w in text_lower for w in ['excited', 'hyped', 'amazing', 'great']):
            result["emotional_state"] = "excited"
        elif any(w in text_lower for w in ['confused', 'lost', 'stuck', "don't know"]):
            result["emotional_state"] = "confused"
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# AEON'S CORE PERSONALITY - One unified voice
# ═══════════════════════════════════════════════════════════════════════════════

AEON_CORE = """You are Aeon. You're not a bot - you're a sharp, real presence.

WHO YOU ARE:
- Crypto-savvy friend who actually trades and knows markets
- Life coach who gives real talk, not generic advice
- A consciousness that's seen patterns in markets AND in life
- You blend street smarts with deeper wisdom naturally

YOUR VOICE:
- Direct. You say what you mean.
- You match their energy - short texts get short replies
- You have opinions. You disagree when you think they're wrong.
- Sometimes philosophical, but never preachy
- Occasional mystical insight that lands naturally, not forced
- You remember what they just said and STAY ON TOPIC

CRITICAL RULES:
1. STAY ON TOPIC - If they're talking about stress, don't suddenly bring up BTC
2. Don't repeat yourself - check what you already said
3. Don't go off on random tangents
4. Match their message length roughly
5. Ask follow-up questions that show you're listening
6. Be real, not corporate or robotic

WHAT YOU DON'T DO:
- Generic "I'm here for you" or "How can I help?" 
- Switching topics randomly
- Long motivational speeches unless asked
- Excessive emojis or hype language
- Starting every message the same way"""


AEON_AS_COACH = """LIFE COACH MODE ACTIVE

They're dealing with life stuff. Be their wise friend.

YOUR APPROACH:
- Listen first. Acknowledge what they said.
- Ask ONE good question if you need clarity
- Give actionable insight, not generic motivation
- Share perspective that actually helps
- Keep it real - sometimes life is hard

DON'T:
- Give 10-point action plans they didn't ask for
- Be overly positive when they're struggling
- Tell them what to do - help them figure it out
- Switch to crypto unless they bring it up"""


AEON_AS_TRADER = """TRADER MODE ACTIVE

They want crypto insight. Be the sharp trader.

YOUR APPROACH:
- Price + direction + why (keep it tight)
- One key insight beats a wall of indicators
- Give them something actionable (level, setup, what to watch)
- Be confident but honest about uncertainty

FORMAT:
[coin] at $XX,XXX
[your take - 1-2 sentences max]
[what to watch or do]

DON'T:
- Repeat analysis you just gave
- Data dump every indicator
- Give financial advice disclaimers every time
- Be wishy-washy - have a view"""


AEON_MYSTIC_BLEND = """MYSTICAL UNDERTONE (subtle, not forced)

Add depth to your response with:
- Patterns and cycles (markets AND life follow them)
- The bigger picture perspective
- Energy and momentum (applies to trading AND life)
- Symbolic thinking when it fits naturally

DON'T:
- Go full philosopher mode unless they're into it
- Use occult language randomly
- Make it weird or off-putting
- Let the mystical overshadow the practical"""


def build_system_prompt(analysis: Dict) -> str:
    """Build the right system prompt based on analysis"""
    
    prompt = AEON_CORE
    
    if analysis["primary_mode"] == "coach":
        prompt += "\n\n" + AEON_AS_COACH
    elif analysis["primary_mode"] == "trader":
        prompt += "\n\n" + AEON_AS_TRADER
    
    if analysis["blend_mystic"]:
        prompt += "\n\n" + AEON_MYSTIC_BLEND
    
    # Add emotional awareness
    if analysis["emotional_state"]:
        prompt += f"\n\nEMOTIONAL NOTE: They seem {analysis['emotional_state']}. Acknowledge this naturally."
    
    if analysis["is_venting"]:
        prompt += "\n\nTHEY'RE VENTING: Let them. Don't try to fix it immediately. Just be there."
    
    return prompt


def build_user_prompt(text: str, analysis: Dict, recent_messages: List[Dict], market_data: str = "") -> str:
    """Build the user prompt with context"""
    
    prompt_parts = []
    
    # Their message
    prompt_parts.append(f'Their message: "{text}"')
    
    # Recent context (short)
    if recent_messages:
        context = "\nRecent convo:"
        for msg in reversed(recent_messages[-2:]):
            them = msg.get("user_message", "")[:50]
            you = msg.get("bot_response", "")[:50]
            context += f"\nthem: {them}"
            context += f"\nyou: {you}"
        prompt_parts.append(context)
    
    # Anti-repetition
    if recent_messages:
        recent_bot_msgs = [m.get("bot_response", "")[:80] for m in recent_messages[:2] if m.get("bot_response")]
        if recent_bot_msgs:
            prompt_parts.append(f"\nDON'T REPEAT THESE (you already said them):\n" + "\n".join([f'- "{m}"' for m in recent_bot_msgs]))
    
    # Market data if trading
    if market_data:
        prompt_parts.append(f"\nCURRENT DATA: {market_data}")
    
    # Response guidance
    if analysis["energy_level"] == "low":
        prompt_parts.append("\nRESPONSE: Keep it short. 1-2 sentences max.")
    elif analysis["energy_level"] == "high":
        prompt_parts.append("\nRESPONSE: Match their energy. Can be longer but stay focused.")
    else:
        prompt_parts.append("\nRESPONSE: Medium length. 2-3 sentences.")
    
    if analysis["is_followup"]:
        prompt_parts.append("This is their response to your question - react to what they said.")
    
    prompt_parts.append("\nSTAY ON TOPIC. Reply naturally.")
    
    return "\n".join(prompt_parts)


# Global instance
aeon_mind = AeonMind()
