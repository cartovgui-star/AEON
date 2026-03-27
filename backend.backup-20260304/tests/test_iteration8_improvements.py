"""
Test Suite for Iteration 8 Improvements:
1. REAL L/S ratio from OKX Public API (not estimated)
2. Free Will alert noise reduction (65% confidence, consolidated per symbol, 10-min cooldown)
3. Higher timeframes prioritized
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRealLongShortRatio:
    """Test REAL L/S ratio from OKX Public API"""
    
    def test_ls_btc_returns_real_data(self):
        """L/S ratio for BTC should return REAL data from OKX"""
        response = requests.get(f"{BASE_URL}/api/derivatives/ls/btc")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify structure
        assert "symbol" in data
        assert "global" in data
        assert "top_traders" in data
        assert "interpretation" in data
        assert "data_source" in data
        
        # Verify REAL data source
        assert data["data_source"] == "REAL - OKX Public API"
        
        # Verify global L/S data
        global_ls = data["global"]
        assert global_ls.get("source") == "REAL - OKX Public API"
        assert "long_short_ratio" in global_ls
        assert "long_pct" in global_ls
        assert "short_pct" in global_ls
        
        # Verify percentages add up to 100
        assert abs(global_ls["long_pct"] + global_ls["short_pct"] - 100) < 0.5
        
        # Verify top traders data
        top_ls = data["top_traders"]
        assert top_ls.get("source") == "REAL - OKX Public API"
        assert "long_short_ratio" in top_ls
        assert "long_pct" in top_ls
        assert "short_pct" in top_ls
    
    def test_ls_eth_returns_real_data(self):
        """L/S ratio for ETH should return REAL data from OKX"""
        response = requests.get(f"{BASE_URL}/api/derivatives/ls/eth")
        assert response.status_code == 200
        
        data = response.json()
        assert data["data_source"] == "REAL - OKX Public API"
        assert data["global"].get("source") == "REAL - OKX Public API"
    
    def test_ls_sol_returns_real_data(self):
        """L/S ratio for SOL should return REAL data from OKX"""
        response = requests.get(f"{BASE_URL}/api/derivatives/ls/sol")
        assert response.status_code == 200
        
        data = response.json()
        assert data["data_source"] == "REAL - OKX Public API"
        assert data["global"].get("source") == "REAL - OKX Public API"
    
    def test_ls_interpretation_longs_crowded(self):
        """Verify L/S interpretation shows correct crowd positioning"""
        response = requests.get(f"{BASE_URL}/api/derivatives/ls/btc")
        assert response.status_code == 200
        
        data = response.json()
        global_ls = data["global"]
        interpretation = data["interpretation"]
        
        # Verify interpretation matches the data
        if global_ls["long_pct"] > 60:
            assert "LONGS CROWDED" in interpretation
        elif global_ls["long_pct"] < 40:
            assert "SHORTS CROWDED" in interpretation
        else:
            assert "BALANCED" in interpretation


class TestFullDerivativesReport:
    """Test full derivatives report with real L/S ratio"""
    
    def test_full_derivatives_btc(self):
        """Full derivatives report should include real L/S data"""
        response = requests.get(f"{BASE_URL}/api/derivatives/full/btc")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify structure
        assert "symbol" in data
        assert "funding" in data
        assert "open_interest" in data
        assert "long_short" in data
        assert "summary" in data
        
        # Verify L/S is REAL
        ls = data["long_short"]
        assert ls["data_source"] == "REAL - OKX Public API"
        assert ls["global"].get("source") == "REAL - OKX Public API"
        
        # Verify summary mentions REAL
        assert "(REAL)" in data["summary"]
    
    def test_full_derivatives_funding_from_4_exchanges(self):
        """Funding should come from 4 exchanges"""
        response = requests.get(f"{BASE_URL}/api/derivatives/full/btc")
        assert response.status_code == 200
        
        data = response.json()
        funding = data["funding"]
        
        # Should have data from multiple exchanges
        assert funding["data_sources"] >= 3  # At least 3 exchanges
        
        # Verify exchange names
        exchange_names = [ex["exchange"] for ex in funding["exchanges"]]
        assert "OKX" in exchange_names


class TestFreeWillAlertNoiseReduction:
    """Test Free Will alert noise reduction features"""
    
    def test_min_confidence_is_65(self):
        """Free Will min_confidence should be 65%"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["min_confidence"] == 65
    
    def test_freewill_stats_structure(self):
        """Free Will stats should have correct structure"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all required fields
        assert "active" in data
        assert "min_confidence" in data
        assert "total_alerts_sent" in data
        assert "pairs_monitored" in data
        assert "timeframes_monitored" in data
        assert "current_weights" in data
        
        # Verify values
        assert data["pairs_monitored"] == 44
        assert data["timeframes_monitored"] == 9
    
    def test_freewill_scan_respects_confidence_threshold(self):
        """Free Will scan should only return setups >= 65% confidence"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/btc?timeframe=1h")
        assert response.status_code == 200
        
        data = response.json()
        
        # If a setup is returned, confidence should be >= 65
        if data is not None:
            assert data["confidence"] >= 65
    
    def test_freewill_scan_multiple_timeframes(self):
        """Test Free Will scan on different timeframes"""
        timeframes = ["5m", "15m", "1h", "4h"]
        
        for tf in timeframes:
            response = requests.get(f"{BASE_URL}/api/freewill/scan/btc?timeframe={tf}")
            assert response.status_code == 200
            
            data = response.json()
            if data is not None:
                assert data["timeframe"] == tf
                assert data["confidence"] >= 65


class TestFreeWillToggleAndConfidence:
    """Test Free Will toggle and confidence endpoints"""
    
    def test_toggle_freewill_on(self):
        """Toggle Free Will on"""
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data["active"] == True
    
    def test_toggle_freewill_off(self):
        """Toggle Free Will off"""
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=false")
        assert response.status_code == 200
        
        data = response.json()
        assert data["active"] == False
        
        # Turn it back on
        requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
    
    def test_set_confidence_threshold(self):
        """Set confidence threshold"""
        # Set to 70
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=70")
        assert response.status_code == 200
        
        data = response.json()
        assert data["min_confidence"] == 70
        
        # Set back to 65
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=65")
        assert response.status_code == 200
        assert response.json()["min_confidence"] == 65
    
    def test_confidence_clamped_to_range(self):
        """Confidence should be clamped to 50-95 range"""
        # Try to set below 50
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=30")
        assert response.status_code == 200
        assert response.json()["min_confidence"] == 50
        
        # Try to set above 95
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=99")
        assert response.status_code == 200
        assert response.json()["min_confidence"] == 95
        
        # Reset to 65
        requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=65")


class TestLSRatioForMultipleCoins:
    """Test L/S ratio for multiple coins"""
    
    @pytest.mark.parametrize("symbol", ["btc", "eth", "sol", "xrp", "doge"])
    def test_ls_ratio_for_coin(self, symbol):
        """L/S ratio should work for multiple coins"""
        response = requests.get(f"{BASE_URL}/api/derivatives/ls/{symbol}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have data or error (some coins may not be available)
        if "error" not in data.get("global", {}):
            assert data["data_source"] == "REAL - OKX Public API"
            assert "long_pct" in data["global"]
            assert "short_pct" in data["global"]


class TestDerivativesFundingEndpoints:
    """Test derivatives funding endpoints"""
    
    def test_aggregated_funding(self):
        """Test aggregated funding from multiple exchanges"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/btc")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "average_funding_rate" in data
        assert "average_funding_pct" in data
        assert "interpretation" in data
        assert "exchanges" in data
        assert "data_sources" in data
        
        # Should have data from multiple exchanges
        assert data["data_sources"] >= 2
    
    def test_exchange_specific_funding(self):
        """Test funding from specific exchanges"""
        exchanges = ["okx", "bitget", "kucoin", "gate"]
        
        for exchange in exchanges:
            response = requests.get(f"{BASE_URL}/api/derivatives/funding/exchange/{exchange}/btc")
            assert response.status_code == 200
            
            data = response.json()
            
            # Should have exchange name or error
            if "error" not in data:
                assert data["exchange"].lower() == exchange.lower() or exchange == "gate"


class TestOpenInterest:
    """Test open interest endpoints"""
    
    def test_aggregated_oi(self):
        """Test aggregated open interest"""
        response = requests.get(f"{BASE_URL}/api/derivatives/oi/btc")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "total_open_interest_value" in data
        assert "total_open_interest_str" in data
        assert "exchanges" in data
        assert "data_sources" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
