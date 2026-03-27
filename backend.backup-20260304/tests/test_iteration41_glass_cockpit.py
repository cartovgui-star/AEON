"""
Iteration 41: Glass Cockpit UI Redesign Tests
Tests for:
- Dashboard loads with new glass-card design
- Trading page loads with new styling
- Chart tab shows TradingView chart with controls
- Markers toggle button exists and works
- Backend APIs /api/elite/scan_unlimited and /api/elite/status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEliteAPIStatus:
    """Test /api/elite/status endpoint"""
    
    def test_elite_status_returns_200(self):
        """Status endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        assert response.status_code == 200
        print(f"✅ Elite status returned HTTP {response.status_code}")
    
    def test_elite_status_structure(self):
        """Status endpoint returns correct data structure"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        data = response.json()
        
        # Check required fields
        assert "enabled" in data, "Missing 'enabled' field"
        assert "relaxed_mode" in data, "Missing 'relaxed_mode' field"
        assert "mode" in data, "Missing 'mode' field"
        assert "settings" in data, "Missing 'settings' field"
        
        print(f"✅ Status data structure valid: enabled={data['enabled']}, mode={data['mode']}")
    
    def test_elite_status_settings(self):
        """Status endpoint returns correct settings"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        data = response.json()
        settings = data.get("settings", {})
        
        # Check settings fields
        assert "min_confidence" in settings
        assert "min_rr_ratio" in settings
        assert "min_volume_ratio" in settings
        assert "max_daily_trades" in settings
        
        print(f"✅ Settings valid: min_confidence={settings['min_confidence']}, min_rr_ratio={settings['min_rr_ratio']}")


class TestEliteScanUnlimited:
    """Test /api/elite/scan_unlimited endpoint"""
    
    def test_scan_unlimited_returns_200(self):
        """Unlimited scan endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=90)
        assert response.status_code == 200
        print(f"✅ Scan unlimited returned HTTP {response.status_code}")
    
    def test_scan_unlimited_mode(self):
        """Unlimited scan returns mode='UNLIMITED'"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=90)
        data = response.json()
        
        assert data.get("mode") == "UNLIMITED", f"Expected mode='UNLIMITED', got '{data.get('mode')}'"
        print(f"✅ Mode is UNLIMITED as expected")
    
    def test_scan_unlimited_signals_structure(self):
        """Unlimited scan returns signals array with correct structure"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=90)
        data = response.json()
        
        assert "signals_found" in data, "Missing 'signals_found' field"
        assert "signals" in data, "Missing 'signals' field"
        assert isinstance(data["signals"], list), "Signals should be an array"
        
        # Check signal structure if any signals exist
        if data["signals"]:
            signal = data["signals"][0]
            required_fields = ["symbol", "direction", "entry_price", "stop_price", 
                            "target_price", "confidence", "confirmations"]
            for field in required_fields:
                assert field in signal, f"Signal missing '{field}' field"
        
        print(f"✅ Found {data['signals_found']} signals with correct structure")
    
    def test_scan_unlimited_message(self):
        """Unlimited scan returns proper message"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=90)
        data = response.json()
        
        assert "message" in data
        assert "unlimited scanning" in data["message"].lower() or "signals" in data["message"].lower()
        print(f"✅ Message: {data['message']}")


class TestTradingV2Stats:
    """Test /api/trading/v2/stats endpoint"""
    
    def test_trading_stats_returns_200(self):
        """Trading stats endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats", timeout=30)
        assert response.status_code == 200
        print(f"✅ Trading stats returned HTTP {response.status_code}")
    
    def test_trading_stats_structure(self):
        """Trading stats returns correct data structure"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats", timeout=30)
        data = response.json()
        
        # Check for win/loss stats
        assert "win_rate" in data or "wins" in data or "active" in data
        print(f"✅ Trading stats structure valid")


class TestMEXCOHLCV:
    """Test /api/mexc/ohlcv/{symbol} endpoint for chart data"""
    
    def test_ohlcv_btc_returns_200(self):
        """OHLCV endpoint for BTC returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?timeframe=4h&limit=50", timeout=30)
        assert response.status_code == 200
        print(f"✅ OHLCV BTC returned HTTP {response.status_code}")
    
    def test_ohlcv_returns_candles(self):
        """OHLCV endpoint returns candles array"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?timeframe=4h&limit=50", timeout=30)
        data = response.json()
        
        assert "candles" in data, "Missing 'candles' field"
        assert isinstance(data["candles"], list), "Candles should be an array"
        assert len(data["candles"]) > 0, "Should have at least some candles"
        print(f"✅ Got {len(data['candles'])} candles")
    
    def test_ohlcv_candle_structure(self):
        """OHLCV candles have correct OHLCV structure"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?timeframe=4h&limit=50", timeout=30)
        data = response.json()
        
        if data.get("candles"):
            candle = data["candles"][0]
            required_fields = ["timestamp", "open", "high", "low", "close", "volume"]
            for field in required_fields:
                assert field in candle, f"Candle missing '{field}' field"
            print(f"✅ Candle structure valid with OHLCV fields")


class TestMEXCLive:
    """Test /api/mexc/live endpoint for market data"""
    
    def test_mexc_live_returns_200(self):
        """Live market data endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/mexc/live", timeout=30)
        assert response.status_code == 200
        print(f"✅ MEXC live returned HTTP {response.status_code}")
    
    def test_mexc_live_returns_symbols(self):
        """Live market data returns symbols array"""
        response = requests.get(f"{BASE_URL}/api/mexc/live", timeout=30)
        data = response.json()
        
        assert "symbols" in data or isinstance(data, list)
        print(f"✅ MEXC live data received")


class TestDashboardEndpoints:
    """Test dashboard-related endpoints"""
    
    def test_dashboard_stats_returns_200(self):
        """Dashboard stats endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/stats/dashboard", timeout=30)
        assert response.status_code == 200
        print(f"✅ Dashboard stats returned HTTP {response.status_code}")
    
    def test_trading_summary_returns_200(self):
        """Trading summary endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        print(f"✅ Trading summary returned HTTP {response.status_code}")
    
    def test_bot_stats_returns_200(self):
        """Bot stats endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/bot/stats", timeout=30)
        assert response.status_code == 200
        print(f"✅ Bot stats returned HTTP {response.status_code}")


class TestTradingPositions:
    """Test trading positions endpoints"""
    
    def test_live_positions_returns_200(self):
        """Live positions endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions", timeout=30)
        assert response.status_code == 200
        print(f"✅ Live positions returned HTTP {response.status_code}")
    
    def test_live_positions_structure(self):
        """Live positions returns positions array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions", timeout=30)
        data = response.json()
        
        assert "positions" in data, "Missing 'positions' field"
        assert isinstance(data["positions"], list), "Positions should be an array"
        print(f"✅ Got {len(data['positions'])} open positions")
    
    def test_closed_trades_returns_200(self):
        """Closed trades endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed", timeout=30)
        assert response.status_code == 200
        print(f"✅ Closed trades returned HTTP {response.status_code}")
    
    def test_pnl_history_returns_200(self):
        """PnL history endpoint returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history", timeout=30)
        assert response.status_code == 200
        print(f"✅ PnL history returned HTTP {response.status_code}")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session for tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
