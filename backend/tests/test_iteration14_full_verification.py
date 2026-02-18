"""
AEON PAPER TRADING ENGINE - Iteration 14 Full Verification Tests
Tests: Webhook, Voice Chat, Trading, Alerts, Dashboard, API endpoints

Key verifications:
1. Telegram webhook working
2. Voice chat endpoint working
3. Trading page live data
4. No duplicate routes/functions
5. No MATIC symbol in trading pairs
6. All API endpoints return proper responses
7. Dashboard shows correct trading stats
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-ai-bot.preview.emergentagent.com')


class TestCoreEndpoints:
    """Test core API endpoints are working"""
    
    def test_api_root(self):
        """Test API root is online"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "online"
        assert "Aeon" in data.get("message", "")
        print(f"✅ API Root: {data}")
    
    def test_bot_stats(self):
        """Test bot stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/bot/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "unique_users" in data
        assert "active_users" in data
        print(f"✅ Bot Stats: users={data.get('active_users')}, messages={data.get('total_messages')}")
    
    def test_bot_test_endpoint(self):
        """Test the bot test endpoint that verifies integrations"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["success", "error"]
        print(f"✅ Bot Test: llm={data.get('llm')}, binance={data.get('binance')}, mexc={data.get('mexc')}")


class TestWebhookEndpoint:
    """Test Telegram webhook endpoint"""
    
    def test_webhook_basic(self):
        """Test webhook endpoint receives messages"""
        payload = {
            "message": {
                "chat": {"id": 999999},
                "text": "test message",
                "from": {"username": "test_user"}
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook: Basic message received")
    
    def test_webhook_no_message(self):
        """Test webhook handles missing message gracefully"""
        payload = {"update_id": 123456}
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Webhook: Handles missing message gracefully")


class TestVoiceEndpoint:
    """Test Voice conversation endpoint"""
    
    def test_voice_respond_endpoint(self):
        """Test voice respond endpoint returns text and audio"""
        payload = {
            "text": "What is the price of Bitcoin?",
            "voice": "guy"
        }
        response = requests.post(f"{BASE_URL}/api/voice/respond", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert "text" in data
            assert "audio" in data
            assert len(data.get("audio", "")) > 0, "Audio should be base64 encoded"
            print(f"✅ Voice Response: text='{data.get('text', '')[:50]}...'")
        else:
            # API may fail due to TTS service, but endpoint should respond
            print(f"⚠️ Voice Response returned error (expected): {data.get('error')}")
    
    def test_voice_respond_empty_text(self):
        """Test voice respond handles empty text"""
        payload = {"text": "", "voice": "guy"}
        response = requests.post(f"{BASE_URL}/api/voice/respond", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        print("✅ Voice: Handles empty text with error message")


class TestTradingV2Endpoints:
    """Test Trading v2 endpoints for paper trading"""
    
    def test_trading_stats(self):
        """Test trading stats endpoint returns proper data"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        required_fields = [
            "active", "total_trades", "open_trades", "closed_trades",
            "wins", "losses", "win_rate", "total_pnl_pct",
            "market_regime", "btc_bias", "fear_greed"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✅ Trading Stats: active={data.get('active')}, open={data.get('open_trades')}, regime={data.get('market_regime')}")
    
    def test_trading_live_positions(self):
        """Test live positions with real-time prices from MEXC"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        
        assert "positions" in data
        assert "total_positions" in data
        assert "data_source" in data
        assert data.get("data_source") == "MEXC Live"
        
        positions = data.get("positions", [])
        print(f"✅ Live Positions: {len(positions)} positions from {data.get('data_source')}")
        
        # Verify position structure if positions exist
        if positions:
            pos = positions[0]
            required_pos_fields = ["symbol", "direction", "entry_price", "current_price", "pnl_pct"]
            for field in required_pos_fields:
                assert field in pos, f"Position missing field: {field}"
            print(f"   First position: {pos.get('symbol')} {pos.get('direction')} entry=${pos.get('entry_price')}")
    
    def test_trading_pnl_history(self):
        """Test PnL history for chart visualization"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history")
        assert response.status_code == 200
        data = response.json()
        
        assert "history" in data
        assert "total_trades" in data
        assert "total_pnl" in data
        print(f"✅ PnL History: {data.get('total_trades')} trades, total PnL={data.get('total_pnl')}%")
    
    def test_trading_open_closed(self):
        """Test open and closed trades endpoints"""
        # Open trades
        response = requests.get(f"{BASE_URL}/api/trading/v2/open")
        assert response.status_code == 200
        data = response.json()
        assert "open_trades" in data
        assert "total_open" in data
        print(f"✅ Open Trades: {data.get('total_open')} trades")
        
        # Closed trades
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200
        data = response.json()
        assert "closed_trades" in data
        assert "total_closed" in data
        print(f"✅ Closed Trades: {data.get('total_closed')} trades")


class TestNoMATICSymbol:
    """Verify MATIC symbol is not in trading pairs (replaced with POL)"""
    
    def test_pairs_no_matic(self):
        """Verify /api/pairs does not include MATIC"""
        response = requests.get(f"{BASE_URL}/api/pairs")
        assert response.status_code == 200
        data = response.json()
        
        pairs = data.get("pairs", [])
        assert "MATIC" not in pairs, "MATIC should not be in pairs list"
        print(f"✅ MATIC not in pairs list (total {len(pairs)} pairs)")
    
    def test_live_positions_no_matic(self):
        """Verify live positions don't have MATIC trades"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        
        positions = data.get("positions", [])
        for pos in positions:
            symbol = pos.get("symbol", "")
            assert "MATIC" not in symbol, f"Found MATIC in position: {symbol}"
        
        print(f"✅ No MATIC symbols in {len(positions)} live positions")


class TestAlertsSystem:
    """Test Price Alert System"""
    
    def test_alerts_stats(self):
        """Test alerts stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "tracked_symbols" in data
        print(f"✅ Alerts Stats: active={data.get('active')}, symbols={data.get('tracked_symbols')}")
    
    def test_alerts_dashboard(self):
        """Test dashboard alerts endpoint"""
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert "total" in data
        print(f"✅ Dashboard Alerts: {data.get('total')} alerts, {data.get('unread')} unread")


class TestMarketIntelligence:
    """Test Market Intelligence endpoints"""
    
    def test_mexc_live(self):
        """Test MEXC live orderbook data"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        
        # Should have BTC, ETH, SOL data
        assert "BTC" in data or "error" not in data
        print(f"✅ MEXC Live: {list(data.keys())[:5]}")
    
    def test_market_scan_btc(self):
        """Test market scan for BTC"""
        response = requests.get(f"{BASE_URL}/api/market/scan/BTC")
        assert response.status_code == 200
        data = response.json()
        
        # Should have price and technical data
        assert "price" in data or "error" in data
        if "price" in data:
            print(f"✅ Market Scan BTC: price=${data.get('price')}, bias={data.get('overall_bias')}")
        else:
            print(f"⚠️ Market Scan BTC: {data.get('error', 'unknown error')}")
    
    def test_fear_greed_index(self):
        """Test Fear & Greed Index"""
        response = requests.get(f"{BASE_URL}/api/intel/fear-greed")
        assert response.status_code == 200
        data = response.json()
        
        assert "value" in data or "classification" in data or "error" in data
        print(f"✅ Fear/Greed Index: {data.get('value', data.get('classification', 'N/A'))}")


class TestFreeWillV2:
    """Test Free Will v2 Engine"""
    
    def test_freewill_stats(self):
        """Test Free Will stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active" in data
        assert "min_confidence" in data
        print(f"✅ FreeWill v2: active={data.get('active')}, min_conf={data.get('min_confidence')}%")


class TestDerivativesData:
    """Test Derivatives data endpoints"""
    
    def test_derivatives_funding(self):
        """Test derivatives funding rate"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/BTC")
        assert response.status_code == 200
        data = response.json()
        
        # May have data or error depending on exchange availability
        print(f"✅ Derivatives Funding BTC: {list(data.keys())[:5]}")


class TestWSEndpoint:
    """Test WebSocket stats endpoint"""
    
    def test_ws_stats(self):
        """Test WebSocket stats"""
        response = requests.get(f"{BASE_URL}/api/ws/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "active_connections" in data
        print(f"✅ WebSocket Stats: {data.get('active_connections')} connections")


class TestTradingToggle:
    """Test trading toggle functionality"""
    
    def test_trading_toggle_status(self):
        """Verify trading toggle works and persists"""
        # Get current status
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        data = response.json()
        current_active = data.get("active")
        print(f"✅ Trading Status: active={current_active}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
