"""
AEON Iteration 10 Tests - Free Will v2 & Backtesting Framework
Tests for:
- Free Will v2 ultra-selective alerts (80%+ confidence, 3+ confirmations, 8 data sources)
- Backtesting framework (RSI, BB, EMA strategies)
- Alert volume minimization (max 10/day, 30min cooldown)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFreeWillV2Stats:
    """Test Free Will v2 stats endpoint - should show ultra-selective configuration"""
    
    def test_freewill_stats_endpoint(self):
        """Test /api/freewill/stats returns correct configuration"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify min_confidence is 80
        assert data.get("min_confidence") == 80, f"Expected min_confidence=80, got {data.get('min_confidence')}"
        
        # Verify min_confirmations is 3
        assert data.get("min_confirmations") == 3, f"Expected min_confirmations=3, got {data.get('min_confirmations')}"
        
        # Verify 8 data sources
        data_sources = data.get("data_sources", [])
        assert len(data_sources) == 8, f"Expected 8 data sources, got {len(data_sources)}"
        
        # Verify specific data sources
        expected_sources = [
            "Technical Analysis",
            "Divergence Detection",
            "Market Structure",
            "VWAP",
            "Order Flow / CVD",
            "Options (BTC/ETH)",
            "Derivatives",
            "Fear & Greed"
        ]
        for source in expected_sources:
            assert source in data_sources, f"Missing data source: {source}"
    
    def test_freewill_stats_alert_limits(self):
        """Test alert volume minimization settings"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Max 10 alerts per day
        assert data.get("max_daily_alerts") == 10, f"Expected max_daily_alerts=10, got {data.get('max_daily_alerts')}"
        
        # 30 min cooldown per symbol
        assert data.get("alert_cooldown_mins") == 30, f"Expected alert_cooldown_mins=30, got {data.get('alert_cooldown_mins')}"
    
    def test_freewill_stats_structure(self):
        """Test stats response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = [
            "active", "min_confidence", "min_confirmations",
            "alert_cooldown_mins", "total_alerts_sent", "daily_alerts",
            "max_daily_alerts", "setups_analyzed", "pairs_monitored",
            "timeframes", "data_sources"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestFreeWillV2Scan:
    """Test Free Will v2 scan endpoint - returns setup only if 80%+ confidence AND 3+ confirmations"""
    
    def test_freewill_scan_btc(self):
        """Test scanning BTC - may return null if no elite setup"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/btc?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        
        # If setup found, verify it meets criteria
        if data is not None:
            assert data.get("confidence", 0) >= 80, f"Confidence below 80%: {data.get('confidence')}"
            assert data.get("confirmation_count", 0) >= 3, f"Confirmations below 3: {data.get('confirmation_count')}"
            assert "symbol" in data
            assert "direction" in data
            assert data.get("direction") in ["LONG", "SHORT"]
    
    def test_freewill_scan_eth(self):
        """Test scanning ETH"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/eth?timeframe=1h")
        assert response.status_code == 200
        
        data = response.json()
        
        if data is not None:
            assert data.get("confidence", 0) >= 80
            assert data.get("confirmation_count", 0) >= 3
            assert "confirmations" in data
            assert isinstance(data.get("confirmations"), list)
    
    def test_freewill_scan_sol(self):
        """Test scanning SOL"""
        response = requests.get(f"{BASE_URL}/api/freewill/scan/sol?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        
        # Null is expected if no elite setup
        if data is not None:
            assert data.get("confidence", 0) >= 80
            assert data.get("confirmation_count", 0) >= 3
    
    def test_freewill_scan_response_structure(self):
        """Test scan response structure when setup is found"""
        # Try multiple symbols to find one with a setup
        symbols = ["btc", "eth", "sol", "xrp", "doge"]
        timeframes = ["1h", "4h"]
        
        setup_found = None
        for symbol in symbols:
            for tf in timeframes:
                response = requests.get(f"{BASE_URL}/api/freewill/scan/{symbol}?timeframe={tf}")
                if response.status_code == 200 and response.json() is not None:
                    setup_found = response.json()
                    break
            if setup_found:
                break
        
        if setup_found:
            # Verify structure
            required_fields = [
                "symbol", "timeframe", "direction", "confidence",
                "confirmations", "confirmation_count", "entry",
                "stop", "target", "risk_reward", "price", "timestamp"
            ]
            for field in required_fields:
                assert field in setup_found, f"Missing field in setup: {field}"
            
            # Verify risk/reward is positive
            assert setup_found.get("risk_reward", 0) > 0


class TestBacktestRSI:
    """Test RSI mean reversion backtesting strategy"""
    
    def test_backtest_rsi_btc(self):
        """Test RSI backtest for BTC"""
        response = requests.get(f"{BASE_URL}/api/backtest/rsi/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify required fields
        assert data.get("symbol") == "BTC/USDT"
        assert data.get("strategy") == "RSI Mean Reversion"
        assert "win_rate" in data
        assert "total_pnl_pct" in data
        assert "profit_factor" in data
        assert "total_trades" in data
    
    def test_backtest_rsi_eth(self):
        """Test RSI backtest for ETH"""
        response = requests.get(f"{BASE_URL}/api/backtest/rsi/eth?timeframe=4h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "ETH/USDT"
        assert data.get("strategy") == "RSI Mean Reversion"
        assert "win_rate" in data
    
    def test_backtest_rsi_custom_params(self):
        """Test RSI backtest with custom parameters"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/rsi/btc?timeframe=1h&oversold=25&overbought=75&stop_pct=1.5&target_pct=3.0&days=30"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("strategy") == "RSI Mean Reversion"
    
    def test_backtest_rsi_response_structure(self):
        """Test RSI backtest response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/backtest/rsi/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = [
            "symbol", "timeframe", "strategy", "total_trades",
            "wins", "losses", "win_rate", "total_pnl_pct",
            "avg_win_pct", "avg_loss_pct", "profit_factor",
            "max_drawdown_pct", "avg_bars_held", "best_trade_pct",
            "worst_trade_pct", "trades", "timestamp"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestBacktestBB:
    """Test Bollinger Band backtesting strategy"""
    
    def test_backtest_bb_btc(self):
        """Test BB backtest for BTC"""
        response = requests.get(f"{BASE_URL}/api/backtest/bb/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "BTC/USDT"
        assert data.get("strategy") == "Bollinger Band"
        assert "win_rate" in data
        assert "profit_factor" in data
    
    def test_backtest_bb_eth(self):
        """Test BB backtest for ETH"""
        response = requests.get(f"{BASE_URL}/api/backtest/bb/eth?timeframe=4h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "ETH/USDT"
        assert data.get("strategy") == "Bollinger Band"
    
    def test_backtest_bb_sol(self):
        """Test BB backtest for SOL"""
        response = requests.get(f"{BASE_URL}/api/backtest/bb/sol?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "SOL/USDT"
        assert data.get("strategy") == "Bollinger Band"


class TestBacktestEMA:
    """Test EMA crossover backtesting strategy"""
    
    def test_backtest_ema_btc(self):
        """Test EMA backtest for BTC"""
        response = requests.get(f"{BASE_URL}/api/backtest/ema/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "BTC/USDT"
        assert data.get("strategy") == "EMA Crossover"
        assert "win_rate" in data
        assert "profit_factor" in data
    
    def test_backtest_ema_eth(self):
        """Test EMA backtest for ETH"""
        response = requests.get(f"{BASE_URL}/api/backtest/ema/eth?timeframe=4h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "ETH/USDT"
        assert data.get("strategy") == "EMA Crossover"
    
    def test_backtest_ema_custom_periods(self):
        """Test EMA backtest with custom fast/slow periods"""
        response = requests.get(
            f"{BASE_URL}/api/backtest/ema/btc?timeframe=1h&fast=12&slow=26&stop_pct=1.5&days=30"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("strategy") == "EMA Crossover"


class TestBacktestCompare:
    """Test strategy comparison endpoint"""
    
    def test_backtest_compare_btc(self):
        """Test comparing all strategies for BTC"""
        response = requests.get(f"{BASE_URL}/api/backtest/compare/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "BTC/USDT"
        assert "strategies" in data
        assert len(data.get("strategies", [])) == 3  # RSI, BB, EMA
        assert "best_strategy" in data
    
    def test_backtest_compare_eth(self):
        """Test comparing all strategies for ETH"""
        response = requests.get(f"{BASE_URL}/api/backtest/compare/eth?timeframe=4h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data.get("symbol") == "ETH/USDT"
        assert len(data.get("strategies", [])) == 3
        assert "best_strategy" in data
    
    def test_backtest_compare_returns_best(self):
        """Test that compare returns the best strategy by profit factor"""
        response = requests.get(f"{BASE_URL}/api/backtest/compare/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        strategies = data.get("strategies", [])
        best_strategy = data.get("best_strategy")
        
        # Find strategy with highest profit factor
        valid_strategies = [s for s in strategies if "error" not in s and s.get("total_trades", 0) > 0]
        if valid_strategies:
            highest_pf = max(valid_strategies, key=lambda x: x.get("profit_factor", 0))
            assert best_strategy == highest_pf.get("strategy")
    
    def test_backtest_compare_structure(self):
        """Test compare response structure"""
        response = requests.get(f"{BASE_URL}/api/backtest/compare/btc?timeframe=1h&days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ["symbol", "timeframe", "days", "strategies", "best_strategy", "timestamp"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestFreeWillV2Toggle:
    """Test Free Will v2 toggle and configuration endpoints"""
    
    def test_freewill_toggle_on(self):
        """Test toggling Free Will on"""
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("active") == True
    
    def test_freewill_toggle_off(self):
        """Test toggling Free Will off"""
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=false")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("active") == False
        
        # Turn back on
        requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
    
    def test_freewill_confidence_setting(self):
        """Test setting minimum confidence threshold"""
        # Set to 85
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=85")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("min_confidence") == 85
        
        # Reset to 80
        requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=80")
    
    def test_freewill_confidence_bounds(self):
        """Test confidence bounds (70-95)"""
        # Test lower bound
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=60")
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") == 70  # Should be clamped to 70
        
        # Test upper bound
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=99")
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") == 95  # Should be clamped to 95
        
        # Reset to 80
        requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=80")


class TestBacktestMultipleSymbols:
    """Test backtesting across multiple symbols"""
    
    def test_backtest_multiple_symbols_rsi(self):
        """Test RSI backtest for multiple symbols"""
        symbols = ["btc", "eth", "sol", "xrp", "doge"]
        
        for symbol in symbols:
            response = requests.get(f"{BASE_URL}/api/backtest/rsi/{symbol}?timeframe=1h&days=30")
            assert response.status_code == 200, f"Failed for {symbol}"
            
            data = response.json()
            assert data.get("symbol") == f"{symbol.upper()}/USDT"
            assert "total_trades" in data
    
    def test_backtest_multiple_symbols_compare(self):
        """Test strategy comparison for multiple symbols"""
        symbols = ["btc", "eth", "sol"]
        
        for symbol in symbols:
            response = requests.get(f"{BASE_URL}/api/backtest/compare/{symbol}?timeframe=1h&days=30")
            assert response.status_code == 200, f"Failed for {symbol}"
            
            data = response.json()
            assert len(data.get("strategies", [])) == 3


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "online"
    
    def test_api_pairs(self):
        """Test pairs endpoint"""
        response = requests.get(f"{BASE_URL}/api/pairs")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("total_pairs") == 44


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
