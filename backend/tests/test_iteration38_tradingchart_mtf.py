"""
Test Iteration 38: TradingView Chart + MTF Confluence Analysis
Tests for new features:
1. TradingView-style chart with OHLCV data
2. MTF (Multi-Timeframe) Confluence Analysis endpoints
3. Symbol selector and timeframe functionality
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

if not BASE_URL:
    BASE_URL = "https://aeontrading.xyz"


class TestOHLCVEndpoint:
    """Test MEXC OHLCV data endpoint for TradingView chart"""

    def test_ohlcv_btc_default_timeframe(self):
        """Test OHLCV endpoint for BTC with default 4h timeframe"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == "BTC/USDT"
        assert "candles" in data
        assert len(data["candles"]) > 0
        assert "current_price" in data
        assert data["current_price"] > 0
        assert "price_change_pct" in data
        
        # Verify candle structure
        candle = data["candles"][0]
        assert "timestamp" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle

    def test_ohlcv_eth_5m(self):
        """Test OHLCV endpoint for ETH with 5m timeframe"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/ETH?timeframe=5m&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "ETH/USDT"
        assert data["timeframe"] == "5m"
        assert len(data["candles"]) <= 10

    def test_ohlcv_sol_15m(self):
        """Test OHLCV endpoint for SOL with 15m timeframe"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/SOL?timeframe=15m")
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "SOL/USDT"
        assert data["timeframe"] == "15m"

    def test_ohlcv_multiple_symbols(self):
        """Test OHLCV endpoint works for multiple symbols"""
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
        
        for symbol in symbols:
            response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/{symbol}?limit=5")
            assert response.status_code == 200, f"Failed for symbol {symbol}"
            data = response.json()
            assert data["symbol"] == f"{symbol}/USDT"
            assert len(data["candles"]) > 0

    def test_ohlcv_1h_timeframe(self):
        """Test OHLCV endpoint with 1h timeframe"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/DOGE?timeframe=1h&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data["timeframe"] == "1h"
        assert len(data["candles"]) <= 20

    def test_ohlcv_1d_timeframe(self):
        """Test OHLCV endpoint with 1d daily timeframe"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?timeframe=1d&limit=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data["timeframe"] == "1d"


class TestMTFConfluenceAPI:
    """Test Multi-Timeframe Confluence Analysis endpoints"""

    def test_mtf_confluence_single_symbol(self):
        """Test MTF confluence analysis for a single symbol"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/confluence/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == "BTC/USDT"
        assert "confluence_level" in data
        assert data["confluence_level"] in ["STRONG", "MODERATE", "WEAK", "NONE"]
        assert "confluence_count" in data
        assert "consensus_direction" in data
        assert data["consensus_direction"] in ["LONG", "SHORT", "MIXED", "NEUTRAL"]
        assert "weighted_confidence" in data
        assert "timeframes" in data
        
        # Verify each timeframe analysis
        timeframes = data["timeframes"]
        assert "5m" in timeframes
        assert "15m" in timeframes
        assert "30m" in timeframes
        
        for tf in ["5m", "15m", "30m"]:
            tf_data = timeframes[tf]
            assert "signal" in tf_data
            assert "strength" in tf_data
            assert "rsi" in tf_data
            assert "volume_ratio" in tf_data

    def test_mtf_confluence_eth(self):
        """Test MTF confluence for ETH"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/confluence/ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "ETH/USDT"
        assert "direction_votes" in data
        assert "LONG" in data["direction_votes"]
        assert "SHORT" in data["direction_votes"]
        assert "NEUTRAL" in data["direction_votes"]

    def test_mtf_scan_all_symbols(self):
        """Test MTF scan for all symbols"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/scan")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        assert "strong_confluence" in data
        assert "moderate_confluence" in data
        assert "scanned_at" in data
        
        summary = data["summary"]
        assert "strong_setups" in summary
        assert "moderate_setups" in summary
        assert "total_actionable" in summary
        assert "scanned_symbols" in summary
        assert summary["scanned_symbols"] == 15  # 15 symbols tracked

    def test_mtf_scan_with_min_confluence(self):
        """Test MTF scan with minimum confluence filter"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/scan?min_confluence=1")
        assert response.status_code == 200
        
        data = response.json()
        # With min_confluence=1, should include weak setups
        assert "weak_confluence" in data

    def test_mtf_best_setups(self):
        """Test MTF best setups endpoint"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/best")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_setups" in data
        assert "strong_count" in data
        assert "moderate_count" in data
        assert "setups" in data
        assert "scanned_at" in data
        
        # Verify total equals strong + moderate
        assert data["total_setups"] == data["strong_count"] + data["moderate_count"]

    def test_mtf_correlation_report(self):
        """Test MTF correlation report endpoint"""
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/report")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        assert "timeframe_correlation" in data
        assert "direction_breakdown" in data
        assert "insights" in data
        assert "recommendations" in data
        assert "generated_at" in data
        
        # Check timeframe correlation structure
        tf_corr = data["timeframe_correlation"]
        assert "5m_15m" in tf_corr
        assert "5m_30m" in tf_corr
        assert "15m_30m" in tf_corr
        assert "all_three" in tf_corr
        
        # Check direction breakdown
        dir_breakdown = data["direction_breakdown"]
        assert "LONG" in dir_breakdown
        assert "SHORT" in dir_breakdown


class TestTradingV2API:
    """Test Trading V2 API endpoints used by Trading page"""

    def test_trading_v2_stats(self):
        """Test trading v2 stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "active" in data
        assert "total_trades" in data
        assert "win_rate" in data
        assert "market_regime" in data
        assert "btc_bias" in data
        assert "fear_greed" in data

    def test_trading_v2_live_positions(self):
        """Test live positions endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/live-positions")
        assert response.status_code == 200
        
        data = response.json()
        assert "positions" in data
        assert "total_positions" in data
        assert "data_source" in data
        assert data["data_source"] == "MEXC Live"

    def test_trading_v2_closed(self):
        """Test closed trades endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/closed")
        assert response.status_code == 200
        
        data = response.json()
        assert "closed_trades" in data

    def test_trading_v2_pnl_history(self):
        """Test PnL history endpoint"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/pnl-history")
        assert response.status_code == 200
        
        data = response.json()
        assert "history" in data


class TestScalperAPI:
    """Test existing scalper API endpoints"""

    def test_scalper_status(self):
        """Test scalper status endpoint"""
        response = requests.get(f"{BASE_URL}/api/scalper/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "enabled" in data
        assert "is_scanning" in data
        assert "settings_summary" in data

    def test_scalper_signals_btc(self):
        """Test scalper signals for BTC"""
        response = requests.get(f"{BASE_URL}/api/scalper/signals/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == "BTC/USDT"
        assert "signal" in data
        assert "strength" in data
        assert "rsi" in data
        assert "volume_ratio" in data

    def test_scalper_scan_5m(self):
        """Test scalper scan on 5m timeframe"""
        response = requests.get(f"{BASE_URL}/api/scalper/scan?timeframe=5m")
        assert response.status_code == 200
        
        data = response.json()
        assert "timeframe" in data
        assert data["timeframe"] == "5m"
        assert "signals" in data

    def test_scalper_settings(self):
        """Test scalper settings endpoint"""
        response = requests.get(f"{BASE_URL}/api/scalper/settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "settings" in data
        assert "available_symbols" in data
        assert "available_timeframes" in data
        assert len(data["available_symbols"]) == 15
        assert "5m" in data["available_timeframes"]
        assert "15m" in data["available_timeframes"]
        assert "30m" in data["available_timeframes"]


class TestDataValidation:
    """Test data validation and edge cases"""

    def test_ohlcv_candle_order(self):
        """Verify candles are in chronological order"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/BTC?limit=50")
        assert response.status_code == 200
        
        data = response.json()
        candles = data["candles"]
        
        if len(candles) > 1:
            timestamps = [c["timestamp"] for c in candles]
            assert timestamps == sorted(timestamps), "Candles should be in chronological order"

    def test_ohlcv_price_consistency(self):
        """Verify OHLCV price values are consistent"""
        response = requests.get(f"{BASE_URL}/api/mexc/ohlcv/ETH?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        
        for candle in data["candles"]:
            # High should be >= open, close, low
            assert candle["high"] >= candle["open"]
            assert candle["high"] >= candle["close"]
            assert candle["high"] >= candle["low"]
            
            # Low should be <= open, close, high
            assert candle["low"] <= candle["open"]
            assert candle["low"] <= candle["close"]
            assert candle["low"] <= candle["high"]
            
            # Volume should be positive
            assert candle["volume"] >= 0

    def test_mtf_confluence_timing(self):
        """Test MTF confluence endpoint response time"""
        import time
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/scalper/mtf/confluence/SOL")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 30, f"MTF confluence took too long: {elapsed}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
