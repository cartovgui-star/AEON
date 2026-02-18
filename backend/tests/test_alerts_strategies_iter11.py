"""
AEON TRADING BOT - Iteration 11 Test Suite
Tests for Price Alerts and Multi-Strategy Engine

Features tested:
1. Alert System Stats (/api/alerts/stats)
2. Dashboard Alerts (/api/alerts/dashboard)
3. Add Custom Price Alert (/api/alerts/add)
4. List Custom Alerts (/api/alerts/custom)
5. Multi-Strategy Scan (/api/strategies/all/{symbol})
6. MA Crossover Strategy (/api/strategies/ma/{symbol})
7. RSI Momentum Strategy (/api/strategies/rsi/{symbol})
8. Breakout Strategy (/api/strategies/breakout/{symbol})
9. BB Squeeze Strategy (/api/strategies/bb/{symbol})
10. MACD Reversal Strategy (/api/strategies/macd/{symbol})
11. Trend Pullback Strategy (/api/strategies/pullback/{symbol})
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://aeon-ai-bot.preview.emergentagent.com')


class TestAlertSystem:
    """Tests for the Price Alert System"""
    
    def test_alerts_stats_endpoint(self):
        """Test alert stats endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify required fields
        assert "active" in data
        assert "auto_alerts_enabled" in data
        assert "tracked_symbols" in data
        assert "custom_alerts" in data
        assert "total_alerts_sent" in data
        assert "alerts_today" in data
        assert "thresholds" in data
        
        # Verify thresholds structure
        thresholds = data["thresholds"]
        assert "price_change_5min" in thresholds
        assert "price_change_1h" in thresholds
        assert "rsi_oversold" in thresholds
        assert "rsi_overbought" in thresholds
        assert "volume_spike_mult" in thresholds
        
        print(f"✅ Alert stats: {data['tracked_symbols']} symbols tracked, {data['custom_alerts']} custom alerts")
    
    def test_alerts_dashboard_endpoint(self):
        """Test dashboard alerts endpoint"""
        response = requests.get(f"{BASE_URL}/api/alerts/dashboard?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "unread" in data
        assert isinstance(data["alerts"], list)
        
        print(f"✅ Dashboard alerts: {data['total']} total, {data['unread']} unread")
    
    def test_add_custom_alert(self):
        """Test adding a custom price alert"""
        alert_data = {
            "symbol": "SOL",
            "target_price": 150,
            "direction": "above"
        }
        
        response = requests.post(f"{BASE_URL}/api/alerts/add", json=alert_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "alert_id" in data
        assert "message" in data
        assert "SOL" in data["message"]
        
        print(f"✅ Custom alert added: {data['alert_id']}")
        return data["alert_id"]
    
    def test_add_alert_below_target(self):
        """Test adding a price alert for below target"""
        alert_data = {
            "symbol": "ETH",
            "target_price": 1800,
            "direction": "below"
        }
        
        response = requests.post(f"{BASE_URL}/api/alerts/add", json=alert_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "below" in data["message"].lower() or "1,800" in data["message"]
        
        print(f"✅ Below target alert added: {data['alert_id']}")
    
    def test_list_custom_alerts(self):
        """Test listing custom price alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts/custom")
        assert response.status_code == 200
        
        data = response.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        # Verify alert structure if any exist
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "alert_id" in alert
            assert "symbol" in alert
            assert "alert_type" in alert
            assert "condition" in alert
            assert "active" in alert
        
        print(f"✅ Custom alerts listed: {len(data['alerts'])} alerts")
    
    def test_delete_alert(self):
        """Test deleting a custom alert"""
        # First add an alert
        alert_data = {
            "symbol": "DOGE",
            "target_price": 0.5,
            "direction": "above"
        }
        
        add_response = requests.post(f"{BASE_URL}/api/alerts/add", json=alert_data)
        assert add_response.status_code == 200
        alert_id = add_response.json()["alert_id"]
        
        # Now delete it
        delete_response = requests.delete(f"{BASE_URL}/api/alerts/{alert_id}")
        assert delete_response.status_code == 200
        
        data = delete_response.json()
        assert data["success"] == True
        
        print(f"✅ Alert {alert_id} deleted successfully")


class TestMultiStrategyEngine:
    """Tests for the Multi-Strategy Analysis Engine"""
    
    def test_strategies_all_btc(self):
        """Test multi-strategy scan for BTC"""
        response = requests.get(f"{BASE_URL}/api/strategies/all/BTC?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "timeframe" in data
        assert "overall_signal" in data
        assert "average_confidence" in data
        assert "buy_signals" in data
        assert "sell_signals" in data
        assert "neutral_signals" in data
        assert "strategies" in data
        
        # Verify signal values
        assert data["overall_signal"] in ["BUY", "SELL", "NEUTRAL", "STRONG_BUY", "STRONG_SELL"]
        assert 0 <= data["average_confidence"] <= 100
        
        # Verify strategies list
        assert isinstance(data["strategies"], list)
        assert len(data["strategies"]) >= 4  # Should have at least 4 strategies
        
        print(f"✅ BTC multi-strategy: {data['overall_signal']} ({data['average_confidence']:.1f}% conf)")
        print(f"   Buy: {data['buy_signals']}, Sell: {data['sell_signals']}, Neutral: {data['neutral_signals']}")
    
    def test_strategies_all_eth(self):
        """Test multi-strategy scan for ETH"""
        response = requests.get(f"{BASE_URL}/api/strategies/all/ETH?timeframe=1h")
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "ETH/USDT"
        assert data["timeframe"] == "1h"
        assert "strategies" in data
        
        print(f"✅ ETH multi-strategy: {data['overall_signal']} ({data['average_confidence']:.1f}% conf)")
    
    def test_strategies_all_sol(self):
        """Test multi-strategy scan for SOL"""
        response = requests.get(f"{BASE_URL}/api/strategies/all/SOL")
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "SOL/USDT"
        
        print(f"✅ SOL multi-strategy: {data['overall_signal']} ({data['average_confidence']:.1f}% conf)")
    
    def test_best_strategy_structure(self):
        """Test that best_strategy has correct structure"""
        response = requests.get(f"{BASE_URL}/api/strategies/all/BTC")
        assert response.status_code == 200
        
        data = response.json()
        
        # best_strategy can be null if all are NEUTRAL
        if data.get("best_strategy"):
            best = data["best_strategy"]
            assert "strategy" in best
            assert "signal" in best
            assert "confidence" in best
            assert "price" in best
            assert "entry" in best
            assert "stop" in best
            assert "target" in best
            
            print(f"✅ Best strategy: {best['strategy']} - {best['signal']} ({best['confidence']}% conf)")
        else:
            print("✅ No best strategy (all neutral)")


class TestIndividualStrategies:
    """Tests for individual strategy endpoints"""
    
    def test_ma_crossover_strategy(self):
        """Test MA Crossover strategy endpoint"""
        response = requests.get(f"{BASE_URL}/api/strategies/ma/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data["strategy"] == "MA_CROSSOVER"
        assert "signal" in data
        assert "confidence" in data
        assert "ema_fast" in data
        assert "ema_slow" in data
        assert "explanation" in data
        
        print(f"✅ MA Crossover BTC: {data['signal']} (EMA{data['params']['fast']}/{data['params']['slow']})")
    
    def test_ma_crossover_custom_params(self):
        """Test MA Crossover with custom parameters"""
        response = requests.get(f"{BASE_URL}/api/strategies/ma/ETH?fast=12&slow=26")
        assert response.status_code == 200
        
        data = response.json()
        # Note: The endpoint may or may not use custom params based on implementation
        assert data["strategy"] == "MA_CROSSOVER"
        
        print(f"✅ MA Crossover ETH: {data['signal']}")
    
    def test_rsi_momentum_strategy(self):
        """Test RSI Momentum strategy endpoint"""
        response = requests.get(f"{BASE_URL}/api/strategies/rsi/SOL")
        assert response.status_code == 200
        
        data = response.json()
        assert data["strategy"] == "RSI_MOMENTUM"
        assert "rsi" in data
        assert "prev_rsi" in data
        assert 0 <= data["rsi"] <= 100
        
        print(f"✅ RSI Momentum SOL: {data['signal']} (RSI: {data['rsi']:.1f})")
    
    def test_breakout_strategy(self):
        """Test Breakout strategy endpoint"""
        response = requests.get(f"{BASE_URL}/api/strategies/breakout/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data["strategy"] == "BREAKOUT"
        assert "resistance" in data
        assert "support" in data
        assert "range_pct" in data
        assert "volume_mult" in data
        
        print(f"✅ Breakout BTC: {data['signal']} (R: ${data['resistance']:,.0f}, S: ${data['support']:,.0f})")
    
    def test_bb_squeeze_strategy(self):
        """Test Bollinger Band Squeeze strategy endpoint"""
        response = requests.get(f"{BASE_URL}/api/strategies/bb/ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data["strategy"] == "BB_SQUEEZE"
        assert "bb_upper" in data
        assert "bb_middle" in data
        assert "bb_lower" in data
        assert "bandwidth" in data
        
        print(f"✅ BB Squeeze ETH: {data['signal']} (BW: {data['bandwidth']:.2f}%)")
    
    def test_macd_reversal_strategy(self):
        """Test MACD Reversal strategy endpoint"""
        response = requests.get(f"{BASE_URL}/api/strategies/macd/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data["strategy"] == "MACD_REVERSAL"
        assert "macd_line" in data
        assert "signal_line" in data
        assert "histogram" in data
        
        print(f"✅ MACD Reversal BTC: {data['signal']} (Histogram: {data['histogram']:.2f})")
    
    def test_trend_pullback_strategy(self):
        """Test Trend Pullback strategy endpoint"""
        response = requests.get(f"{BASE_URL}/api/strategies/pullback/ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data["strategy"] == "TREND_PULLBACK"
        assert "ema_21" in data
        assert "ema_50" in data
        assert "trend" in data
        assert "distance_pct" in data
        assert data["trend"] in ["UPTREND", "DOWNTREND"]
        
        print(f"✅ Trend Pullback ETH: {data['signal']} ({data['trend']})")


class TestStrategyDetails:
    """Tests for strategy response details"""
    
    def test_strategy_entry_stop_target(self):
        """Test that all strategies return entry, stop, target"""
        strategies = [
            ("ma", "BTC"),
            ("rsi", "ETH"),
            ("breakout", "SOL"),
            ("bb", "BTC"),
            ("macd", "ETH"),
            ("pullback", "SOL")
        ]
        
        for strat, symbol in strategies:
            response = requests.get(f"{BASE_URL}/api/strategies/{strat}/{symbol}")
            assert response.status_code == 200
            
            data = response.json()
            assert "entry" in data, f"{strat} missing entry"
            assert "stop" in data, f"{strat} missing stop"
            assert "target" in data, f"{strat} missing target"
            assert data["entry"] > 0
            
            print(f"✅ {strat.upper()} {symbol}: Entry=${data['entry']:,.2f}, Stop=${data['stop']:,.2f}, Target=${data['target']:,.2f}")
    
    def test_strategy_timestamp(self):
        """Test that strategies include timestamp"""
        response = requests.get(f"{BASE_URL}/api/strategies/all/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        
        # Check individual strategies have timestamps too
        if data.get("strategies"):
            for strat in data["strategies"]:
                assert "timestamp" in strat
        
        print(f"✅ Timestamps present in responses")
    
    def test_multiple_symbols_strategies(self):
        """Test strategies across multiple symbols"""
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
        
        for symbol in symbols:
            response = requests.get(f"{BASE_URL}/api/strategies/all/{symbol}?timeframe=4h")
            assert response.status_code == 200
            
            data = response.json()
            assert data["symbol"] == f"{symbol}/USDT"
            assert len(data.get("strategies", [])) >= 1
            
            print(f"✅ {symbol}: {data['overall_signal']} ({data['average_confidence']:.0f}% conf, {len(data['strategies'])} strategies)")


class TestAlertAndStrategyIntegration:
    """Integration tests between alerts and strategies"""
    
    def test_alert_stats_tracked_symbols(self):
        """Verify tracked symbols count matches expected"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Should track at least 10 symbols (BTC, ETH, SOL, etc.)
        assert data["tracked_symbols"] >= 10
        
        print(f"✅ Alert system tracking {data['tracked_symbols']} symbols")
    
    def test_alert_thresholds_valid(self):
        """Verify alert thresholds are reasonable"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats")
        assert response.status_code == 200
        
        thresholds = response.json()["thresholds"]
        
        # Verify thresholds are reasonable
        assert 0 < thresholds["price_change_5min"] <= 10  # 0-10% for 5min
        assert 0 < thresholds["price_change_1h"] <= 20    # 0-20% for 1h
        assert 0 < thresholds["rsi_oversold"] <= 40       # RSI oversold threshold
        assert 60 <= thresholds["rsi_overbought"] <= 100  # RSI overbought threshold
        assert 1 <= thresholds["volume_spike_mult"] <= 10 # Volume multiplier
        
        print(f"✅ Alert thresholds valid: 5m={thresholds['price_change_5min']}%, RSI OS/OB={thresholds['rsi_oversold']}/{thresholds['rsi_overbought']}")


class TestHealthAndPairs:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "online"
        
        print(f"✅ API is online")
    
    def test_pairs_endpoint(self):
        """Test pairs endpoint"""
        response = requests.get(f"{BASE_URL}/api/pairs")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_pairs" in data
        assert "pairs" in data
        assert len(data["pairs"]) > 0
        
        print(f"✅ {data['total_pairs']} trading pairs available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
