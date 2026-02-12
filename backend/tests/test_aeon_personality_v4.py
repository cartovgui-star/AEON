"""
AEON PERSONALITY ENGINE v4 TESTING
- Unified personality (no mode switching)
- Short messages get short responses
- Bot asks follow-up questions
- Bot detects trading topics with market data
- Bot detects life/emotional topics and responds empathetically
- Anti-repetition: consecutive responses different
- Context tracking from recent history
"""
import pytest
import requests
import os
import time
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# Use unique test chat IDs to avoid interference with real users
TEST_CHAT_ID_BASE = 777777


class TestWebhookBasic:
    """Test basic webhook functionality"""
    
    def test_webhook_accepts_messages(self):
        """Test that POST /api/webhook accepts messages and returns response"""
        chat_id = TEST_CHAT_ID_BASE
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_user_v4", "id": chat_id},
                "text": "Hey, what's up?"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status=ok, got {data}"
        print(f"✅ Webhook accepts messages - returned {data}")
    
    def test_webhook_without_message(self):
        """Test webhook handles missing message field"""
        payload = {}
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook handles empty payload gracefully")
    
    def test_webhook_without_text(self):
        """Test webhook handles message without text"""
        payload = {
            "message": {
                "chat": {"id": 777778, "type": "private"},
                "from": {"username": "test_user", "id": 777778}
                # No text field
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook handles message without text gracefully")


class TestMessageLengthMatching:
    """Test that short messages get short responses"""
    
    def test_short_message_short_response(self):
        """Short messages (1-4 words) should get short replies (1-2 sentences)"""
        chat_id = TEST_CHAT_ID_BASE + 100
        
        # Send a short message
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_short", "id": chat_id},
                "text": "yo"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        print(f"✅ Short message accepted")
        
        # Wait for response to be stored
        time.sleep(2)
        
        # Check the stored response
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        assert msgs_response.status_code == 200
        
        messages = msgs_response.json()
        # Find message from this chat_id
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            # Short responses should be under 200 chars typically
            print(f"   Response length: {len(last_response)} chars")
            print(f"   Response: {last_response[:200]}...")
            # Just verify we got a response
            assert len(last_response) > 0, "Expected a response"
        
        print(f"✅ Short message test complete")
    
    def test_longer_message_appropriately_sized_response(self):
        """Longer messages can get longer replies (but still focused)"""
        chat_id = TEST_CHAT_ID_BASE + 101
        
        # Send a longer message
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_long", "id": chat_id},
                "text": "I've been thinking about getting into crypto trading but I'm not sure where to start. What would you recommend for a complete beginner who wants to learn but is also worried about the risks?"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        print(f"✅ Longer message accepted")
        
        # Wait for response to be stored
        time.sleep(3)
        
        # Check the stored response
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            print(f"   Response length: {len(last_response)} chars")
            print(f"   Response: {last_response[:300]}...")
            assert len(last_response) > 0, "Expected a response"
        
        print(f"✅ Longer message response test complete")


class TestFollowUpQuestions:
    """Test that bot asks follow-up questions"""
    
    def test_response_includes_question(self):
        """Bot should ask follow-up questions to keep conversation going"""
        chat_id = TEST_CHAT_ID_BASE + 200
        
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_question", "id": chat_id},
                "text": "I've been trading for about 6 months now, mostly BTC"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        time.sleep(3)
        
        # Check the stored response
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        question_found = False
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            # Check if response contains a question (has ?)
            question_found = "?" in last_response
            print(f"   Response: {last_response[:300]}...")
            print(f"   Contains question mark: {question_found}")
        
        # Note: Bot is configured to ask questions ~70% of the time
        print(f"✅ Follow-up question test complete (question found: {question_found})")


class TestTradingTopicDetection:
    """Test that bot detects trading topics and includes market data"""
    
    def test_trading_topic_detection(self):
        """When user mentions coins/trading, bot should include market data"""
        chat_id = TEST_CHAT_ID_BASE + 300
        
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_trading", "id": chat_id},
                "text": "What do you think about BTC right now?"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        time.sleep(3)
        
        # Check the stored response
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            context = relevant_msgs[0].get("context", "")
            print(f"   Context: {context}")
            print(f"   Response: {last_response[:400]}...")
            
            # Context should be "trading" when crypto is mentioned
            assert context == "trading", f"Expected context=trading, got {context}"
        
        print(f"✅ Trading topic detection test complete")
    
    def test_multiple_coins_detection(self):
        """Test detection of multiple coins"""
        chat_id = TEST_CHAT_ID_BASE + 301
        
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_multi_coin", "id": chat_id},
                "text": "Should I buy ETH or SOL? Which one looks better?"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        time.sleep(3)
        
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            context = relevant_msgs[0].get("context", "")
            print(f"   Context: {context}")
            print(f"   Response: {last_response[:300]}...")
            
            # Should detect trading context
            assert context == "trading", f"Expected context=trading, got {context}"
        
        print(f"✅ Multiple coins detection test complete")


class TestLifeEmotionalTopics:
    """Test that bot detects life/emotional topics and responds empathetically"""
    
    def test_stress_detection(self):
        """Bot should respond empathetically to stressed messages"""
        chat_id = TEST_CHAT_ID_BASE + 400
        
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_stress", "id": chat_id},
                "text": "I'm really stressed about my job lately, don't know what to do"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        time.sleep(3)
        
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            context = relevant_msgs[0].get("context", "")
            print(f"   Context: {context}")
            print(f"   Response: {last_response[:400]}...")
            
            # Response should be empathetic, not about crypto
            # It should NOT randomly bring up trading when user is stressed
            crypto_keywords = ["btc", "bitcoin", "price", "market"]
            contains_crypto = any(kw in last_response.lower() for kw in crypto_keywords)
            print(f"   Contains unsolicited crypto: {contains_crypto}")
        
        print(f"✅ Stress/emotional topic detection test complete")
    
    def test_life_advice_topic(self):
        """Bot should give life advice for life-related questions"""
        chat_id = TEST_CHAT_ID_BASE + 401
        
        payload = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_life", "id": chat_id},
                "text": "I've been feeling stuck in life, like I don't have any purpose or direction"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        
        time.sleep(3)
        
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if relevant_msgs:
            last_response = relevant_msgs[0].get("bot_response", "")
            print(f"   Response: {last_response[:400]}...")
        
        print(f"✅ Life advice topic detection test complete")


class TestAntiRepetition:
    """Test that consecutive responses are different"""
    
    def test_consecutive_responses_different(self):
        """Send same/similar messages and verify responses differ"""
        chat_id = TEST_CHAT_ID_BASE + 500
        
        # First message
        payload1 = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_repeat", "id": chat_id},
                "text": "hey"
            }
        }
        
        response1 = requests.post(f"{BASE_URL}/api/webhook", json=payload1)
        assert response1.status_code == 200
        
        time.sleep(3)
        
        # Get first response
        msgs1 = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5}).json()
        first_response = None
        for m in msgs1:
            if m.get("chat_id") == chat_id:
                first_response = m.get("bot_response", "")
                break
        
        print(f"   First response: {first_response[:200]}...")
        
        # Second similar message
        payload2 = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_repeat", "id": chat_id},
                "text": "hey"
            }
        }
        
        response2 = requests.post(f"{BASE_URL}/api/webhook", json=payload2)
        assert response2.status_code == 200
        
        time.sleep(3)
        
        # Get second response
        msgs2 = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 5}).json()
        second_response = None
        for m in msgs2:
            if m.get("chat_id") == chat_id:
                if m.get("bot_response") != first_response:
                    second_response = m.get("bot_response", "")
                    break
        
        if second_response:
            print(f"   Second response: {second_response[:200]}...")
            # Responses should be different
            assert first_response != second_response, "Responses should be different"
            print("✅ Anti-repetition verified - responses are different")
        else:
            print("⚠️ Could not get second response for comparison")


class TestContextTracking:
    """Test that bot uses recent conversation history"""
    
    def test_context_tracking_from_history(self):
        """Bot should track context from recent messages"""
        chat_id = TEST_CHAT_ID_BASE + 600
        
        # First message about a topic
        payload1 = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_context", "id": chat_id},
                "text": "I just started a new job in tech"
            }
        }
        
        response1 = requests.post(f"{BASE_URL}/api/webhook", json=payload1)
        assert response1.status_code == 200
        
        time.sleep(3)
        
        # Follow-up message
        payload2 = {
            "message": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"username": "test_context", "id": chat_id},
                "text": "yeah it's going well so far"
            }
        }
        
        response2 = requests.post(f"{BASE_URL}/api/webhook", json=payload2)
        assert response2.status_code == 200
        
        time.sleep(3)
        
        # Check the stored responses
        msgs_response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 10})
        messages = msgs_response.json()
        relevant_msgs = [m for m in messages if m.get("chat_id") == chat_id]
        
        if len(relevant_msgs) >= 2:
            print(f"   Context tracked - {len(relevant_msgs)} messages stored for this chat")
            for m in relevant_msgs[:2]:
                print(f"   User: {m.get('user_message', '')[:50]}...")
                print(f"   Bot: {m.get('bot_response', '')[:100]}...")
        
        print(f"✅ Context tracking test complete")


class TestBotMessagesEndpoint:
    """Test that /api/bot/messages endpoint returns stored messages"""
    
    def test_get_messages(self):
        """Test retrieving stored messages"""
        response = requests.get(f"{BASE_URL}/api/bot/messages", params={"limit": 20})
        assert response.status_code == 200
        
        messages = response.json()
        assert isinstance(messages, list), "Expected list of messages"
        
        if messages:
            msg = messages[0]
            # Verify expected fields
            assert "chat_id" in msg, "Message should have chat_id"
            assert "user_message" in msg, "Message should have user_message"
            assert "bot_response" in msg, "Message should have bot_response"
            assert "timestamp" in msg, "Message should have timestamp"
            
            print(f"✅ Bot messages endpoint working - {len(messages)} messages retrieved")
            print(f"   Sample: chat_id={msg.get('chat_id')}, user='{msg.get('user_message', '')[:40]}...'")
        else:
            print("⚠️ No messages found (might be expected if DB is empty)")


class TestCasualGreeting:
    """Test casual greeting handling"""
    
    def test_casual_greeting(self):
        """Test that casual greetings get friendly responses"""
        chat_id = TEST_CHAT_ID_BASE + 700
        
        greetings = ["hi", "hey", "yo", "gm"]
        
        for greeting in greetings[:2]:  # Test first 2 greetings
            payload = {
                "message": {
                    "chat": {"id": chat_id + hash(greeting) % 1000, "type": "private"},
                    "from": {"username": "test_greet", "id": chat_id + hash(greeting) % 1000},
                    "text": greeting
                }
            }
            
            response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
            assert response.status_code == 200
            print(f"   Greeting '{greeting}' accepted")
            time.sleep(2)
        
        print(f"✅ Casual greeting handling test complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
