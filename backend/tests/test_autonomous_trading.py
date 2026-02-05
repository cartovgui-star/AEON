"""
Test suite for Aeon Autonomous Trading System
Tests: Trading APIs, Learning System, Market Intelligence
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTradingAPIs:
    """Test autonomous trading endpoints"""
    
    def test_trading_summary(self):
        """Test /api/trading/summary returns trading stats"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "closed_stats" in data
        assert "open_positions" in data
        assert "open_pnl_pct" in data
        assert "total_pnl_pct" in data
        assert "strategy_weights" in data
        assert "active" in data
        
        # Verify closed_stats structure
        stats = data["closed_stats"]
        assert "total_predictions" in stats
        assert "wins" in stats
        assert "losses" in stats
        assert "win_rate" in stats
        assert "total_pnl_pct" in stats
        
        # Verify data types
        assert isinstance(data["active"], bool)
        assert isinstance(data["open_positions"], int)
        assert isinstance(data["total_pnl_pct"], (int, float))
    
    def test_trading_opportunities(self):
        """Test /api/trading/opportunities returns market opportunities"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities")
        assert response.status_code == 200
        
        data = response.json()
        # Should return a list (may be empty if no high-confidence setups)
        assert isinstance(data, list)
        
        # If opportunities exist, verify structure
        if len(data) > 0:
            opp = data[0]
            assert "symbol" in opp
            assert "signal" in opp
            assert "confidence" in opp
            assert "price" in opp
    
    def test_trading_analyze_btc(self):
        """Test /api/trading/analyze/btc returns BTC analysis"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "signal" in data
        assert "confidence" in data
        assert "score" in data
        assert "price" in data
        assert "reasons" in data
        assert "signals_used" in data
        assert "indicators" in data
        
        # Verify signal is valid
        assert data["signal"] in ["LONG", "SHORT", "NEUTRAL", "NONE"]
        
        # Verify confidence is a number
        assert isinstance(data["confidence"], (int, float))
        
        # Verify indicators structure
        indicators = data["indicators"]
        assert "rsi" in indicators
        assert "macd" in indicators
        assert "bb_upper" in indicators
        assert "ema_9" in indicators
    
    def test_trading_analyze_eth(self):
        """Test /api/trading/analyze/eth returns ETH analysis"""
        response = requests.get(f"{BASE_URL}/api/trading/analyze/eth")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == "ETH/USDT"
        assert "signal" in data
        assert "confidence" in data
    
    def test_trading_strategy(self):
        """Test /api/trading/strategy returns strategy weights"""
        response = requests.get(f"{BASE_URL}/api/trading/strategy")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "weights" in data
        assert "performance" in data
        assert "active" in data
        assert "min_confidence" in data
        
        # Verify weights structure
        weights = data["weights"]
        assert "rsi_oversold" in weights
        assert "rsi_overbought" in weights
        assert "macd_bullish" in weights
        assert "macd_bearish" in weights
        assert "bb_lower" in weights
        assert "bb_upper" in weights
        assert "ema_stack_bull" in weights
        assert "ema_stack_bear" in weights
        
        # Verify data types
        assert isinstance(data["active"], bool)
        assert isinstance(data["min_confidence"], int)


class TestLearningSystem:
    """Test learning system endpoints"""
    
    def test_learning_stats(self):
        """Test /api/learning/stats returns prediction statistics"""
        response = requests.get(f"{BASE_URL}/api/learning/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "total_predictions" in data
        assert "wins" in data
        assert "losses" in data
        assert "win_rate" in data
        assert "avg_win_pct" in data
        assert "avg_loss_pct" in data
        assert "total_pnl_pct" in data
        
        # Verify data types
        assert isinstance(data["total_predictions"], int)
        assert isinstance(data["win_rate"], (int, float))
        assert isinstance(data["total_pnl_pct"], (int, float))
    
    def test_learning_open(self):
        """Test /api/learning/open returns open predictions"""
        response = requests.get(f"{BASE_URL}/api/learning/open")
        assert response.status_code == 200
        
        data = response.json()
        # Should return a list
        assert isinstance(data, list)
        
        # If predictions exist, verify structure
        if len(data) > 0:
            pred = data[0]
            assert "prediction_id" in pred
            assert "symbol" in pred
            assert "prediction" in pred
            assert "entry_price" in pred


class TestMarketIntelligence:
    """Test market intelligence endpoints"""
    
    def test_market_scan_btc(self):
        """Test /api/market/scan/btc returns full market scan"""
        response = requests.get(f"{BASE_URL}/api/market/scan/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "price" in data
        assert "technical" in data
        assert "signals" in data
        assert "overall_bias" in data
        assert "orderbook" in data
        
        # Verify price is a number
        assert isinstance(data["price"], (int, float))
        assert data["price"] > 0
        
        # Verify technical indicators
        tech = data["technical"]
        assert "rsi" in tech
        assert "macd" in tech
        
        # Verify bias is valid
        assert data["overall_bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    
    def test_market_ta_btc(self):
        """Test /api/market/ta/btc returns technical analysis"""
        response = requests.get(f"{BASE_URL}/api/market/ta/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "price" in data
        assert "indicators" in data
        assert "overall_bias" in data
    
    def test_market_funding_btc(self):
        """Test /api/market/funding/btc returns funding rate"""
        response = requests.get(f"{BASE_URL}/api/market/funding/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "funding_rate" in data
        assert "funding_rate_pct" in data
        assert "mark_price" in data
    
    def test_market_positions_btc(self):
        """Test /api/market/positions/btc returns position data"""
        response = requests.get(f"{BASE_URL}/api/market/positions/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "long_short" in data
        assert "whale" in data
        assert "taker_flow" in data


class TestBotAPIs:
    """Test bot-related endpoints"""
    
    def test_root_endpoint(self):
        """Test root API endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "status" in data
        assert data["status"] == "online"
    
    def test_bot_stats(self):
        """Test /api/bot/stats returns bot statistics"""
        response = requests.get(f"{BASE_URL}/api/bot/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_messages" in data
        assert "unique_users" in data
        assert "messages_today" in data
        assert "active_users" in data
    
    def test_bot_test(self):
        """Test /api/bot/test returns system status"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        # Should be success if all systems are working
        assert data["status"] in ["success", "error"]
    
    def test_mexc_live(self):
        """Test /api/mexc/live returns live orderbook data"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        
        data = response.json()
        # Should have BTC, ETH, SOL data or error
        if "error" not in data:
            # Check for at least one coin
            assert len(data) > 0
            # Check structure of first coin
            for coin, coin_data in data.items():
                assert "price" in coin_data
                assert "change" in coin_data
                break


class TestTradingToggle:
    """Test trading toggle endpoint"""
    
    def test_trading_toggle_on(self):
        """Test toggling trading on"""
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "active" in data
        assert data["active"] == True
    
    def test_trading_toggle_off(self):
        """Test toggling trading off"""
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=false")
        assert response.status_code == 200
        
        data = response.json()
        assert "active" in data
        assert data["active"] == False
    
    def test_trading_toggle_back_on(self):
        """Re-enable trading after test"""
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=true")
        assert response.status_code == 200
        assert response.json()["active"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
