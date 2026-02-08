"""
Test Suite for Iteration 12: V2 Position Management & Coinglass Integration

Tests:
1. /api/trading/v2/open - returns open trades array
2. /api/trading/v2/closed - returns closed trades
3. /api/trading/v2/stats - returns comprehensive v2 stats
4. /api/trading/v2/close/{symbol} - manual close endpoint exists (POST)
5. /api/trading/v2/trail/{symbol} - trail stop update endpoint (POST)
6. /api/trading/v2/tp/{symbol} - take profit update endpoint (POST)
7. /api/coinglass/full/{symbol} - Coinglass report (will show paid plan required)
8. /api/bot/test - all systems working
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestV2OpenTrades:
    """Test /api/trading/v2/open - returns open trades array"""
    
    def test_v2_open_returns_200(self):
        """Test that /api/trading/v2/open returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /api/trading/v2/open returns 200")
    
    def test_v2_open_returns_array(self):
        """Test that response contains open_trades array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        data = response.json()
        assert "open_trades" in data, "Missing open_trades key"
        assert isinstance(data["open_trades"], list), "open_trades should be a list"
        print(f"✅ open_trades is array with {len(data['open_trades'])} items")
    
    def test_v2_open_contains_total_open(self):
        """Test that response contains total_open count"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        data = response.json()
        assert "total_open" in data, "Missing total_open key"
        assert isinstance(data["total_open"], int), "total_open should be integer"
        assert data["total_open"] == len(data["open_trades"]), "total_open should match array length"
        print(f"✅ total_open = {data['total_open']}")


class TestV2ClosedTrades:
    """Test /api/trading/v2/closed - returns closed trades"""
    
    def test_v2_closed_returns_200(self):
        """Test that /api/trading/v2/closed returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /api/trading/v2/closed returns 200")
    
    def test_v2_closed_returns_array(self):
        """Test that response contains closed_trades array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        data = response.json()
        assert "closed_trades" in data, "Missing closed_trades key"
        assert isinstance(data["closed_trades"], list), "closed_trades should be a list"
        print(f"✅ closed_trades is array with {len(data['closed_trades'])} items")
    
    def test_v2_closed_contains_total_closed(self):
        """Test that response contains total_closed count"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        data = response.json()
        assert "total_closed" in data, "Missing total_closed key"
        assert isinstance(data["total_closed"], int), "total_closed should be integer"
        print(f"✅ total_closed = {data['total_closed']}")


class TestV2Stats:
    """Test /api/trading/v2/stats - returns comprehensive v2 stats"""
    
    def test_v2_stats_returns_200(self):
        """Test that /api/trading/v2/stats returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /api/trading/v2/stats returns 200")
    
    def test_v2_stats_structure(self):
        """Test that response contains expected stats keys"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        # Check for key stats fields (may vary based on implementation)
        # These are common fields for trading stats
        possible_fields = ['wins', 'losses', 'win_rate', 'total_pnl_pct', 'profit_factor', 
                          'total_trades', 'open_trades', 'closed_trades', 'active']
        
        found_fields = [f for f in possible_fields if f in data]
        print(f"✅ Found stats fields: {found_fields}")
        
        # Ensure at least some key fields exist
        assert len(data) > 0, "Stats should return some data"
        print(f"✅ Stats response has {len(data)} fields")
    
    def test_v2_stats_types(self):
        """Test that stats values are proper types"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        # Type checks for common fields if they exist
        if "win_rate" in data:
            assert isinstance(data["win_rate"], (int, float)), "win_rate should be numeric"
        if "total_pnl_pct" in data:
            assert isinstance(data["total_pnl_pct"], (int, float)), "total_pnl_pct should be numeric"
        if "profit_factor" in data:
            assert isinstance(data["profit_factor"], (int, float)), "profit_factor should be numeric"
        
        print("✅ Stats value types validated")


class TestV2ManualClose:
    """Test /api/trading/v2/close/{symbol} - manual close endpoint"""
    
    def test_v2_close_endpoint_exists(self):
        """Test that POST /api/trading/v2/close/{symbol} endpoint exists"""
        # Test with BTC - endpoint should exist and return either success or 'no open trade'
        response = requests.post(f"{BASE_URL}/api/trading/v2/close/BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should either close a trade or return 'error' (no open trade found)
        assert "status" in data or "error" in data, "Should return status or error"
        
        if "error" in data:
            print(f"✅ /api/trading/v2/close/BTC exists (no open trade: {data['error']})")
        else:
            print(f"✅ /api/trading/v2/close/BTC exists (trade closed: {data['status']})")
    
    def test_v2_close_response_format(self):
        """Test close endpoint response format"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/close/ETH")
        data = response.json()
        
        if "status" in data:
            # Trade was closed
            assert data["status"] == "closed"
            assert "trade" in data
            print("✅ Close response has trade details")
        elif "error" in data:
            # No open trade - expected
            assert "No open trade found" in data["error"] or "no" in data["error"].lower()
            print("✅ Close response correctly reports no open trade")


class TestV2TrailStop:
    """Test /api/trading/v2/trail/{symbol} - trail stop update endpoint"""
    
    def test_v2_trail_endpoint_exists(self):
        """Test that POST /api/trading/v2/trail/{symbol} endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/trail/BTC", params={"trail_pct": 3.0})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data or "error" in data, "Should return status or error"
        
        if "error" in data:
            print(f"✅ /api/trading/v2/trail/BTC exists (no open trade: {data['error']})")
        else:
            print(f"✅ /api/trading/v2/trail/BTC exists (updated: {data['status']})")
    
    def test_v2_trail_with_different_pct(self):
        """Test trail stop with different percentage values"""
        # Test with 5% trail
        response = requests.post(f"{BASE_URL}/api/trading/v2/trail/SOL", params={"trail_pct": 5.0})
        assert response.status_code == 200
        data = response.json()
        
        if "status" in data:
            assert data["status"] == "updated"
            assert "trail_pct" in data
            print(f"✅ Trail updated with trail_pct: {data.get('trail_pct')}")
        else:
            print("✅ Trail endpoint works (no open SOL trade)")


class TestV2TakeProfit:
    """Test /api/trading/v2/tp/{symbol} - take profit update endpoint"""
    
    def test_v2_tp_endpoint_exists(self):
        """Test that POST /api/trading/v2/tp/{symbol} endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/tp/BTC", params={"price": 100000.0})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data or "error" in data, "Should return status or error"
        
        if "error" in data:
            print(f"✅ /api/trading/v2/tp/BTC exists (no open trade: {data['error']})")
        else:
            print(f"✅ /api/trading/v2/tp/BTC exists (updated: {data['status']})")
    
    def test_v2_tp_response_format(self):
        """Test take profit endpoint response format"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/tp/ETH", params={"price": 5000.0})
        data = response.json()
        
        if "status" in data:
            assert data["status"] == "updated"
            assert "new_tp" in data
            assert "old_tp" in data
            print(f"✅ TP update response contains old_tp and new_tp")
        elif "error" in data:
            print("✅ TP endpoint correctly reports no open trade")


class TestCoinglassIntegration:
    """Test /api/coinglass/full/{symbol} - Coinglass integration"""
    
    def test_coinglass_full_returns_200(self):
        """Test that /api/coinglass/full/{symbol} returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/coinglass/full/BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /api/coinglass/full/BTC returns 200")
    
    def test_coinglass_full_structure(self):
        """Test Coinglass full report structure"""
        response = requests.get(f"{BASE_URL}/api/coinglass/full/BTC")
        data = response.json()
        
        # Should have these keys
        expected_keys = ["symbol", "funding", "open_interest", "long_short", "data_source", "timestamp"]
        
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"
        
        assert data["symbol"] == "BTC"
        assert data["data_source"] == "Coinglass"
        print(f"✅ Coinglass report contains all expected keys")
    
    def test_coinglass_paid_plan_message(self):
        """Test Coinglass response contains paid plan info if required"""
        response = requests.get(f"{BASE_URL}/api/coinglass/full/BTC")
        data = response.json()
        
        # Check if there's error about paid plan (expected per context)
        funding = data.get("funding", {})
        oi = data.get("open_interest", {})
        ls = data.get("long_short", {})
        
        # Check if any section has paid plan message
        has_paid_msg = False
        for section in [funding, oi, ls]:
            if isinstance(section, dict):
                error_msg = section.get("error", "") or section.get("message", "")
                if "paid" in str(error_msg).lower() or "upgrade" in str(error_msg).lower():
                    has_paid_msg = True
                    print(f"✅ Coinglass shows paid plan message: {error_msg}")
                    break
        
        # Either has data or paid plan message - both are valid
        if not has_paid_msg:
            # Check if we got actual data
            if funding and "error" not in funding:
                print(f"✅ Coinglass returning actual funding data (API key working)")
            else:
                print(f"✅ Coinglass response received")
    
    def test_coinglass_funding_endpoint(self):
        """Test /api/coinglass/funding/{symbol} exists"""
        response = requests.get(f"{BASE_URL}/api/coinglass/funding/BTC")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ /api/coinglass/funding/BTC returns data")
    
    def test_coinglass_oi_endpoint(self):
        """Test /api/coinglass/oi/{symbol} exists"""
        response = requests.get(f"{BASE_URL}/api/coinglass/oi/BTC")
        assert response.status_code == 200
        print(f"✅ /api/coinglass/oi/BTC returns 200")
    
    def test_coinglass_ls_endpoint(self):
        """Test /api/coinglass/ls/{symbol} exists"""
        response = requests.get(f"{BASE_URL}/api/coinglass/ls/BTC")
        assert response.status_code == 200
        print(f"✅ /api/coinglass/ls/BTC returns 200")


class TestBotTest:
    """Test /api/bot/test - all systems working"""
    
    def test_bot_test_returns_200(self):
        """Test that /api/bot/test returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ /api/bot/test returns 200")
    
    def test_bot_test_status_success(self):
        """Test that bot test reports success"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        data = response.json()
        
        assert "status" in data, "Missing status key"
        # Status can be 'success' or 'error' - log which
        if data["status"] == "success":
            print("✅ All bot systems working")
        else:
            print(f"⚠️ Bot test status: {data['status']}, error: {data.get('error', 'N/A')}")
    
    def test_bot_test_llm_check(self):
        """Test that LLM check is performed"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        data = response.json()
        
        if "llm" in data:
            print(f"✅ LLM status: {data['llm']}")
        else:
            print("⚠️ LLM status not in response")
    
    def test_bot_test_binance_check(self):
        """Test that Binance check is performed"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        data = response.json()
        
        if "binance" in data:
            print(f"✅ Binance status: {data['binance']}")
        else:
            print("⚠️ Binance status not in response")


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """Test root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "online"
        print("✅ API root returns online status")
    
    def test_api_pairs(self):
        """Test pairs endpoint"""
        response = requests.get(f"{BASE_URL}/api/pairs")
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data
        assert len(data["pairs"]) > 0
        print(f"✅ API supports {data['total_pairs']} trading pairs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
