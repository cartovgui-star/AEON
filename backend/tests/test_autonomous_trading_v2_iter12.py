"""
ITERATION 12 - Autonomous Trading V2 Tests
Tests the autonomous trading engine that was fixed (record_prediction method name issue)
Verifies:
1. Trading is ACTIVE and executing paper trades
2. Open trades have correct structure
3. Stats endpoint returns correct data
4. Settings persistence (min_confidence should be 70)
5. Opportunities endpoint returns signals
"""
import pytest
import requests
import os

# Use the public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-bot.preview.emergentagent.com')


class TestAutonomousTradingV2Stats:
    """Tests for /api/trading/v2/stats endpoint - Verifies trading engine status"""
    
    def test_trading_stats_returns_200(self):
        """Verify stats endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Stats endpoint returns 200")
    
    def test_trading_is_active(self):
        """CRITICAL: Verify autonomous trading is ACTIVE"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        assert "active" in data, "Missing 'active' field in stats"
        assert data["active"] == True, f"Trading should be ACTIVE, got {data['active']}"
        print(f"✓ Trading is ACTIVE: {data['active']}")
    
    def test_trading_has_open_trades(self):
        """CRITICAL: Verify trades are being opened (bug was fixed)"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        assert "open_trades" in data, "Missing 'open_trades' field"
        assert data["open_trades"] > 0, f"Should have open trades, got {data['open_trades']}"
        print(f"✓ Open trades count: {data['open_trades']}")
    
    def test_trading_stats_structure(self):
        """Verify all required fields exist in stats"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        required_fields = [
            "active", "total_signals_analyzed", "total_trades", 
            "open_trades", "closed_trades", "wins", "losses",
            "win_rate", "total_pnl_pct", "market_regime", 
            "btc_bias", "fear_greed", "min_confidence", "timestamp"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✓ All {len(required_fields)} required fields present")
    
    def test_min_confidence_setting_persisted(self):
        """Verify min_confidence is 70 (persisted setting)"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        assert "min_confidence" in data, "Missing 'min_confidence' field"
        assert data["min_confidence"] == 70, f"min_confidence should be 70, got {data['min_confidence']}"
        print(f"✓ min_confidence persisted correctly: {data['min_confidence']}")
    
    def test_total_trades_reflects_execution(self):
        """Verify total_trades shows trades have been executed"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        assert "total_trades" in data, "Missing 'total_trades' field"
        assert data["total_trades"] > 0, f"total_trades should be > 0, got {data['total_trades']}"
        print(f"✓ Total trades executed: {data['total_trades']}")


class TestAutonomousTradingV2Open:
    """Tests for /api/trading/v2/open endpoint - Verifies open trades structure"""
    
    def test_open_trades_returns_200(self):
        """Verify open endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Open trades endpoint returns 200")
    
    def test_open_trades_has_array(self):
        """Verify response contains trades array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        data = response.json()
        
        assert "open_trades" in data, "Missing 'open_trades' field"
        assert isinstance(data["open_trades"], list), "open_trades should be a list"
        assert "total_open" in data, "Missing 'total_open' field"
        print(f"✓ Open trades array with {data['total_open']} trades")
    
    def test_open_trades_have_correct_structure(self):
        """CRITICAL: Verify each trade has proper structure"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        data = response.json()
        
        if len(data["open_trades"]) == 0:
            pytest.skip("No open trades to verify structure")
        
        trade = data["open_trades"][0]
        
        # These fields are critical for the trading display
        required_fields = [
            "id", "symbol", "direction", "entry_price", 
            "stop_price", "target_price", "confidence", 
            "confirmations", "timeframe", "status"
        ]
        
        for field in required_fields:
            assert field in trade, f"Trade missing required field: {field}"
        
        # Validate field types
        assert trade["direction"] in ["LONG", "SHORT"], f"Invalid direction: {trade['direction']}"
        assert isinstance(trade["entry_price"], (int, float)), "entry_price should be numeric"
        assert isinstance(trade["stop_price"], (int, float)), "stop_price should be numeric"
        assert isinstance(trade["target_price"], (int, float)), "target_price should be numeric"
        assert isinstance(trade["confidence"], (int, float)), "confidence should be numeric"
        assert isinstance(trade["confirmations"], list), "confirmations should be a list"
        
        print(f"✓ Trade structure validated: {trade['symbol']} {trade['direction']}")
        print(f"  Entry: ${trade['entry_price']}, Stop: ${trade['stop_price']}, Target: ${trade['target_price']}")
    
    def test_open_trades_have_valid_prices(self):
        """Verify stop and target prices make sense relative to entry"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        data = response.json()
        
        if len(data["open_trades"]) == 0:
            pytest.skip("No open trades to verify")
        
        for trade in data["open_trades"][:3]:  # Check first 3 trades
            entry = trade["entry_price"]
            stop = trade["stop_price"]
            target = trade["target_price"]
            direction = trade["direction"]
            
            if direction == "LONG":
                # For LONG: stop < entry < target
                assert stop < entry, f"LONG stop ({stop}) should be < entry ({entry})"
                assert target > entry, f"LONG target ({target}) should be > entry ({entry})"
            else:
                # For SHORT: stop > entry > target
                assert stop > entry, f"SHORT stop ({stop}) should be > entry ({entry})"
                assert target < entry, f"SHORT target ({target}) should be < entry ({entry})"
        
        print("✓ Price logic validated for trades")


class TestAutonomousTradingOpportunities:
    """Tests for /api/trading/opportunities endpoint"""
    
    def test_opportunities_returns_200(self):
        """Verify opportunities endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Opportunities endpoint returns 200")
    
    def test_opportunities_returns_array(self):
        """Verify response is an array of opportunities"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities")
        data = response.json()
        
        assert isinstance(data, list), f"Expected array, got {type(data)}"
        print(f"✓ Got {len(data)} opportunities")
    
    def test_opportunities_have_structure(self):
        """Verify opportunity structure"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities")
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No opportunities currently")
        
        opp = data[0]
        required_fields = [
            "symbol", "timeframe", "direction", "confidence",
            "confirmations", "price", "entry", "stop", "target"
        ]
        
        for field in required_fields:
            assert field in opp, f"Opportunity missing field: {field}"
        
        assert opp["direction"] in ["LONG", "SHORT"], f"Invalid direction: {opp['direction']}"
        assert 0 <= opp["confidence"] <= 100, f"Invalid confidence: {opp['confidence']}"
        
        print(f"✓ Opportunity: {opp['symbol']} {opp['direction']} @ {opp['confidence']}% confidence")


class TestAutonomousTradingV2Closed:
    """Tests for /api/trading/v2/closed endpoint"""
    
    def test_closed_trades_returns_200(self):
        """Verify closed trades endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Closed trades endpoint returns 200")
    
    def test_closed_trades_structure(self):
        """Verify closed trades response structure"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        data = response.json()
        
        assert "closed_trades" in data, "Missing 'closed_trades' field"
        assert "total_closed" in data, "Missing 'total_closed' field"
        assert isinstance(data["closed_trades"], list), "closed_trades should be a list"
        
        print(f"✓ Total closed trades: {data['total_closed']}")


class TestTradingToggle:
    """Tests for trading toggle functionality"""
    
    def test_toggle_endpoint_works(self):
        """Verify toggle endpoint responds"""
        # Get current state
        stats_response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        current_state = stats_response.json().get("active", True)
        
        # Try toggling (but keep it on after test)
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active={current_state}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "active" in data, "Missing 'active' in response"
        assert "engine" in data, "Missing 'engine' in response"
        
        print(f"✓ Toggle works - Engine: {data.get('engine')}, Active: {data.get('active')}")


class TestTradingConfidence:
    """Tests for confidence threshold setting"""
    
    def test_confidence_endpoint_works(self):
        """Verify confidence setting endpoint"""
        # Set to 70 (should already be 70)
        response = requests.post(f"{BASE_URL}/api/trading/v2/confidence?min_conf=70")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "min_confidence" in data, "Missing 'min_confidence' in response"
        assert data["min_confidence"] == 70, f"Expected 70, got {data['min_confidence']}"
        
        print(f"✓ Confidence setting works: {data['min_confidence']}%")


class TestLegacyTradingEndpoints:
    """Tests for backward-compatible v1 endpoints"""
    
    def test_trading_summary_endpoint(self):
        """Verify /trading/summary works (v2 stats)"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        print("✓ /trading/summary works")
    
    def test_trading_strategy_endpoint(self):
        """Verify /trading/strategy works (v1 legacy)"""
        response = requests.get(f"{BASE_URL}/api/trading/strategy")
        assert response.status_code == 200
        data = response.json()
        assert "note" in data  # Should mention v1 legacy
        print("✓ /trading/strategy (v1 legacy) works")


class TestTradingAnalyze:
    """Tests for single symbol analysis"""
    
    def test_analyze_btc(self):
        """Analyze BTC with v2 engine"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/BTC")
        # May return None if no signal, that's OK
        assert response.status_code == 200
        data = response.json()
        
        if data is not None:
            print(f"✓ BTC analysis: {data.get('direction', 'N/A')} @ {data.get('confidence', 'N/A')}%")
        else:
            print("✓ BTC analysis: No signal (confidence too low)")


class TestIntegrationEndToEnd:
    """End-to-end integration tests"""
    
    def test_full_trading_flow(self):
        """Verify the full trading data flow works"""
        # 1. Check stats
        stats = requests.get(f"{BASE_URL}/api/trading/v2/stats").json()
        assert stats["active"] == True, "Trading should be active"
        
        # 2. Check open trades match stats
        open_trades = requests.get(f"{BASE_URL}/api/trading/v2/open").json()
        assert open_trades["total_open"] == stats["open_trades"], "Open trades count mismatch"
        
        # 3. Check opportunities are being generated
        opportunities = requests.get(f"{BASE_URL}/api/trading/opportunities").json()
        # May or may not have opportunities based on market conditions
        
        print(f"✓ Full flow verified:")
        print(f"  - Active: {stats['active']}")
        print(f"  - Open trades: {stats['open_trades']}")
        print(f"  - Total trades: {stats['total_trades']}")
        print(f"  - Current opportunities: {len(opportunities)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
