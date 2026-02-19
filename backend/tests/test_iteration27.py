"""
Test suite for Iteration 27 - Major update with:
1. New Dashboard features (Quick Trade, Kill Switch)
2. Multi-style trading (SCALP/DAY/SWING) with dynamic leverage up to 200x
3. Enhanced voice with OpenAI Whisper STT
4. Quick Trade API endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestVoiceInfo:
    """Test /api/voice/info endpoint - STT availability status"""
    
    def test_voice_info_returns_correct_structure(self):
        """Voice info endpoint should return TTS voices and STT availability"""
        response = requests.get(f"{BASE_URL}/api/voice/info")
        assert response.status_code == 200
        
        data = response.json()
        assert "tts_voices" in data
        assert "stt_available" in data
        assert "stt_provider" in data
        
        # Verify voices list
        assert isinstance(data["tts_voices"], list)
        assert len(data["tts_voices"]) >= 1
        
        # Verify STT status
        assert isinstance(data["stt_available"], bool)


class TestQuickTrade:
    """Test /api/trading/v2/quick-trade endpoint"""
    
    def test_quick_trade_scalp_style(self):
        """Quick trade with 15m timeframe should create SCALP trade with high leverage"""
        response = requests.post(
            f"{BASE_URL}/api/trading/v2/quick-trade",
            json={
                "symbol": "BTC",
                "direction": "LONG",
                "timeframe": "15m",
                "confidence": 80
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        trade = data.get("trade", {})
        assert trade.get("trade_type") == "SCALP"
        assert trade.get("symbol") == "BTC/USDT"
        assert trade.get("direction") == "LONG"
        assert trade.get("timeframe") == "15m"
        
        # SCALP should have leverage 50-200x
        leverage = trade.get("leverage", 0)
        assert leverage >= 50, f"SCALP leverage should be >= 50, got {leverage}"
        assert leverage <= 200, f"SCALP leverage should be <= 200, got {leverage}"
    
    def test_quick_trade_day_style(self):
        """Quick trade with 1h timeframe should create DAY trade"""
        response = requests.post(
            f"{BASE_URL}/api/trading/v2/quick-trade",
            json={
                "symbol": "ETH",
                "direction": "SHORT",
                "timeframe": "1h",
                "confidence": 75
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        trade = data.get("trade", {})
        assert trade.get("trade_type") == "DAY"
        assert trade.get("symbol") == "ETH/USDT"
        assert trade.get("direction") == "SHORT"
        
        # DAY should have leverage 20-75x
        leverage = trade.get("leverage", 0)
        assert leverage >= 20, f"DAY leverage should be >= 20, got {leverage}"
        assert leverage <= 75, f"DAY leverage should be <= 75, got {leverage}"
    
    def test_quick_trade_swing_style(self):
        """Quick trade with 1d timeframe should create SWING trade with conservative leverage"""
        response = requests.post(
            f"{BASE_URL}/api/trading/v2/quick-trade",
            json={
                "symbol": "SOL",
                "direction": "LONG",
                "timeframe": "1d",
                "confidence": 85
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        trade = data.get("trade", {})
        assert trade.get("trade_type") == "SWING"
        assert trade.get("symbol") == "SOL/USDT"
        
        # SWING should have leverage 10-25x
        leverage = trade.get("leverage", 0)
        assert leverage >= 10, f"SWING leverage should be >= 10, got {leverage}"
        assert leverage <= 25, f"SWING leverage should be <= 25, got {leverage}"
    
    def test_quick_trade_returns_confirmations(self):
        """Quick trade should return trade confirmations"""
        response = requests.post(
            f"{BASE_URL}/api/trading/v2/quick-trade",
            json={
                "symbol": "BTC",
                "direction": "LONG",
                "timeframe": "4h",
                "confidence": 70
            }
        )
        
        data = response.json()
        trade = data.get("trade", {})
        
        confirmations = trade.get("confirmations", [])
        assert len(confirmations) >= 1
        assert any("style" in c.lower() for c in confirmations)
        assert any("leverage" in c.lower() for c in confirmations)
    
    def test_quick_trade_has_stop_and_target(self):
        """Quick trade should calculate stop and target prices"""
        response = requests.post(
            f"{BASE_URL}/api/trading/v2/quick-trade",
            json={
                "symbol": "BTC",
                "direction": "LONG",
                "timeframe": "1h",
                "confidence": 75
            }
        )
        
        data = response.json()
        trade = data.get("trade", {})
        
        assert "stop_price" in trade
        assert "target_price" in trade
        assert "entry_price" in trade
        
        entry = trade.get("entry_price", 0)
        stop = trade.get("stop_price", 0)
        target = trade.get("target_price", 0)
        
        # For LONG: stop < entry < target
        if trade.get("direction") == "LONG":
            assert stop < entry, "Stop should be below entry for LONG"
            assert target > entry, "Target should be above entry for LONG"


class TestCloseAll:
    """Test /api/trading/v2/close-all endpoint (Kill Switch)"""
    
    def test_close_all_returns_success(self):
        """Close all endpoint should return success structure"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/close-all")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data.get("success") == True
        assert "closed_count" in data
        assert "message" in data
    
    def test_close_all_emergency_message(self):
        """Close all should return emergency close message"""
        response = requests.post(f"{BASE_URL}/api/trading/v2/close-all")
        
        data = response.json()
        message = data.get("message", "")
        assert "Emergency close" in message or "close" in message.lower()


class TestLivePositions:
    """Test /api/trading/v2/live-positions endpoint"""
    
    def test_live_positions_returns_list(self):
        """Live positions endpoint should return positions array"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        
        data = response.json()
        assert "positions" in data
        assert isinstance(data["positions"], list)


class TestTradingStats:
    """Test trading stats endpoint with new trade styles"""
    
    def test_trading_stats_has_market_info(self):
        """Trading stats should include market regime and btc bias"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Check for market context fields
        assert "market_regime" in data
        assert "btc_bias" in data


class TestHealthEndpoints:
    """Basic health check tests"""
    
    def test_root_endpoint(self):
        """Root API should return online status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "online"
    
    def test_system_health(self):
        """System health should return service status"""
        response = requests.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
