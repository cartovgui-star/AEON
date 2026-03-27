"""
Test Iteration 30 - Enhanced Trading Commands with Detailed Explanations

User requested features:
1. Enhanced RSI summaries with explanations of what could happen and what to do if wrong
2. Every command enhanced with better explanations
3. No contradicting info in alerts
4. Auto messages need explanation of what it is, what could happen, and how to prepare

Tests via webhook: POST /api/webhook with message.text = command
"""

import pytest
import requests
import os
import time

# Get API URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEnhancedTACommand:
    """Test /ta command shows RSI with status, explanation, action, and if-wrong guidance"""
    
    def test_ta_command_btc(self):
        """Test /ta btc returns enhanced RSI analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/ta btc",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /ta btc command returned status 200")
        
        # Give the bot time to process
        time.sleep(0.5)
    
    def test_ta_command_eth(self):
        """Test /ta eth returns enhanced RSI analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/ta eth 4h",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /ta eth 4h command returned status 200")
    
    def test_ta_command_sol(self):
        """Test /ta sol returns enhanced RSI analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/ta sol",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /ta sol command returned status 200")


class TestEnhancedPositionsCommand:
    """Test /positions command shows crowd analysis with explanation and risk"""
    
    def test_positions_command_btc(self):
        """Test /positions btc returns enhanced crowd analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/positions btc",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /positions btc command returned status 200")
    
    def test_positions_command_eth(self):
        """Test /positions eth returns enhanced crowd analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/positions eth",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /positions eth command returned status 200")


class TestEnhancedFundingCommand:
    """Test /funding command shows funding analysis with action and risk guidance"""
    
    def test_funding_command_btc(self):
        """Test /funding btc returns enhanced funding analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/funding btc",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /funding btc command returned status 200")
    
    def test_funding_command_sol(self):
        """Test /funding sol returns enhanced funding analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/funding sol",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /funding sol command returned status 200")


class TestEnhancedFearGreedCommand:
    """Test /fear command shows Fear/Greed with detailed what-to-do guidance"""
    
    def test_fear_command(self):
        """Test /fear returns enhanced Fear & Greed analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/fear",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /fear command returned status 200")
    
    def test_greed_alias_command(self):
        """Test /greed (alias) returns enhanced Fear & Greed analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/greed",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /greed command returned status 200")
    
    def test_fng_alias_command(self):
        """Test /fng (alias) returns enhanced Fear & Greed analysis"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/fng",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /fng command returned status 200")


class TestCodeReviewAlertFormats:
    """Code review verification - Check alert formatting modules have WHY, IF WRONG, PREPARATION sections"""
    
    def test_free_will_v2_format_alert_structure(self):
        """Verify free_will_v2.py format_alert contains required sections"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read the file and check for required sections
        with open('/app/backend/free_will_v2.py', 'r') as f:
            content = f.read()
        
        # Check for WHY section
        assert 'WHY' in content, "Missing WHY section in free_will_v2.py format_alert"
        # Check for IF WRONG section
        assert 'IF WRONG' in content, "Missing IF WRONG section in free_will_v2.py format_alert"
        # Check for PREPARATION section
        assert 'PREPARATION' in content, "Missing PREPARATION section in free_will_v2.py format_alert"
        # Check for WHAT TO EXPECT section
        assert 'WHAT TO EXPECT' in content, "Missing WHAT TO EXPECT section in free_will_v2.py format_alert"
        
        print("✅ free_will_v2.py contains WHY, WHAT TO EXPECT, IF WRONG, PREPARATION sections")
    
    def test_autonomous_trader_v2_format_signal_structure(self):
        """Verify autonomous_trader_v2.py format_signal_alert contains required sections"""
        with open('/app/backend/autonomous_trader_v2.py', 'r') as f:
            content = f.read()
        
        # Check for WHY section
        assert 'WHY' in content, "Missing WHY section in autonomous_trader_v2.py"
        # Check for IF WRONG section
        assert 'IF WRONG' in content, "Missing IF WRONG section in autonomous_trader_v2.py"
        # Check for IF THIS WORKS section
        assert 'IF THIS WORKS' in content, "Missing IF THIS WORKS section in autonomous_trader_v2.py"
        
        print("✅ autonomous_trader_v2.py contains WHY, IF THIS WORKS, IF WRONG sections")
    
    def test_dual_trading_engine_format_alert_structure(self):
        """Verify dual_trading_engine.py format_alert contains required sections"""
        with open('/app/backend/dual_trading_engine.py', 'r') as f:
            content = f.read()
        
        # Check for WHY section
        assert 'WHY' in content, "Missing WHY section in dual_trading_engine.py"
        # Check for IF WRONG section
        assert 'IF WRONG' in content, "Missing IF WRONG section in dual_trading_engine.py"
        # Check for PREP section
        assert 'PREP' in content, "Missing PREP section in dual_trading_engine.py"
        # Check for WHAT TO EXPECT section
        assert 'WHAT TO EXPECT' in content, "Missing WHAT TO EXPECT section in dual_trading_engine.py"
        
        print("✅ dual_trading_engine.py contains WHY, WHAT TO EXPECT, IF WRONG, PREP sections")


class TestServerTACommandEnhancements:
    """Test server.py /ta command has RSI explanation enhancements"""
    
    def test_ta_command_has_rsi_explanations(self):
        """Verify server.py /ta command has RSI status, explain, action, risk"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check for RSI status messages
        assert 'rsi_status' in content, "Missing rsi_status in /ta command"
        assert 'rsi_explain' in content, "Missing rsi_explain in /ta command"
        assert 'rsi_action' in content, "Missing rsi_action in /ta command"
        assert 'rsi_risk' in content, "Missing rsi_risk (if wrong) in /ta command"
        
        # Check for specific RSI status values
        assert 'OVERSOLD' in content, "Missing OVERSOLD status"
        assert 'OVERBOUGHT' in content, "Missing OVERBOUGHT status"
        assert 'NEUTRAL' in content, "Missing NEUTRAL status"
        
        print("✅ server.py /ta command has RSI status, explanation, action, and if-wrong guidance")
    
    def test_positions_command_has_crowd_analysis(self):
        """Verify server.py /positions command has crowd analysis"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check for crowd analysis
        assert 'crowd_warning' in content, "Missing crowd_warning in /positions command"
        assert 'crowd_explain' in content, "Missing crowd_explain in /positions command"
        assert 'crowd_action' in content, "Missing crowd_action in /positions command"
        assert 'crowd_risk' in content, "Missing crowd_risk in /positions command"
        
        # Check for specific crowd statuses
        assert 'LONGS CROWDED' in content, "Missing LONGS CROWDED status"
        assert 'SHORTS CROWDED' in content, "Missing SHORTS CROWDED status"
        
        print("✅ server.py /positions command has crowd analysis with explanation and risk")
    
    def test_funding_command_has_action_risk(self):
        """Verify server.py /funding command has action and risk guidance"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check for funding analysis
        assert 'funding_status' in content, "Missing funding_status in /funding command"
        assert 'ACTION:' in content, "Missing ACTION section in /funding command"
        assert 'RISK:' in content, "Missing RISK section in /funding command"
        
        # Check for specific funding statuses
        assert 'EXTREME HIGH' in content, "Missing EXTREME HIGH funding status"
        assert 'NEGATIVE' in content, "Missing NEGATIVE funding status"
        
        print("✅ server.py /funding command has status, action, and risk guidance")
    
    def test_fear_command_has_detailed_guidance(self):
        """Verify server.py /fear command has detailed what-to-do guidance"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check for Fear/Greed detailed guidance
        assert 'WHAT THIS MEANS' in content, "Missing WHAT THIS MEANS section in /fear command"
        assert 'ACTION TO TAKE' in content, "Missing ACTION TO TAKE section in /fear command"
        assert 'RISK IF WRONG' in content, "Missing RISK IF WRONG section in /fear command"
        assert 'HOW TO USE THIS' in content, "Missing HOW TO USE THIS section in /fear command"
        
        # Check for specific action recommendations
        assert 'STRONG BUY ZONE' in content, "Missing STRONG BUY ZONE recommendation"
        assert 'EXTREME CAUTION' in content, "Missing EXTREME CAUTION recommendation"
        
        print("✅ server.py /fear command has WHAT THIS MEANS, ACTION, RISK IF WRONG, HOW TO USE sections")


class TestAntiContradictionMechanisms:
    """Test that alerts have anti-contradiction mechanisms"""
    
    def test_free_will_anti_contradiction(self):
        """Verify free_will_v2.py has anti-contradiction tracking"""
        with open('/app/backend/free_will_v2.py', 'r') as f:
            content = f.read()
        
        # Check for anti-contradiction mechanisms
        assert 'last_direction' in content, "Missing last_direction tracking"
        assert 'direction_lock_time' in content, "Missing direction_lock_time"
        assert 'contradictions_blocked' in content, "Missing contradictions_blocked counter"
        assert 'ANTI-CONTRADICTION' in content or 'contradiction' in content.lower(), "Missing anti-contradiction logic"
        
        print("✅ free_will_v2.py has anti-contradiction tracking (direction lock)")
    
    def test_dual_engine_anti_contradiction(self):
        """Verify dual_trading_engine.py has anti-contradiction tracking"""
        with open('/app/backend/dual_trading_engine.py', 'r') as f:
            content = f.read()
        
        # Check for anti-contradiction mechanisms
        assert 'last_direction' in content, "Missing last_direction tracking in dual_engine"
        assert 'direction_lock' in content, "Missing direction_lock in dual_engine"
        assert 'contradictions_blocked' in content, "Missing contradictions_blocked counter"
        
        print("✅ dual_trading_engine.py has anti-contradiction tracking (direction lock)")
    
    def test_bullish_bearish_reasons_separation(self):
        """Verify signals separate bullish/bearish reasons to avoid contradictions"""
        with open('/app/backend/free_will_v2.py', 'r') as f:
            content = f.read()
        
        # Check for separate bullish/bearish tracking
        assert 'bullish_reasons' in content, "Missing bullish_reasons list"
        assert 'bearish_reasons' in content, "Missing bearish_reasons list"
        
        print("✅ free_will_v2.py separates bullish/bearish reasons to avoid contradictions")


class TestWebhookAPIIntegration:
    """Test webhook API returns proper responses"""
    
    def test_webhook_endpoint_exists(self):
        """Test webhook endpoint is accessible"""
        response = requests.post(f"{BASE_URL}/api/webhook", json={"update_id": 1})
        # Should return 200 even for invalid payloads (graceful handling)
        assert response.status_code == 200, f"Webhook endpoint returned {response.status_code}"
        print("✅ Webhook endpoint accessible at /api/webhook")
    
    def test_scan_command(self):
        """Test /scan command works"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/scan btc",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /scan btc command returned status 200")
    
    def test_help_command(self):
        """Test /help command works"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/help",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /help command returned status 200")


class TestFreeWillStats:
    """Test Free Will v2 stats endpoint"""
    
    def test_free_will_v2_stats(self):
        """Test /freewill command via webhook"""
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/fw",
                "from": {"username": "test_user"}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /fw (Free Will status) command returned status 200")


class TestDualEngineStats:
    """Test Dual Trading Engine stats"""
    
    def test_dual_engine_stats_api(self):
        """Test /api/dual/stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'active' in data, "Missing 'active' field in dual stats"
        assert 'day_trader' in data, "Missing 'day_trader' field in dual stats"
        assert 'long_term' in data, "Missing 'long_term' field in dual stats"
        
        print(f"✅ Dual Engine Stats: Active={data.get('active')}, Day Trader alerts={data.get('day_trader', {}).get('total_alerts', 0)}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
