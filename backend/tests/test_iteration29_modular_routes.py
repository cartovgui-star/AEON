"""
Test suite for iteration 29 - Testing new modular routes after server.py refactoring
Testing new route files: calculators, advanced, orderflow, options, backtest, coinglass, dual, data, sentiment, strategy_health, voice, user
"""

import pytest
import requests
import os

# Use the public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://trading-engine-demo.preview.emergentagent.com')


class TestBaseEndpoints:
    """Basic health and status endpoints"""
    
    def test_api_root(self):
        """Test API root endpoint returns online status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "Aeon" in data["message"]
    
    def test_system_health(self):
        """Test system health endpoint"""
        response = requests.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200
        data = response.json()
        # Should have self-healer stats
        assert "services" in data or "active" in data


class TestCalculatorsRoute:
    """Test /api/calc/* endpoints - PnL and position calculators"""
    
    def test_calc_pnl_long(self):
        """Test PnL calculation for LONG position"""
        response = requests.get(
            f"{BASE_URL}/api/calc/pnl",
            params={"entry": 100, "exit": 110, "size": 1000, "leverage": 10, "direction": "LONG"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["direction"] == "LONG"
        assert data["pnl_pct"] == 100  # 10% price change * 10x leverage = 100%
        assert data["pnl_usd"] == 1000
        assert data["status"] == "PROFIT"
    
    def test_calc_pnl_short(self):
        """Test PnL calculation for SHORT position"""
        response = requests.get(
            f"{BASE_URL}/api/calc/pnl",
            params={"entry": 100, "exit": 90, "size": 1000, "leverage": 5, "direction": "SHORT"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["direction"] == "SHORT"
        assert data["pnl_pct"] == 50  # 10% price change * 5x leverage = 50%
        assert data["status"] == "PROFIT"
    
    def test_calc_position(self):
        """Test position size calculator"""
        response = requests.get(
            f"{BASE_URL}/api/calc/position",
            params={"balance": 10000, "risk_pct": 1, "entry": 100, "stop": 95, "leverage": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert "position_size" in data or "recommended_size" in data or "size" in data
    
    def test_calc_scenarios(self):
        """Test PnL scenarios generator"""
        response = requests.get(
            f"{BASE_URL}/api/calc/scenarios",
            params={"entry": 100, "size": 1000, "leverage": 10, "direction": "LONG"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should have multiple scenarios
        assert "scenarios" in data or isinstance(data, list)


class TestAdvancedRoute:
    """Test /api/advanced/* endpoints - Divergence, Structure, VWAP"""
    
    def test_divergence_btc(self):
        """Test divergence detection for BTC"""
        response = requests.get(f"{BASE_URL}/api/advanced/divergence/BTC")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "BTC" in data["symbol"]
        assert "has_divergence" in data or "divergences" in data
    
    def test_structure_btc(self):
        """Test market structure analysis for BTC"""
        response = requests.get(f"{BASE_URL}/api/advanced/structure/BTC")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        # Should have structure analysis results
        assert "trend" in data or "structure" in data or "bias" in data
    
    def test_vwap_btc(self):
        """Test VWAP calculation for BTC"""
        response = requests.get(f"{BASE_URL}/api/advanced/vwap/BTC")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "vwap" in data or "value" in data or "error" not in data
    
    def test_full_advanced_analysis(self):
        """Test full advanced analysis (all combined)"""
        response = requests.get(f"{BASE_URL}/api/advanced/full/BTC")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data


class TestDualRoute:
    """Test /api/dual/* endpoints - Dual Trading Engine (Day Trader + Long Term)"""
    
    def test_dual_stats(self):
        """Test Dual Engine statistics"""
        response = requests.get(f"{BASE_URL}/api/dual/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "day_trader" in data
        assert "long_term" in data
        # Day trader should have specific settings
        assert data["day_trader"]["min_confidence"] >= 65
        assert data["long_term"]["min_confidence"] >= 75


class TestCoinglassRoute:
    """Test /api/coinglass/* endpoints - Derivatives data from Coinglass"""
    
    def test_coinglass_full(self):
        """Test full Coinglass report for BTC"""
        response = requests.get(f"{BASE_URL}/api/coinglass/full/BTC")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
        # May have data or error (paid tier required for some endpoints)
        assert "funding_rate" in data or "open_interest" in data
    
    def test_coinglass_funding(self):
        """Test Coinglass funding rates"""
        response = requests.get(f"{BASE_URL}/api/coinglass/funding/BTC")
        assert response.status_code == 200
        # Endpoint returns data or error message
    
    def test_coinglass_oi(self):
        """Test Coinglass open interest"""
        response = requests.get(f"{BASE_URL}/api/coinglass/oi/BTC")
        assert response.status_code == 200


class TestSentimentRoute:
    """Test /api/sentiment/* endpoints - Sentiment analysis"""
    
    def test_sentiment_composite(self):
        """Test composite sentiment for BTC"""
        response = requests.get(f"{BASE_URL}/api/sentiment/composite", params={"symbol": "BTC"})
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
    
    def test_sentiment_news(self):
        """Test news sentiment"""
        response = requests.get(f"{BASE_URL}/api/sentiment/news")
        assert response.status_code == 200
    
    def test_sentiment_fear_greed(self):
        """Test Fear & Greed Index"""
        response = requests.get(f"{BASE_URL}/api/sentiment/fear-greed")
        assert response.status_code == 200


class TestVoiceRoute:
    """Test /api/voice/* endpoints - Voice conversation"""
    
    def test_voice_info(self):
        """Test voice info (available voices and STT status)"""
        response = requests.get(f"{BASE_URL}/api/voice/info")
        assert response.status_code == 200
        data = response.json()
        assert "tts_voices" in data
        assert "stt_available" in data
        # Should have multiple voice options
        assert len(data["tts_voices"]) >= 1


class TestOrderFlowRoute:
    """Test /api/orderflow/* endpoints - Order flow analysis"""
    
    def test_orderflow_cvd(self):
        """Test CVD (Cumulative Volume Delta) analysis"""
        response = requests.get(f"{BASE_URL}/api/orderflow/cvd/BTC")
        assert response.status_code == 200
    
    def test_orderflow_footprint(self):
        """Test footprint chart data"""
        response = requests.get(f"{BASE_URL}/api/orderflow/footprint/BTC")
        assert response.status_code == 200
    
    def test_orderflow_full(self):
        """Test full order flow analysis"""
        response = requests.get(f"{BASE_URL}/api/orderflow/full/BTC")
        assert response.status_code == 200


class TestOptionsRoute:
    """Test /api/options/* endpoints - Options analysis"""
    
    def test_options_btc(self):
        """Test BTC options analysis"""
        response = requests.get(f"{BASE_URL}/api/options/BTC")
        assert response.status_code == 200


class TestBacktestRoute:
    """Test /api/backtest/* endpoints - Backtesting"""
    
    def test_backtest_strategies(self):
        """Test list available strategies"""
        response = requests.get(f"{BASE_URL}/api/backtest/strategies")
        assert response.status_code == 200


class TestDataRoute:
    """Test /api/data/* endpoints - Historical and candle data"""
    
    def test_data_candles(self):
        """Test historical candles data"""
        response = requests.get(
            f"{BASE_URL}/api/data/candles/BTC",
            params={"timeframe": "1h", "limit": 10}
        )
        assert response.status_code == 200


class TestStrategyHealthRoute:
    """Test /api/strategy-health/* endpoints - Strategy monitoring"""
    
    def test_strategy_health_stats(self):
        """Test strategy health statistics"""
        response = requests.get(f"{BASE_URL}/api/strategy-health/stats")
        assert response.status_code == 200


class TestUserRoute:
    """Test /api/user/* endpoints - User profile and settings"""
    
    def test_user_profiles(self):
        """Test user profile endpoint"""
        response = requests.get(f"{BASE_URL}/api/user/profiles")
        assert response.status_code == 200


class TestTradingIntegration:
    """Integration tests for trading-related endpoints"""
    
    def test_trading_summary(self):
        """Test trading summary endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        data = response.json()
        # Should have engine stats
        assert "engine" in data or "stats" in data or "active" in data
    
    def test_trading_live_positions(self):
        """Test live positions endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data or isinstance(data, list)
    
    def test_mexc_live(self):
        """Test MEXC live orderbook data"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data


class TestFreewillRoute:
    """Test /api/freewill/* endpoints - Free Will v2 alerting"""
    
    def test_freewill_stats(self):
        """Test Free Will v2 statistics"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "min_confidence" in data
        # Should have data sources list
        assert "data_sources" in data or "timeframes" in data


class TestMarketRoute:
    """Test /api/market/* endpoints - Market data"""
    
    def test_market_summary(self):
        """Test global market summary"""
        response = requests.get(f"{BASE_URL}/api/market/summary")
        assert response.status_code == 200


class TestMTFRoute:
    """Test /api/mtf/* endpoints - Multi-timeframe analysis"""
    
    def test_mtf_btc(self):
        """Test multi-timeframe analysis for BTC"""
        response = requests.get(f"{BASE_URL}/api/mtf/BTC")
        assert response.status_code == 200
    
    def test_mtf_alignment(self):
        """Test trend alignment across timeframes"""
        response = requests.get(f"{BASE_URL}/api/mtf/align/BTC")
        assert response.status_code == 200


class TestIntelRoute:
    """Test /api/intel/* endpoints - Market intelligence"""
    
    def test_intel_full(self):
        """Test full market intelligence"""
        response = requests.get(f"{BASE_URL}/api/intel/full/BTC")
        assert response.status_code == 200


class TestBotStats:
    """Test /api/bot/* endpoints - Bot statistics"""
    
    def test_bot_stats(self):
        """Test bot usage statistics"""
        response = requests.get(f"{BASE_URL}/api/bot/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data or "unique_users" in data
    
    def test_bot_test(self):
        """Test bot connectivity check"""
        response = requests.get(f"{BASE_URL}/api/bot/test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
