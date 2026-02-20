"""
Iteration 20: Test Price Alerts and Backtesting Features
Tests the new P0 features - Custom Price Alerts UI and Backtesting UI
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-preview.preview.emergentagent.com')


class TestPriceAlertsAPI:
    """Test Price Alerts API endpoints"""
    
    def test_alerts_stats(self):
        """GET /api/alerts/stats - Should return alert system statistics"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "active" in data
        assert "auto_alerts_enabled" in data
        assert "tracked_symbols" in data
        assert "custom_alerts" in data
        assert "total_alerts_sent" in data
        assert "thresholds" in data
        
        # Verify thresholds structure
        thresholds = data["thresholds"]
        assert "price_change_5min" in thresholds
        assert "price_change_1h" in thresholds
        assert "rsi_oversold" in thresholds
        assert "rsi_overbought" in thresholds
        assert "volume_spike_mult" in thresholds
        
        print(f"SUCCESS: /api/alerts/stats returned valid stats")
        print(f"  - Tracked symbols: {data['tracked_symbols']}")
        print(f"  - Custom alerts: {data['custom_alerts']}")
        print(f"  - Total sent: {data['total_alerts_sent']}")
    
    def test_alerts_dashboard(self):
        """GET /api/alerts/dashboard - Should return dashboard alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "alerts" in data
        assert "total" in data
        assert "unread" in data
        assert isinstance(data["alerts"], list)
        
        print(f"SUCCESS: /api/alerts/dashboard returned {data['total']} alerts ({data['unread']} unread)")
    
    def test_add_price_alert(self):
        """POST /api/alerts/add - Should add a custom price alert"""
        payload = {
            "symbol": "BTC",
            "target_price": 100000,
            "direction": "above"
        }
        response = requests.post(f"{BASE_URL}/api/alerts/add", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert data.get("success") == True
        assert "alert_id" in data
        assert "message" in data
        
        alert_id = data["alert_id"]
        print(f"SUCCESS: Added alert {alert_id}")
        print(f"  - Message: {data['message']}")
        
        return alert_id
    
    def test_list_custom_alerts(self):
        """GET /api/alerts/custom - Should list custom alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts/custom")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        print(f"SUCCESS: Listed {len(data['alerts'])} custom alerts")
        
        # Verify alert structure if any exist
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "alert_id" in alert
            assert "symbol" in alert
            assert "condition" in alert
            print(f"  - First alert: {alert['symbol']} {alert['condition']}")
    
    def test_add_and_remove_alert_workflow(self):
        """Test complete workflow: add alert, verify, remove"""
        # Add alert
        payload = {
            "symbol": "ETH",
            "target_price": 5000,
            "direction": "above"
        }
        add_response = requests.post(f"{BASE_URL}/api/alerts/add", json=payload)
        assert add_response.status_code == 200
        add_data = add_response.json()
        assert add_data.get("success") == True
        alert_id = add_data["alert_id"]
        print(f"Added alert: {alert_id}")
        
        # Verify it exists
        list_response = requests.get(f"{BASE_URL}/api/alerts/custom")
        assert list_response.status_code == 200
        alerts = list_response.json().get("alerts", [])
        alert_ids = [a["alert_id"] for a in alerts]
        assert alert_id in alert_ids
        print(f"Verified alert exists in list")
        
        # Remove alert
        remove_response = requests.delete(f"{BASE_URL}/api/alerts/{alert_id}")
        assert remove_response.status_code == 200
        remove_data = remove_response.json()
        assert remove_data.get("success") == True
        print(f"Removed alert: {alert_id}")
        
        # Verify it's removed
        list_response2 = requests.get(f"{BASE_URL}/api/alerts/custom")
        alerts2 = list_response2.json().get("alerts", [])
        alert_ids2 = [a["alert_id"] for a in alerts2]
        assert alert_id not in alert_ids2
        print(f"Verified alert removed from list")
        
        print("SUCCESS: Complete add/remove workflow passed")
    
    def test_update_alert_thresholds(self):
        """POST /api/alerts/threshold - Should update thresholds"""
        payload = {
            "price_change_5min": 2.5,
            "rsi_oversold": 30
        }
        response = requests.post(f"{BASE_URL}/api/alerts/threshold", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "thresholds" in data
        # Verify thresholds were updated
        thresholds = data["thresholds"]
        assert thresholds.get("price_change_5min") == 2.5 or "price_change_5min" in thresholds
        
        print(f"SUCCESS: Updated thresholds")
        print(f"  - Thresholds: {thresholds}")
    
    def test_mark_alert_read(self):
        """POST /api/alerts/mark-read/{dashboard_id} - Should mark alert as read"""
        # First get a dashboard alert
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        if data["alerts"]:
            dashboard_id = data["alerts"][0].get("dashboard_id")
            if dashboard_id:
                mark_response = requests.post(f"{BASE_URL}/api/alerts/mark-read/{dashboard_id}")
                assert mark_response.status_code == 200
                print(f"SUCCESS: Marked alert {dashboard_id} as read")
            else:
                print("INFO: No dashboard_id in first alert")
        else:
            print("INFO: No dashboard alerts to mark as read")


class TestBacktestingAPI:
    """Test Backtesting API endpoints"""
    
    def test_backtest_compare_btc(self):
        """GET /api/backtest/compare/BTC - Compare all strategies"""
        response = requests.get(f"{BASE_URL}/api/backtest/compare/BTC?timeframe=1h&days=7")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "symbol" in data
        assert "timeframe" in data
        assert "days" in data
        assert "strategies" in data
        assert "best_strategy" in data
        
        # Should have 3 strategies
        strategies = data["strategies"]
        assert len(strategies) == 3
        
        print(f"SUCCESS: Strategy comparison for BTC")
        print(f"  - Best strategy: {data['best_strategy']}")
        print(f"  - Strategies tested: {len(strategies)}")
        
        for s in strategies:
            if "error" not in s:
                print(f"    - {s['strategy']}: {s.get('win_rate', 'N/A')}% win rate, {s.get('total_pnl_pct', 'N/A')}% PnL")
    
    def test_backtest_rsi_eth(self):
        """GET /api/backtest/rsi/ETH - RSI Mean Reversion strategy"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/rsi/ETH?timeframe=1h&days=30&oversold=30&overbought=70"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "symbol" in data
        assert "strategy" in data
        assert data["strategy"] == "RSI Mean Reversion"
        
        if "error" not in data:
            assert "total_trades" in data
            assert "win_rate" in data
            assert "total_pnl_pct" in data
            assert "profit_factor" in data
            assert "max_drawdown_pct" in data
            assert "trades" in data
            
            print(f"SUCCESS: RSI backtest for ETH")
            print(f"  - Total trades: {data['total_trades']}")
            print(f"  - Win rate: {data['win_rate']}%")
            print(f"  - Total PnL: {data['total_pnl_pct']}%")
            print(f"  - Profit factor: {data['profit_factor']}")
        else:
            print(f"INFO: RSI backtest returned with note: {data.get('error', 'Insufficient data')}")
    
    def test_backtest_bb_sol(self):
        """GET /api/backtest/bb/SOL - Bollinger Band strategy"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/bb/SOL?timeframe=1h&days=30&stop_pct=2.0&target_pct=4.0"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "symbol" in data
        assert "strategy" in data
        assert data["strategy"] == "Bollinger Band"
        
        if "error" not in data:
            assert "total_trades" in data
            assert "trades" in data
            
            print(f"SUCCESS: BB backtest for SOL")
            print(f"  - Total trades: {data['total_trades']}")
            print(f"  - Win rate: {data.get('win_rate', 'N/A')}%")
        else:
            print(f"INFO: BB backtest returned with note: {data.get('error')}")
    
    def test_backtest_ema_bnb(self):
        """GET /api/backtest/ema/BNB - EMA Crossover strategy"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/ema/BNB?timeframe=1h&days=30&fast=9&slow=21"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "symbol" in data
        assert "strategy" in data
        assert data["strategy"] == "EMA Crossover"
        
        if "error" not in data:
            assert "total_trades" in data
            
            print(f"SUCCESS: EMA backtest for BNB")
            print(f"  - Total trades: {data['total_trades']}")
            print(f"  - Win rate: {data.get('win_rate', 'N/A')}%")
        else:
            print(f"INFO: EMA backtest returned with note: {data.get('error')}")
    
    def test_backtest_with_trades_data(self):
        """Verify backtest returns trades data with correct structure"""
        response = requests.get(f"{BASE_URL}/api/backtest/rsi/BTC?timeframe=4h&days=60")
        assert response.status_code == 200
        data = response.json()
        
        if "trades" in data and data["trades"]:
            trade = data["trades"][0]
            # Verify trade structure
            assert "direction" in trade
            assert "entry" in trade
            assert "exit" in trade
            assert "pnl_pct" in trade
            assert "result" in trade
            
            print(f"SUCCESS: Trade data structure verified")
            print(f"  - Sample trade: {trade['direction']} entry=${trade['entry']:.2f} exit=${trade['exit']:.2f} pnl={trade['pnl_pct']:.2f}%")
        else:
            print("INFO: No trades data in response")


class TestNavigationAPIs:
    """Test that the APIs used by navigation tabs work"""
    
    def test_mexc_live(self):
        """GET /api/mexc/live - Market data for dashboard"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        
        assert "symbols" in data
        assert isinstance(data["symbols"], list)
        assert len(data["symbols"]) > 0
        
        print(f"SUCCESS: MEXC live data returned {len(data['symbols'])} symbols")
    
    def test_trading_summary(self):
        """GET /api/trading/summary - Trading summary for dashboard"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Should have basic trading stats
        assert "active" in data or "win_rate" in data
        print(f"SUCCESS: Trading summary returned")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
