"""
Test LIVE MEXC Data Integration for Paper Trading
Tests the new endpoints added for live positions with real market prices
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-trading-ai.preview.emergentagent.com')


class TestLiveMEXCIntegration:
    """Tests for live MEXC data integration in paper trading"""
    
    def test_live_positions_returns_200(self):
        """Verify /api/trading/v2/live-positions endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        print(f"Live positions endpoint returned {response.status_code}")
    
    def test_live_positions_has_positions_array(self):
        """Verify response contains positions array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        data = response.json()
        assert "positions" in data
        assert isinstance(data["positions"], list)
        print(f"Found {len(data['positions'])} positions")
    
    def test_live_positions_has_data_source(self):
        """Verify data_source field shows 'MEXC Live'"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        data = response.json()
        assert "data_source" in data
        assert data["data_source"] == "MEXC Live"
        print(f"Data source: {data['data_source']}")
    
    def test_position_has_required_fields(self):
        """Verify each position has: entry_price, current_price, pnl_pct, stop_price, target_price"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        data = response.json()
        
        if len(data["positions"]) > 0:
            position = data["positions"][0]
            required_fields = ["entry_price", "current_price", "pnl_pct", "stop_price", "target_price"]
            
            for field in required_fields:
                assert field in position, f"Missing field: {field}"
            
            print(f"Position {position.get('symbol')}: entry={position.get('entry_price')}, current={position.get('current_price')}, pnl={position.get('pnl_pct')}%")
        else:
            pytest.skip("No positions to verify")
    
    def test_position_current_price_from_mexc(self):
        """Verify current_price is a valid price (not 0 or None)"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        data = response.json()
        
        if len(data["positions"]) > 0:
            for position in data["positions"][:3]:  # Check first 3
                assert position.get("current_price") is not None
                assert position.get("current_price") > 0
                print(f"{position.get('symbol')}: ${position.get('current_price')}")
        else:
            pytest.skip("No positions to verify")


class TestPnLHistory:
    """Tests for PnL history endpoint"""
    
    def test_pnl_history_returns_200(self):
        """Verify /api/trading/v2/pnl-history endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history")
        assert response.status_code == 200
        print(f"PnL history endpoint returned {response.status_code}")
    
    def test_pnl_history_has_history_array(self):
        """Verify response contains history array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history")
        data = response.json()
        assert "history" in data
        assert isinstance(data["history"], list)
        print(f"Found {len(data['history'])} history entries")
    
    def test_pnl_history_has_stats(self):
        """Verify response contains total_trades, total_pnl, wins, losses"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history")
        data = response.json()
        
        assert "total_trades" in data
        assert "total_pnl" in data
        assert "wins" in data
        assert "losses" in data
        
        print(f"Stats: {data['total_trades']} trades, PnL: {data['total_pnl']}%, W/L: {data['wins']}/{data['losses']}")


class TestTradingStats:
    """Tests for trading stats endpoint"""
    
    def test_stats_returns_200(self):
        """Verify /api/trading/v2/stats endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        print(f"Stats endpoint returned {response.status_code}")
    
    def test_stats_shows_active(self):
        """Verify active field is present and is boolean"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        assert "active" in data
        assert isinstance(data["active"], bool)
        print(f"Trading active: {data['active']}")
    
    def test_stats_has_market_conditions(self):
        """Verify market regime, btc_bias are present"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        data = response.json()
        
        assert "market_regime" in data
        assert "btc_bias" in data
        
        print(f"Market regime: {data['market_regime']}, BTC bias: {data['btc_bias']}")
    
    def test_stats_has_open_trades_count(self):
        """Verify open_trades count matches live positions"""
        stats_response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        live_response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        
        stats = stats_response.json()
        live = live_response.json()
        
        assert "open_trades" in stats
        assert stats["open_trades"] == len(live.get("positions", []))
        
        print(f"Open trades: {stats['open_trades']} (verified against live positions)")


class TestMarketIntelligence:
    """Tests for MEXC market data via market_intelligence module"""
    
    def test_ticker_endpoint(self):
        """Test that we can get live ticker from MEXC"""
        response = requests.get(f"{BASE_URL}/api/market/scan/BTC")
        data = response.json()
        
        assert "price" in data
        assert data["price"] is not None
        assert data["price"] > 0
        
        print(f"BTC price from MEXC: ${data['price']}")
    
    def test_technical_analysis(self):
        """Test TA endpoint returns valid data"""
        response = requests.get(f"{BASE_URL}/api/market/ta/ETH")
        data = response.json()
        
        assert "indicators" in data
        indicators = data.get("indicators", {})
        
        # Check for RSI
        assert "rsi" in indicators
        assert 0 <= indicators["rsi"] <= 100
        
        print(f"ETH RSI: {indicators['rsi']}")
