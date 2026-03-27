"""
Test Suite for Iteration 23 - Backend Routes Refactoring Validation
Tests verify all refactored API endpoints work after modularization into routes/*.py

Covers:
- Self-Healing System (/api/system/health)
- Trading Routes (from routes/trading.py)
- Alert Routes (from routes/alerts.py)
- Market Routes (from routes/market.py)
- Dual Engine Routes
- Free Will Routes
- CSV Export endpoint
- Intelligence Routes
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestBasicEndpoints:
    """Test core API endpoints are responding"""
    
    def test_root_endpoint(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "online"
        print("✓ Root endpoint working")
    
    def test_pairs_endpoint(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/pairs")
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data
        assert "total_pairs" in data
        assert data["total_pairs"] >= 40
        print(f"✓ Pairs endpoint: {data['total_pairs']} pairs available")


class TestSelfHealerSystem:
    """Test Self-Healing System (new feature)"""
    
    def test_system_health_endpoint(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "overall" in data
        assert "services" in data
        assert "total_services" in data
        assert "healthy_services" in data
        assert "recent_healing" in data
        
        # Check services
        services = data["services"]
        expected_services = ["rituals", "trading_v2", "free_will", "dual_engine", "price_alerts"]
        for svc in expected_services:
            assert svc in services, f"Service {svc} not found"
            svc_data = services[svc]
            assert "status" in svc_data
            assert "error_count" in svc_data
            assert "restart_count" in svc_data
        
        print(f"✓ Self-Healer: {data['healthy_services']}/{data['total_services']} healthy")


class TestTradingRoutes:
    """Test refactored trading routes (routes/trading.py)"""
    
    def test_trading_summary(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "total_trades" in data
        assert "win_rate" in data
        assert "total_pnl_pct" in data
        print(f"✓ Trading Summary: {data['total_trades']} trades, {data['win_rate']}% win rate")
    
    def test_trading_v2_stats(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "open_trades" in data
        assert "closed_trades" in data
        print("✓ Trading V2 Stats endpoint working")
    
    def test_trading_v2_open(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trading/v2/open")
        assert response.status_code == 200
        data = response.json()
        assert "open_trades" in data
        assert "total_open" in data
        print(f"✓ Open trades: {data['total_open']}")
    
    def test_trading_v2_closed(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200
        data = response.json()
        assert "closed_trades" in data
        assert "total_closed" in data
        print(f"✓ Closed trades: {data['total_closed']}")
    
    def test_trades_closed(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trades/closed")
        assert response.status_code == 200
        data = response.json()
        assert "trades" in data
        assert "total" in data
        # Check trade structure if trades exist
        if data["trades"]:
            trade = data["trades"][0]
            assert "symbol" in trade
            assert "direction" in trade
            assert "entry_price" in trade
            assert "exit_price" in trade
            assert "pnl_pct" in trade
        print(f"✓ Trades closed API: {data['total']} trades")
    
    def test_trades_export_csv(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trades/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        assert "attachment" in response.headers.get("Content-Disposition", "")
        
        # Check CSV has headers
        content = response.text
        assert "Date" in content
        assert "Symbol" in content
        assert "PnL%" in content
        print("✓ CSV Export endpoint working with proper headers")


class TestDualEngineRoutes:
    """Test Dual Trading Engine routes (Day Trader + Long Term)"""
    
    def test_dual_stats(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "day_trader" in data
        assert "long_term" in data
        
        # Day Trader checks
        dt = data["day_trader"]
        assert dt["name"] == "Day Trader"
        assert dt["style"] == "AGGRESSIVE"
        assert "min_confidence" in dt
        
        # Long Term checks
        lt = data["long_term"]
        assert lt["name"] == "Long Term"
        assert lt["style"] == "SMART"
        
        print(f"✓ Dual Engine: DayTrader conf={dt['min_confidence']}%, LongTerm conf={lt['min_confidence']}%")


class TestFreeWillRoutes:
    """Test Free Will v2 routes"""
    
    def test_freewill_stats(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "min_confidence" in data
        assert "min_confirmations" in data
        assert "data_sources" in data
        assert "pairs_monitored" in data
        
        assert len(data["data_sources"]) >= 5
        print(f"✓ FreeWill v2: {len(data['data_sources'])} data sources, {data['pairs_monitored']} pairs")


class TestAlertRoutes:
    """Test Alert System routes"""
    
    def test_alerts_stats(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "tracked_symbols" in data
        assert "thresholds" in data
        print(f"✓ Alerts: {data['tracked_symbols']} symbols tracked")
    
    def test_alerts_dashboard(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/alerts/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert "total" in data
        assert "unread" in data
        print(f"✓ Dashboard alerts: {data['total']} total, {data['unread']} unread")
    
    def test_alerts_custom_list(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/alerts/custom")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        print(f"✓ Custom alerts: {len(data['alerts'])} alerts")


class TestMarketRoutes:
    """Test Market data routes"""
    
    def test_mexc_live(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        print(f"✓ MEXC Live: {len(data['symbols'])} symbols")
    
    def test_market_scan(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/market/scan/BTC")
        assert response.status_code == 200
        data = response.json()
        if "error" not in data:
            assert "price" in data or "signals" in data
            print(f"✓ Market Scan BTC: working")
        else:
            print(f"⚠ Market Scan BTC: {data.get('error', 'unknown error')}")


class TestIntelligenceRoutes:
    """Test Intelligence/Analysis routes"""
    
    def test_intel_top100(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/intel/top100")
        assert response.status_code == 200
        data = response.json()
        if "error" not in data:
            print(f"✓ Top 100 endpoint working")
    
    def test_intel_fear_greed(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/intel/fear-greed")
        assert response.status_code == 200
        data = response.json()
        # May have rate limit errors but endpoint should respond
        print(f"✓ Fear & Greed endpoint responding")


class TestBotRoutes:
    """Test Bot stats and utility routes"""
    
    def test_bot_stats(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/bot/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_messages" in data
        assert "unique_users" in data
        assert "active_users" in data
        print(f"✓ Bot Stats: {data['unique_users']} users, {data['total_messages']} messages")
    
    def test_bot_test(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/bot/test")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        print(f"✓ Bot Test: {data.get('status', 'unknown')}")


class TestDerivativesRoutes:
    """Test Derivatives routes"""
    
    def test_derivatives_funding(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/derivatives/funding/BTC")
        assert response.status_code == 200
        print("✓ Derivatives funding endpoint working")
    
    def test_coinglass_funding(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/coinglass/funding/BTC")
        assert response.status_code == 200
        print("✓ Coinglass funding endpoint working")


class TestStrategyRoutes:
    """Test Strategy routes"""
    
    def test_strategies_all(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/strategies/all/BTC")
        assert response.status_code == 200
        print("✓ Strategies all endpoint working")


class TestSMCRoutes:
    """Test SMC (Smart Money Concepts) routes"""
    
    def test_smc_zones(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/smc/zones/BTC")
        assert response.status_code == 200
        print("✓ SMC zones endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
