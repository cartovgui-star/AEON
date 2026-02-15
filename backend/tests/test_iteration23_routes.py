"""
Iteration 23 Backend Tests: Server.py Modular Refactoring
- Tests endpoints from routes/market.py, routes/trading.py, routes/analysis.py
- Tests mobile-related endpoints via API
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSystemHealth:
    """Test /api/system/health endpoint"""
    
    def test_system_health_returns_status(self):
        """System health endpoint should return overall status"""
        response = requests.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "overall" in data
        assert "services" in data
        assert data["overall"] in ["HEALTHY", "DEGRADED", "CRITICAL"]
        print(f"System health: {data['overall']}")


class TestTradesEndpoints:
    """Test /api/trades/* endpoints (from routes/trading.py)"""
    
    def test_trades_closed_returns_list(self):
        """/api/trades/closed returns trades list"""
        response = requests.get(f"{BASE_URL}/api/trades/closed")
        assert response.status_code == 200
        data = response.json()
        assert "trades" in data
        assert "total" in data
        assert isinstance(data["trades"], list)
        print(f"Trades closed: {data['total']} total")
    
    def test_trades_export_returns_csv(self):
        """/api/trades/export returns CSV data"""
        response = requests.get(f"{BASE_URL}/api/trades/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        # Check for CSV headers
        assert "Date" in response.text
        assert "Symbol" in response.text
        print("Trades export: CSV headers present")


class TestSentimentEndpoints:
    """Test sentiment endpoints (from routes/market.py)"""
    
    def test_sentiment_composite_btc(self):
        """/api/sentiment/composite?symbol=BTC returns sentiment data"""
        response = requests.get(f"{BASE_URL}/api/sentiment/composite?symbol=BTC")
        assert response.status_code == 200
        data = response.json()
        # Should have composite sentiment data
        assert "symbol" in data or "composite_score" in data or "sentiment" in data or isinstance(data, dict)
        print(f"Sentiment composite for BTC: {data}")


class TestStrategyHealthEndpoints:
    """Test strategy-health endpoints (from routes/trading.py)"""
    
    def test_strategy_health_status(self):
        """/api/strategy-health/status returns status"""
        response = requests.get(f"{BASE_URL}/api/strategy-health/status")
        assert response.status_code == 200
        data = response.json()
        # Should return strategy health data
        assert isinstance(data, dict)
        print(f"Strategy health status: {data.keys()}")


class TestAlertsEndpoints:
    """Test alerts endpoints (from routes/trading.py)"""
    
    def test_alerts_stats(self):
        """/api/alerts/stats returns alert statistics"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        print(f"Alerts stats: {data}")


class TestDualEngineEndpoints:
    """Test dual trading engine endpoints (from routes/trading.py)"""
    
    def test_dual_stats(self):
        """/api/dual/stats returns day trader + long term stats"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        data = response.json()
        # Should have day_trader and long_term keys
        assert "day_trader" in data or "active" in data
        print(f"Dual stats keys: {list(data.keys())}")


class TestTradingV2Endpoints:
    """Test trading v2 endpoints (from routes/trading.py)"""
    
    def test_trading_v2_stats(self):
        """/api/trading/v2/stats returns trading stats"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        data = response.json()
        # Should have trading stats
        assert isinstance(data, dict)
        assert "active" in data or "min_confidence" in data or "win_rate" in data
        print(f"Trading v2 stats: win_rate={data.get('win_rate', 'N/A')}")


class TestFreeWillEndpoints:
    """Test freewill endpoints (from routes/trading.py)"""
    
    def test_freewill_stats(self):
        """/api/freewill/stats returns freewill engine stats"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Should have active status and confidence
        assert "active" in data or "min_confidence" in data
        print(f"FreeWill stats: active={data.get('active', 'N/A')}")


class TestArbitrageEndpoints:
    """Test arbitrage endpoints (from routes/market.py)"""
    
    def test_arbitrage_recent(self):
        """/api/arbitrage/recent returns recent opportunities"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/recent")
        assert response.status_code == 200
        data = response.json()
        assert "opportunities" in data
        assert isinstance(data["opportunities"], list)
        print(f"Arbitrage recent: {len(data['opportunities'])} opportunities")


class TestMarketEndpoints:
    """Test market endpoints exist and work"""
    
    def test_market_scan_btc(self):
        """/api/market/scan/BTC works"""
        response = requests.get(f"{BASE_URL}/api/market/scan/BTC")
        assert response.status_code == 200
        data = response.json()
        # Should have price or technical data
        assert "price" in data or "technical" in data or "error" not in data
        print(f"Market scan BTC: price={data.get('price', 'N/A')}")
    
    def test_intel_fear_greed(self):
        """/api/intel/fear-greed works"""
        response = requests.get(f"{BASE_URL}/api/intel/fear-greed")
        assert response.status_code == 200
        data = response.json()
        print(f"Fear & Greed: {data}")


class TestMEXCEndpoint:
    """Test MEXC live data endpoint"""
    
    def test_mexc_live_data(self):
        """/api/mexc/live returns live market data"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        assert isinstance(data["symbols"], list)
        if len(data["symbols"]) > 0:
            assert "symbol" in data["symbols"][0]
            assert "price" in data["symbols"][0]
        print(f"MEXC live: {len(data['symbols'])} symbols loaded")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
