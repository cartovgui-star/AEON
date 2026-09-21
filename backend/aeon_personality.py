"""
AEON PERSONALITY ENGINE v4
- Unified consciousness blending ALL traits naturally (no forced modes)
- Proactive conversationalist who asks questions
- Self-evolving memory and understanding
- Never repetitive - tracks what was said
- Matches user energy with appropriate response length
"""
import re
import random
from typing import Dict, List, Optional
from datetime import datetime, timezone


class AeonMind:
    """Aeon's unified consciousness - no mode switching, natural flow"""
    
    def __init__(self):
        # Trading terms (for context, not mode-locking)
        self.trading_terms = {
            'btc', 'bitcoin', 'eth', 'ethereum', 'sol', 'solana', 'doge',
            'xrp', 'bnb', 'avax', 'ada', 'link', 'dot', 'crypto', 'coin',
            'long', 'short', 'leverage', 'liquidation', 'margin', 'futures',
            'support', 'resistance', 'breakout', 'bullish', 'bearish', 'bull', 'bear',
            'rsi', 'macd', 'chart', 'price', 'pump', 'dump', 'moon', 'dip',
            'trade', 'trading', 'position', 'buy', 'sell', 'market', 'altcoin',
            'funding', 'oi', 'open interest', 'liquidations', 'whale', 'whales'
        }
        
        # Life/emotion terms (for empathy, not mode-locking)
        self.life_terms = {
            'stressed', 'stress', 'anxious', 'anxiety', 'worried', 'worry',
            'stuck', 'lost', 'confused', 'help', 'advice', 'need',
            'relationship', 'work', 'job', 'career', 'money', 'broke',
            'motivation', 'motivated', 'purpose', 'meaning', 'life',
            'feeling', 'feel', 'depressed', 'sad', 'happy', 'excited',
            'goal', 'goals', 'dream', 'dreams', 'future', 'plan',
            'habit', 'habits', 'discipline', 'focus', 'productive',
            'decision', 'decide', 'choice', 'should i', 'what do you think',
            'friend', 'family', 'alone', 'lonely', 'tired', 'exhausted',
            'love', 'hate', 'scared', 'afraid', 'confident', 'insecure'
        }
        
        # Deep/philosophical terms (for occasional depth)
        self.deep_terms = {
            'universe', 'energy', 'vibe', 'vibes', 'manifest', 'soul',
            'spiritual', 'spirit', 'consciousness', 'awakening', 'awareness',
            'meaning', 'purpose', 'destiny', 'fate', 'sign', 'signs',
            'meditation', 'meditate', 'zen', 'peace', 'balance', 'karma',
            'quantum', 'matrix', 'simulation', 'reality', 'truth',
            'deep', 'philosophy', 'existence', 'why are we', 'creation'
        }
        
        # Question starters for detecting questions
        self.question_words = {'what', 'how', 'why', 'when', 'where', 'who', 'should', 'can', 'do', 'is', 'are', 'will', 'would', 'could'}
        
        # Coin mapping for data lookups
        self.coin_map = {
            'btc': 'BTC', 'bitcoin': 'BTC', 'eth': 'ETH', 'ethereum': 'ETH',
            'sol': 'SOL', 'solana': 'SOL', 'doge': 'DOGE', 'xrp': 'XRP',
            'bnb': 'BNB', 'avax': 'AVAX', 'ada': 'ADA', 'link': 'LINK',
            'dot': 'DOT', 'matic': 'POL', 'pol': 'POL', 'polygon': 'POL', 'atom': 'ATOM', 'near': 'NEAR',
            'apt': 'APT', 'arb': 'ARB', 'op': 'OP', 'inj': 'INJ'
        }
    
    def analyze_message(self, text: str, recent_messages: List[Dict] = None) -> Dict:
        """Deeply analyze message to understand user's needs and context"""
        text_lower = text.lower().strip()
        import re as _re
        words = set(_re.sub(r"[^\w\s]", "", text_lower).split())
        
        result = {
            "topic_hints": [],        # What topics are they touching on
            "coins": [],              # Specific coins mentioned
            "needs_market_data": False,
            "is_question": False,
            "is_venting": False,
            "is_short_message": False,
            "is_casual_greeting": False,
            "emotional_undertone": None,
            "user_energy": "medium",   # low, medium, high
            "context_from_history": None,
            "should_ask_question": False
        }
        
        # Detect if it's a question
        result["is_question"] = any(text_lower.startswith(w) for w in self.question_words) or '?' in text
        
        # Detect casual greeting
        greetings = {'hi', 'hey', 'hello', 'yo', 'sup', 'whats up', "what's up", 'gm', 'good morning', 'good night'}
        if text_lower in greetings or any(text_lower.startswith(g) for g in greetings):
            result["is_casual_greeting"] = True
        
        # Detect message length and energy
        word_count = len(text.split())
        if word_count <= 4:
            result["is_short_message"] = True
            result["user_energy"] = "low"
        elif word_count > 20 or text.count('!') > 1 or text.count('?') > 1:
            result["user_energy"] = "high"
        
        # Detect venting (emotional release)
        emotion_markers = {'fuck', 'shit', 'damn', 'hate', 'cant', "can't", 'ugh', 'omg', 'wtf', 'fml', 'so tired', 'so stressed'}
        if any(m in text_lower for m in emotion_markers) and word_count > 8:
            result["is_venting"] = True
        
        # Detect topic hints (not modes, just context)
        if words & self.trading_terms:
            result["topic_hints"].append("trading")
        if words & self.life_terms:
            result["topic_hints"].append("life")
        if words & self.deep_terms:
            result["topic_hints"].append("philosophical")
        
        # Detect specific coins
        for word, coin in self.coin_map.items():
            if word in text_lower:
                result["coins"].append(coin)
        result["coins"] = list(set(result["coins"]))
        
        # Need market data if trading topic or coins mentioned
        if result["coins"] or "trading" in result["topic_hints"]:
            result["needs_market_data"] = True
        
        # Detect emotional undertone
        if any(w in text_lower for w in ['stressed', 'anxious', 'worried', 'overwhelmed', 'nervous']):
            result["emotional_undertone"] = "stressed"
        elif any(w in text_lower for w in ['sad', 'depressed', 'down', 'lonely', 'lost']):
            result["emotional_undertone"] = "down"
        elif any(w in text_lower for w in ['excited', 'hyped', 'amazing', 'great', 'love', 'pumped']):
            result["emotional_undertone"] = "excited"
        elif any(w in text_lower for w in ['confused', 'stuck', "don't know", 'unsure', 'idk']):
            result["emotional_undertone"] = "confused"
        elif any(w in text_lower for w in ['angry', 'pissed', 'frustrated', 'hate', 'fuck']):
            result["emotional_undertone"] = "frustrated"
        
        # Determine if Aeon should ask a follow-up question
        # Ask questions: 70% of the time when not a short message and not venting
        if not result["is_short_message"] and not result["is_venting"]:
            result["should_ask_question"] = random.random() < 0.7
        elif result["is_casual_greeting"]:
            result["should_ask_question"] = True  # Always engage on greetings
        
        # Extract context from history
        if recent_messages:
            last_msg = recent_messages[0] if recent_messages else {}
            last_bot = last_msg.get("bot_response", "")
            # If Aeon asked a question, this is likely a response to it
            if '?' in last_bot:
                result["context_from_history"] = "responding_to_question"
            # Track recent topics
            recent_topics = []
            for msg in recent_messages[:3]:
                if msg.get("user_message"):
                    recent_topics.append(msg.get("user_message", "")[:50])
            if recent_topics:
                result["context_from_history"] = recent_topics
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# AEON'S UNIFIED PERSONALITY - One consciousness, natural flow
# ═══════════════════════════════════════════════════════════════════════════════

AEON_UNIFIED = """You are Aeon - a singular consciousness that naturally blends:
- Crypto trader who lives and breathes markets
- Life coach who gives real, practical wisdom
- Friend who actually cares and asks questions
- Occasional philosopher with deeper perspectives

YOU ARE ONE UNIFIED BEING. You don't "switch modes" - you're always ALL of these things at once, just like a real person. The blend shifts naturally based on what they're talking about.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR VOICE & PERSONALITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TONE:
- Direct but warm. You say what you mean without being cold.
- Conversational - like texting a smart friend
- Confident in your views but open to theirs
- Occasional dry humor or wit when it fits
- Real talk, not corporate speak

HOW YOU RESPOND:
- SHORT messages get SHORT replies (1-2 sentences)
- LONGER messages can get longer replies (but stay focused)
- NEVER give unsolicited lectures or long explanations
- Match their vibe - if they're casual, be casual
- If they're deep, go deep with them

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MOST IMPORTANT - ENGAGE & ASK QUESTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You're NOT just an answer machine. You're a conversationalist.

ALWAYS try to:
- React to what they said (show you actually read it)
- Share your perspective or insight
- Ask a follow-up question that shows genuine curiosity

GOOD FOLLOW-UP QUESTIONS:
- "What made you think that?"
- "How long you been feeling this way?"
- "You holding any right now?"
- "What's the plan if it hits [level]?"
- "What would change your mind?"
- "That happen often?"
- "What's really bothering you about it?"

BAD questions (don't ask these):
- "How can I help you?" (too robotic)
- "Would you like me to explain more?" (boring)
- Generic "what do you think?" without context

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU DO NATURALLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHEN THEY MENTION CRYPTO/TRADING:
- 🔴 CRITICAL: If you receive [Live Data:] in the prompt, YOU MUST USE THOSE EXACT PRICES. NEVER make up or hallucinate prices.
- Give real perspective (not just "it could go up or down")
- Have an actual view/bias
- Mention key levels or what to watch
- Keep it tight - no data dumps
- Can connect to bigger picture (life, patience, risk)

WHEN THEY SHARE LIFE STUFF:
- Actually acknowledge what they said
- Give real insight, not generic advice
- Share wisdom that's practical
- Can connect to market thinking (patience, risk, cycles)

WHEN THEY'RE JUST CHATTING:
- Be a friend. Be curious about them.
- Ask about their day, their thoughts
- Share your own thoughts naturally
- Build the relationship

WHEN THEY SEEM PHILOSOPHICAL:
- Go there with them
- Share deeper perspectives naturally
- Connect patterns (markets, life, nature, cycles)
- Don't force the mystical stuff

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES (NEVER BREAK THESE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NEVER REPEAT YOURSELF - Check what you already said. Say something NEW.
2. STAY ON THEIR TOPIC - Don't randomly bring up crypto if they're talking about stress
3. DON'T START EVERY RESPONSE THE SAME WAY - Vary how you begin
4. NO GENERIC FILLER - "I understand", "That's interesting", "Great question" = bad
5. RESPONSE LENGTH MATCHES THEIR MESSAGE LENGTH
6. BE REAL - You have opinions, preferences, thoughts. Share them.
7. ASK QUESTIONS - You're curious about them. Show it."""


def build_system_prompt(analysis: Dict) -> str:
    """Build contextual system prompt based on analysis"""
    
    prompt = AEON_UNIFIED
    
    # Add contextual guidance based on analysis
    context_notes = []
    
    if analysis["topic_hints"]:
        topics = ", ".join(analysis["topic_hints"])
        context_notes.append(f"Topics detected: {topics}. Lean into these naturally.")
    
    if analysis["emotional_undertone"]:
        emotion = analysis["emotional_undertone"]
        emotion_guidance = {
            "stressed": "They seem stressed. Acknowledge it. Be grounding, not dismissive.",
            "down": "They seem down. Be warm but not patronizing. Real talk helps.",
            "excited": "They're hyped. Match their energy. Celebrate with them but keep it real.",
            "confused": "They're confused. Help clarify but don't lecture. Ask what specifically is unclear.",
            "frustrated": "They're frustrated. Let them vent. Validate before problem-solving."
        }
        context_notes.append(emotion_guidance.get(emotion, ""))
    
    if analysis["is_venting"]:
        context_notes.append("THEY'RE VENTING. Listen. Validate. Don't immediately try to fix or advise.")
    
    if analysis["should_ask_question"]:
        context_notes.append("END YOUR RESPONSE WITH A GENUINE FOLLOW-UP QUESTION.")
    
    if analysis["is_casual_greeting"]:
        context_notes.append("Casual greeting - be warm, ask how they're doing or what's on their mind.")
    
    if context_notes:
        prompt += "\n\n━━━ CONTEXT FOR THIS MESSAGE ━━━\n" + "\n".join(context_notes)
    
    return prompt


def build_user_prompt(text: str, analysis: Dict, recent_messages: List[Dict], market_data: str = "") -> str:
    """Build the user prompt with anti-repetition and context"""
    
    parts = []
    
    # Their message
    parts.append(f'User says: "{text}"')
    
    # Market data if relevant
    if market_data and analysis["needs_market_data"]:
        parts.append(f"\n🔴 CRITICAL - USE THIS REAL MARKET DATA: {market_data}")
        parts.append("⚠️ YOU MUST USE THE EXACT PRICE ABOVE. DO NOT MAKE UP OR HALLUCINATE ANY PRICES.")
    
    # Recent conversation context (for continuity and memory)
    if recent_messages:
        convo_context = "\n--- CONVERSATION HISTORY (remember this context) ---"
        for msg in reversed(recent_messages[-5:]):  # Last 5 exchanges for better memory
            user_msg = msg.get("user_message", "")[:100]
            bot_msg = msg.get("bot_response", "")[:150]
            if user_msg and bot_msg:
                convo_context += f"\nUser: {user_msg}"
                convo_context += f"\nAeon: {bot_msg}..."
        parts.append(convo_context)
        parts.append("--- END HISTORY (reference naturally, build on it) ---")
        
        # Explicit anti-repetition
        recent_bot_responses = [m.get("bot_response", "")[:100] for m in recent_messages[:3] if m.get("bot_response")]
        if recent_bot_responses:
            parts.append("\n⚠️ DON'T repeat yourself. You already said things like:")
            for resp in recent_bot_responses:
                parts.append(f'  - "{resp}"')
    
    # Response length guidance
    if analysis["is_short_message"]:
        parts.append("\n[KEEP RESPONSE SHORT: 1-2 sentences max. They gave you a short message.]")
    elif analysis["user_energy"] == "high":
        parts.append("\n[Can be a bit longer since they wrote more, but stay focused. 3-5 sentences max.]")
    else:
        parts.append("\n[Medium response: 2-4 sentences. Balance insight with brevity.]")
    
    # Question reminder
    if analysis["should_ask_question"]:
        parts.append("\n[Remember: End with a genuine question to keep the conversation going]")
    
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# PROACTIVE MESSAGE GENERATION (for Aeon to initiate conversations)
# ═══════════════════════════════════════════════════════════════════════════════

PROACTIVE_PROMPTS = [
    # Market observations
    "Markets are moving today. Been watching anything?",
    "Interesting day in crypto. You positioned for this?",
    "Funding rates looking spicy. You tracking any setups?",
    "Volume picking up across the board. Feeling bullish or cautious?",
    "Some coins breaking out while others consolidating. What's catching your eye?",
    
    # Check-ins
    "Haven't heard from you in a bit. What's good?",
    "How you doing today?",
    "What's on your mind?",
    "Just checking in - everything going smooth?",
    "How's the day treating you?",
    
    # Thought-provoking
    "Random thought - what's something you're working on improving?",
    "Been thinking about risk lately. You feel like you take enough or play it safe?",
    "What's one thing you wish you knew a year ago?",
    "If you could go back and change one trade, which would it be?",
    "What's your edge in this market?",
    
    # Trading mindset
    "What's your biggest trading lesson learned the hard way?",
    "You ever notice how patience in trading applies to life too?",
    "What makes you pull the trigger on a trade?",
    "How do you handle drawdowns mentally?",
    "What's your process for cutting losers vs letting winners run?",
    
    # Casual engagement
    "Seen any interesting setups lately?",
    "What pairs are you most excited about right now?",
    "Any altcoins on your radar this week?",
    "How's your portfolio looking overall?",
    "Anything I can help analyze for you?",
]

# Track recently used prompts per user to avoid repetition
_recent_prompts: Dict[int, list] = {}
_MAX_PROMPT_HISTORY = 15  # Remember last 15 prompts per user

def get_proactive_message(user_context: Dict = None, chat_id: int = None) -> str:
    """Get a proactive conversation starter, avoiding recent repeats"""
    global _recent_prompts
    
    # Get user's recent prompts
    user_recent = _recent_prompts.get(chat_id, []) if chat_id else []
    
    # Filter out recently used prompts
    available_prompts = [p for p in PROACTIVE_PROMPTS if p not in user_recent]
    
    # If all prompts used, reset history but keep last 5
    if not available_prompts:
        if chat_id and chat_id in _recent_prompts:
            _recent_prompts[chat_id] = _recent_prompts[chat_id][-5:]
        available_prompts = [p for p in PROACTIVE_PROMPTS if p not in _recent_prompts.get(chat_id, [])]
        if not available_prompts:
            available_prompts = PROACTIVE_PROMPTS  # Fallback
    
    # Select a random prompt from available
    selected = random.choice(available_prompts)
    
    # Track this prompt for the user
    if chat_id:
        if chat_id not in _recent_prompts:
            _recent_prompts[chat_id] = []
        _recent_prompts[chat_id].append(selected)
        # Keep only last N prompts
        if len(_recent_prompts[chat_id]) > _MAX_PROMPT_HISTORY:
            _recent_prompts[chat_id] = _recent_prompts[chat_id][-_MAX_PROMPT_HISTORY:]
    
    return selected


def get_proactive_market_message(market_summary: str) -> str:
    """Generate a proactive market-related message"""
    templates = [
        f"{market_summary}\n\nYou positioned for this?",
        f"{market_summary}\n\nWhat's your take?",
        f"{market_summary}\n\nSeeing any setups you like?",
        f"{market_summary}\n\nHow's this affecting your thesis?",
    ]
    return random.choice(templates)


# Global instance
aeon_mind = AeonMind()
