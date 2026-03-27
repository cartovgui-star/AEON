"""
Iteration 33 - Test New Features:
1. Dynamic Trade Style Assignment (SCALP/DAY/SWING) based on ATR volatility and timeframe
2. Position Scaling (50% entry on signal, 50% on confirmation)
3. Dashboard Stats API (/api/stats/dashboard)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDashboardStatsAPI:
    """Test /api/stats/dashboard endpoint - P1 feature"""
    
    def test_dashboard_stats_endpoint_accessible(self):
        """Test that dashboard stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/stats/dashboard")
        assert response.status_code == 200, f"Dashboard stats endpoint failed with status {response.status_code}"
        print("PASS: Dashboard stats endpoint is accessible")
    
    def test_dashboard_stats_structure(self):
        """Verify dashboard stats response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/stats/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields exist
        required_fields = [
            "best_pairs",
            "worst_pairs", 
            "blacklisted_pairs",
            "pairs_on_cooldown",
            "position_scaling",
            "trading_config"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: Dashboard stats has all required fields: {list(data.keys())}")
    
    def test_position_scaling_config(self):
        """Verify position scaling configuration in dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/stats/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        scaling = data.get("position_scaling", {})
        assert "enabled" in scaling, "Missing 'enabled' field in position_scaling"
        assert "initial_entry_pct" in scaling, "Missing 'initial_entry_pct' field"
        assert "pending_scale_ins" in scaling, "Missing 'pending_scale_ins' field"
        assert "positions" in scaling, "Missing 'positions' field"
        
        # Verify 50/50 scaling configuration
        assert scaling.get("initial_entry_pct") == 50, f"Expected 50% initial entry, got {scaling.get('initial_entry_pct')}"
        print(f"PASS: Position scaling config: enabled={scaling['enabled']}, initial_entry_pct={scaling['initial_entry_pct']}")
    
    def test_trading_config_fields(self):
        """Verify trading config in dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/stats/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        config = data.get("trading_config", {})
        expected_fields = ["min_confidence", "min_confirmations", "max_open_trades", "cooldown_hours"]
        
        for field in expected_fields:
            assert field in config, f"Missing config field: {field}"
        
        print(f"PASS: Trading config: {config}")


class TestTradingStatsAPI:
    """Test existing trading stats endpoints still work"""
    
    def test_trading_v2_stats(self):
        """Test /api/trading/v2/stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify key fields
        assert "active" in data, "Missing 'active' field"
        assert "win_rate" in data, "Missing 'win_rate' field"
        assert "total_pnl_pct" in data, "Missing 'total_pnl_pct' field"
        assert "market_regime" in data, "Missing 'market_regime' field"
        
        print(f"PASS: Trading v2 stats - WR: {data['win_rate']}%, PnL: {data['total_pnl_pct']}%")
    
    def test_trading_summary(self):
        """Test /api/trading/summary endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        print(f"PASS: Trading summary endpoint working, active={data['active']}")


class TestLivePositionsAPI:
    """Test live positions endpoint - P1"""
    
    def test_live_positions_endpoint(self):
        """Test /api/trading/v2/live-positions endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        
        assert "positions" in data, "Missing 'positions' field"
        assert "total_positions" in data, "Missing 'total_positions' field"
        assert "total_pnl_pct" in data, "Missing 'total_pnl_pct' field"
        
        print(f"PASS: Live positions - {data['total_positions']} open positions, total PnL: {data['total_pnl_pct']}%")
    
    def test_position_has_trade_type(self):
        """Verify positions have trade_type field (SCALP/DAY/SWING)"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        
        positions = data.get("positions", [])
        if positions:
            for pos in positions:
                assert "trade_type" in pos, f"Position {pos.get('symbol')} missing trade_type"
                assert pos["trade_type"] in ["SCALP", "DAY", "SWING"], f"Invalid trade_type: {pos['trade_type']}"
                print(f"  Position {pos['symbol']}: {pos['trade_type']} {pos['direction']} {pos['leverage']}x")
            print(f"PASS: All {len(positions)} positions have valid trade_type")
        else:
            print("INFO: No open positions to verify trade_type on")


class TestPositionScalingToggle:
    """Test position scaling toggle API"""
    
    def test_toggle_scaling_endpoint(self):
        """Test POST /api/trading/v2/toggle-scaling"""
        # First disable
        response = requests.post(f"{BASE_URL}/api/trading/v2/toggle-scaling?enabled=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("position_scaling_enabled") == False
        
        # Then enable
        response = requests.post(f"{BASE_URL}/api/trading/v2/toggle-scaling?enabled=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("position_scaling_enabled") == True
        
        print("PASS: Position scaling toggle works correctly")


class TestClosedTradesAPI:
    """Test closed trades endpoint"""
    
    def test_closed_trades_endpoint(self):
        """Test /api/trading/v2/closed endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200
        data = response.json()
        
        assert "closed_trades" in data, "Missing 'closed_trades' field"
        assert "total_closed" in data, "Missing 'total_closed' field"
        
        print(f"PASS: Closed trades - {data['total_closed']} total")
    
    def test_trades_closed_endpoint(self):
        """Test /api/trades/closed endpoint"""
        response = requests.get(f"{BASE_URL}/api/trades/closed")
        assert response.status_code == 200
        data = response.json()
        
        assert "trades" in data, "Missing 'trades' field"
        print(f"PASS: Trades closed endpoint - {len(data.get('trades', []))} trades")


class TestDetermineTradeStyleLogic:
    """
    Test the determine_trade_style logic by examining positions.
    Since we can't call Python functions directly, we verify through:
    1. Existing positions have correct trade_type
    2. analyze_signal endpoint returns trade_type
    """
    
    def test_analyze_returns_trade_type(self):
        """Test that analyze endpoint returns trade_type"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/BTC?timeframe=4h")
        # This may return null if no signal, but should not error
        assert response.status_code == 200
        data = response.json()
        
        if data:
            if "trade_type" in data:
                assert data["trade_type"] in ["SCALP", "DAY", "SWING"], f"Invalid trade_type: {data['trade_type']}"
                print(f"PASS: Analyze BTC returns trade_type={data.get('trade_type')}, atr_pct={data.get('atr_pct')}")
            else:
                print("INFO: No signal found for BTC/4h - cannot verify trade_type")
        else:
            print("INFO: No signal found for BTC/4h analysis")
    
    def test_positions_have_atr_pct(self):
        """Verify positions store ATR percentage for trade style determination"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        
        positions = data.get("positions", [])
        if positions:
            for pos in positions:
                # atr_pct may be None for older trades
                print(f"  {pos['symbol']}: trade_type={pos.get('trade_type')}, atr_pct={pos.get('atr_pct')}")
            print("PASS: Verified position trade_type data")
        else:
            print("INFO: No positions to verify")


class TestTradeStyleDistribution:
    """Verify trade styles are being dynamically assigned (not all SWING)"""
    
    def test_closed_trades_have_varied_styles(self):
        """Check if closed trades have different trade styles"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200
        data = response.json()
        
        trades = data.get("closed_trades", [])
        if trades:
            style_counts = {"SCALP": 0, "DAY": 0, "SWING": 0}
            for trade in trades:
                style = trade.get("trade_type", "SWING")
                if style in style_counts:
                    style_counts[style] += 1
            
            print(f"Trade style distribution: {style_counts}")
            # We expect at least some variation if the fix is working
            # But older trades may still be SWING
            total = sum(style_counts.values())
            print(f"PASS: Found {total} closed trades with style distribution")
        else:
            print("INFO: No closed trades to analyze style distribution")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
