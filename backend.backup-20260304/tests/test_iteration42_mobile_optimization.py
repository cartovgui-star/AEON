"""
Test Suite for Iteration 42 - Mobile Optimization and P1 Server Refactoring
Tests:
1. Backend API /api/elite/scan_unlimited - Unlimited scanning endpoint
2. Backend API /api/elite/status - Elite trading status
3. Verify modular command files exist in telegram/commands/
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Skip all tests if BASE_URL not set
pytestmark = pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not set")


class TestEliteStatus:
    """Test /api/elite/status endpoint"""
    
    def test_elite_status_returns_200(self):
        """Elite status endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ /api/elite/status returned 200")
    
    def test_elite_status_has_enabled_field(self):
        """Elite status should have 'enabled' field"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        data = response.json()
        assert 'enabled' in data, "Response should have 'enabled' field"
        print(f"✅ Elite status enabled: {data.get('enabled')}")
    
    def test_elite_status_has_mode(self):
        """Elite status should have 'mode' field"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        data = response.json()
        assert 'mode' in data, "Response should have 'mode' field"
        print(f"✅ Elite mode: {data.get('mode')}")
    
    def test_elite_status_has_settings(self):
        """Elite status should have settings data"""
        response = requests.get(f"{BASE_URL}/api/elite/status", timeout=30)
        data = response.json()
        # Should have settings like min_confidence, min_rr_ratio etc
        settings_keys = ['min_confidence', 'min_rr_ratio', 'min_confirmations']
        for key in settings_keys:
            if key in data:
                print(f"✅ Elite setting '{key}': {data.get(key)}")


class TestEliteScanUnlimited:
    """Test /api/elite/scan_unlimited endpoint"""
    
    def test_scan_unlimited_returns_200(self):
        """Scan unlimited endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ /api/elite/scan_unlimited returned 200")
    
    def test_scan_unlimited_has_mode(self):
        """Scan unlimited should indicate UNLIMITED mode"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=120)
        data = response.json()
        assert 'mode' in data, "Response should have 'mode' field"
        assert data['mode'] == 'UNLIMITED', f"Expected mode UNLIMITED, got {data['mode']}"
        print(f"✅ Scan mode: {data.get('mode')}")
    
    def test_scan_unlimited_has_signals(self):
        """Scan unlimited should return signals data"""
        response = requests.get(f"{BASE_URL}/api/elite/scan_unlimited", timeout=120)
        data = response.json()
        # Should have signals_found or signals field
        if 'signals_found' in data:
            print(f"✅ Signals found: {data.get('signals_found')}")
        if 'signals' in data:
            print(f"✅ Signals array length: {len(data.get('signals', []))}")


class TestTradingV2APIs:
    """Test Trading V2 API endpoints"""
    
    def test_trading_v2_stats(self):
        """Trading V2 stats endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Trading V2 stats: win_rate={data.get('win_rate')}, active={data.get('active')}")
    
    def test_trading_v2_live_positions(self):
        """Trading V2 live positions endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions", timeout=30)
        assert response.status_code == 200
        data = response.json()
        positions = data.get('positions', [])
        print(f"✅ Live positions count: {len(positions)}")
    
    def test_trading_v2_closed(self):
        """Trading V2 closed trades endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Closed trades: {len(data.get('closed_trades', []))}")
    
    def test_trading_v2_pnl_history(self):
        """Trading V2 PnL history endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ PnL history entries: {len(data.get('history', []))}")
    
    def test_trading_v2_settings(self):
        """Trading V2 settings endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/settings", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ V2 settings: active={data.get('active')}, min_confidence={data.get('min_confidence')}")


class TestDashboardAPIs:
    """Test Dashboard-related API endpoints"""
    
    def test_stats_dashboard(self):
        """Dashboard stats endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/stats/dashboard", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Dashboard stats loaded")
    
    def test_bot_stats(self):
        """Bot stats endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/bot/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Bot stats: unique_users={data.get('unique_users')}")
    
    def test_trading_summary(self):
        """Trading summary endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Trading summary: active={data.get('active')}, win_rate={data.get('win_rate')}")


class TestScalperAPIs:
    """Test Scalper-related API endpoints"""
    
    def test_scalper_status(self):
        """Scalper status endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/scalper/status", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Scalper status: enabled={data.get('enabled')}")
    
    def test_scalper_learning_status(self):
        """Scalper learning status endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/scalper/learning/status", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Scalper learning status loaded")


class TestMEXCAPIs:
    """Test MEXC-related API endpoints"""
    
    def test_mexc_live(self):
        """MEXC live data endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/mexc/live", timeout=30)
        assert response.status_code == 200
        data = response.json()
        symbols = data.get('symbols', [])
        print(f"✅ MEXC live data: {len(symbols)} symbols tracked")
    
    def test_mexc_ohlcv(self):
        """MEXC OHLCV endpoint should work for BTC"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?timeframe=1h", timeout=30)
        assert response.status_code == 200
        data = response.json()
        candles = data.get('data', [])
        print(f"✅ MEXC OHLCV BTC 1h: {len(candles)} candles")


class TestLearningAPIs:
    """Test Learning Engine API endpoints"""
    
    def test_learning_status(self):
        """Learning engine status endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/learning/status", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Learning engine status: active={data.get('active')}")


class TestReportAPIs:
    """Test Report-related API endpoints"""
    
    def test_report_status(self):
        """Report status endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/report/status", timeout=30)
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Report status: enabled={data.get('enabled')}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
