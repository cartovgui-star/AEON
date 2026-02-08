"""
Autonomous Trader v2 Backend Tests - Iteration 11
Tests the new elite trading engine with ALL data sources

Endpoints tested:
1. /api/trading/summary - v2 stats with correct fields
2. /api/trading/opportunities - elite signals array
3. /api/trading/v2/stats - comprehensive v2 statistics
4. /api/trading/toggle?active=true - toggles v2 engine
5. /api/freewill/stats - free will v2 stats with data_sources
6. /api/bot/test - success status with all systems
7. /api/trading/analyze/BTC - analyze symbol (may return null)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTradingSummaryV2:
    """Test /api/trading/summary - v2 stats with correct fields"""
    
    def test_trading_summary_returns_v2_stats(self):
        """Verify summary returns v2 stats with all required fields"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify v2-specific fields exist
        required_fields = [
            "active",
            "total_signals_analyzed",
            "win_rate",
            "market_regime",
            "btc_bias",
            "fear_greed",
            "min_confidence",
            "min_confirmations"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"Trading summary v2 stats: active={data['active']}, signals={data['total_signals_analyzed']}")
        
    def test_trading_summary_min_confidence_85(self):
        """Verify min_confidence is 85 for v2 engine"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("min_confidence") == 85, f"Expected min_confidence=85, got {data.get('min_confidence')}"
        print(f"min_confidence verified: {data.get('min_confidence')}")
    
    def test_trading_summary_min_confirmations_4(self):
        """Verify min_confirmations is 4 for v2 engine"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("min_confirmations") == 4, f"Expected min_confirmations=4, got {data.get('min_confirmations')}"
        print(f"min_confirmations verified: {data.get('min_confirmations')}")
    
    def test_trading_summary_market_regime_valid(self):
        """Verify market_regime is a valid value"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        valid_regimes = ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE", "CHOPPY", "UNKNOWN"]
        assert data.get("market_regime") in valid_regimes, f"Invalid market_regime: {data.get('market_regime')}"
        print(f"market_regime: {data.get('market_regime')}")
    
    def test_trading_summary_btc_bias_valid(self):
        """Verify btc_bias is a valid value"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        valid_biases = ["BULLISH", "BEARISH", "NEUTRAL"]
        assert data.get("btc_bias") in valid_biases, f"Invalid btc_bias: {data.get('btc_bias')}"
        print(f"btc_bias: {data.get('btc_bias')}")
    
    def test_trading_summary_fear_greed_in_range(self):
        """Verify fear_greed is 0-100"""
        response = requests.get(f"{BASE_URL}/api/trading/summary", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        fg = data.get("fear_greed", 50)
        assert 0 <= fg <= 100, f"fear_greed out of range: {fg}"
        print(f"fear_greed: {fg}")


class TestTradingOpportunities:
    """Test /api/trading/opportunities - elite signals array"""
    
    def test_trading_opportunities_returns_array(self):
        """Verify opportunities returns an array (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"Elite signals count: {len(data)}")
    
    def test_trading_opportunities_signal_structure(self):
        """If signals exist, verify their structure"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        
        if len(data) > 0:
            signal = data[0]
            expected_fields = ["symbol", "direction", "confidence", "entry", "stop", "target"]
            for field in expected_fields:
                assert field in signal, f"Signal missing field: {field}"
            
            # Confidence should be >= 85
            assert signal.get("confidence", 0) >= 85, f"Signal confidence below 85: {signal.get('confidence')}"
            print(f"Signal: {signal.get('symbol')} {signal.get('direction')} conf={signal.get('confidence')}")
        else:
            print("No signals found (expected in volatile/extreme fear market conditions)")


class TestTradingV2Stats:
    """Test /api/trading/v2/stats - comprehensive v2 statistics"""
    
    def test_v2_stats_endpoint(self):
        """Verify v2/stats endpoint returns comprehensive stats"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify comprehensive stats fields
        stat_fields = [
            "active", "total_signals_analyzed", "total_trades",
            "open_trades", "closed_trades", "wins", "losses",
            "win_rate", "total_pnl_pct"
        ]
        
        for field in stat_fields:
            assert field in data, f"Missing stat field: {field}"
        
        print(f"v2 Stats: trades={data.get('total_trades')}, win_rate={data.get('win_rate')}%")
    
    def test_v2_stats_has_profit_factor(self):
        """Verify v2 stats includes profit_factor"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "profit_factor" in data, "Missing profit_factor"
        print(f"profit_factor: {data.get('profit_factor')}")
    
    def test_v2_stats_has_expectancy(self):
        """Verify v2 stats includes expectancy"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "expectancy" in data, "Missing expectancy"
        print(f"expectancy: {data.get('expectancy')}")


class TestTradingToggle:
    """Test /api/trading/toggle - toggle v2 engine on/off"""
    
    def test_toggle_trading_on(self):
        """Verify toggle with active=true returns engine=v2"""
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=true", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("active") == True, f"Expected active=True, got {data.get('active')}"
        assert data.get("engine") == "v2", f"Expected engine=v2, got {data.get('engine')}"
        print("Trading toggle ON verified: engine=v2")
    
    def test_toggle_trading_off(self):
        """Verify toggle with active=false"""
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=false", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("active") == False, f"Expected active=False, got {data.get('active')}"
        print("Trading toggle OFF verified")
        
        # Turn it back on
        requests.post(f"{BASE_URL}/api/trading/toggle?active=true", timeout=10)


class TestFreeWillStats:
    """Test /api/freewill/stats - free will v2 stats with data_sources"""
    
    def test_freewill_stats_returns_data_sources(self):
        """Verify freewill stats includes data_sources array"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "data_sources" in data, "Missing data_sources field"
        assert isinstance(data["data_sources"], list), "data_sources should be a list"
        
        # Verify 8 data sources
        expected_sources = [
            "Technical Analysis",
            "Divergence Detection",
            "Market Structure",
            "VWAP",
            "Order Flow / CVD",
            "Options (BTC/ETH)",
            "Derivatives",
            "Fear & Greed"
        ]
        
        for source in expected_sources:
            assert source in data["data_sources"], f"Missing data source: {source}"
        
        print(f"data_sources verified: {len(data['data_sources'])} sources")
    
    def test_freewill_stats_min_confidence_80(self):
        """Verify freewill min_confidence is 80"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("min_confidence") == 80, f"Expected min_confidence=80, got {data.get('min_confidence')}"
        print(f"freewill min_confidence: {data.get('min_confidence')}")
    
    def test_freewill_stats_min_confirmations_3(self):
        """Verify freewill min_confirmations is 3"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("min_confirmations") == 3, f"Expected min_confirmations=3, got {data.get('min_confirmations')}"
        print(f"freewill min_confirmations: {data.get('min_confirmations')}")


class TestBotTest:
    """Test /api/bot/test - success status with all systems"""
    
    def test_bot_test_returns_success(self):
        """Verify bot/test returns success status"""
        response = requests.get(f"{BASE_URL}/api/bot/test", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "success", f"Expected status=success, got {data.get('status')}"
        print("bot/test status: success")
    
    def test_bot_test_llm_ok(self):
        """Verify LLM system is working"""
        response = requests.get(f"{BASE_URL}/api/bot/test", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("llm") == True, f"LLM not working: {data.get('llm')}"
        print("LLM system: OK")
    
    def test_bot_test_binance_ok(self):
        """Verify Binance connection is working"""
        response = requests.get(f"{BASE_URL}/api/bot/test", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("binance") == True, f"Binance not working: {data.get('binance')}"
        print("Binance system: OK")
    
    def test_bot_test_mexc_ok(self):
        """Verify MEXC credentials are set"""
        response = requests.get(f"{BASE_URL}/api/bot/test", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("mexc") == True, f"MEXC not configured: {data.get('mexc')}"
        print("MEXC system: OK")
    
    def test_bot_test_telegram_ok(self):
        """Verify Telegram token is set"""
        response = requests.get(f"{BASE_URL}/api/bot/test", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("telegram") == True, f"Telegram not configured: {data.get('telegram')}"
        print("Telegram system: OK")


class TestTradingAnalyze:
    """Test /api/trading/analyze/{symbol} - analyze symbol"""
    
    def test_analyze_btc_endpoint(self):
        """Verify analyze BTC endpoint works (may return null)"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/BTC", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        # May be null if below threshold - that's expected
        if data is None:
            print("BTC analyze returned null (below threshold - expected in current market)")
        else:
            assert "symbol" in data or "direction" in data, "Response should have symbol or direction"
            print(f"BTC analyze result: {data.get('direction', 'N/A')} conf={data.get('confidence', 'N/A')}")
    
    def test_analyze_eth_endpoint(self):
        """Verify analyze ETH endpoint works"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/ETH", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if data is None:
            print("ETH analyze returned null (below threshold - expected)")
        else:
            print(f"ETH analyze result: {data.get('direction', 'N/A')} conf={data.get('confidence', 'N/A')}")
    
    def test_analyze_sol_endpoint(self):
        """Verify analyze SOL endpoint works"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/SOL", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        if data is None:
            print("SOL analyze returned null (below threshold - expected)")
        else:
            print(f"SOL analyze result: {data.get('direction', 'N/A')} conf={data.get('confidence', 'N/A')}")


class TestV2OpenClosedTrades:
    """Test /api/trading/v2/open and /api/trading/v2/closed endpoints"""
    
    def test_v2_open_trades(self):
        """Verify v2/open endpoint returns open trades"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/open", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "open_trades" in data, "Missing open_trades field"
        assert "total_open" in data, "Missing total_open field"
        print(f"Open trades: {data.get('total_open')}")
    
    def test_v2_closed_trades(self):
        """Verify v2/closed endpoint returns closed trades"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "closed_trades" in data, "Missing closed_trades field"
        assert "total_closed" in data, "Missing total_closed field"
        print(f"Closed trades: {data.get('total_closed')}")


class TestV2ConfidenceSetting:
    """Test /api/trading/v2/confidence - set min confidence"""
    
    def test_set_v2_confidence(self):
        """Verify setting v2 confidence works"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/confidence?min_conf=90", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("min_confidence") == 90, f"Expected min_confidence=90, got {data.get('min_confidence')}"
        print("v2 confidence set to 90")
        
        # Reset to default
        requests.post(f"{BASE_URL}/api/trading/v2/confidence?min_conf=85", timeout=10)
    
    def test_v2_confidence_bounds(self):
        """Verify confidence is bounded 70-98"""
        # Test lower bound
        response = requests.post(f"{BASE_URL}/api/trading/v2/confidence?min_conf=50", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") >= 70, f"Lower bound not enforced: {data.get('min_confidence')}"
        
        # Test upper bound
        response = requests.post(f"{BASE_URL}/api/trading/v2/confidence?min_conf=99", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") <= 98, f"Upper bound not enforced: {data.get('min_confidence')}"
        
        # Reset to default
        requests.post(f"{BASE_URL}/api/trading/v2/confidence?min_conf=85", timeout=10)
        print("v2 confidence bounds verified (70-98)")


class TestHealthAndBasics:
    """Basic health checks"""
    
    def test_api_health(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "online", f"Expected status=online, got {data.get('status')}"
        print("API health: online")
    
    def test_pairs_endpoint(self):
        """Verify pairs endpoint returns 44 pairs"""
        response = requests.get(f"{BASE_URL}/api/pairs", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("total_pairs") == 44, f"Expected 44 pairs, got {data.get('total_pairs')}"
        print(f"Total pairs: {data.get('total_pairs')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
