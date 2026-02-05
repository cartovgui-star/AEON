"""
Test suite for Aeon Comprehensive API Testing
Tests: Derivatives (4 exchanges), Intel, News, On-chain, Whales, MTF, Calculator, Trading
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ═══════════════════════════════════════════════════════════════════════════════
# DERIVATIVES APIs - Real data from OKX, Bitget, KuCoin, Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestDerivativesFunding:
    """Test derivatives funding rate endpoints from multiple exchanges"""
    
    def test_aggregated_funding_btc(self):
        """Test /api/derivatives/funding/btc - aggregated from 4 exchanges"""
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
        assert "timestamp" in data
        
        # Verify exchanges list
        assert isinstance(data["exchanges"], list)
        assert data["data_sources"] >= 1  # At least one exchange should respond
        
        # Verify average funding rate is a number
        assert isinstance(data["average_funding_rate"], (int, float))
        
        print(f"BTC Funding: {data['average_funding_pct']} from {data['data_sources']} exchanges")
        print(f"Interpretation: {data['interpretation']}")
    
    def test_exchange_funding_okx(self):
        """Test /api/derivatives/funding/exchange/okx/btc"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/exchange/okx/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "exchange" in data
        assert data["exchange"] == "OKX"
        
        if "error" not in data:
            assert "funding_rate" in data
            assert "funding_rate_pct" in data
            print(f"OKX BTC Funding: {data.get('funding_rate_pct', 'N/A')}")
    
    def test_exchange_funding_bitget(self):
        """Test /api/derivatives/funding/exchange/bitget/btc"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/exchange/bitget/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "exchange" in data
        assert data["exchange"] == "Bitget"
        
        if "error" not in data:
            assert "funding_rate" in data
            print(f"Bitget BTC Funding: {data.get('funding_rate_pct', 'N/A')}")
    
    def test_exchange_funding_kucoin(self):
        """Test /api/derivatives/funding/exchange/kucoin/btc"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/exchange/kucoin/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "exchange" in data
        assert data["exchange"] == "KuCoin"
        
        if "error" not in data:
            assert "funding_rate" in data
            print(f"KuCoin BTC Funding: {data.get('funding_rate_pct', 'N/A')}")
    
    def test_exchange_funding_gate(self):
        """Test /api/derivatives/funding/exchange/gate/btc"""
        response = requests.get(f"{BASE_URL}/api/derivatives/funding/exchange/gate/btc")
        assert response.status_code == 200
        
        data = response.json()
        assert "exchange" in data
        assert data["exchange"] == "Gate.io"
        
        if "error" not in data:
            assert "funding_rate" in data
            print(f"Gate.io BTC Funding: {data.get('funding_rate_pct', 'N/A')}")


class TestDerivativesOpenInterest:
    """Test derivatives open interest endpoints"""
    
    def test_aggregated_oi_btc(self):
        """Test /api/derivatives/oi/btc - aggregated OI from OKX/Bitget"""
        response = requests.get(f"{BASE_URL}/api/derivatives/oi/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "total_open_interest_str" in data
        assert "exchanges" in data
        assert "data_sources" in data
        assert "timestamp" in data
        
        # Verify exchanges list
        assert isinstance(data["exchanges"], list)
        
        print(f"BTC Total OI: {data['total_open_interest_str']} from {data['data_sources']} exchanges")


class TestDerivativesFullReport:
    """Test full derivatives report endpoint"""
    
    def test_full_derivatives_btc(self):
        """Test /api/derivatives/full/btc - comprehensive derivatives report"""
        response = requests.get(f"{BASE_URL}/api/derivatives/full/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "timestamp" in data
        assert "funding" in data
        assert "open_interest" in data
        assert "long_short" in data
        assert "summary" in data
        
        # Verify funding data
        funding = data["funding"]
        assert "average_funding_pct" in funding or "error" in funding
        
        # Verify OI data
        oi = data["open_interest"]
        assert "total_open_interest_str" in oi or "error" in oi
        
        # Verify L/S data (estimated from funding)
        ls = data["long_short"]
        if "error" not in ls:
            assert "long_pct" in ls
            assert "short_pct" in ls
            assert "note" in ls  # Should mention it's estimated
        
        print(f"Full BTC Derivatives Report:")
        print(f"  Funding: {funding.get('average_funding_pct', 'N/A')}")
        print(f"  OI: {oi.get('total_open_interest_str', 'N/A')}")
        print(f"  L/S: {ls.get('long_pct', 'N/A')}% Long / {ls.get('short_pct', 'N/A')}% Short")


# ═══════════════════════════════════════════════════════════════════════════════
# INTEL APIs - Fear & Greed, Top 100, Market Summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntelAPIs:
    """Test enhanced market intelligence endpoints"""
    
    def test_fear_greed_index(self):
        """Test /api/intel/fear-greed - Fear & Greed Index from Alternative.me"""
        response = requests.get(f"{BASE_URL}/api/intel/fear-greed")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "value" in data
        assert "classification" in data
        
        # Verify value is in valid range (0-100)
        assert isinstance(data["value"], int)
        assert 0 <= data["value"] <= 100
        
        # Verify classification is valid
        valid_classifications = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
        assert data["classification"] in valid_classifications
        
        print(f"Fear & Greed Index: {data['value']} ({data['classification']})")
    
    def test_top_100_coins(self):
        """Test /api/intel/top100 - Top coins from MEXC"""
        response = requests.get(f"{BASE_URL}/api/intel/top100")
        assert response.status_code == 200
        
        data = response.json()
        # Should return a list
        assert isinstance(data, list)
        
        # Should have at least some coins
        assert len(data) >= 1
        
        # Verify structure of first coin
        coin = data[0]
        assert "symbol" in coin
        assert "current_price" in coin
        assert "price_change_percentage_24h" in coin
        
        print(f"Top coins returned: {len(data)}")
        for c in data[:3]:
            print(f"  {c.get('symbol', '').upper()}: ${c.get('current_price', 0):,.2f} ({c.get('price_change_percentage_24h', 0):+.2f}%)")
    
    def test_market_summary(self):
        """Test /api/intel/summary - Comprehensive market summary"""
        response = requests.get(f"{BASE_URL}/api/intel/summary")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "summary" in data
        
        # Summary should be a non-empty string
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 50  # Should have meaningful content
        
        print(f"Market Summary (first 200 chars): {data['summary'][:200]}...")


# ═══════════════════════════════════════════════════════════════════════════════
# NEWS APIs - Latest news and sentiment
# ═══════════════════════════════════════════════════════════════════════════════

class TestNewsAPIs:
    """Test news and sentiment endpoints"""
    
    def test_latest_news(self):
        """Test /api/news/latest - Latest crypto news"""
        response = requests.get(f"{BASE_URL}/api/news/latest")
        assert response.status_code == 200
        
        data = response.json()
        # Should return a list
        assert isinstance(data, list)
        
        # If news exists, verify structure
        if len(data) > 0:
            news = data[0]
            assert "title" in news
            assert "sentiment" in news
            
            # Verify sentiment structure
            sentiment = news["sentiment"]
            assert "label" in sentiment
            assert "emoji" in sentiment
            
            print(f"Latest news ({len(data)} articles):")
            for n in data[:3]:
                print(f"  {n['sentiment']['emoji']} {n['title'][:60]}...")
    
    def test_news_sentiment(self):
        """Test /api/news/sentiment - News sentiment summary"""
        response = requests.get(f"{BASE_URL}/api/news/sentiment")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "sentiment" in data
        assert "bullish_pct" in data
        assert "bearish_pct" in data
        
        # Verify sentiment is valid
        assert data["sentiment"] in ["BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"]
        
        # Verify percentages are numbers
        assert isinstance(data["bullish_pct"], (int, float))
        assert isinstance(data["bearish_pct"], (int, float))
        
        print(f"News Sentiment: {data['sentiment']}")
        print(f"  Bullish: {data['bullish_pct']}% | Bearish: {data['bearish_pct']}%")


# ═══════════════════════════════════════════════════════════════════════════════
# ON-CHAIN APIs - Bitcoin on-chain stats and exchange flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnChainAPIs:
    """Test on-chain data endpoints"""
    
    def test_btc_onchain_stats(self):
        """Test /api/onchain/btc - Bitcoin on-chain stats from mempool.space"""
        response = requests.get(f"{BASE_URL}/api/onchain/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "network" in data
        assert data["network"] == "Bitcoin"
        
        # Should have fees data
        if "fees" in data:
            fees = data["fees"]
            assert "fastest" in fees
            assert "hour" in fees
            print(f"BTC Fees: Fastest={fees['fastest']} sat/vB, Hour={fees['hour']} sat/vB")
        
        # Should have fee interpretation
        if "fee_interpretation" in data:
            print(f"Fee Interpretation: {data['fee_interpretation']}")
    
    def test_exchange_flow(self):
        """Test /api/onchain/flow - Exchange flow estimate"""
        response = requests.get(f"{BASE_URL}/api/onchain/flow")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "flow_estimate" in data or "error" in data
        
        if "error" not in data:
            assert "mempool_tx_count" in data
            assert "interpretation" in data
            
            print(f"Exchange Flow: {data['flow_estimate']}")
            print(f"  Mempool TX: {data['mempool_tx_count']:,}")
            print(f"  {data['interpretation']}")


# ═══════════════════════════════════════════════════════════════════════════════
# WHALE TRACKING APIs
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhaleAPIs:
    """Test whale tracking endpoints"""
    
    def test_whale_activity(self):
        """Test /api/whales/activity - Whale activity summary"""
        response = requests.get(f"{BASE_URL}/api/whales/activity")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "activity" in data
        
        # Activity should be valid level
        assert data["activity"] in ["HIGH", "MODERATE", "LOW"]
        
        # Should have emoji
        if "emoji" in data:
            assert data["emoji"] in ["🔴", "🟡", "🟢"]
        
        print(f"Whale Activity: {data.get('emoji', '')} {data['activity']}")
        
        if "large_transactions" in data:
            print(f"  Large TX: {data['large_transactions']}")
        if "whale_transactions" in data:
            print(f"  Whale TX (>100 BTC): {data['whale_transactions']}")
        if "total_btc_moved" in data:
            print(f"  Total BTC Moved: {data['total_btc_moved']} BTC")


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME ANALYSIS APIs
# ═══════════════════════════════════════════════════════════════════════════════

class TestMTFAPIs:
    """Test multi-timeframe analysis endpoints"""
    
    def test_mtf_analysis_btc(self):
        """Test /api/mtf/btc - Multi-timeframe analysis (1h, 4h, 1d)"""
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
        assert "1h" in timeframes or "4h" in timeframes or "1d" in timeframes
        
        # Verify confidence is a number
        assert isinstance(data["confidence"], (int, float))
        assert 0 <= data["confidence"] <= 100
        
        print(f"BTC MTF Analysis:")
        print(f"  Confluence: {data['confluence_emoji']} {data['confluence']}")
        print(f"  Confidence: {data['confidence']}%")
        print(f"  Recommendation: {data['recommendation']}")
        
        for tf, tf_data in timeframes.items():
            if "bias" in tf_data:
                print(f"  {tf}: {tf_data.get('emoji', '')} {tf_data['bias']} (score: {tf_data.get('score', 0):+.1f})")
    
    def test_trend_alignment_btc(self):
        """Test /api/mtf/align/btc - Trend alignment across timeframes"""
        response = requests.get(f"{BASE_URL}/api/mtf/align/btc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "symbol" in data
        assert "status" in data
        assert "trade_quality" in data
        assert "alignment_details" in data
        assert "daily_bias" in data
        assert "recommendation" in data
        
        # Verify status is valid
        assert data["status"] in ["FULL ALIGNMENT", "PARTIAL ALIGNMENT", "NO ALIGNMENT"]
        
        # Verify trade quality
        assert data["trade_quality"] in ["HIGH", "MEDIUM", "LOW"]
        
        print(f"BTC Trend Alignment:")
        print(f"  Status: {data['status']}")
        print(f"  Trade Quality: {data['trade_quality']}")
        print(f"  Daily Bias: {data['daily_bias']}")


# ═══════════════════════════════════════════════════════════════════════════════
# FUTURES CALCULATOR APIs
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculatorAPIs:
    """Test futures calculator endpoints"""
    
    def test_calc_pnl_long(self):
        """Test /api/calc/pnl - PnL calculation for LONG position"""
        params = {
            "entry": 65000,
            "exit": 68000,
            "size": 1000,
            "leverage": 10,
            "direction": "LONG"
        }
        response = requests.get(f"{BASE_URL}/api/calc/pnl", params=params)
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "direction" in data
        assert "entry_price" in data
        assert "exit_price" in data
        assert "leverage" in data
        assert "position_size_usd" in data
        assert "margin_required" in data
        assert "pnl_pct" in data
        assert "pnl_usd" in data
        assert "roi_on_margin" in data
        assert "liquidation_price" in data
        assert "status" in data
        
        # Verify calculations
        assert data["direction"] == "LONG"
        assert data["entry_price"] == 65000
        assert data["exit_price"] == 68000
        assert data["leverage"] == 10
        
        # Price went up 4.6%, with 10x leverage = ~46% PnL
        assert data["pnl_pct"] > 40
        assert data["pnl_usd"] > 0
        assert data["status"] == "PROFIT"
        
        print(f"LONG PnL Calculation:")
        print(f"  Entry: ${data['entry_price']:,} -> Exit: ${data['exit_price']:,}")
        print(f"  Position: ${data['position_size_usd']:,} @ {data['leverage']}x")
        print(f"  PnL: {data['pnl_pct']:+.2f}% (${data['pnl_usd']:+,.2f})")
        print(f"  ROI on Margin: {data['roi_on_margin']:+.2f}%")
        print(f"  Liquidation: ${data['liquidation_price']:,.2f}")
    
    def test_calc_pnl_short(self):
        """Test /api/calc/pnl - PnL calculation for SHORT position"""
        params = {
            "entry": 68000,
            "exit": 65000,
            "size": 1000,
            "leverage": 5,
            "direction": "SHORT"
        }
        response = requests.get(f"{BASE_URL}/api/calc/pnl", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["direction"] == "SHORT"
        assert data["pnl_usd"] > 0  # Price went down, short profits
        assert data["status"] == "PROFIT"
        
        print(f"SHORT PnL: {data['pnl_pct']:+.2f}% (${data['pnl_usd']:+,.2f})")
    
    def test_calc_position_size(self):
        """Test /api/calc/position - Position size calculator"""
        params = {
            "balance": 10000,
            "risk_pct": 2,
            "entry": 65000,
            "stop": 63000,
            "leverage": 10
        }
        response = requests.get(f"{BASE_URL}/api/calc/position", params=params)
        assert response.status_code == 200
        
        data = response.json()
        # Verify structure
        assert "account_balance" in data
        assert "risk_pct" in data
        assert "risk_amount_usd" in data
        assert "entry_price" in data
        assert "stop_loss_price" in data
        assert "stop_distance_pct" in data
        assert "leverage" in data
        assert "recommended_position_size" in data
        assert "margin_required" in data
        assert "coins_to_buy" in data
        assert "max_loss_at_stop" in data
        
        # Verify calculations
        assert data["account_balance"] == 10000
        assert data["risk_amount_usd"] == 200  # 2% of 10000
        assert data["recommended_position_size"] > 0
        
        print(f"Position Size Calculation:")
        print(f"  Account: ${data['account_balance']:,} | Risk: {data['risk_pct']}% (${data['risk_amount_usd']})")
        print(f"  Entry: ${data['entry_price']:,} | Stop: ${data['stop_loss_price']:,} ({data['stop_distance_pct']:.2f}%)")
        print(f"  Recommended Position: ${data['recommended_position_size']:,.2f}")
        print(f"  Margin Required: ${data['margin_required']:,.2f}")
        print(f"  Coins to Buy: {data['coins_to_buy']:.6f}")
    
    def test_calc_scenarios(self):
        """Test /api/calc/scenarios - PnL scenarios at different price levels"""
        params = {
            "entry": 65000,
            "size": 1000,
            "leverage": 10,
            "direction": "LONG"
        }
        response = requests.get(f"{BASE_URL}/api/calc/scenarios", params=params)
        assert response.status_code == 200
        
        data = response.json()
        # Should return a list of scenarios
        assert isinstance(data, list)
        assert len(data) > 5  # Should have multiple scenarios
        
        # Verify structure of scenarios
        scenario = data[0]
        assert "price_change" in scenario
        assert "exit_price" in scenario
        assert "pnl_usd" in scenario
        assert "pnl_pct" in scenario
        assert "status" in scenario
        
        print(f"PnL Scenarios for LONG @ $65,000 with 10x:")
        for s in data:
            emoji = "✅" if s["status"] == "PROFIT" else "❌" if s["status"] == "LOSS" else "⚪"
            print(f"  {s['price_change']}: ${s['exit_price']:,.0f} -> {emoji} {s['pnl_pct']:+.1f}% (${s['pnl_usd']:+,.0f})")


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING APIs - Autonomous trading stats and opportunities
# ═══════════════════════════════════════════════════════════════════════════════

class TestTradingAPIs:
    """Test autonomous trading endpoints"""
    
    def test_trading_summary(self):
        """Test /api/trading/summary - Autonomous trading stats"""
        response = requests.get(f"{BASE_URL}/api/trading/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert "closed_stats" in data
        assert "open_positions" in data
        assert "total_pnl_pct" in data
        assert "active" in data
        
        stats = data["closed_stats"]
        print(f"Trading Summary:")
        print(f"  Status: {'ACTIVE' if data['active'] else 'PAUSED'}")
        print(f"  Total Trades: {stats.get('total_predictions', 0)}")
        print(f"  Win Rate: {stats.get('win_rate', 0)}%")
        print(f"  Total PnL: {data['total_pnl_pct']:+.2f}%")
        print(f"  Open Positions: {data['open_positions']}")
    
    def test_trading_opportunities(self):
        """Test /api/trading/opportunities - Current market opportunities"""
        response = requests.get(f"{BASE_URL}/api/trading/opportunities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        print(f"Trading Opportunities: {len(data)} found")
        for opp in data[:3]:
            print(f"  {opp.get('symbol')}: {opp.get('signal')} @ {opp.get('confidence', 0)}% confidence")


# ═══════════════════════════════════════════════════════════════════════════════
# MEXC LIVE PRICES
# ═══════════════════════════════════════════════════════════════════════════════

class TestMEXCLive:
    """Test MEXC live price endpoints"""
    
    def test_mexc_live_prices(self):
        """Test /api/mexc/live - Live MEXC orderbook data"""
        response = requests.get(f"{BASE_URL}/api/mexc/live")
        assert response.status_code == 200
        
        data = response.json()
        
        if "error" not in data:
            # Should have at least BTC
            assert len(data) >= 1
            
            # Verify structure
            for coin, coin_data in data.items():
                assert "price" in coin_data
                assert "change" in coin_data
                assert "bid_depth" in coin_data
                assert "ask_depth" in coin_data
                assert "imbalance" in coin_data
                
                print(f"{coin}: {coin_data['price']} ({coin_data['change']}) | Imbalance: {coin_data['imbalance']}")
                break  # Just check first one


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
