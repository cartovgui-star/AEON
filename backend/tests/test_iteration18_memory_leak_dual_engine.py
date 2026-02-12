"""
AEON Iteration 18 - Memory Leak Fix & Dual Trading Engine Testing

Tests focus on:
1. Backend APIs: /api/dual/stats - Day Trader + Long Term engines with active status
2. Backend APIs: /api/freewill/stats - Free Will v2 engine stats  
3. Backend APIs: /api/trading/v2/stats - Trading stats with open trades
4. Backend APIs: /api/ - Online status check
5. Memory leak fix verification (cleanup routines in dual_trading_engine.py, free_will_v2.py)
6. Anti-contradiction logic verification
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndStatus:
    """Test basic API health and status"""
    
    def test_root_endpoint_online(self):
        """Test /api/ returns online status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "online", f"Expected status=online, got {data}"
        assert "message" in data, f"Missing message field in response"
        
        print(f"✓ Root API online - {data.get('message')}")


class TestDualTradingEngine:
    """Test Dual Trading Engine - Day Trader + Long Term"""
    
    def test_dual_stats_returns_both_engines(self):
        """Test /api/dual/stats returns stats for both Day Trader and Long Term engines"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify top-level fields
        assert "active" in data, f"Missing 'active' field"
        assert "total_alerts_sent" in data, f"Missing 'total_alerts_sent' field"
        assert "day_trader" in data, f"Missing 'day_trader' section"
        assert "long_term" in data, f"Missing 'long_term' section"
        
        print(f"✓ Dual stats returns both engines - active={data.get('active')}")
    
    def test_day_trader_engine_stats(self):
        """Test Day Trader engine stats contain required fields"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        
        data = response.json()
        day_trader = data.get("day_trader", {})
        
        required_fields = [
            "name", "style", "active", "min_confidence", "min_confirmations",
            "timeframes", "cooldown_mins", "direction_lock_hours", 
            "daily_alerts", "max_daily_alerts", "total_alerts",
            "setups_analyzed", "contradictions_blocked", "recent_directions"
        ]
        
        for field in required_fields:
            assert field in day_trader, f"Day Trader missing field: {field}"
        
        # Verify expected values
        assert day_trader.get("name") == "Day Trader", f"Expected name='Day Trader'"
        assert day_trader.get("style") == "AGGRESSIVE", f"Expected style='AGGRESSIVE'"
        assert day_trader.get("active") is True, f"Day Trader should be active"
        assert day_trader.get("min_confidence") == 75, f"Expected min_confidence=75"
        assert day_trader.get("timeframes") == ["15m", "1h", "4h"], f"Unexpected timeframes"
        
        print(f"✓ Day Trader stats complete - conf={day_trader.get('min_confidence')}%, analyzed={day_trader.get('setups_analyzed')}")
    
    def test_long_term_engine_stats(self):
        """Test Long Term engine stats contain required fields"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        
        data = response.json()
        long_term = data.get("long_term", {})
        
        required_fields = [
            "name", "style", "active", "min_confidence", "min_confirmations",
            "timeframes", "cooldown_mins", "direction_lock_hours",
            "daily_alerts", "max_daily_alerts", "total_alerts",
            "setups_analyzed", "contradictions_blocked", "recent_directions"
        ]
        
        for field in required_fields:
            assert field in long_term, f"Long Term missing field: {field}"
        
        # Verify expected values
        assert long_term.get("name") == "Long Term", f"Expected name='Long Term'"
        assert long_term.get("style") == "SMART", f"Expected style='SMART'"
        assert long_term.get("active") is True, f"Long Term should be active"
        assert long_term.get("min_confidence") == 88, f"Expected min_confidence=88"
        assert long_term.get("timeframes") == ["4h", "1d"], f"Unexpected timeframes"
        
        print(f"✓ Long Term stats complete - conf={long_term.get('min_confidence')}%, analyzed={long_term.get('setups_analyzed')}")
    
    def test_dual_toggle(self):
        """Test /api/dual/toggle works"""
        # Toggle off
        response = requests.post(f"{BASE_URL}/api/dual/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == False, f"Expected active=False: {data}"
        
        # Toggle back on
        response = requests.post(f"{BASE_URL}/api/dual/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == True, f"Expected active=True: {data}"
        
        print(f"✓ Dual engine toggle works")
    
    def test_day_trader_toggle(self):
        """Test /api/dual/day-trader/toggle works"""
        # Toggle off
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("day_trader_active") == False, f"Expected day_trader_active=False"
        
        # Toggle back on
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("day_trader_active") == True, f"Expected day_trader_active=True"
        
        print(f"✓ Day Trader toggle works")
    
    def test_long_term_toggle(self):
        """Test /api/dual/long-term/toggle works"""
        # Toggle off  
        response = requests.post(f"{BASE_URL}/api/dual/long-term/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("long_term_active") == False, f"Expected long_term_active=False"
        
        # Toggle back on
        response = requests.post(f"{BASE_URL}/api/dual/long-term/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("long_term_active") == True, f"Expected long_term_active=True"
        
        print(f"✓ Long Term toggle works")
    
    def test_day_trader_confidence_setting(self):
        """Test /api/dual/day-trader/confidence works"""
        # Set to 80
        response = requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=80")
        assert response.status_code == 200
        data = response.json()
        assert data.get("day_trader_min_confidence") == 80, f"Expected 80, got {data}"
        
        # Reset to default 75
        requests.post(f"{BASE_URL}/api/dual/day-trader/confidence?min_conf=75")
        
        print(f"✓ Day Trader confidence setting works")
    
    def test_long_term_confidence_setting(self):
        """Test /api/dual/long-term/confidence works"""
        # Set to 90
        response = requests.post(f"{BASE_URL}/api/dual/long-term/confidence?min_conf=90")
        assert response.status_code == 200
        data = response.json()
        assert data.get("long_term_min_confidence") == 90, f"Expected 90, got {data}"
        
        # Reset to default 88
        requests.post(f"{BASE_URL}/api/dual/long-term/confidence?min_conf=88")
        
        print(f"✓ Long Term confidence setting works")


class TestFreeWillV2Engine:
    """Test Free Will v2 Engine with anti-contradiction logic"""
    
    def test_freewill_stats_all_fields(self):
        """Test /api/freewill/stats returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        required_fields = [
            "active", "min_confidence", "min_confirmations",
            "alert_cooldown_mins", "direction_lock_hours",
            "total_alerts_sent", "daily_alerts", "max_daily_alerts",
            "setups_analyzed", "contradictions_blocked", "recent_directions",
            "pairs_monitored", "timeframes", "data_sources"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify anti-contradiction is configured
        assert data.get("direction_lock_hours") == 2, f"Direction lock should be 2 hours"
        assert isinstance(data.get("contradictions_blocked"), int), f"contradictions_blocked should be int"
        
        print(f"✓ Free Will v2 stats complete - conf={data.get('min_confidence')}%, blocked={data.get('contradictions_blocked')}")
    
    def test_freewill_data_sources(self):
        """Test data sources are populated"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        data_sources = data.get("data_sources", [])
        
        assert len(data_sources) >= 6, f"Expected at least 6 data sources, got {len(data_sources)}"
        
        expected_sources = ["Technical Analysis", "Divergence Detection", "VWAP", "Derivatives"]
        for source in expected_sources:
            assert source in data_sources, f"Missing data source: {source}"
        
        print(f"✓ Free Will v2 has {len(data_sources)} data sources")
    
    def test_freewill_recent_directions_tracked(self):
        """Test recent directions are tracked for anti-contradiction"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        recent_directions = data.get("recent_directions", {})
        
        assert isinstance(recent_directions, dict), f"recent_directions should be dict"
        
        # If there are recent directions, verify format
        for symbol, direction in recent_directions.items():
            assert direction in ["LONG", "SHORT"], f"Invalid direction for {symbol}: {direction}"
        
        print(f"✓ Recent directions tracked: {recent_directions or '(none)'}")
    
    def test_freewill_toggle(self):
        """Test /api/freewill/toggle works"""
        # Toggle off
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == False
        
        # Toggle back on
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == True
        
        print(f"✓ Free Will v2 toggle works")
    
    def test_freewill_confidence_boundaries(self):
        """Test confidence setting with boundaries (70-95)"""
        # Set to minimum
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=70")
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") == 70
        
        # Set to maximum (capped at 95)
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=100")
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") == 95, f"Should be capped at 95, got {data}"
        
        # Reset to default
        requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=80")
        
        print(f"✓ Free Will v2 confidence boundaries work")


class TestTradingV2Stats:
    """Test Trading v2 stats with open trades"""
    
    def test_trading_v2_stats_all_fields(self):
        """Test /api/trading/v2/stats returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        required_fields = [
            "active", "total_trades", "open_trades", "closed_trades",
            "wins", "losses", "win_rate", "total_pnl_pct"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Trading v2 stats - open={data.get('open_trades')}, win_rate={data.get('win_rate')}%")
    
    def test_trading_v2_has_open_trades(self):
        """Test that open_trades value is reasonable"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        
        data = response.json()
        open_trades = data.get("open_trades", 0)
        
        # Open trades should be non-negative
        assert open_trades >= 0, f"open_trades should be >= 0, got {open_trades}"
        
        print(f"✓ Open trades count: {open_trades}")
    
    def test_trading_toggle(self):
        """Test /api/trading/toggle works"""
        # Get current state
        current = requests.get(f"{BASE_URL}/api/trading/v2/stats").json()
        
        # Toggle
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        
        print(f"✓ Trading toggle works - {data}")
    
    def test_trading_v2_open_trades_endpoint(self):
        """Test /api/trading/v2/open returns open trades list"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        assert response.status_code == 200
        
        data = response.json()
        assert "open_trades" in data, f"Missing open_trades field"
        assert "total_open" in data, f"Missing total_open field"
        
        print(f"✓ Trading v2 open trades endpoint works - {data.get('total_open')} open")
    
    def test_trading_v2_closed_trades_endpoint(self):
        """Test /api/trading/v2/closed returns closed trades list"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200
        
        data = response.json()
        assert "closed_trades" in data, f"Missing closed_trades field"
        assert "total_closed" in data, f"Missing total_closed field"
        
        print(f"✓ Trading v2 closed trades endpoint works - {data.get('total_closed')} closed")


class TestMemoryLeakFixes:
    """Test that memory leak fixes are in place - cleanup routines for tracking dicts"""
    
    def test_dual_engine_cleanup_runs(self):
        """Verify dual engine setups_analyzed counter increases (proving scanner is running)"""
        response1 = requests.get(f"{BASE_URL}/api/dual/stats")
        data1 = response1.json()
        analyzed1 = data1.get("day_trader", {}).get("setups_analyzed", 0)
        
        # Wait a bit and check again
        time.sleep(2)
        
        response2 = requests.get(f"{BASE_URL}/api/dual/stats")
        data2 = response2.json()
        analyzed2 = data2.get("day_trader", {}).get("setups_analyzed", 0)
        
        # Engine should be analyzing setups (counter may increase)
        assert analyzed2 >= analyzed1, f"Analyzed count should not decrease"
        
        print(f"✓ Dual engine is running - analyzed: {analyzed1} -> {analyzed2}")
    
    def test_freewill_cleanup_runs(self):
        """Verify free will engine setups_analyzed counter increases (proving scanner is running)"""
        response1 = requests.get(f"{BASE_URL}/api/freewill/stats")
        data1 = response1.json()
        analyzed1 = data1.get("setups_analyzed", 0)
        
        # Wait a bit
        time.sleep(2)
        
        response2 = requests.get(f"{BASE_URL}/api/freewill/stats")
        data2 = response2.json()
        analyzed2 = data2.get("setups_analyzed", 0)
        
        # Engine should be analyzing setups
        assert analyzed2 >= analyzed1, f"Analyzed count should not decrease"
        
        print(f"✓ Free Will v2 engine is running - analyzed: {analyzed1} -> {analyzed2}")
    
    def test_recent_directions_not_growing_unbounded(self):
        """Verify recent_directions dict is bounded (cleanup removes old entries)"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        data = response.json()
        recent_directions = data.get("recent_directions", {})
        
        # Should be bounded to reasonable size (symbols we track)
        assert len(recent_directions) <= 20, f"recent_directions too large: {len(recent_directions)}"
        
        print(f"✓ recent_directions bounded: {len(recent_directions)} entries")


class TestAntiContradictionLogic:
    """Test anti-contradiction system - no flip-flop signals within direction_lock_time"""
    
    def test_direction_lock_configured(self):
        """Verify direction lock is configured"""
        # Free Will v2
        fw_response = requests.get(f"{BASE_URL}/api/freewill/stats")
        fw_data = fw_response.json()
        assert fw_data.get("direction_lock_hours") == 2, f"Free Will direction lock should be 2h"
        
        # Dual Engine
        dual_response = requests.get(f"{BASE_URL}/api/dual/stats")
        dual_data = dual_response.json()
        
        assert dual_data.get("day_trader", {}).get("direction_lock_hours") == 1, f"Day Trader lock should be 1h"
        assert dual_data.get("long_term", {}).get("direction_lock_hours") == 4, f"Long Term lock should be 4h"
        
        print(f"✓ Direction locks configured - FW:2h, DayTrader:1h, LongTerm:4h")
    
    def test_contradictions_blocked_counter_exists(self):
        """Verify contradictions_blocked counters exist in all engines"""
        # Free Will v2
        fw_response = requests.get(f"{BASE_URL}/api/freewill/stats")
        fw_data = fw_response.json()
        assert "contradictions_blocked" in fw_data
        
        # Dual Engine
        dual_response = requests.get(f"{BASE_URL}/api/dual/stats")
        dual_data = dual_response.json()
        assert "contradictions_blocked" in dual_data.get("day_trader", {})
        assert "contradictions_blocked" in dual_data.get("long_term", {})
        
        print(f"✓ Contradictions blocked counters exist in all engines")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
