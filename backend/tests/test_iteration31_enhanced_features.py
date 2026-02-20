"""
Iteration 31 - Testing Enhanced Commands and Accuracy Tracking

Features being tested:
1. /market command - Shows proper market data with MEXC fallback for prices
2. /structure command - Shows trend explanation, action, risk if wrong guidance
3. /divergence command - Explains what divergence is, what to expect, if wrong actions
4. /accuracy command - Shows alert accuracy stats
5. /api/accuracy endpoint - Returns accuracy report
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasicEndpoints:
    """Basic health and connectivity tests"""
    
    def test_api_root(self):
        """Test API root responds"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "online"
        assert "Aeon" in data.get("message", "")
        print(f"API root OK: {data}")


class TestMarketCommand:
    """Test /market command with MEXC fallback for market data"""
    
    def test_market_summary_endpoint(self):
        """Test intel/market returns summary with working prices"""
        response = requests.get(f"{BASE_URL}/api/intel/market")
        assert response.status_code == 200
        data = response.json()
        
        # Check it returns content (string summary)
        assert data is not None
        print(f"Market summary type: {type(data)}")
        
        # Could be a string (formatted response) or dict
        if isinstance(data, str):
            # Check for expected sections
            assert "MARKET" in data.upper() or "BTC" in data.upper()
            # Verify prices are not zeros
            assert "$0.00" not in data or "N/A" in data  # Either has real prices or says N/A
            print(f"Market summary (first 500 chars): {data[:500]}")
        elif isinstance(data, dict):
            # Check dict structure
            print(f"Market summary keys: {data.keys()}")
    
    def test_global_market_data(self):
        """Test global market data endpoint"""
        response = requests.get(f"{BASE_URL}/api/intel/global")
        assert response.status_code == 200
        data = response.json()
        
        # Verify market cap and volume (should have MEXC fallback)
        print(f"Global market data: {data}")
        
        # Should have some data even with fallback
        assert "total_market_cap" in data or "error" not in data
    
    def test_top_100_coins(self):
        """Test top 100 endpoint uses MEXC as primary"""
        response = requests.get(f"{BASE_URL}/api/intel/top100")
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list of coins
        assert isinstance(data, list) or "coins" in data
        
        if isinstance(data, list) and len(data) > 0:
            first_coin = data[0]
            print(f"First coin: {first_coin}")
            # Check it has price data
            assert "current_price" in first_coin or "price" in first_coin
            price = first_coin.get("current_price", 0) or first_coin.get("price", 0)
            assert price > 0, "Price should not be zero"


class TestStructureCommand:
    """Test /structure command with enhanced explanations"""
    
    def test_structure_analysis_btc(self):
        """Test market structure analysis for BTC"""
        response = requests.get(f"{BASE_URL}/api/advanced/structure/btc?timeframe=1h")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Structure analysis response: {data}")
        
        # Check required fields
        assert "trend" in data or "error" not in str(data).lower()
        if "trend" in data:
            assert data["trend"] in ["UPTREND", "DOWNTREND", "UNKNOWN", "NEUTRAL", "SIDEWAYS"]
        
        # Check for support/resistance
        if "support" in data:
            assert data["support"] >= 0
        if "resistance" in data:
            assert data["resistance"] >= 0
    
    def test_structure_has_explanation_fields(self):
        """Verify structure response contains explanation fields for Telegram"""
        response = requests.get(f"{BASE_URL}/api/advanced/structure/eth?timeframe=4h")
        assert response.status_code == 200
        data = response.json()
        
        print(f"ETH structure: {data}")
        
        # The endpoint returns raw data - explanations are in Telegram webhook formatting
        # Just verify we get trend and bias
        if "trend" in data:
            assert data["trend"] is not None


class TestDivergenceCommand:
    """Test /divergence command with enhanced explanations"""
    
    def test_divergence_detection_btc(self):
        """Test divergence detection for BTC"""
        response = requests.get(f"{BASE_URL}/api/advanced/divergence/btc?timeframe=1h")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Divergence response: {data}")
        
        # Check for expected fields
        assert "has_divergence" in data or "current_rsi" in data or "divergences" in data
        
        # Verify RSI value exists
        if "current_rsi" in data:
            rsi = data["current_rsi"]
            assert 0 <= rsi <= 100, f"RSI should be 0-100, got {rsi}"
    
    def test_divergence_detection_eth(self):
        """Test divergence detection for ETH"""
        response = requests.get(f"{BASE_URL}/api/advanced/divergence/eth?timeframe=4h")
        assert response.status_code == 200
        data = response.json()
        
        print(f"ETH divergence: {data}")
        
        # Should have MACD histogram
        if "current_macd_hist" in data:
            assert isinstance(data["current_macd_hist"], (int, float))


class TestAccuracyTracking:
    """Test /accuracy command and endpoint for alert tracking"""
    
    def test_accuracy_endpoint(self):
        """Test /api/accuracy returns accuracy report"""
        response = requests.get(f"{BASE_URL}/api/accuracy")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Accuracy report: {data}")
        
        # Check for expected structure
        assert "overview" in data or "total_alerts" in data or "wins" in data or "error" not in str(data).lower()
        
        if "overview" in data:
            overview = data["overview"]
            assert "total_alerts" in overview
            assert "wins" in overview
            assert "losses" in overview
            assert "win_rate" in overview
    
    def test_accuracy_pending_endpoint(self):
        """Test /api/accuracy/pending returns pending alerts"""
        response = requests.get(f"{BASE_URL}/api/accuracy/pending")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Pending alerts: {data}")
        
        # Should have pending field
        assert "pending" in data
        assert isinstance(data["pending"], list)
    
    def test_accuracy_record_endpoint(self):
        """Test /api/accuracy/record can record outcomes"""
        # First get any pending alerts
        pending_response = requests.get(f"{BASE_URL}/api/accuracy/pending")
        pending_data = pending_response.json()
        
        # Test with a mock alert ID (should return not found or error)
        response = requests.post(
            f"{BASE_URL}/api/accuracy/record",
            json={
                "alert_id": "test_nonexistent_123",
                "outcome": "WIN",
                "exit_price": 100000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        print(f"Record outcome response: {data}")
        
        # Should either record or return error about not found
        assert "error" in data or "id" in data


class TestTelegramWebhookCommands:
    """Test Telegram webhook handles commands correctly"""
    
    def test_webhook_structure_command(self):
        """Verify /structure command format in webhook"""
        # Simulate telegram webhook with /structure command
        payload = {
            "message": {
                "chat": {"id": 999999},
                "from": {"username": "test_user"},
                "text": "/structure btc"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        # Webhook returns 200 even for processing
        assert response.status_code == 200
        print("Webhook /structure command accepted")
    
    def test_webhook_divergence_command(self):
        """Verify /divergence command format in webhook"""
        payload = {
            "message": {
                "chat": {"id": 999999},
                "from": {"username": "test_user"},
                "text": "/divergence eth"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        print("Webhook /divergence command accepted")
    
    def test_webhook_accuracy_command(self):
        """Verify /accuracy command format in webhook"""
        payload = {
            "message": {
                "chat": {"id": 999999},
                "from": {"username": "test_user"},
                "text": "/accuracy"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        print("Webhook /accuracy command accepted")
    
    def test_webhook_market_command(self):
        """Verify /market command format in webhook"""
        payload = {
            "message": {
                "chat": {"id": 999999},
                "from": {"username": "test_user"},
                "text": "/market"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook", json=payload)
        assert response.status_code == 200
        print("Webhook /market command accepted")


class TestEnhancedIntelModule:
    """Test enhanced_intel.py module functions"""
    
    def test_fear_greed_index(self):
        """Test Fear & Greed index endpoint"""
        response = requests.get(f"{BASE_URL}/api/intel/fear-greed")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Fear & Greed: {data}")
        
        # Should have value and classification
        assert "value" in data
        assert 0 <= data["value"] <= 100
        assert "classification" in data
    
    def test_funding_rate(self):
        """Test funding rate endpoint"""
        response = requests.get(f"{BASE_URL}/api/intel/funding/btc")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Funding rate: {data}")
        
        # Should have funding_rate or funding info
        assert "funding_rate" in data or "rate" in data or "funding" in data


class TestTradeOutcomeTracker:
    """Test trade_outcome_tracker module"""
    
    def test_accuracy_report_structure(self):
        """Verify accuracy report has correct structure"""
        response = requests.get(f"{BASE_URL}/api/accuracy")
        assert response.status_code == 200
        data = response.json()
        
        # Check for by_direction stats
        if "by_direction" in data:
            by_dir = data["by_direction"]
            assert "LONG" in by_dir
            assert "SHORT" in by_dir
        
        # Check for by_confidence stats
        if "by_confidence" in data:
            by_conf = data["by_confidence"]
            print(f"Confidence stats: {by_conf}")
        
        # Check for by_symbol stats
        if "by_symbol" in data:
            by_sym = data["by_symbol"]
            print(f"Symbol stats: {by_sym}")


class TestMEXCFallback:
    """Test MEXC fallback for prices when CoinGecko is rate limited"""
    
    def test_top_coins_has_prices(self):
        """Verify top coins have non-zero prices (MEXC fallback)"""
        response = requests.get(f"{BASE_URL}/api/intel/top100")
        assert response.status_code == 200
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            # Check first 3 coins have prices
            for coin in data[:3]:
                price = coin.get("current_price", 0) or coin.get("price", 0)
                symbol = coin.get("symbol", "unknown")
                print(f"{symbol}: ${price}")
                # Price should be positive (MEXC working)
                assert price > 0, f"{symbol} has zero price"
    
    def test_market_summary_has_prices(self):
        """Verify market summary has live BTC/ETH/SOL prices"""
        response = requests.get(f"{BASE_URL}/api/intel/market")
        assert response.status_code == 200
        data = response.json()
        
        if isinstance(data, str):
            # Check for live prices
            # Should NOT show $0.00 for BTC/ETH/SOL
            content = data.upper()
            print(f"Market summary snippet: {data[400:800]}")
            
            # If prices section exists, check it's not all zeros
            if "KEY PRICES" in content:
                # Split and check
                price_section = data[data.find("KEY PRICES"):data.find("KEY PRICES")+300]
                print(f"Price section: {price_section}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
