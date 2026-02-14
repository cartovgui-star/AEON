"""
Test file for Iteration 19 - Dual Trading Engine Settings and Price Validation
Tests:
1. /api/dual/stats - Returns correct dual engine status
2. /api/dual/day-trader/toggle - Toggle Day Trader on/off
3. /api/dual/long-term/confidence - Set Long Term confidence
4. Settings persistence after save
5. Backend starts without errors after refactoring
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDualTradingEngineAPIs:
    """Test Dual Trading Engine endpoints for Day Trader + Long Term"""
    
    def test_api_health(self):
        """Test backend is running"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "Aeon" in data["message"]
        print("✅ Backend health check passed")
    
    def test_dual_stats_returns_correct_structure(self):
        """Test /api/dual/stats returns correct structure with Day Trader and Long Term"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "active" in data
        assert "total_alerts_sent" in data
        assert "day_trader" in data
        assert "long_term" in data
        
        # Check Day Trader fields
        day_trader = data["day_trader"]
        assert day_trader["name"] == "Day Trader"
        assert day_trader["style"] == "AGGRESSIVE"
        assert "active" in day_trader
        assert "min_confidence" in day_trader
        assert "min_confirmations" in day_trader
        assert "timeframes" in day_trader
        assert "15m" in day_trader["timeframes"]
        assert "1h" in day_trader["timeframes"]
        assert "4h" in day_trader["timeframes"]
        assert "direction_lock_hours" in day_trader
        assert day_trader["direction_lock_hours"] == 1  # 1 hour lock for Day Trader
        
        # Check Long Term fields
        long_term = data["long_term"]
        assert long_term["name"] == "Long Term"
        assert long_term["style"] == "SMART"
        assert "active" in long_term
        assert "min_confidence" in long_term
        assert "min_confirmations" in long_term
        assert "timeframes" in long_term
        assert "4h" in long_term["timeframes"]
        assert "1d" in long_term["timeframes"]
        assert "direction_lock_hours" in long_term
        assert long_term["direction_lock_hours"] == 4  # 4 hour lock for Long Term
        
        print("✅ /api/dual/stats returns correct structure")
        print(f"   Day Trader: active={day_trader['active']}, conf={day_trader['min_confidence']}%")
        print(f"   Long Term: active={long_term['active']}, conf={long_term['min_confidence']}%")
    
    def test_day_trader_toggle_on(self):
        """Test /api/dual/day-trader/toggle can turn Day Trader ON"""
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["day_trader_active"] == True
        print("✅ Day Trader toggle ON works")
    
    def test_day_trader_toggle_off(self):
        """Test /api/dual/day-trader/toggle can turn Day Trader OFF"""
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["day_trader_active"] == False
        
        # Turn it back on
        requests.post(f"{BASE_URL}/api/dual/day-trader/toggle?active=true")
        print("✅ Day Trader toggle OFF works")
    
    def test_long_term_toggle_on(self):
        """Test /api/dual/long-term/toggle can turn Long Term ON"""
        response = requests.post(f"{BASE_URL}/api/dual/long-term/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["long_term_active"] == True
        print("✅ Long Term toggle ON works")
    
    def test_day_trader_confidence_set(self):
        """Test /api/dual/day-trader/confidence can set min confidence"""
        # Set to 80%
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=80")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["day_trader_min_confidence"] == 80
        
        # Verify in stats
        stats = requests.get(f"{BASE_URL}/api/dual/stats").json()
        assert stats["day_trader"]["min_confidence"] == 80
        
        # Reset to default 75%
        requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=75")
        print("✅ Day Trader confidence setting works")
    
    def test_long_term_confidence_set(self):
        """Test /api/dual/long-term/confidence can set min confidence"""
        # Set to 92%
        response = requests.post(f"{BASE_URL}/api/dual/long-term/confidence?min_conf=92")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["long_term_min_confidence"] == 92
        
        # Verify in stats
        stats = requests.get(f"{BASE_URL}/api/dual/stats").json()
        assert stats["long_term"]["min_confidence"] == 92
        
        # Reset to default 88%
        requests.post(f"{BASE_URL}/api/dual/long-term/confidence?min_conf=88")
        print("✅ Long Term confidence setting works")
    
    def test_confidence_boundaries(self):
        """Test confidence boundaries are enforced"""
        # Day Trader: min 65, max 95
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=50")
        assert response.status_code == 200
        data = response.json()
        assert data["day_trader_min_confidence"] == 65  # Should be capped at 65
        
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=99")
        data = response.json()
        assert data["day_trader_min_confidence"] == 95  # Should be capped at 95
        
        # Long Term: min 75, max 95
        response = requests.post(f"{BASE_URL}/api/dual/long-term/confidence?min_conf=60")
        data = response.json()
        assert data["long_term_min_confidence"] == 75  # Should be capped at 75
        
        # Reset to defaults
        requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=75")
        requests.post(f"{BASE_URL}/api/dual/long-term/confidence?min_conf=88")
        print("✅ Confidence boundaries enforced correctly")


class TestFreeWillV2APIs:
    """Test Free Will v2 APIs for Elite Alerts"""
    
    def test_freewill_stats_returns_correct_structure(self):
        """Test /api/freewill/stats returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "min_confidence" in data
        assert "min_confirmations" in data
        assert "direction_lock_hours" in data
        assert "contradictions_blocked" in data
        assert "data_sources" in data
        assert "pairs_monitored" in data
        assert "timeframes" in data
        
        print("✅ /api/freewill/stats returns correct structure")
        print(f"   Min Confidence: {data['min_confidence']}%")
        print(f"   Direction Lock: {data['direction_lock_hours']}h")
        print(f"   Contradictions Blocked: {data['contradictions_blocked']}")
        print(f"   Data Sources: {len(data['data_sources'])}")
    
    def test_freewill_toggle(self):
        """Test /api/freewill/toggle works"""
        # Turn off
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == False
        
        # Turn back on
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == True
        
        print("✅ Free Will toggle works")
    
    def test_freewill_confidence_set(self):
        """Test /api/freewill/confidence can set min confidence"""
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=85")
        assert response.status_code == 200
        data = response.json()
        assert data["min_confidence"] == 85
        
        # Reset to default
        requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=80")
        print("✅ Free Will confidence setting works")


class TestTradingV2APIs:
    """Test Autonomous Trader v2 APIs"""
    
    def test_trading_v2_stats(self):
        """Test /api/trading/v2/stats returns stats"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "open_trades" in data or "total_trades" in data
        print("✅ /api/trading/v2/stats works")
    
    def test_trading_toggle(self):
        """Test /api/trading/toggle works"""
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == True
        print("✅ Trading toggle works")


class TestPriceValidation:
    """Test price validation features in alerts"""
    
    def test_dual_engine_has_validate_method(self):
        """Verify dual_trading_engine.py has validate_and_format_alert method"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from dual_trading_engine import DualTradingEngine, TradingStyleEngine
        
        # Check method exists
        assert hasattr(TradingStyleEngine, 'validate_and_format_alert')
        assert hasattr(DualTradingEngine, 'validate_and_format_alert')
        print("✅ validate_and_format_alert method exists in dual_trading_engine")
    
    def test_free_will_has_validate_method(self):
        """Verify free_will_v2.py has validate_and_format_alert method"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from free_will_v2 import FreeWillEngineV2
        
        # Check method exists
        assert hasattr(FreeWillEngineV2, 'validate_and_format_alert')
        print("✅ validate_and_format_alert method exists in free_will_v2")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
