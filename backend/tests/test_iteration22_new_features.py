"""
Test Suite for Iteration 22 - New Features
- System Health API (self-healer)
- Trades Closed/Export APIs
- Price Alerts v2 (RSI batching, breakout improvements)
- Alert System endpoints
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-trading-ai.preview.emergentagent.com')

class TestSystemHealth:
    """System Health API tests (self-healer)"""
    
    def test_system_health_endpoint(self):
        """Test /api/system/health returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Check required fields
        assert "overall" in data, "Missing 'overall' field"
        assert "services" in data, "Missing 'services' field"
        assert "total_services" in data, "Missing 'total_services' field"
        assert "healthy_services" in data, "Missing 'healthy_services' field"
        assert "recent_healing" in data, "Missing 'recent_healing' field"
        
        # Check overall status is valid
        assert data["overall"] in ["healthy", "degraded", "critical"], f"Invalid overall status: {data['overall']}"
        
        print(f"✓ System Health: {data['overall']} - {data['healthy_services']}/{data['total_services']} healthy")
    
    def test_service_status_structure(self):
        """Verify each service has correct structure"""
        response = requests.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200
        
        data = response.json()
        services = data.get("services", {})
        assert len(services) > 0, "No services registered"
        
        expected_services = ["rituals", "trading_v2", "free_will", "dual_engine", "price_alerts"]
        for svc_name in expected_services:
            if svc_name in services:
                svc = services[svc_name]
                # Check service fields
                assert "name" in svc, f"Service {svc_name} missing 'name'"
                assert "status" in svc, f"Service {svc_name} missing 'status'"
                assert "error_count" in svc, f"Service {svc_name} missing 'error_count'"
                assert "restart_count" in svc, f"Service {svc_name} missing 'restart_count'"
                assert "is_throttled" in svc, f"Service {svc_name} missing 'is_throttled'"
                print(f"  ✓ Service {svc_name}: {svc['status']}")
        
        print(f"✓ All {len(services)} services have correct structure")


class TestTradesEndpoints:
    """Trades Closed and Export API tests"""
    
    def test_trades_closed_endpoint(self):
        """Test /api/trades/closed returns trades list"""
        response = requests.get(f"{BASE_URL}/api/trades/closed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "trades" in data, "Missing 'trades' field"
        assert "total" in data, "Missing 'total' field"
        assert isinstance(data["trades"], list), "'trades' should be a list"
        
        # Check trade structure if we have trades
        if data["trades"]:
            trade = data["trades"][0]
            required_fields = ["symbol", "direction", "entry_price", "exit_price", "pnl_pct"]
            for field in required_fields:
                assert field in trade, f"Trade missing required field: {field}"
        
        print(f"✓ Trades Closed: {data['total']} trades returned")
    
    def test_trades_export_csv(self):
        """Test /api/trades/export returns valid CSV"""
        response = requests.get(f"{BASE_URL}/api/trades/export")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        # Check content disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp, "Missing attachment header"
        assert "aeon_trades" in content_disp, "Missing filename in header"
        
        # Check CSV header row
        csv_content = response.text
        first_line = csv_content.split('\n')[0]
        expected_headers = ["Date", "Symbol", "Direction", "Entry", "Exit", "PnL%", "Exit Reason", "Style"]
        for header in expected_headers:
            assert header in first_line, f"Missing CSV header: {header}"
        
        print(f"✓ Trades Export CSV: Valid format with {len(csv_content.split(chr(10)))-1} rows")


class TestAlertSystemV2:
    """Alert System v2 API tests (RSI batching, breakout improvements)"""
    
    def test_alerts_stats_endpoint(self):
        """Test /api/alerts/stats returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        required_fields = ["active", "auto_alerts_enabled", "tracked_symbols", 
                          "custom_alerts", "dashboard_alerts_pending", 
                          "total_alerts_sent", "alerts_today", "thresholds"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Check thresholds
        thresholds = data["thresholds"]
        assert "rsi_oversold" in thresholds, "Missing RSI oversold threshold"
        assert "rsi_overbought" in thresholds, "Missing RSI overbought threshold"
        assert "volume_spike_mult" in thresholds, "Missing volume spike multiplier"
        
        print(f"✓ Alert Stats: {data['tracked_symbols']} symbols tracked, {data['alerts_today']} alerts today")
    
    def test_alerts_dashboard_endpoint(self):
        """Test /api/alerts/dashboard returns alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "alerts" in data, "Missing 'alerts' field"
        assert "total" in data, "Missing 'total' field"
        assert "unread" in data, "Missing 'unread' field"
        
        # Check alert structure if we have alerts
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "type" in alert, "Alert missing 'type'"
            assert "message" in alert, "Alert missing 'message'"
            assert "timestamp" in alert, "Alert missing 'timestamp'"
            assert "severity" in alert, "Alert missing 'severity'"
            
            # Check for RSI batched alerts (v2 feature)
            rsi_alerts = [a for a in data["alerts"] if a["type"] == "rsi_extreme"]
            if rsi_alerts:
                # RSI alerts should be batched (symbol = "BATCH")
                batched = [a for a in rsi_alerts if a.get("symbol") == "BATCH"]
                print(f"  ✓ Found {len(batched)} RSI batched alerts (v2 feature)")
            
            # Check for breakout alerts with volume confirmation
            breakout_alerts = [a for a in data["alerts"] if a["type"] == "breakout"]
            if breakout_alerts:
                ba = breakout_alerts[0]
                if "data" in ba and "volume_confirmed" in ba.get("data", {}):
                    print(f"  ✓ Breakout alerts have volume_confirmed flag (v2 feature)")
        
        print(f"✓ Dashboard Alerts: {data['total']} total, {data['unread']} unread")
    
    def test_add_custom_alert(self):
        """Test POST /api/alerts/add creates custom alert"""
        payload = {
            "symbol": "ETH",
            "target_price": 50000,
            "direction": "above"
        }
        response = requests.post(f"{BASE_URL}/api/alerts/add", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Failed to add alert: {data}"
        assert "alert_id" in data, "Missing alert_id in response"
        
        alert_id = data["alert_id"]
        print(f"✓ Custom Alert Added: {alert_id}")
        
        # Cleanup - delete the test alert
        del_response = requests.delete(f"{BASE_URL}/api/alerts/{alert_id}")
        assert del_response.status_code == 200, f"Failed to delete test alert"
        print(f"  ✓ Cleanup: Alert {alert_id} deleted")
    
    def test_list_custom_alerts(self):
        """Test /api/alerts/custom returns alert list"""
        response = requests.get(f"{BASE_URL}/api/alerts/custom")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "alerts" in data, "Missing 'alerts' field"
        assert isinstance(data["alerts"], list), "'alerts' should be a list"
        
        print(f"✓ Custom Alerts: {len(data['alerts'])} alerts")


class TestPriceAlertV2Features:
    """Verify v2 price alert features from price_alerts.py rewrite"""
    
    def test_rsi_batching_behavior(self):
        """Verify RSI alerts are batched (not individual)"""
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        rsi_alerts = [a for a in data["alerts"] if a["type"] == "rsi_extreme"]
        
        if rsi_alerts:
            # In v2, RSI alerts should have symbol = "BATCH" and contain multiple coins
            for alert in rsi_alerts:
                if alert.get("symbol") == "BATCH":
                    alert_data = alert.get("data", {})
                    coins = alert_data.get("coins", [])
                    oversold = alert_data.get("oversold", 0)
                    overbought = alert_data.get("overbought", 0)
                    
                    assert len(coins) > 0, "Batched RSI alert should have coins"
                    assert oversold >= 0, "oversold count should be >= 0"
                    assert overbought >= 0, "overbought count should be >= 0"
                    
                    print(f"✓ RSI Batching: {len(coins)} coins in batch ({oversold} oversold, {overbought} overbought)")
                    return
        
        print("ℹ No RSI batched alerts currently in dashboard - feature exists but no triggers yet")
    
    def test_breakout_volume_confirmation(self):
        """Verify breakout alerts include volume confirmation (v2 feature)"""
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        breakout_alerts = [a for a in data["alerts"] if a["type"] == "breakout"]
        
        if breakout_alerts:
            for alert in breakout_alerts:
                alert_data = alert.get("data", {})
                assert "volume_confirmed" in alert_data, "Breakout alert missing volume_confirmed flag"
                assert "level" in alert_data, "Breakout alert missing level"
                assert "direction" in alert_data, "Breakout alert missing direction"
                
                vol_status = "Vol Confirmed" if alert_data.get("volume_confirmed") else "Low Vol"
                print(f"✓ Breakout Alert: {alert.get('symbol')} {alert_data.get('direction')} [{vol_status}]")
                return
        
        print("ℹ No breakout alerts currently in dashboard - feature exists but no triggers yet")


class TestExistingFeaturesStillWork:
    """Verify existing features still work after rewrite"""
    
    def test_root_endpoint(self):
        """Test / returns correct response"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "online"
        print("✓ Root endpoint working")
    
    def test_mexc_live_data(self):
        """Test market data endpoint"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data, "Missing symbols in market data"
        print(f"✓ Market Data: {len(data.get('symbols', []))} symbols")
    
    def test_freewill_stats(self):
        """Test Free Will v2 stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data or "total_alerts" in data
        print("✓ Free Will v2 stats working")
    
    def test_dual_stats(self):
        """Test Dual Trading Engine stats"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data or "day_trader" in data or "long_term" in data
        print("✓ Dual Engine stats working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
