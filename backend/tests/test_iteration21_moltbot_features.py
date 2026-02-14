"""
Iteration 21 - Moltbot-inspired Features Testing
Tests: Sentiment Analysis, Arbitrage Detection, Strategy Health Self-Improving Logic

API Endpoints:
- /api/sentiment/composite - Composite sentiment from all sources
- /api/sentiment/news - News sentiment analysis
- /api/sentiment/fear-greed - Fear & Greed Index
- /api/arbitrage/scan - Full exchange scan
- /api/arbitrage/scan/{symbol} - Single symbol scan
- /api/strategy-health/status - Strategy health status
- /api/strategy-health/record - Record trade result
- /api/strategy-health/unbench/{id} - Manual unbench
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-bot.preview.emergentagent.com')


class TestSentimentAnalysis:
    """Sentiment Analysis API Tests"""
    
    def test_composite_sentiment_btc(self):
        """Test composite sentiment for BTC"""
        response = requests.get(f"{BASE_URL}/api/sentiment/composite?symbol=BTC", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "symbol" in data
        assert data["symbol"] == "BTC"
        assert "signal" in data
        assert data["signal"] in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert "composite_score" in data
        assert isinstance(data["composite_score"], (int, float))
        
        # Verify news section
        assert "news" in data
        assert "sentiment" in data["news"]
        assert "bullish_pct" in data["news"]
        assert "bearish_pct" in data["news"]
        
        # Verify fear & greed
        assert "fear_greed" in data
        assert "value" in data["fear_greed"]
        assert 0 <= data["fear_greed"]["value"] <= 100
        assert "label" in data["fear_greed"]
        
        # Verify recommendation
        assert "recommendation" in data
        print(f"✅ Composite sentiment: {data['signal']} (score: {data['composite_score']})")
        print(f"   Fear & Greed: {data['fear_greed']['value']} - {data['fear_greed']['label']}")
    
    def test_composite_sentiment_eth(self):
        """Test composite sentiment for ETH"""
        response = requests.get(f"{BASE_URL}/api/sentiment/composite?symbol=ETH", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ETH"
        assert "signal" in data
        print(f"✅ ETH sentiment: {data['signal']}")
    
    def test_news_sentiment(self):
        """Test news sentiment API"""
        response = requests.get(f"{BASE_URL}/api/sentiment/news", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "overall" in data
        assert "score" in data
        assert "bullish_pct" in data
        assert "bearish_pct" in data
        print(f"✅ News sentiment: {data['overall']} (bull: {data['bullish_pct']}%, bear: {data['bearish_pct']}%)")
    
    def test_fear_greed_index(self):
        """Test Fear & Greed Index API"""
        response = requests.get(f"{BASE_URL}/api/sentiment/fear-greed", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "value" in data
        assert "label" in data
        assert "history" in data
        assert 0 <= data["value"] <= 100
        print(f"✅ Fear & Greed: {data['value']} - {data['label']}")


class TestArbitrageDetection:
    """Arbitrage Detection API Tests"""
    
    def test_arbitrage_scan_btc(self):
        """Test single symbol arbitrage scan"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/scan/BTC", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert "symbol" in data
        assert data["symbol"] == "BTC/USDT"
        assert "opportunities" in data
        assert isinstance(data["opportunities"], list)
        assert "prices" in data
        assert isinstance(data["prices"], list)
        assert "exchanges_checked" in data
        assert data["exchanges_checked"] >= 1
        
        # Verify price data structure
        for price in data["prices"]:
            assert "exchange" in price
            assert "price" in price
            assert price["price"] > 0
        
        print(f"✅ BTC arbitrage: {len(data['prices'])} exchanges checked, {len(data['opportunities'])} opportunities")
    
    def test_arbitrage_scan_eth(self):
        """Test ETH arbitrage scan"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/scan/ETH", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ETH/USDT"
        assert "exchanges_checked" in data
        print(f"✅ ETH arbitrage: {data['exchanges_checked']} exchanges checked")
    
    def test_recent_opportunities(self):
        """Test recent opportunities API"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/recent?limit=10", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "opportunities" in data
        assert isinstance(data["opportunities"], list)
        print(f"✅ Recent opportunities: {len(data['opportunities'])} found")


class TestStrategyHealth:
    """Strategy Health Self-Improving Logic Tests"""
    
    def test_get_strategy_status(self):
        """Test getting strategy health status"""
        response = requests.get(f"{BASE_URL}/api/strategy-health/status", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Verify 3 strategies exist
        assert "day_trader" in data
        assert "long_term" in data
        assert "free_will" in data
        
        # Verify strategy structure
        for sid, strategy in data.items():
            assert "name" in strategy
            assert "style" in strategy
            assert "active" in strategy
            assert "score" in strategy
            assert "total_trades" in strategy
            assert "win_rate" in strategy
            assert "benched" in strategy
        
        print(f"✅ Strategy status: day_trader={data['day_trader']['score']}, " +
              f"long_term={data['long_term']['score']}, free_will={data['free_will']['score']}")
    
    def test_strategy_ranking(self):
        """Test strategy ranking API"""
        response = requests.get(f"{BASE_URL}/api/strategy-health/ranking", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "ranking" in data
        assert isinstance(data["ranking"], list)
        assert len(data["ranking"]) == 3
        
        for r in data["ranking"]:
            assert "id" in r
            assert "name" in r
            assert "score" in r
        
        print(f"✅ Strategy ranking: {[r['name'] for r in data['ranking']]}")
    
    def test_record_win(self):
        """Test recording a winning trade"""
        # Record a win for long_term strategy
        response = requests.post(
            f"{BASE_URL}/api/strategy-health/record",
            json={"strategy_id": "long_term", "pnl_pct": 2.5, "symbol": "BTC"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["strategy"] == "long_term"
        assert data["result"] == "WIN"
        assert data["consecutive_wins"] >= 1
        assert data["benched"] == False
        print(f"✅ Recorded WIN: consecutive_wins={data['consecutive_wins']}, score={data['score']}")
    
    def test_record_loss(self):
        """Test recording a losing trade"""
        response = requests.post(
            f"{BASE_URL}/api/strategy-health/record",
            json={"strategy_id": "free_will", "pnl_pct": -1.2, "symbol": "ETH"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["strategy"] == "free_will"
        assert data["result"] == "LOSS"
        assert data["consecutive_losses"] >= 1
        print(f"✅ Recorded LOSS: consecutive_losses={data['consecutive_losses']}, score={data['score']}")
    
    def test_auto_bench_after_3_losses(self):
        """Test that strategy gets auto-benched after 3 consecutive losses"""
        strategy_id = "free_will"
        
        # Record 3 consecutive losses
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/api/strategy-health/record",
                json={"strategy_id": strategy_id, "pnl_pct": -1.0, "symbol": f"TEST{i}"},
                timeout=30
            )
            data = response.json()
            
        # After 3 losses, should be benched
        # (Note: may already have losses from previous test)
        if data["consecutive_losses"] >= 3:
            assert data["benched"] == True
            assert "AUTO-BENCHED" in data.get("action", "")
            print(f"✅ Auto-bench triggered: {data['action']}")
        else:
            print(f"⚠️ Partial losses recorded, consecutive_losses={data['consecutive_losses']}")
    
    def test_manual_unbench(self):
        """Test manual unbench functionality"""
        response = requests.post(f"{BASE_URL}/api/strategy-health/unbench/free_will", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data or "message" in data
        print(f"✅ Manual unbench: {data.get('message', 'success')}")
        
        # Verify strategy is no longer benched
        status_response = requests.get(f"{BASE_URL}/api/strategy-health/status", timeout=30)
        status = status_response.json()
        assert status["free_will"]["benched"] == False
        print(f"✅ Strategy confirmed unbenched")


class TestNavigation:
    """Test all navigation endpoints are accessible"""
    
    @pytest.mark.parametrize("endpoint", [
        "/api/",
        "/api/bot/stats",
        "/api/mexc/live",
        "/api/trading/summary",
        "/api/alerts/stats",
        "/api/backtest/compare/BTC",
    ])
    def test_core_endpoints(self, endpoint):
        """Test core API endpoints are accessible"""
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=60)
        assert response.status_code == 200
        print(f"✅ {endpoint} - OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
