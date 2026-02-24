"""
Test V2.1 Backtest API Endpoints - Quick verification tests
Tests the HIGH WIN RATE strategy backtest against MEXC historical data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBacktestV21:
    """Test V2.1 Backtest API endpoints"""
    
    def test_settings_endpoint(self):
        """Test /api/backtest/v21/settings returns correct V2.1 strategy settings"""
        response = requests.get(f"{BASE_URL}/api/backtest/v21/settings", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "settings" in data
        assert "description" in data
        
        settings = data["settings"]
        # Verify V2.1 settings
        assert settings["min_confidence"] == 90
        assert settings["min_confirmations"] == 5
        assert settings["min_rr_ratio"] == 3.0
        assert settings["min_adx"] == 25
        assert settings["min_volume_multiplier"] == 1.5
        assert "ema_no_trade_zone_pct" in settings
        assert "session_filter" in settings
        
        print(f"✅ V2.1 Settings verified: {settings}")
    
    def test_status_endpoint(self):
        """Test /api/backtest/v21/status returns current backtest status"""
        response = requests.get(f"{BASE_URL}/api/backtest/v21/status", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "is_running" in data
        assert "progress" in data
        assert "has_result" in data
        
        print(f"✅ Status: running={data['is_running']}, progress={data['progress']}%, has_result={data['has_result']}")
    
    def test_result_endpoint(self):
        """Test /api/backtest/v21/result returns last backtest result"""
        response = requests.get(f"{BASE_URL}/api/backtest/v21/result", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data
        
        if data["status"] == "success":
            result = data["result"]
            assert "data_source" in result
            assert result["data_source"] == "MEXC"
            assert "win_rate" in result
            assert "settings" in result
            print(f"✅ Result available: Win Rate={result['win_rate']}%, Data Source={result['data_source']}")
        else:
            print(f"✅ No result yet (expected if first run)")
    
    def test_run_endpoint(self):
        """Test POST /api/backtest/v21/run starts a backtest"""
        response = requests.post(
            f"{BASE_URL}/api/backtest/v21/run",
            json={"symbols": ["BTC/USDT"], "interval": "1h", "days": 7},
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["started", "already_running"]
        
        print(f"✅ Run endpoint: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
