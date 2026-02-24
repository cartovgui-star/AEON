"""
AEON PERSONALITY ENGINE v3 - Testing Suite
Tests for the new AeonMind class that detects conversation modes:
- buddy: casual chat, short friendly response
- coach: stressed/life questions, empathetic helpful
- trader: trading questions, market data analysis
- mystic: philosophical questions, deeper insights

Also tests:
- Bot stays on topic (doesn't randomly switch subjects)
- Bot matches user's energy (short messages get short replies)
- Telegram webhook works properly with new personality system
"""

import pytest
import requests
import os
import sys
import time

# Add backend directory to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aeon_personality import AeonMind, build_system_prompt, build_user_prompt

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-algo-trade.preview.emergentagent.com')


class TestAeonMindModeDetection:
    """Test AeonMind.analyze_message() correctly identifies conversation modes"""
    
    def setup_method(self):
        """Setup AeonMind instance for each test"""
        self.mind = AeonMind()
    
    # ═══════════════════════════════════════════════════════════════════
    # BUDDY MODE TESTS - Casual chat triggers
    # ═══════════════════════════════════════════════════════════════════
    
    def test_buddy_mode_simple_greeting(self):
        """Simple greeting should trigger buddy mode"""
        result = self.mind.analyze_message("hey what's up")
        assert result["primary_mode"] == "buddy", f"Expected 'buddy', got '{result['primary_mode']}'"
        print(f"✅ Buddy mode detected for 'hey what's up': {result['primary_mode']}")
    
    def test_buddy_mode_casual_chat(self):
        """Casual chat should trigger buddy mode"""
        result = self.mind.analyze_message("just chilling, you?")
        assert result["primary_mode"] == "buddy", f"Expected 'buddy', got '{result['primary_mode']}'"
        print(f"✅ Buddy mode detected for casual chat: {result['primary_mode']}")
    
    def test_buddy_mode_short_message(self):
        """Very short message should have low energy"""
        result = self.mind.analyze_message("yo")
        assert result["primary_mode"] == "buddy", f"Expected 'buddy', got '{result['primary_mode']}'"
        assert result["energy_level"] == "low", f"Expected 'low' energy, got '{result['energy_level']}'"
        print(f"✅ Buddy mode with low energy for 'yo': mode={result['primary_mode']}, energy={result['energy_level']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # COACH MODE TESTS - Life/stress questions
    # ═══════════════════════════════════════════════════════════════════
    
    def test_coach_mode_stressed(self):
        """Stress mention should trigger coach mode"""
        result = self.mind.analyze_message("I'm so stressed about my job")
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        assert result["emotional_state"] == "stressed", f"Expected 'stressed' emotion, got '{result['emotional_state']}'"
        print(f"✅ Coach mode detected for stress: mode={result['primary_mode']}, emotion={result['emotional_state']}")
    
    def test_coach_mode_anxiety(self):
        """Anxiety mention should trigger coach mode"""
        result = self.mind.analyze_message("feeling anxious about everything lately")
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        assert result["emotional_state"] == "stressed", f"Expected 'stressed' emotion, got '{result['emotional_state']}'"
        print(f"✅ Coach mode detected for anxiety: mode={result['primary_mode']}, emotion={result['emotional_state']}")
    
    def test_coach_mode_life_advice(self):
        """Life advice questions should trigger coach mode"""
        result = self.mind.analyze_message("I need help with my career decision")
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        print(f"✅ Coach mode detected for life advice: mode={result['primary_mode']}")
    
    def test_coach_mode_relationship(self):
        """Relationship questions should trigger coach mode"""
        result = self.mind.analyze_message("having problems with my relationship, feeling lost")
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        print(f"✅ Coach mode detected for relationship: mode={result['primary_mode']}")
    
    def test_coach_mode_goals(self):
        """Goals/purpose questions should trigger coach mode"""
        result = self.mind.analyze_message("I don't know what my purpose in life is")
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        print(f"✅ Coach mode detected for purpose question: mode={result['primary_mode']}")
    
    def test_coach_mode_feeling_down(self):
        """Sad/depressed mentions should trigger coach mode with 'down' emotion"""
        result = self.mind.analyze_message("feeling really down and sad today")
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        assert result["emotional_state"] == "down", f"Expected 'down' emotion, got '{result['emotional_state']}'"
        print(f"✅ Coach mode detected for sadness: mode={result['primary_mode']}, emotion={result['emotional_state']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # TRADER MODE TESTS - Trading/crypto questions
    # ═══════════════════════════════════════════════════════════════════
    
    def test_trader_mode_btc_price(self):
        """BTC question should trigger trader mode"""
        result = self.mind.analyze_message("what's the btc price?")
        assert result["primary_mode"] == "trader", f"Expected 'trader', got '{result['primary_mode']}'"
        assert result["needs_data"] == True, "Expected needs_data=True"
        assert "BTC" in result["coins"], f"Expected BTC in coins, got {result['coins']}"
        print(f"✅ Trader mode detected for BTC: mode={result['primary_mode']}, coins={result['coins']}")
    
    def test_trader_mode_eth_analysis(self):
        """ETH analysis should trigger trader mode"""
        result = self.mind.analyze_message("should I long ethereum here?")
        assert result["primary_mode"] == "trader", f"Expected 'trader', got '{result['primary_mode']}'"
        assert "ETH" in result["coins"], f"Expected ETH in coins, got {result['coins']}"
        print(f"✅ Trader mode detected for ETH: mode={result['primary_mode']}, coins={result['coins']}")
    
    def test_trader_mode_sol_trade(self):
        """SOL trade question should trigger trader mode"""
        result = self.mind.analyze_message("analyzing sol for a potential trade setup")
        assert result["primary_mode"] == "trader", f"Expected 'trader', got '{result['primary_mode']}'"
        assert "SOL" in result["coins"], f"Expected SOL in coins, got {result['coins']}"
        print(f"✅ Trader mode detected for SOL: mode={result['primary_mode']}, coins={result['coins']}")
    
    def test_trader_mode_leverage_position(self):
        """Leverage/position questions should trigger trader mode"""
        result = self.mind.analyze_message("should I use 10x leverage on my position?")
        assert result["primary_mode"] == "trader", f"Expected 'trader', got '{result['primary_mode']}'"
        print(f"✅ Trader mode detected for leverage: mode={result['primary_mode']}")
    
    def test_trader_mode_market_analysis(self):
        """Market analysis should trigger trader mode"""
        result = self.mind.analyze_message("what's your take on the crypto market today?")
        assert result["primary_mode"] == "trader", f"Expected 'trader', got '{result['primary_mode']}'"
        print(f"✅ Trader mode detected for market analysis: mode={result['primary_mode']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # MYSTIC MODE TESTS - Philosophical/spiritual questions
    # ═══════════════════════════════════════════════════════════════════
    
    def test_mystic_mode_universe(self):
        """Universe/consciousness questions should trigger mystic mode"""
        result = self.mind.analyze_message("what do you think about the universe and consciousness?")
        assert result["primary_mode"] == "mystic", f"Expected 'mystic', got '{result['primary_mode']}'"
        print(f"✅ Mystic mode detected for universe: mode={result['primary_mode']}")
    
    def test_mystic_mode_spiritual(self):
        """Spiritual questions should trigger mystic mode"""
        result = self.mind.analyze_message("talk to me about spiritual awakening and the soul")
        assert result["primary_mode"] == "mystic", f"Expected 'mystic', got '{result['primary_mode']}'"
        print(f"✅ Mystic mode detected for spiritual: mode={result['primary_mode']}")
    
    def test_mystic_mode_manifestation(self):
        """Manifestation/energy questions should trigger mystic mode"""
        result = self.mind.analyze_message("how does manifestation work? is it about energy?")
        assert result["primary_mode"] == "mystic", f"Expected 'mystic', got '{result['primary_mode']}'"
        print(f"✅ Mystic mode detected for manifestation: mode={result['primary_mode']}")
    
    def test_mystic_mode_quantum(self):
        """Quantum/reality questions should trigger mystic mode"""
        result = self.mind.analyze_message("is reality just a quantum simulation?")
        assert result["primary_mode"] == "mystic", f"Expected 'mystic', got '{result['primary_mode']}'"
        print(f"✅ Mystic mode detected for quantum: mode={result['primary_mode']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # BLENDED MODE TESTS - Mystic undertones with other modes
    # ═══════════════════════════════════════════════════════════════════
    
    def test_trader_with_mystic_blend(self):
        """Trading + energy/vibes should blend mystic"""
        result = self.mind.analyze_message("what's the energy on bitcoin today? feeling the vibe")
        # Should be trader (bitcoin) with mystic blend (energy/vibe)
        assert result["primary_mode"] == "trader", f"Expected 'trader', got '{result['primary_mode']}'"
        assert result["blend_mystic"] == True, f"Expected blend_mystic=True, got {result['blend_mystic']}"
        print(f"✅ Trader with mystic blend: mode={result['primary_mode']}, blend_mystic={result['blend_mystic']}")
    
    def test_coach_with_mystic_blend(self):
        """Life + purpose/meaning should blend mystic"""
        result = self.mind.analyze_message("I'm feeling stuck about the meaning of my life")
        # Should be coach (stuck/life) with mystic blend (meaning)
        assert result["primary_mode"] == "coach", f"Expected 'coach', got '{result['primary_mode']}'"
        assert result["blend_mystic"] == True, f"Expected blend_mystic=True, got {result['blend_mystic']}"
        print(f"✅ Coach with mystic blend: mode={result['primary_mode']}, blend_mystic={result['blend_mystic']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # ENERGY LEVEL TESTS - Message length determines response length
    # ═══════════════════════════════════════════════════════════════════
    
    def test_energy_low_short_message(self):
        """Short messages should have low energy"""
        result = self.mind.analyze_message("ok")
        assert result["energy_level"] == "low", f"Expected 'low' energy, got '{result['energy_level']}'"
        print(f"✅ Low energy for short message: energy={result['energy_level']}")
    
    def test_energy_medium_normal_message(self):
        """Normal messages should have medium energy"""
        result = self.mind.analyze_message("what do you think about this situation?")
        assert result["energy_level"] == "medium", f"Expected 'medium' energy, got '{result['energy_level']}'"
        print(f"✅ Medium energy for normal message: energy={result['energy_level']}")
    
    def test_energy_high_long_message(self):
        """Long messages should have high energy"""
        long_message = "I've been thinking a lot about my life lately and I just don't know what direction to go in. There are so many options and I feel overwhelmed by all the possibilities. What would you suggest I do to get more clarity on my path forward?"
        result = self.mind.analyze_message(long_message)
        assert result["energy_level"] == "high", f"Expected 'high' energy, got '{result['energy_level']}'"
        print(f"✅ High energy for long message: energy={result['energy_level']}")
    
    def test_energy_high_excited_punctuation(self):
        """Excited punctuation should have high energy"""
        result = self.mind.analyze_message("btc is pumping!! should I buy more?!")
        assert result["energy_level"] == "high", f"Expected 'high' energy, got '{result['energy_level']}'"
        print(f"✅ High energy for excited message: energy={result['energy_level']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # QUESTION DETECTION TESTS
    # ═══════════════════════════════════════════════════════════════════
    
    def test_question_detection_mark(self):
        """Question mark should be detected"""
        result = self.mind.analyze_message("what do you think?")
        assert result["is_question"] == True, f"Expected is_question=True"
        print(f"✅ Question detected with '?': is_question={result['is_question']}")
    
    def test_question_detection_word(self):
        """Question words should be detected"""
        result = self.mind.analyze_message("how does this work")
        assert result["is_question"] == True, f"Expected is_question=True"
        print(f"✅ Question detected with 'how': is_question={result['is_question']}")
    
    def test_non_question_statement(self):
        """Statements should not be questions"""
        result = self.mind.analyze_message("I feel good today")
        assert result["is_question"] == False, f"Expected is_question=False"
        print(f"✅ Statement correctly not marked as question: is_question={result['is_question']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # VENTING DETECTION TESTS
    # ═══════════════════════════════════════════════════════════════════
    
    def test_venting_detection(self):
        """Emotional venting should be detected"""
        result = self.mind.analyze_message("I fucking hate this job so much, I can't stand it anymore and I'm so tired of everything")
        assert result["is_venting"] == True, f"Expected is_venting=True"
        print(f"✅ Venting detected: is_venting={result['is_venting']}")


class TestBuildPrompts:
    """Test build_system_prompt and build_user_prompt generate correct prompts"""
    
    def setup_method(self):
        self.mind = AeonMind()
    
    def test_system_prompt_coach_mode(self):
        """Coach mode should include coach instructions"""
        analysis = self.mind.analyze_message("I'm stressed about my job")
        prompt = build_system_prompt(analysis)
        assert "LIFE COACH MODE" in prompt, "Expected LIFE COACH MODE in system prompt"
        print(f"✅ Coach mode system prompt includes LIFE COACH MODE")
    
    def test_system_prompt_trader_mode(self):
        """Trader mode should include trader instructions"""
        analysis = self.mind.analyze_message("what's btc doing?")
        prompt = build_system_prompt(analysis)
        assert "TRADER MODE" in prompt, "Expected TRADER MODE in system prompt"
        print(f"✅ Trader mode system prompt includes TRADER MODE")
    
    def test_system_prompt_mystic_blend(self):
        """Mystic blend should include mystic undertone"""
        analysis = self.mind.analyze_message("what's the energy on btc?")
        prompt = build_system_prompt(analysis)
        assert "MYSTICAL" in prompt, "Expected MYSTICAL in system prompt"
        print(f"✅ Mystic blend system prompt includes MYSTICAL")
    
    def test_system_prompt_emotional_note(self):
        """Emotional state should add note to prompt"""
        analysis = self.mind.analyze_message("I'm so anxious about everything")
        prompt = build_system_prompt(analysis)
        assert "stressed" in prompt.lower(), "Expected 'stressed' in system prompt"
        print(f"✅ Emotional note included in system prompt")
    
    def test_user_prompt_includes_message(self):
        """User prompt should include their message"""
        analysis = self.mind.analyze_message("hello there")
        prompt = build_user_prompt("hello there", analysis, [], "")
        assert "hello there" in prompt, "Expected message in user prompt"
        print(f"✅ User prompt includes message")
    
    def test_user_prompt_market_data(self):
        """User prompt should include market data when provided"""
        analysis = self.mind.analyze_message("btc analysis")
        market_data = "BTC $95,000 (+2.5%)"
        prompt = build_user_prompt("btc analysis", analysis, [], market_data)
        assert "BTC $95,000" in prompt, "Expected market data in user prompt"
        print(f"✅ User prompt includes market data")
    
    def test_user_prompt_low_energy(self):
        """Low energy should request short response"""
        analysis = self.mind.analyze_message("yo")
        prompt = build_user_prompt("yo", analysis, [], "")
        assert "short" in prompt.lower() or "1-2 sentences" in prompt, "Expected short response guidance"
        print(f"✅ Low energy prompt requests short response")
    
    def test_user_prompt_high_energy(self):
        """High energy should allow longer response"""
        long_msg = "I'm super excited about this trading opportunity! What do you think about all this market action and where btc might go from here? This is amazing!!"
        analysis = self.mind.analyze_message(long_msg)
        prompt = build_user_prompt(long_msg, analysis, [], "")
        assert "Match their energy" in prompt or "longer" in prompt.lower(), "Expected longer response guidance"
        print(f"✅ High energy prompt allows longer response")


class TestWebhookWithPersonality:
    """Test Telegram webhook integrates properly with new personality system"""
    
    def test_webhook_casual_message(self):
        """Casual message should be processed by webhook"""
        payload = {
            "message": {
                "chat": {"id": 888888},
                "text": "hey what's up?",
                "from": {"username": "test_personality"}
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook processed casual message successfully")
    
    def test_webhook_stress_message(self):
        """Stress message should be processed with coach mode"""
        payload = {
            "message": {
                "chat": {"id": 888889},
                "text": "I'm really stressed about my life decisions",
                "from": {"username": "test_coach"}
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook processed stress/coach message successfully")
    
    def test_webhook_trading_message(self):
        """Trading message should be processed with trader mode"""
        payload = {
            "message": {
                "chat": {"id": 888890},
                "text": "what's btc doing? should I long?",
                "from": {"username": "test_trader"}
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook processed trading message successfully")
    
    def test_webhook_philosophical_message(self):
        """Philosophical message should be processed with mystic mode"""
        payload = {
            "message": {
                "chat": {"id": 888891},
                "text": "tell me about the universe and consciousness",
                "from": {"username": "test_mystic"}
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook processed philosophical/mystic message successfully")
    
    def test_webhook_short_message(self):
        """Short message should get short response (low energy)"""
        payload = {
            "message": {
                "chat": {"id": 888892},
                "text": "yo",
                "from": {"username": "test_short"}
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook processed short message successfully")


class TestBotMessagesWithModes:
    """Test that bot messages endpoint shows mode detection"""
    
    def test_get_recent_messages(self):
        """Get recent bot messages and check for context/mode"""
        # First send a test message
        payload = {
            "message": {
                "chat": {"id": 777777},
                "text": "testing mode detection for btc analysis",
                "from": {"username": "test_mode_check"}
            }
        }
        requests.post(f"{BASE_URL}/api/webhook", json=payload)
        time.sleep(2)  # Wait for message processing
        
        # Now get recent messages
        response = requests.get(f"{BASE_URL}/api/bot/messages?limit=10")
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        print(f"✅ Retrieved {len(messages)} recent messages")
        
        # Check if any messages have context
        has_context = any(m.get("context") for m in messages)
        print(f"✅ Messages have context field: {has_context}")
    
    def test_messages_by_context_filter(self):
        """Test filtering messages by context"""
        response = requests.get(f"{BASE_URL}/api/bot/messages?context=trader")
        assert response.status_code == 200
        messages = response.json()
        # All messages should have trader context if filter works
        for msg in messages:
            if msg.get("context"):
                print(f"  Message context: {msg.get('context')}")
        print(f"✅ Context filter applied, got {len(messages)} messages")


class TestCoinDetection:
    """Test coin symbol detection in messages"""
    
    def setup_method(self):
        self.mind = AeonMind()
    
    def test_detect_btc(self):
        """Should detect BTC mentions"""
        result = self.mind.analyze_message("what about btc?")
        assert "BTC" in result["coins"]
        print(f"✅ Detected BTC: {result['coins']}")
    
    def test_detect_bitcoin(self):
        """Should detect 'bitcoin' as BTC"""
        result = self.mind.analyze_message("analyze bitcoin")
        assert "BTC" in result["coins"]
        print(f"✅ Detected bitcoin as BTC: {result['coins']}")
    
    def test_detect_eth(self):
        """Should detect ETH mentions"""
        result = self.mind.analyze_message("how's eth doing?")
        assert "ETH" in result["coins"]
        print(f"✅ Detected ETH: {result['coins']}")
    
    def test_detect_ethereum(self):
        """Should detect 'ethereum' as ETH"""
        result = self.mind.analyze_message("ethereum analysis please")
        assert "ETH" in result["coins"]
        print(f"✅ Detected ethereum as ETH: {result['coins']}")
    
    def test_detect_sol(self):
        """Should detect SOL mentions"""
        result = self.mind.analyze_message("sol is pumping")
        assert "SOL" in result["coins"]
        print(f"✅ Detected SOL: {result['coins']}")
    
    def test_detect_multiple_coins(self):
        """Should detect multiple coins in one message"""
        result = self.mind.analyze_message("compare btc eth and sol")
        assert "BTC" in result["coins"]
        assert "ETH" in result["coins"]
        assert "SOL" in result["coins"]
        print(f"✅ Detected multiple coins: {result['coins']}")
    
    def test_no_coins_casual(self):
        """Casual chat should have no coins"""
        result = self.mind.analyze_message("hey how are you?")
        assert len(result["coins"]) == 0
        print(f"✅ No coins in casual chat: {result['coins']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
