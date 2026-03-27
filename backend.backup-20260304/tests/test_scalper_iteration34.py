"""
Scalper API Tests - Iteration 34
Tests for:
- /api/scalper/status - Basic scalper status
- /api/scalper/learning/status - Auto-learning status
- /api/scalper/learning/optimize POST - Force optimization
- /api/scalper/v2/status - V2.1 integration status
- /api/scalper/v2/toggle POST - Enable/disable V2.1 integration
- /api/scalper/reversals/analyze/{symbol} - Reversal pattern detection
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScalperStatus:
    """Scalper status endpoint tests"""
    
    def test_scalper_status_endpoint(self):
        """Test /api/scalper/status returns valid data"""
        response = requests.get(f"{BASE_URL}/api/scalper/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "enabled" in data, "Missing 'enabled' field"
        assert "is_scanning" in data, "Missing 'is_scanning' field"
        assert "active_signals" in data, "Missing 'active_signals' field"
        assert "settings_summary" in data, "Missing 'settings_summary' field"
        
        # Check settings_summary structure
        settings = data["settings_summary"]
        assert "profit_target" in settings, "Missing profit_target in settings"
        assert "stop_loss" in settings, "Missing stop_loss in settings"
        assert "volume_threshold" in settings, "Missing volume_threshold in settings"
        assert "rsi_range" in settings, "Missing rsi_range in settings"
        
        print(f"✓ Scalper status: enabled={data['enabled']}, active_signals={data['active_signals']}")


class TestScalperLearning:
    """Scalper auto-learning endpoints tests"""
    
    def test_learning_status_endpoint(self):
        """Test /api/scalper/learning/status returns learning system status"""
        response = requests.get(f"{BASE_URL}/api/scalper/learning/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "auto_learn_enabled" in data, "Missing 'auto_learn_enabled' field"
        assert "learning_interval_hours" in data, "Missing 'learning_interval_hours' field"
        assert "recent_performance" in data, "Missing 'recent_performance' field"
        assert "learning_summary" in data, "Missing 'learning_summary' field"
        
        # Check learning_summary structure
        summary = data["learning_summary"]
        assert "current_params" in summary, "Missing current_params in learning_summary"
        assert "optimization_interval_hours" in summary, "Missing optimization_interval_hours"
        
        print(f"✓ Learning status: auto_learn_enabled={data['auto_learn_enabled']}, interval={data['learning_interval_hours']}h")
    
    def test_force_optimize_endpoint(self):
        """Test POST /api/scalper/learning/optimize triggers optimization"""
        response = requests.post(f"{BASE_URL}/api/scalper/learning/optimize")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Missing 'success' field"
        assert data["success"] == True, "Expected success=True"
        assert "new_settings" in data, "Missing 'new_settings' field"
        assert "optimized_at" in data, "Missing 'optimized_at' field"
        
        # Verify new_settings has expected keys
        settings = data["new_settings"]
        assert "profit_target_pct" in settings, "Missing profit_target_pct"
        assert "stop_loss_pct" in settings, "Missing stop_loss_pct"
        assert "volume_threshold" in settings, "Missing volume_threshold"
        assert "auto_learn" in settings, "Missing auto_learn flag"
        
        print(f"✓ Optimization complete: changes={data.get('changes', {})}")


class TestScalperV2Integration:
    """Scalper V2.1 integration endpoints tests"""
    
    def test_v2_status_endpoint(self):
        """Test /api/scalper/v2/status returns integration status"""
        response = requests.get(f"{BASE_URL}/api/scalper/v2/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "v2_integration_enabled" in data, "Missing 'v2_integration_enabled' field"
        assert "min_strength_for_v2" in data, "Missing 'min_strength_for_v2' field"
        assert "queued_signals" in data, "Missing 'queued_signals' field"
        assert "signals_in_queue" in data, "Missing 'signals_in_queue' field"
        
        # Verify min_strength is valid
        assert data["min_strength_for_v2"] >= 1, "min_strength should be >= 1"
        assert data["min_strength_for_v2"] <= 3, "min_strength should be <= 3"
        
        print(f"✓ V2 status: enabled={data['v2_integration_enabled']}, queued={data['queued_signals']}")
    
    def test_v2_toggle_enable(self):
        """Test POST /api/scalper/v2/toggle?enabled=true enables integration"""
        response = requests.post(f"{BASE_URL}/api/scalper/v2/toggle?enabled=true")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Missing 'success' field"
        assert data["success"] == True, "Expected success=True"
        assert "v2_integration_enabled" in data, "Missing 'v2_integration_enabled' field"
        assert data["v2_integration_enabled"] == True, "Expected v2_integration_enabled=True"
        
        print(f"✓ V2 toggle enable: message={data.get('message')}")
    
    def test_v2_toggle_disable(self):
        """Test POST /api/scalper/v2/toggle?enabled=false disables integration"""
        response = requests.post(f"{BASE_URL}/api/scalper/v2/toggle?enabled=false")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Missing 'success' field"
        assert data["success"] == True, "Expected success=True"
        assert "v2_integration_enabled" in data, "Missing 'v2_integration_enabled' field"
        assert data["v2_integration_enabled"] == False, "Expected v2_integration_enabled=False"
        
        print(f"✓ V2 toggle disable: message={data.get('message')}")
        
        # Re-enable for other tests
        requests.post(f"{BASE_URL}/api/scalper/v2/toggle?enabled=true")


class TestReversalPatterns:
    """Reversal pattern detection endpoint tests"""
    
    def test_reversal_analyze_btc(self):
        """Test /api/scalper/reversals/analyze/BTC returns pattern analysis"""
        response = requests.get(f"{BASE_URL}/api/scalper/reversals/analyze/BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "symbol" in data, "Missing 'symbol' field"
        assert "timeframe" in data, "Missing 'timeframe' field"
        assert "patterns_detected" in data, "Missing 'patterns_detected' field"
        assert "total_patterns" in data, "Missing 'total_patterns' field"
        assert "current_candle" in data, "Missing 'current_candle' field"
        assert "rsi" in data, "Missing 'rsi' field"
        
        # Verify symbol format
        assert "BTC" in data["symbol"].upper(), "Symbol should contain BTC"
        
        # Verify current_candle structure
        candle = data["current_candle"]
        assert "open" in candle, "Missing open in current_candle"
        assert "high" in candle, "Missing high in current_candle"
        assert "low" in candle, "Missing low in current_candle"
        assert "close" in candle, "Missing close in current_candle"
        
        # If patterns detected, verify structure
        if data["total_patterns"] > 0:
            pattern = data["patterns_detected"][0]
            assert "pattern" in pattern, "Missing pattern name"
            assert "type" in pattern, "Missing pattern type"
            assert "confidence" in pattern, "Missing confidence"
        
        print(f"✓ BTC reversal analysis: patterns={data['total_patterns']}, RSI={data['rsi']}")
    
    def test_reversal_analyze_eth(self):
        """Test reversal analysis for ETH"""
        response = requests.get(f"{BASE_URL}/api/scalper/reversals/analyze/ETH")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "symbol" in data, "Missing 'symbol' field"
        assert "ETH" in data["symbol"].upper(), "Symbol should contain ETH"
        
        print(f"✓ ETH reversal analysis: patterns={data.get('total_patterns', 0)}, RSI={data.get('rsi')}")
    
    def test_reversal_analyze_with_timeframe(self):
        """Test reversal analysis with specific timeframe"""
        response = requests.get(f"{BASE_URL}/api/scalper/reversals/analyze/BTC?timeframe=15m")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["timeframe"] == "15m", f"Expected timeframe '15m', got '{data['timeframe']}'"
        
        print(f"✓ BTC 15m reversal analysis: patterns={data['total_patterns']}")


class TestScalperSignals:
    """Scalper signal scanning endpoints tests"""
    
    def test_scan_signals(self):
        """Test /api/scalper/scan returns signals for timeframe"""
        response = requests.get(f"{BASE_URL}/api/scalper/scan?timeframe=5m")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "timeframe" in data, "Missing 'timeframe' field"
        assert "total_signals" in data, "Missing 'total_signals' field"
        assert "signals" in data, "Missing 'signals' field"
        
        # Verify signals is a list
        assert isinstance(data["signals"], list), "signals should be a list"
        
        print(f"✓ Scan 5m: found {data['total_signals']} signals")
    
    def test_opportunities(self):
        """Test /api/scalper/opportunities returns best opportunities"""
        response = requests.get(f"{BASE_URL}/api/scalper/opportunities?min_strength=2")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "min_strength" in data, "Missing 'min_strength' field"
        assert "count" in data, "Missing 'count' field"
        assert "opportunities" in data, "Missing 'opportunities' field"
        
        print(f"✓ Opportunities (str>=2): found {data['count']} opportunities")


class TestScalperSettings:
    """Scalper settings endpoints tests"""
    
    def test_get_settings(self):
        """Test /api/scalper/settings returns current settings"""
        response = requests.get(f"{BASE_URL}/api/scalper/settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "settings" in data, "Missing 'settings' field"
        assert "available_symbols" in data, "Missing 'available_symbols' field"
        assert "available_timeframes" in data, "Missing 'available_timeframes' field"
        
        # Verify settings structure
        settings = data["settings"]
        expected_keys = ["profit_target_pct", "stop_loss_pct", "volume_threshold", 
                        "rsi_overbought", "rsi_oversold", "enabled", "auto_learn", 
                        "use_reversal_exits", "send_to_v2"]
        for key in expected_keys:
            assert key in settings, f"Missing {key} in settings"
        
        # Verify available symbols and timeframes
        assert len(data["available_symbols"]) == 15, "Expected 15 available symbols"
        assert "5m" in data["available_timeframes"], "Missing 5m in available_timeframes"
        
        print(f"✓ Settings: enabled={settings['enabled']}, auto_learn={settings['auto_learn']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
