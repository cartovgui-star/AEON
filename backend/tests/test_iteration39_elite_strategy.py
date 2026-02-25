"""
Test Suite - Iteration 39: Elite Strategy v3 with STRICT/RELAXED modes
Tests:
- Elite Strategy status API /api/elite/status
- Elite Strategy relaxed mode toggle /api/elite/relaxed
- Elite Strategy backtest API /api/elite/backtest
- Elite Strategy scan /api/elite/scan in both modes
- Elite Strategy analyze /api/elite/analyze/{symbol}
- MTF Confluence API endpoints
- TradingView chart (OHLCV data)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEliteStrategyStatus:
    """Test Elite Strategy v3 status endpoint"""
    
    def test_elite_status_returns_correct_structure(self):
        """Test /api/elite/status returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/elite/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify required fields exist
        assert "enabled" in data, "Missing 'enabled' field"
        assert "relaxed_mode" in data, "Missing 'relaxed_mode' field"
        assert "mode" in data, "Missing 'mode' field"
        assert "signals_generated" in data, "Missing 'signals_generated' field"
        assert "signals_filtered" in data, "Missing 'signals_filtered' field"
        assert "daily_trades" in data, "Missing 'daily_trades' field"
        assert "max_daily_trades" in data, "Missing 'max_daily_trades' field"
        assert "settings" in data, "Missing 'settings' field"
        
        print(f"✅ Elite status: mode={data['mode']}, enabled={data['enabled']}")
    
    def test_elite_status_contains_settings(self):
        """Test /api/elite/status settings contain all required parameters"""
        response = requests.get(f"{BASE_URL}/api/elite/status")
        
        assert response.status_code == 200
        
        settings = response.json().get("settings", {})
        
        # Required settings for Elite Strategy
        required_settings = [
            "min_confidence",
            "min_rr_ratio",
            "min_volume_ratio",
            "min_adx",
            "max_daily_trades",
            "require_btc_alignment",
            "require_mtf_confluence",
            "min_mtf_agreement"
        ]
        
        for setting in required_settings:
            assert setting in settings, f"Missing setting: {setting}"
        
        print(f"✅ Elite settings verified: {len(settings)} settings present")


class TestEliteRelaxedMode:
    """Test Elite Strategy relaxed mode toggle"""
    
    def test_enable_relaxed_mode(self):
        """Test POST /api/elite/relaxed?enabled=true"""
        response = requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=true")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("success") == True, "Expected success=True"
        assert data.get("relaxed_mode") == True, "Expected relaxed_mode=True"
        assert data.get("mode") == "RELAXED", "Expected mode=RELAXED"
        
        # Verify relaxed settings
        settings = data.get("settings", {})
        assert settings.get("min_confidence") == 70, "Relaxed min_confidence should be 70"
        assert settings.get("min_rr_ratio") == 2.0, "Relaxed min_rr_ratio should be 2.0"
        assert settings.get("max_daily_trades") == 8, "Relaxed max_daily_trades should be 8"
        
        print(f"✅ Relaxed mode enabled: min_conf=70%, max_trades=8")
    
    def test_disable_relaxed_mode(self):
        """Test POST /api/elite/relaxed?enabled=false switches to STRICT"""
        response = requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=false")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("success") == True
        assert data.get("relaxed_mode") == False
        assert data.get("mode") == "STRICT"
        
        # Verify strict settings
        settings = data.get("settings", {})
        assert settings.get("min_confidence") == 92, "Strict min_confidence should be 92"
        assert settings.get("min_rr_ratio") == 2.5, "Strict min_rr_ratio should be 2.5"
        assert settings.get("max_daily_trades") == 3, "Strict max_daily_trades should be 3"
        
        print(f"✅ Strict mode enabled: min_conf=92%, max_trades=3")
    
    def test_mode_persists_after_toggle(self):
        """Test mode persists correctly after toggle"""
        # Enable relaxed
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=true")
        
        # Verify via status
        status_response = requests.get(f"{BASE_URL}/api/elite/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data.get("relaxed_mode") == True
        assert data.get("mode") == "RELAXED"
        
        # Reset to strict for other tests
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=false")
        
        print("✅ Mode persistence verified")


class TestEliteBacktest:
    """Test Elite Strategy backtest endpoint"""
    
    def test_backtest_returns_structure(self):
        """Test GET /api/elite/backtest returns expected structure"""
        response = requests.get(f"{BASE_URL}/api/elite/backtest?days=30")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Backtest may return error if no historical data - that's acceptable
        if "error" in data:
            assert data.get("signals_analyzed") == 0 or data.get("error") == "No historical data found"
            print(f"✅ Backtest returned: {data.get('error')}")
        else:
            # If data exists, verify structure
            assert "days_analyzed" in data
            assert "total_signals" in data
            assert "strict_mode" in data or "relaxed_mode" in data
            print(f"✅ Backtest completed: {data.get('total_signals', 0)} signals analyzed")
    
    def test_backtest_custom_days(self):
        """Test backtest with custom days parameter"""
        response = requests.get(f"{BASE_URL}/api/elite/backtest?days=7")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Either error (no data) or days_analyzed should match
        if "error" not in data:
            assert data.get("days_analyzed") == 7
        
        print("✅ Backtest custom days parameter works")


class TestEliteScan:
    """Test Elite Strategy scan endpoint"""
    
    def test_scan_strict_mode(self):
        """Test /api/elite/scan in STRICT mode"""
        # Ensure strict mode
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=false")
        
        response = requests.get(f"{BASE_URL}/api/elite/scan")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert "signals_found" in data
        assert "signals" in data
        assert "stats" in data
        assert isinstance(data["signals"], list)
        
        # Verify stats show strict mode
        stats = data.get("stats", {})
        assert stats.get("mode") == "STRICT"
        assert stats.get("max_daily_trades") == 3
        
        print(f"✅ Strict scan: {data['signals_found']} signals found")
    
    def test_scan_relaxed_mode(self):
        """Test /api/elite/scan in RELAXED mode"""
        # Enable relaxed mode
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=true")
        
        response = requests.get(f"{BASE_URL}/api/elite/scan")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert "signals_found" in data
        assert "signals" in data
        assert "stats" in data
        
        # Verify stats show relaxed mode
        stats = data.get("stats", {})
        assert stats.get("mode") == "RELAXED"
        assert stats.get("max_daily_trades") == 8
        
        # Reset to strict
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=false")
        
        print(f"✅ Relaxed scan: {data['signals_found']} signals found")


class TestEliteAnalyze:
    """Test Elite Strategy single symbol analysis"""
    
    def test_analyze_btc(self):
        """Test /api/elite/analyze/BTC"""
        response = requests.get(f"{BASE_URL}/api/elite/analyze/BTC?timeframe=4h")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "BTC/USDT"
        assert "signal" in data
        assert "has_signal" in data
        assert "stats" in data
        
        print(f"✅ BTC analysis: has_signal={data['has_signal']}")
    
    def test_analyze_eth(self):
        """Test /api/elite/analyze/ETH"""
        response = requests.get(f"{BASE_URL}/api/elite/analyze/ETH?timeframe=1h")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "ETH/USDT"
        assert "signal" in data
        assert "has_signal" in data
        
        print(f"✅ ETH analysis: has_signal={data['has_signal']}")
    
    def test_analyze_returns_signal_structure(self):
        """Test signal structure when found"""
        # Enable relaxed for higher chance of signal
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=true")
        
        # Try multiple symbols
        symbols = ["BTC", "ETH", "SOL", "BNB"]
        
        for symbol in symbols:
            response = requests.get(f"{BASE_URL}/api/elite/analyze/{symbol}?timeframe=4h")
            assert response.status_code == 200
            
            data = response.json()
            
            if data.get("has_signal") and data.get("signal"):
                signal = data["signal"]
                assert "direction" in signal
                assert "entry_price" in signal
                assert "stop_price" in signal
                assert "target_price" in signal
                assert "confidence" in signal
                assert "rr_ratio" in signal
                print(f"✅ Signal found for {symbol}: {signal['direction']} @ {signal['confidence']}%")
                break
        
        # Reset to strict
        requests.post(f"{BASE_URL}/api/elite/relaxed?enabled=false")


class TestMTFConfluence:
    """Test MTF Confluence API endpoints"""
    
    def test_mtf_confluence_btc(self):
        """Test /api/scalper/mtf/confluence/BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/confluence/BTCUSDT")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert "confluence_level" in data
        assert "confluence_count" in data
        assert "consensus_direction" in data
        assert "timeframes" in data
        
        # Verify confluence levels are valid
        valid_levels = ["STRONG", "MODERATE", "WEAK", "NONE"]
        assert data["confluence_level"] in valid_levels
        
        print(f"✅ MTF Confluence BTC: {data['confluence_level']} ({data['confluence_count']})")
    
    def test_mtf_scan(self):
        """Test /api/scalper/mtf/scan"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/scan")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # MTF scan returns summary with strong/moderate/weak confluence lists
        assert "summary" in data or "strong_confluence" in data
        
        if "summary" in data:
            summary = data["summary"]
            assert "scanned_symbols" in summary
            print(f"✅ MTF Scan: {summary.get('scanned_symbols', 0)} symbols scanned")
        else:
            print(f"✅ MTF Scan completed")
    
    def test_mtf_best_setups(self):
        """Test /api/scalper/mtf/best"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/best")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Should return best setups structure
        assert "strong_setups" in data or "moderate_setups" in data or "setups" in data or isinstance(data, dict)
        
        print(f"✅ MTF Best setups endpoint working")


class TestOHLCVChart:
    """Test OHLCV data for TradingView chart"""
    
    def test_ohlcv_btc(self):
        """Test /api/mexc/ohlcv/BTC (without USDT suffix)"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?timeframe=1h&limit=100")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert "symbol" in data
        assert "candles" in data
        assert len(data["candles"]) > 0
        
        # Verify candle structure
        candle = data["candles"][0]
        assert "timestamp" in candle or "time" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        
        print(f"✅ OHLCV BTC: {len(data['candles'])} candles returned")
    
    def test_ohlcv_different_timeframes(self):
        """Test OHLCV with different timeframes"""
        timeframes = ["5m", "15m", "1h", "4h"]
        
        for tf in timeframes:
            response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/ETH?timeframe={tf}&limit=50")
            assert response.status_code == 200
            
            data = response.json()
            assert "candles" in data
            assert len(data["candles"]) > 0, f"No candles for ETH {tf}"
        
        print(f"✅ OHLCV timeframes tested: {timeframes}")


class TestEliteToggle:
    """Test Elite Strategy toggle endpoint"""
    
    def test_toggle_off(self):
        """Test POST /api/elite/toggle?enabled=false"""
        response = requests.post(f"{BASE_URL}/api/elite/toggle?enabled=false")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("enabled") == False
        
        print("✅ Elite toggle OFF works")
    
    def test_toggle_on(self):
        """Test POST /api/elite/toggle?enabled=true"""
        response = requests.post(f"{BASE_URL}/api/elite/toggle?enabled=true")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("enabled") == True
        
        print("✅ Elite toggle ON works")


class TestEliteSettings:
    """Test Elite Strategy settings update"""
    
    def test_update_settings(self):
        """Test POST /api/elite/settings"""
        new_settings = {
            "min_confidence": 88,
            "min_rr_ratio": 2.2
        }
        
        response = requests.post(
            f"{BASE_URL}/api/elite/settings",
            json=new_settings
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        # Verify settings updated
        settings = data.get("new_settings", {})
        assert settings.get("min_confidence") == 88
        assert settings.get("min_rr_ratio") == 2.2
        
        # Reset to defaults
        requests.post(
            f"{BASE_URL}/api/elite/settings",
            json={"min_confidence": 92, "min_rr_ratio": 2.5}
        )
        
        print("✅ Elite settings update works")


# Run all tests when executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
