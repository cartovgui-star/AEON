"""
Test suite for Aeon Free Will Engine
Tests: Free Will stats, scan, toggle, confidence, and related endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFreeWillStats:
    """Test Free Will engine statistics endpoint"""
    
    def test_freewill_stats(self):
        """Test /api/freewill/stats - Get Free Will engine statistics"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "active" in data
        assert "min_confidence" in data
        assert "total_alerts_sent" in data
        assert "feedback_received" in data
        assert "wins" in data
        assert "losses" in data
        assert "win_rate" in data
        assert "pairs_monitored" in data
        assert "timeframes_monitored" in data
        assert "current_weights" in data
        
        # Verify data types
        assert isinstance(data["active"], bool)
        assert isinstance(data["min_confidence"], int)
        assert isinstance(data["total_alerts_sent"], int)
        assert isinstance(data["pairs_monitored"], int)
        assert isinstance(data["timeframes_monitored"], int)
        
        # Verify expected values
        assert data["pairs_monitored"] == 44  # 44 pairs monitored
        assert data["timeframes_monitored"] == 9  # 9 timeframes
        assert 50 <= data["min_confidence"] <= 95  # Valid confidence range
        
        # Verify weights structure
        weights = data["current_weights"]
        assert "rsi_oversold" in weights
        assert "rsi_overbought" in weights
        assert "macd_cross" in weights
        assert "bb_squeeze" in weights
        assert "ema_stack" in weights
        assert "volume_spike" in weights
        assert "funding_extreme" in weights
        assert "fear_greed_extreme" in weights
        assert "orderbook_imbalance" in weights
        assert "multi_tf_confluence" in weights
        
        print(f"Free Will Stats:")
        print(f"  Active: {data['active']}")
        print(f"  Min Confidence: {data['min_confidence']}%")
        print(f"  Pairs Monitored: {data['pairs_monitored']}")
        print(f"  Timeframes: {data['timeframes_monitored']}")
        print(f"  Total Alerts Sent: {data['total_alerts_sent']}")
        print(f"  Win Rate: {data['win_rate']}%")


class TestFreeWillScan:
    """Test Free Will scan endpoint"""
    
    def test_freewill_scan_btc(self):
        """Test /api/freewill/scan/btc - Scan BTC for setups"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/btc?timeframe=1h")
        assert response.status_code == 200
        
        data = response.json()
        # Can return null if no high-probability setup detected
        # or return a setup dict if confidence >= min_confidence
        if data is not None:
            assert "symbol" in data
            assert "timeframe" in data
            assert "direction" in data
            assert "confidence" in data
            assert "entry" in data
            assert "stop_loss" in data
            assert "take_profit" in data
            assert "signals" in data
            
            # Verify direction is valid
            assert data["direction"] in ["LONG", "SHORT"]
            
            # Verify confidence is high enough
            assert data["confidence"] >= 70
            
            print(f"BTC Setup Found:")
            print(f"  Direction: {data['direction']}")
            print(f"  Confidence: {data['confidence']}%")
            print(f"  Entry: ${data['entry']:,.2f}")
            print(f"  Stop: ${data['stop_loss']:,.2f}")
            print(f"  Target: ${data['take_profit']:,.2f}")
        else:
            print("No high-probability BTC setup detected (confidence < 70%)")
    
    def test_freewill_scan_eth(self):
        """Test /api/freewill/scan/eth - Scan ETH for setups"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/eth?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        # Can return null or setup dict
        if data is not None:
            assert "symbol" in data
            assert "direction" in data
            assert "confidence" in data
            print(f"ETH Setup: {data['direction']} @ {data['confidence']}% confidence")
        else:
            print("No high-probability ETH setup detected")
    
    def test_freewill_scan_sol(self):
        """Test /api/freewill/scan/sol - Scan SOL for setups"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/sol?timeframe=15m")
        assert response.status_code == 200
        
        data = response.json()
        if data is not None:
            assert "symbol" in data
            print(f"SOL Setup: {data['direction']} @ {data['confidence']}% confidence")
        else:
            print("No high-probability SOL setup detected")


class TestFreeWillToggle:
    """Test Free Will toggle endpoint"""
    
    def test_freewill_toggle_off(self):
        """Test /api/freewill/toggle - Toggle Free Will off"""
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=false")
        assert response.status_code == 200
        
        data = response.json()
        assert "active" in data
        assert data["active"] == False
        print("Free Will toggled OFF")
    
    def test_freewill_toggle_on(self):
        """Test /api/freewill/toggle - Toggle Free Will on"""
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "active" in data
        assert data["active"] == True
        print("Free Will toggled ON")


class TestFreeWillConfidence:
    """Test Free Will confidence threshold endpoint"""
    
    def test_freewill_confidence_set(self):
        """Test /api/freewill/confidence - Set min confidence"""
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=75")
        assert response.status_code == 200
        
        data = response.json()
        assert "min_confidence" in data
        assert data["min_confidence"] == 75
        print(f"Min confidence set to {data['min_confidence']}%")
    
    def test_freewill_confidence_bounds_low(self):
        """Test /api/freewill/confidence - Lower bound (50)"""
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=30")
        assert response.status_code == 200
        
        data = response.json()
        # Should be clamped to minimum 50
        assert data["min_confidence"] >= 50
        print(f"Min confidence clamped to {data['min_confidence']}%")
    
    def test_freewill_confidence_bounds_high(self):
        """Test /api/freewill/confidence - Upper bound (95)"""
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=99")
        assert response.status_code == 200
        
        data = response.json()
        # Should be clamped to maximum 95
        assert data["min_confidence"] <= 95
        print(f"Min confidence clamped to {data['min_confidence']}%")
    
    def test_freewill_confidence_reset(self):
        """Reset confidence to default 70%"""
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=70")
        assert response.status_code == 200
        
        data = response.json()
        assert data["min_confidence"] == 70
        print("Min confidence reset to 70%")


class TestTradingSummaryNoErrors:
    """Test trading summary endpoint for division by zero fix"""
    
    def test_trading_summary_no_division_error(self):
        """Test /api/trading/summary - Should not have division by zero errors"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "closed_stats" in data
        assert "open_positions" in data
        assert "open_pnl_pct" in data
        assert "total_pnl_pct" in data
        assert "active" in data
        
        # Verify no NaN or Inf values (would indicate division errors)
        assert isinstance(data["open_pnl_pct"], (int, float))
        assert isinstance(data["total_pnl_pct"], (int, float))
        
        # Check for valid numbers (not NaN or Inf)
        import math
        assert not math.isnan(data["open_pnl_pct"])
        assert not math.isinf(data["open_pnl_pct"])
        assert not math.isnan(data["total_pnl_pct"])
        assert not math.isinf(data["total_pnl_pct"])
        
        stats = data["closed_stats"]
        print(f"Trading Summary (no division errors):")
        print(f"  Total Trades: {stats.get('total_predictions', 0)}")
        print(f"  Win Rate: {stats.get('win_rate', 0)}%")
        print(f"  Total PnL: {data['total_pnl_pct']:+.2f}%")
        print(f"  Open Positions: {data['open_positions']}")
        print(f"  Open PnL: {data['open_pnl_pct']:+.2f}%")


class TestDerivativesFundingAggregated:
    """Test aggregated funding from multiple exchanges"""
    
    def test_derivatives_funding_aggregated(self):
        """Test /api/derivatives/funding/btc - Aggregated from OKX, Bitget, KuCoin, Gate"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "average_funding_rate" in data
        assert "average_funding_pct" in data
        assert "interpretation" in data
        assert "exchanges" in data
        assert "data_sources" in data
        
        # Verify we have data from multiple exchanges
        assert data["data_sources"] >= 1
        
        # Verify exchanges list
        exchanges = data["exchanges"]
        assert isinstance(exchanges, list)
        
        # Check exchange names
        exchange_names = [ex.get("exchange") for ex in exchanges if "error" not in ex]
        print(f"Funding data from {len(exchange_names)} exchanges: {exchange_names}")
        print(f"Average Funding: {data['average_funding_pct']}")
        print(f"Interpretation: {data['interpretation']}")


class TestMultiTimeframeAnalysis:
    """Test multi-timeframe analysis endpoint"""
    
    def test_mtf_btc(self):
        """Test /api/mtf/btc - Multi-timeframe analysis"""
        response = requests.get(f"{BASE_URL}/api/mtf/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "confluence" in data
        assert "confluence_emoji" in data
        assert "confidence" in data
        assert "recommendation" in data
        assert "timeframes" in data
        
        # Verify timeframes
        timeframes = data["timeframes"]
        assert len(timeframes) >= 1
        
        # Verify each timeframe has required fields
        for tf, tf_data in timeframes.items():
            if "error" not in tf_data:
                assert "bias" in tf_data
                assert "score" in tf_data
                assert "signals" in tf_data
        
        print(f"MTF Analysis:")
        print(f"  Confluence: {data['confluence_emoji']} {data['confluence']}")
        print(f"  Confidence: {data['confidence']}%")
        print(f"  Recommendation: {data['recommendation']}")


class TestNewsAndSentiment:
    """Test news and sentiment endpoints"""
    
    def test_news_latest(self):
        """Test /api/news/latest - Latest crypto news"""
        response = requests.get(f"{BASE_URL}/api/news/latest?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            news = data[0]
            assert "title" in news
            assert "sentiment" in news
            print(f"Latest news: {len(data)} articles")
            for n in data[:3]:
                print(f"  {n['sentiment']['emoji']} {n['title'][:50]}...")


class TestWhaleActivity:
    """Test whale activity endpoint"""
    
    def test_whale_activity(self):
        """Test /api/whales/activity - Whale activity summary"""
        response = requests.get(f"{BASE_URL}/api/whales/activity")
        assert response.status_code == 200
        
        data = response.json()
        assert "activity" in data
        assert data["activity"] in ["HIGH", "MODERATE", "LOW"]
        
        print(f"Whale Activity: {data['activity']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
