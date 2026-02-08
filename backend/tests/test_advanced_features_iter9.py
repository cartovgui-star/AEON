"""
Test Suite for Iteration 9 - Advanced Trading Features
Tests:
1. Divergence Detection (RSI/MACD) - /api/advanced/divergence/{symbol}
2. Market Structure (HH/HL/LH/LL, BOS) - /api/advanced/structure/{symbol}
3. VWAP Calculation - /api/advanced/vwap/{symbol}
4. Full Advanced Analysis - /api/advanced/full/{symbol}
5. Order Flow CVD (MEXC) - /api/orderflow/cvd/{symbol}
6. Full Order Flow - /api/orderflow/full/{symbol}
7. Options Max Pain (Deribit) - /api/options/maxpain/{currency}
8. Options Put/Call Ratio (Deribit) - /api/options/pcr/{currency}
9. Full Options Analysis (Deribit) - /api/options/full/{currency}
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED STRATEGIES TESTS (Divergence, Market Structure, VWAP)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDivergenceDetection:
    """Test RSI and MACD divergence detection"""
    
    def test_divergence_btc_default_timeframe(self, api_client):
        """Test divergence detection for BTC with default 1h timeframe"""
        response = api_client.get(f"{BASE_URL}/api/advanced/divergence/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "BTC" in data["symbol"].upper()
        assert "timeframe" in data
        assert data["timeframe"] == "1h"
        assert "divergences" in data
        assert isinstance(data["divergences"], list)
        assert "has_divergence" in data
        assert isinstance(data["has_divergence"], bool)
        assert "current_rsi" in data
        assert isinstance(data["current_rsi"], (int, float))
        assert "current_macd_hist" in data
        assert "signal" in data
        assert "timestamp" in data
        print(f"✅ BTC Divergence: RSI={data['current_rsi']}, has_divergence={data['has_divergence']}")
    
    def test_divergence_eth_4h_timeframe(self, api_client):
        """Test divergence detection for ETH with 4h timeframe"""
        response = api_client.get(f"{BASE_URL}/api/advanced/divergence/eth?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        assert "ETH" in data["symbol"].upper()
        assert data["timeframe"] == "4h"
        assert "current_rsi" in data
        # RSI should be between 0 and 100
        assert 0 <= data["current_rsi"] <= 100
        print(f"✅ ETH 4h Divergence: RSI={data['current_rsi']}")
    
    def test_divergence_sol_15m_timeframe(self, api_client):
        """Test divergence detection for SOL with 15m timeframe"""
        response = api_client.get(f"{BASE_URL}/api/advanced/divergence/sol?timeframe=15m")
        assert response.status_code == 200
        
        data = response.json()
        assert "SOL" in data["symbol"].upper()
        assert "divergences" in data
        print(f"✅ SOL 15m Divergence: {len(data['divergences'])} divergences found")
    
    def test_divergence_response_structure(self, api_client):
        """Verify divergence response has correct structure when divergence found"""
        response = api_client.get(f"{BASE_URL}/api/advanced/divergence/btc")
        assert response.status_code == 200
        
        data = response.json()
        # If divergences exist, verify structure
        if data["has_divergence"] and len(data["divergences"]) > 0:
            div = data["divergences"][0]
            assert "type" in div
            assert div["type"] in ["REGULAR_BULLISH", "REGULAR_BEARISH", "HIDDEN_BULLISH", "HIDDEN_BEARISH"]
            assert "indicator" in div
            assert div["indicator"] in ["RSI", "MACD"]
            assert "signal" in div
            assert div["signal"] in ["BUY", "SELL"]
            assert "strength" in div
            assert "description" in div
            print(f"✅ Divergence structure verified: {div['type']} - {div['signal']}")
        else:
            print(f"✅ No divergence found (valid response)")


class TestMarketStructure:
    """Test market structure analysis (HH/HL/LH/LL, BOS)"""
    
    def test_structure_btc_default(self, api_client):
        """Test market structure for BTC"""
        response = api_client.get(f"{BASE_URL}/api/advanced/structure/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "BTC" in data["symbol"].upper()
        assert "trend" in data
        assert data["trend"] in ["UPTREND", "DOWNTREND", "RANGING"]
        assert "structure" in data
        assert isinstance(data["structure"], list)
        assert "support" in data
        assert "resistance" in data
        assert "current_price" in data
        assert "bias" in data
        assert data["bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert "is_ranging" in data
        assert "range_pct" in data
        assert "timestamp" in data
        print(f"✅ BTC Structure: Trend={data['trend']}, Bias={data['bias']}, Support=${data['support']:,.2f}, Resistance=${data['resistance']:,.2f}")
    
    def test_structure_eth_4h(self, api_client):
        """Test market structure for ETH 4h"""
        response = api_client.get(f"{BASE_URL}/api/advanced/structure/eth?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        assert "ETH" in data["symbol"].upper()
        assert "swing_highs" in data
        assert "swing_lows" in data
        assert isinstance(data["swing_highs"], list)
        assert isinstance(data["swing_lows"], list)
        print(f"✅ ETH 4h Structure: {len(data['swing_highs'])} swing highs, {len(data['swing_lows'])} swing lows")
    
    def test_structure_bos_detection(self, api_client):
        """Test Break of Structure detection"""
        response = api_client.get(f"{BASE_URL}/api/advanced/structure/btc")
        assert response.status_code == 200
        
        data = response.json()
        # BOS can be None or a dict
        if data.get("bos"):
            bos = data["bos"]
            assert "type" in bos
            assert bos["type"] in ["BULLISH_BOS", "BEARISH_BOS"]
            assert "level" in bos
            assert "description" in bos
            print(f"✅ BOS detected: {bos['type']} at ${bos['level']:,.2f}")
        else:
            print(f"✅ No BOS detected (valid response)")


class TestVWAP:
    """Test VWAP calculation"""
    
    def test_vwap_btc_default(self, api_client):
        """Test VWAP for BTC"""
        response = api_client.get(f"{BASE_URL}/api/advanced/vwap/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "BTC" in data["symbol"].upper()
        assert "vwap" in data
        assert isinstance(data["vwap"], (int, float))
        assert data["vwap"] > 0
        assert "current_price" in data
        assert "distance_pct" in data
        assert "upper_band_1" in data
        assert "lower_band_1" in data
        assert "upper_band_2" in data
        assert "lower_band_2" in data
        assert "bias" in data
        assert data["bias"] in ["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]
        assert "signal" in data
        assert "timestamp" in data
        print(f"✅ BTC VWAP: ${data['vwap']:,.2f}, Price=${data['current_price']:,.2f}, Distance={data['distance_pct']:+.2f}%, Bias={data['bias']}")
    
    def test_vwap_eth_bands(self, api_client):
        """Test VWAP bands for ETH"""
        response = api_client.get(f"{BASE_URL}/api/advanced/vwap/eth")
        assert response.status_code == 200
        
        data = response.json()
        # Verify band ordering: lower_band_2 < lower_band_1 < vwap < upper_band_1 < upper_band_2
        assert data["lower_band_2"] < data["lower_band_1"]
        assert data["lower_band_1"] < data["vwap"]
        assert data["vwap"] < data["upper_band_1"]
        assert data["upper_band_1"] < data["upper_band_2"]
        print(f"✅ ETH VWAP bands verified: -2σ=${data['lower_band_2']:,.2f} < -1σ=${data['lower_band_1']:,.2f} < VWAP=${data['vwap']:,.2f} < +1σ=${data['upper_band_1']:,.2f} < +2σ=${data['upper_band_2']:,.2f}")


class TestFullAdvancedAnalysis:
    """Test combined advanced analysis"""
    
    def test_full_analysis_btc(self, api_client):
        """Test full advanced analysis for BTC"""
        response = api_client.get(f"{BASE_URL}/api/advanced/full/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "overall_signal" in data
        assert data["overall_signal"] in ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
        assert "confidence" in data
        assert 0 <= data["confidence"] <= 100
        assert "divergence" in data
        assert "market_structure" in data
        assert "vwap" in data
        assert "signals_breakdown" in data
        assert "buy_signals" in data["signals_breakdown"]
        assert "sell_signals" in data["signals_breakdown"]
        assert "timestamp" in data
        print(f"✅ BTC Full Analysis: Signal={data['overall_signal']}, Confidence={data['confidence']}%, Buy={data['signals_breakdown']['buy_signals']}, Sell={data['signals_breakdown']['sell_signals']}")
    
    def test_full_analysis_eth_4h(self, api_client):
        """Test full advanced analysis for ETH 4h"""
        response = api_client.get(f"{BASE_URL}/api/advanced/full/eth?timeframe=4h")
        assert response.status_code == 200
        
        data = response.json()
        assert data["timeframe"] == "4h"
        assert "divergence" in data
        assert "market_structure" in data
        assert "vwap" in data
        print(f"✅ ETH 4h Full Analysis: Signal={data['overall_signal']}")


# ═══════════════════════════════════════════════════════════════════════════════
# ORDER FLOW TESTS (CVD from MEXC)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrderFlowCVD:
    """Test CVD (Cumulative Volume Delta) from MEXC"""
    
    def test_cvd_btc(self, api_client):
        """Test CVD for BTC"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/cvd/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "cvd" in data
        assert "buy_volume" in data
        assert "sell_volume" in data
        assert "total_volume" in data
        assert "buy_pct" in data
        assert "sell_pct" in data
        assert "bias" in data
        assert data["bias"] in ["BULLISH", "SLIGHT_BULLISH", "NEUTRAL", "SLIGHT_BEARISH", "BEARISH"]
        assert "signal" in data
        assert "trade_count" in data
        assert "timestamp" in data
        
        # Verify percentages add up to 100
        assert abs(data["buy_pct"] + data["sell_pct"] - 100) < 0.1
        print(f"✅ BTC CVD: ${data['cvd']:,.0f}, Buy={data['buy_pct']:.1f}%, Sell={data['sell_pct']:.1f}%, Bias={data['bias']}")
    
    def test_cvd_eth(self, api_client):
        """Test CVD for ETH"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/cvd/eth")
        assert response.status_code == 200
        
        data = response.json()
        assert "cvd" in data
        assert "cvd_trend" in data
        assert data["cvd_trend"] in ["RISING", "FALLING", "UNKNOWN"]
        print(f"✅ ETH CVD: ${data['cvd']:,.0f}, Trend={data['cvd_trend']}")
    
    def test_cvd_sol(self, api_client):
        """Test CVD for SOL"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/cvd/sol")
        assert response.status_code == 200
        
        data = response.json()
        assert "trade_count" in data
        # Should have fetched trades
        assert data["trade_count"] > 0 or "error" in data
        print(f"✅ SOL CVD: {data.get('trade_count', 0)} trades analyzed")


class TestFullOrderFlow:
    """Test full order flow analysis"""
    
    def test_full_orderflow_btc(self, api_client):
        """Test full order flow for BTC"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/full/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "overall_signal" in data
        assert data["overall_signal"] in ["BUY", "SELL", "NEUTRAL"]
        assert "confidence" in data
        assert "cvd" in data
        assert "divergence" in data
        assert "absorption" in data
        assert "timestamp" in data
        print(f"✅ BTC Full Order Flow: Signal={data['overall_signal']}, Confidence={data['confidence']}%")
    
    def test_orderflow_divergence(self, api_client):
        """Test CVD divergence detection"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/divergence/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "has_divergence" in data
        assert isinstance(data["has_divergence"], bool)
        if data["has_divergence"]:
            assert "divergence" in data
            assert data["divergence"]["type"] in ["BULLISH_CVD_DIVERGENCE", "BEARISH_CVD_DIVERGENCE"]
        print(f"✅ BTC CVD Divergence: has_divergence={data['has_divergence']}")
    
    def test_orderflow_absorption(self, api_client):
        """Test absorption detection"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/absorption/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "has_absorption" in data
        assert "large_buys_count" in data
        assert "large_sells_count" in data
        print(f"✅ BTC Absorption: has_absorption={data['has_absorption']}, large_buys={data['large_buys_count']}, large_sells={data['large_sells_count']}")


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONS DATA TESTS (Deribit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptionsMaxPain:
    """Test Max Pain calculation from Deribit"""
    
    def test_maxpain_btc(self, api_client):
        """Test max pain for BTC"""
        response = api_client.get(f"{BASE_URL}/api/options/maxpain/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Check for error or valid data
        if "error" not in data:
            assert "currency" in data
            assert data["currency"] == "BTC"
            assert "max_pain" in data
            assert isinstance(data["max_pain"], (int, float))
            assert data["max_pain"] > 0
            assert "current_price" in data
            assert "distance" in data
            assert "distance_pct" in data
            assert "bias" in data
            assert data["bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
            assert "signal" in data
            assert "expiry" in data
            assert "days_to_expiry" in data
            assert "timestamp" in data
            print(f"✅ BTC Max Pain: ${data['max_pain']:,.0f}, Current=${data['current_price']:,.0f}, Distance={data['distance_pct']:+.1f}%, Bias={data['bias']}")
        else:
            print(f"⚠️ BTC Max Pain returned error: {data['error']}")
    
    def test_maxpain_eth(self, api_client):
        """Test max pain for ETH"""
        response = api_client.get(f"{BASE_URL}/api/options/maxpain/eth")
        assert response.status_code == 200
        
        data = response.json()
        if "error" not in data:
            assert "currency" in data
            assert data["currency"] == "ETH"
            assert "max_pain" in data
            print(f"✅ ETH Max Pain: ${data['max_pain']:,.0f}")
        else:
            print(f"⚠️ ETH Max Pain returned error: {data['error']}")


class TestOptionsPutCallRatio:
    """Test Put/Call Ratio from Deribit"""
    
    def test_pcr_btc(self, api_client):
        """Test put/call ratio for BTC"""
        response = api_client.get(f"{BASE_URL}/api/options/pcr/btc")
        assert response.status_code == 200
        
        data = response.json()
        if "error" not in data:
            assert "currency" in data
            assert data["currency"] == "BTC"
            assert "put_call_ratio_oi" in data
            assert isinstance(data["put_call_ratio_oi"], (int, float))
            assert data["put_call_ratio_oi"] >= 0
            assert "put_call_ratio_volume" in data
            assert "total_put_oi" in data
            assert "total_call_oi" in data
            assert "sentiment" in data
            assert data["sentiment"] in ["EXTREME_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "EXTREME_BEARISH"]
            assert "signal" in data
            assert "timestamp" in data
            print(f"✅ BTC PCR: {data['put_call_ratio_oi']:.3f}, Sentiment={data['sentiment']}")
        else:
            print(f"⚠️ BTC PCR returned error: {data['error']}")
    
    def test_pcr_eth(self, api_client):
        """Test put/call ratio for ETH"""
        response = api_client.get(f"{BASE_URL}/api/options/pcr/eth")
        assert response.status_code == 200
        
        data = response.json()
        if "error" not in data:
            assert "put_call_ratio_oi" in data
            print(f"✅ ETH PCR: {data['put_call_ratio_oi']:.3f}")
        else:
            print(f"⚠️ ETH PCR returned error: {data['error']}")


class TestOptionsOI:
    """Test Options Open Interest by Strike"""
    
    def test_oi_btc(self, api_client):
        """Test OI distribution for BTC"""
        response = api_client.get(f"{BASE_URL}/api/options/oi/btc")
        assert response.status_code == 200
        
        data = response.json()
        if "error" not in data:
            assert "currency" in data
            assert "call_wall" in data
            assert "put_wall" in data
            assert "total_call_oi" in data
            assert "total_put_oi" in data
            print(f"✅ BTC Options OI: Call Wall=${data['call_wall']:,.0f}, Put Wall=${data['put_wall']:,.0f}")
        else:
            print(f"⚠️ BTC Options OI returned error: {data['error']}")


class TestFullOptionsAnalysis:
    """Test full options analysis"""
    
    def test_full_options_btc(self, api_client):
        """Test full options analysis for BTC"""
        response = api_client.get(f"{BASE_URL}/api/options/full/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "currency" in data
        assert data["currency"] == "BTC"
        assert "max_pain" in data
        assert "put_call_ratio" in data
        assert "oi_distribution" in data
        assert "overall_bias" in data
        assert data["overall_bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert "timestamp" in data
        print(f"✅ BTC Full Options: Overall Bias={data['overall_bias']}")
    
    def test_full_options_eth(self, api_client):
        """Test full options analysis for ETH"""
        response = api_client.get(f"{BASE_URL}/api/options/full/eth")
        assert response.status_code == 200
        
        data = response.json()
        assert "currency" in data
        assert data["currency"] == "ETH"
        print(f"✅ ETH Full Options: Overall Bias={data.get('overall_bias', 'N/A')}")


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - Multiple Symbols
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultipleSymbols:
    """Test endpoints work for multiple symbols"""
    
    @pytest.mark.parametrize("symbol", ["btc", "eth", "sol", "xrp", "doge"])
    def test_divergence_multiple_symbols(self, api_client, symbol):
        """Test divergence for multiple symbols"""
        response = api_client.get(f"{BASE_URL}/api/advanced/divergence/{symbol}")
        assert response.status_code == 200
        data = response.json()
        assert "current_rsi" in data
        print(f"✅ {symbol.upper()} divergence: RSI={data['current_rsi']}")
    
    @pytest.mark.parametrize("symbol", ["btc", "eth", "sol"])
    def test_structure_multiple_symbols(self, api_client, symbol):
        """Test market structure for multiple symbols"""
        response = api_client.get(f"{BASE_URL}/api/advanced/structure/{symbol}")
        assert response.status_code == 200
        data = response.json()
        assert "trend" in data
        print(f"✅ {symbol.upper()} structure: Trend={data['trend']}")
    
    @pytest.mark.parametrize("symbol", ["btc", "eth", "sol"])
    def test_cvd_multiple_symbols(self, api_client, symbol):
        """Test CVD for multiple symbols"""
        response = api_client.get(f"{BASE_URL}/api/orderflow/cvd/{symbol}")
        assert response.status_code == 200
        data = response.json()
        assert "bias" in data
        print(f"✅ {symbol.upper()} CVD: Bias={data['bias']}")


# ═══════════════════════════════════════════════════════════════════════════════
# API HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self, api_client):
        """Test API root endpoint"""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "online"
        print(f"✅ API is online")
    
    def test_api_pairs(self, api_client):
        """Test pairs endpoint"""
        response = api_client.get(f"{BASE_URL}/api/pairs")
        assert response.status_code == 200
        data = response.json()
        assert "total_pairs" in data
        assert data["total_pairs"] == 44
        print(f"✅ API supports {data['total_pairs']} pairs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
