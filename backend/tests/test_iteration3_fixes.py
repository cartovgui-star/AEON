"""
Test Iteration 3 - Bug Fixes and Feature Verification
Tests:
1. Telegram /price webhook command (P0 fix)
2. Trade type and leverage in live-positions API
3. Previously duplicate endpoints: /alerts/stats, /freewill/stats, /strategies/all/BTC
4. Mounted routers verification: freewill, derivatives, intelligence
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTelegramPriceCommand:
    """Test P0 fix: Telegram /price command should work without errors"""
    
    def test_price_webhook_returns_ok(self):
        """Webhook should return 200 with status ok for /price command"""
        payload = {
            "update_id": 12345678,
            "message": {
                "message_id": 1,
                "from": {"id": 123456789, "is_bot": False, "first_name": "Test", "username": "testuser"},
                "chat": {"id": 123456789, "first_name": "Test", "username": "testuser", "type": "private"},
                "date": 1737374400,
                "text": "/price"
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok, got {data}"

    def test_price_webhook_no_error(self):
        """Verify /price command doesn't cause dict.items() error on list"""
        payload = {
            "update_id": 12345679,
            "message": {
                "message_id": 2,
                "from": {"id": 987654321, "is_bot": False, "first_name": "TestUser2"},
                "chat": {"id": 987654321, "type": "private"},
                "date": 1737374500,
                "text": "/price"
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload, timeout=30)
        assert response.status_code == 200
        # Should not return 500 error


class TestLivePositionsAPI:
    """Test P1 fix: Live positions should include trade_type and leverage"""
    
    def test_live_positions_returns_data(self):
        """API should return live positions"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert "total_positions" in data
        assert "data_source" in data

    def test_live_positions_have_trade_type(self):
        """Each position should have trade_type field"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        positions = data.get("positions", [])
        
        if len(positions) > 0:
            for pos in positions:
                assert "trade_type" in pos, f"Position missing trade_type: {pos.get('symbol')}"
                assert pos["trade_type"] in ["SCALP", "DAY", "SWING"], f"Invalid trade_type: {pos['trade_type']}"
        else:
            pytest.skip("No positions to verify trade_type")

    def test_live_positions_have_leverage(self):
        """Each position should have leverage field"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        positions = data.get("positions", [])
        
        if len(positions) > 0:
            for pos in positions:
                assert "leverage" in pos, f"Position missing leverage: {pos.get('symbol')}"
                assert isinstance(pos["leverage"], (int, float)), f"Invalid leverage type: {type(pos['leverage'])}"
                assert pos["leverage"] > 0, f"Leverage should be positive: {pos['leverage']}"
        else:
            pytest.skip("No positions to verify leverage")

    def test_live_positions_structure(self):
        """Verify complete position structure"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        positions = data.get("positions", [])
        
        required_fields = ["id", "symbol", "direction", "entry_price", "current_price", 
                          "pnl_pct", "trade_type", "leverage", "position_size"]
        
        if len(positions) > 0:
            pos = positions[0]
            for field in required_fields:
                assert field in pos, f"Position missing required field: {field}"


class TestPreviouslyDuplicateEndpoints:
    """Test endpoints that were previously duplicated (removed 168 lines)"""
    
    def test_alerts_stats_endpoint(self):
        """/api/alerts/stats should work (previously duplicate)"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "tracked_symbols" in data
        assert "auto_alerts_enabled" in data

    def test_freewill_stats_endpoint(self):
        """/api/freewill/stats should work (previously duplicate - now uses app_state)"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "min_confidence" in data
        assert "data_sources" in data

    def test_strategies_all_btc_endpoint(self):
        """/api/strategies/all/BTC should work (previously duplicate)"""
        response = requests.get(f"{BASE_URL}/api/strategies/all/BTC")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "overall_signal" in data
        assert "strategies" in data
        assert len(data.get("strategies", [])) > 0


class TestMountedRouters:
    """Test routers that were mounted (freewill, derivatives, intelligence)"""
    
    def test_freewill_router_mounted(self):
        """Freewill router should be accessible"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200

    def test_derivatives_data_endpoint(self):
        """Derivatives router should provide data"""
        response = requests.get(f"{BASE_URL}/api/derivatives/data/BTC")
        assert response.status_code == 200
        data = response.json()
        # Should return derivatives data
        assert "symbol" in data or "open_interest" in data or "funding_rate" in data or len(data) > 0

    def test_intelligence_sentiment_endpoint(self):
        """Intelligence router should provide sentiment"""
        response = requests.get(f"{BASE_URL}/api/intelligence/sentiment/BTC")
        # Allow 200 or 404 (if coin not found), but not 500
        assert response.status_code in [200, 404]


class TestCoreAPIHealth:
    """Basic health checks for core APIs"""
    
    def test_root_endpoint(self):
        """API root should return online status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "online"

    def test_bot_stats(self):
        """Bot stats should return data"""
        response = requests.get(f"{BASE_URL}/api/bot/stats")
        assert response.status_code == 200

    def test_mexc_live_data(self):
        """MEXC live data should work"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        assert "prices" in data or len(data) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
