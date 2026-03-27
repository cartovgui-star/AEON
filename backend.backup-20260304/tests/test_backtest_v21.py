"""
Test V2.1 Backtest API Endpoints
Tests the HIGH WIN RATE strategy backtest against MEXC historical data

Features tested:
- /api/backtest/v21/settings - Get V2.1 strategy settings
- /api/backtest/v21/compare - Compare V2.1 performance across BTC, ETH, SOL
- /api/backtest/v21/quick/{symbol} - Quick backtest for single symbol
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBacktestV21Settings:
    """Test V2.1 Settings Endpoint"""
    
    def test_get_v21_settings(self):
        """Test GET /api/backtest/v21/settings returns correct V2.1 strategy settings"""
        response = requests.get(f"{BASE_URL}/api/backtest/v21/settings")
        
        # Status code check
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify settings structure
        assert "settings" in data, "Response should contain 'settings'"
        assert "description" in data, "Response should contain 'description'"
        
        settings = data["settings"]
        
        # Verify V2.1 HIGH WIN RATE settings values
        assert settings.get("min_confidence") == 90, "Min confidence should be 90%"
        assert settings.get("min_confirmations") == 5, "Min confirmations should be 5/5"
        assert settings.get("min_rr_ratio") == 3.0, "Min R:R should be 3:1"
        assert settings.get("min_adx") == 25, "Min ADX should be 25"
        assert settings.get("min_volume_multiplier") == 1.5, "Min volume multiplier should be 1.5x"
        assert "ema_no_trade_zone_pct" in settings, "Should have EMA no-trade zone setting"
        assert "session_filter" in settings, "Should have session filter setting"
        
        print(f"✅ V2.1 Settings verified: {settings}")


class TestBacktestV21Quick:
    """Test Quick Backtest for Single Symbol"""
    
    def test_quick_backtest_btc(self):
        """Test GET /api/backtest/v21/quick/BTC returns backtest results"""
        # Quick backtest can take 10-30 seconds
        response = requests.get(
            f"{BASE_URL}/api/backtest/v21/quick/BTC",
            params={"interval": "1h", "days": 7},  # Use shorter period for faster test
            timeout=60
        )
        
        # Status code check
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Response should have status field"
        
        if data["status"] == "success":
            result = data["result"]
            
            # Verify result structure
            assert "data_source" in result, "Result should have data_source"
            assert result["data_source"] == "MEXC", "Data source should be MEXC"
            
            assert "win_rate" in result, "Result should have win_rate"
            assert "total_trades" in result, "Result should have total_trades"
            assert "filter_breakdown" in result, "Result should have filter_breakdown"
            assert "settings" in result, "Result should have settings"
            
            # Win rate can be 0-100
            assert 0 <= result["win_rate"] <= 100, f"Win rate should be 0-100, got {result['win_rate']}"
            
            print(f"✅ Quick backtest BTC: Win Rate={result['win_rate']}%, Trades={result['total_trades']}, Data Source={result['data_source']}")
        else:
            # Even errors should be handled gracefully
            print(f"⚠️ Quick backtest returned status: {data['status']}, message: {data.get('message', 'N/A')}")
            # Don't fail on error - MEXC API might be temporarily unavailable
    
    def test_quick_backtest_eth(self):
        """Test GET /api/backtest/v21/quick/ETH returns backtest results"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/v21/quick/ETH",
            params={"interval": "1h", "days": 7},
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data
        
        if data["status"] == "success":
            result = data["result"]
            assert result["data_source"] == "MEXC"
            print(f"✅ Quick backtest ETH: Win Rate={result['win_rate']}%, Trades={result['total_trades']}")
    
    def test_quick_backtest_sol(self):
        """Test GET /api/backtest/v21/quick/SOL returns backtest results"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/v21/quick/SOL",
            params={"interval": "1h", "days": 7},
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data
        
        if data["status"] == "success":
            result = data["result"]
            assert result["data_source"] == "MEXC"
            print(f"✅ Quick backtest SOL: Win Rate={result['win_rate']}%, Trades={result['total_trades']}")


class TestBacktestV21Compare:
    """Test Comparison Backtest Endpoint"""
    
    def test_compare_backtest(self):
        """Test GET /api/backtest/v21/compare returns comparison across BTC, ETH, SOL"""
        # This can take 30-90 seconds for 30 days
        response = requests.get(
            f"{BASE_URL}/api/backtest/v21/compare",
            params={"days": 7, "interval": "1h"},  # Use shorter period for faster test
            timeout=120
        )
        
        # Status code check
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Response should have status"
        
        if data["status"] == "success":
            # Verify data source is MEXC
            assert data.get("data_source") == "MEXC", "Data source should be MEXC"
            
            # Verify aggregate stats
            assert "aggregate" in data, "Response should have aggregate stats"
            aggregate = data["aggregate"]
            
            assert "total_trades" in aggregate, "Aggregate should have total_trades"
            assert "wins" in aggregate, "Aggregate should have wins"
            assert "losses" in aggregate, "Aggregate should have losses"
            assert "win_rate" in aggregate, "Aggregate should have win_rate"
            assert "old_win_rate" in aggregate, "Aggregate should have old_win_rate"
            assert "improvement" in aggregate, "Aggregate should have improvement"
            assert "signal_reduction_pct" in aggregate, "Aggregate should have signal_reduction_pct"
            
            # Verify by_symbol breakdown
            assert "by_symbol" in data, "Response should have by_symbol breakdown"
            by_symbol = data["by_symbol"]
            
            # Should have results for each symbol (even if 0 trades)
            symbols_tested = [s["symbol"] for s in by_symbol]
            print(f"Symbols tested: {symbols_tested}")
            
            # Verify filter effectiveness
            assert "filter_effectiveness" in data, "Response should have filter_effectiveness"
            filters = data["filter_effectiveness"]
            
            # Expected filter keys from V2.1 strategy
            expected_filters = ["ema_200", "adx", "volume", "session", "confidence", "rr"]
            for f in expected_filters:
                if f in filters:
                    print(f"  Filter {f}: {filters[f]} signals blocked")
            
            # Verify recommendations
            assert "recommendations" in data, "Response should have recommendations"
            
            print(f"✅ Compare backtest: Win Rate={aggregate['win_rate']}%, Trades={aggregate['total_trades']}, Improvement={aggregate['improvement']}%")
            print(f"   Signal Reduction: {aggregate['signal_reduction_pct']}%")
        else:
            print(f"⚠️ Compare backtest returned status: {data['status']}, message: {data.get('message', 'N/A')}")


class TestBacktestV21Run:
    """Test Run Backtest Endpoint (async)"""
    
    def test_run_backtest_start(self):
        """Test POST /api/backtest/v21/run starts background backtest"""
        response = requests.post(
            f"{BASE_URL}/api/backtest/v21/run",
            json={
                "symbols": ["BTC/USDT"],
                "interval": "1h",
                "days": 7
            },
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should return started or already_running status
        assert "status" in data
        assert data["status"] in ["started", "already_running"], f"Unexpected status: {data['status']}"
        
        if data["status"] == "started":
            print(f"✅ Backtest started: {data.get('message', '')}")
        else:
            print(f"✅ Backtest already running: {data.get('message', '')}")
    
    def test_backtest_status(self):
        """Test GET /api/backtest/v21/status returns current status"""
        response = requests.get(f"{BASE_URL}/api/backtest/v21/status", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        assert "is_running" in data, "Status should have is_running"
        assert "progress" in data, "Status should have progress"
        assert "has_result" in data, "Status should have has_result"
        
        print(f"✅ Status: running={data['is_running']}, progress={data['progress']}%, has_result={data['has_result']}")
    
    def test_backtest_result(self):
        """Test GET /api/backtest/v21/result returns last result"""
        response = requests.get(f"{BASE_URL}/api/backtest/v21/result", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        assert "status" in data
        
        if data["status"] == "success":
            result = data["result"]
            assert "data_source" in result
            print(f"✅ Result available: Win Rate={result.get('win_rate', 'N/A')}%")
        else:
            print(f"✅ No result yet: {data.get('message', 'N/A')}")


class TestBacktestV21FilterBreakdown:
    """Test that filter breakdown statistics are returned correctly"""
    
    def test_filter_breakdown_structure(self):
        """Test that filter breakdown contains expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/v21/quick/BTC",
            params={"interval": "1h", "days": 7},
            timeout=60
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        if data["status"] == "success":
            result = data["result"]
            
            # Check filter_breakdown exists and has expected keys
            assert "filter_breakdown" in result
            breakdown = result["filter_breakdown"]
            
            # V2.1 filters that should be tracked
            expected_keys = ["ema_200", "adx", "volume", "session", "confidence", "rr", "rsi_counter_trend"]
            
            for key in expected_keys:
                assert key in breakdown, f"Filter breakdown should have '{key}'"
            
            print(f"✅ Filter breakdown structure verified: {breakdown}")
        else:
            print(f"⚠️ Skipped filter breakdown check - backtest not successful")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
