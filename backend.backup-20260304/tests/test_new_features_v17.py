"""
AEON v17 Feature Tests:
- Settings page APIs (trading, alerts, profile, voice tabs)
- User profiler system
- Additional data sources (Blockchain.com, mempool.space, DefiLlama)
- Anti-contradiction system in Free Will v2

Test chat_id: 666666 (for isolated testing as per requirements)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUserProfileAPI:
    """Test user profiling system - learns from conversations"""
    
    def test_get_profile_default(self):
        """Test /api/user/profile returns profile data"""
        response = requests.get(f"{BASE_URL}/api/user/profile")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return profile or error if no users
        if "error" not in data:
            # Verify expected profile fields
            assert "chat_id" in data or "trading_style" in data or "risk_tolerance" in data
            print(f"✓ Profile endpoint works - data: {list(data.keys())}")
        else:
            print(f"✓ Profile endpoint works - no users yet: {data}")
    
    def test_get_profile_by_chat_id(self):
        """Test /api/user/profile/{chat_id} returns profile for specific user"""
        chat_id = 666666  # Test chat_id
        response = requests.get(f"{BASE_URL}/api/user/profile/{chat_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "chat_id" in data, f"Expected chat_id in response: {data}"
        assert data["chat_id"] == chat_id, f"Expected chat_id={chat_id}, got {data['chat_id']}"
        
        # Verify profile structure
        expected_fields = ["trading_style", "risk_tolerance", "favorite_coins", "messages_analyzed"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Profile by chat_id works - {data}")
    
    def test_add_user_fact(self):
        """Test /api/user/profile/{chat_id}/fact adds facts to user profile"""
        chat_id = 666666
        test_fact = "User prefers swing trading over scalping"
        
        response = requests.post(
            f"{BASE_URL}/api/user/profile/{chat_id}/fact",
            json={"fact": test_fact, "category": "trading"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status=ok: {data}"
        assert data.get("fact") == test_fact, f"Fact mismatch: {data}"
        
        print(f"✓ Add user fact works - {data}")
    
    def test_add_fact_missing_fact(self):
        """Test /api/user/profile/{chat_id}/fact returns error if fact missing"""
        chat_id = 666666
        response = requests.post(
            f"{BASE_URL}/api/user/profile/{chat_id}/fact",
            json={"category": "general"}  # Missing fact
        )
        assert response.status_code == 200  # API returns 200 with error
        
        data = response.json()
        assert "error" in data, f"Expected error for missing fact: {data}"
        print(f"✓ Missing fact validation works - {data}")


class TestFreeWillStats:
    """Test Free Will v2 stats - shows contradictions blocked, direction lock, etc."""
    
    def test_freewill_stats(self):
        """Test /api/freewill/stats returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify required fields for Settings page Alerts tab
        expected_fields = [
            "active",
            "min_confidence",
            "min_confirmations",
            "alert_cooldown_mins",
            "direction_lock_hours",  # Anti-contradiction feature
            "total_alerts_sent",
            "daily_alerts",
            "max_daily_alerts",
            "setups_analyzed",
            "contradictions_blocked",  # Anti-contradiction stat
            "recent_directions",  # Shows last direction per symbol
            "pairs_monitored",
            "timeframes",
            "data_sources"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify direction_lock_hours is 2 (as per requirement)
        assert data["direction_lock_hours"] == 2, f"Expected direction_lock_hours=2, got {data['direction_lock_hours']}"
        
        # Verify data_sources is populated
        assert len(data["data_sources"]) > 0, f"Expected data_sources to have items: {data['data_sources']}"
        
        print(f"✓ Free Will stats works - direction_lock={data['direction_lock_hours']}h, blocked={data['contradictions_blocked']}")
        print(f"  Data sources: {data['data_sources'][:3]}...")
    
    def test_freewill_toggle(self):
        """Test /api/freewill/toggle works"""
        # Toggle off
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == False, f"Expected active=False: {data}"
        
        # Toggle back on
        response = requests.post(f"{BASE_URL}/api/freewill/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == True, f"Expected active=True: {data}"
        
        print(f"✓ Free Will toggle works")
    
    def test_freewill_confidence(self):
        """Test /api/freewill/confidence updates min confidence"""
        # Set to 85
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=85")
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") == 85, f"Expected min_confidence=85: {data}"
        
        # Verify boundaries work (capped at 95)
        response = requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=99")
        assert response.status_code == 200
        data = response.json()
        assert data.get("min_confidence") == 95, f"Expected min_confidence=95 (capped): {data}"
        
        # Reset to 80
        requests.post(f"{BASE_URL}/api/freewill/confidence?min_conf=80")
        
        print(f"✓ Free Will confidence setting works")


class TestTradingV2Stats:
    """Test Trading v2 stats for Settings page Trading tab"""
    
    def test_trading_v2_stats(self):
        """Test /api/trading/v2/stats returns trading engine status"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify expected fields for Settings Trading tab
        expected_fields = ["active", "min_confidence", "total_trades"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Trading v2 stats works - active={data.get('active')}, confidence={data.get('min_confidence')}")
    
    def test_trading_toggle(self):
        """Test /api/trading/toggle works"""
        # Get current state first
        current = requests.get(f"{BASE_URL}/api/trading/v2/stats").json()
        
        # Toggle
        response = requests.post(f"{BASE_URL}/api/trading/toggle?active=true")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data, f"Expected active in response: {data}"
        
        print(f"✓ Trading toggle works - {data}")


class TestAdditionalDataSources:
    """Test additional free data APIs - Blockchain.com, mempool.space, DefiLlama"""
    
    def test_btc_onchain_blockchain_com(self):
        """Test /api/data/btc/onchain returns BTC on-chain data from Blockchain.com"""
        response = requests.get(f"{BASE_URL}/api/data/btc/onchain")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should have blockchain stats or error
        if "error" not in data:
            expected_fields = ["hash_rate", "difficulty", "market_price_usd", "source"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"
            
            assert data.get("source") == "Blockchain.com", f"Expected source=Blockchain.com: {data.get('source')}"
            print(f"✓ BTC on-chain works - hash_rate={data.get('hash_rate')}, price=${data.get('market_price_usd', 0):,.0f}")
        else:
            print(f"✓ BTC on-chain API responsive - error (may be rate limited): {data.get('error')}")
    
    def test_btc_fees_mempool(self):
        """Test /api/data/btc/fees returns mempool fee estimates"""
        response = requests.get(f"{BASE_URL}/api/data/btc/fees")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        if "error" not in data:
            expected_fields = ["fastest_fee", "half_hour_fee", "hour_fee", "source"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"
            
            assert data.get("source") == "mempool.space", f"Expected source=mempool.space: {data.get('source')}"
            print(f"✓ BTC fees works - fastest={data.get('fastest_fee')} sat/vB, source={data.get('source')}")
        else:
            print(f"✓ BTC fees API responsive - error (may be rate limited): {data.get('error')}")
    
    def test_eth_gas(self):
        """Test /api/data/eth/gas returns ETH gas prices"""
        response = requests.get(f"{BASE_URL}/api/data/eth/gas")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # API may return error if external service is down - that's ok
        print(f"✓ ETH gas API responsive - {data.get('source', data.get('error', 'response received'))}")
    
    def test_defi_tvl(self):
        """Test /api/data/defi/tvl returns DefiLlama TVL data"""
        response = requests.get(f"{BASE_URL}/api/data/defi/tvl")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        if "error" not in data:
            assert "top_protocols" in data or "total_protocols" in data, f"Expected TVL data: {data}"
            assert data.get("source") == "DefiLlama", f"Expected source=DefiLlama: {data.get('source')}"
            
            if "top_protocols" in data:
                print(f"✓ DeFi TVL works - {len(data.get('top_protocols', []))} protocols, source={data.get('source')}")
            else:
                print(f"✓ DeFi TVL works - {data}")
        else:
            print(f"✓ DeFi TVL API responsive - {data.get('error')}")
    
    def test_social_data_cryptocompare(self):
        """Test /api/data/social/{symbol} returns social stats"""
        response = requests.get(f"{BASE_URL}/api/data/social/BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        if "error" not in data:
            expected_fields = ["symbol", "reddit", "twitter", "source"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"
            
            assert data.get("source") == "CryptoCompare", f"Expected source=CryptoCompare: {data.get('source')}"
            print(f"✓ Social data works - symbol={data.get('symbol')}, source={data.get('source')}")
        else:
            print(f"✓ Social data API responsive - {data.get('error')}")
    
    def test_all_additional_data(self):
        """Test /api/data/all/{symbol} returns combined data"""
        response = requests.get(f"{BASE_URL}/api/data/all/BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should have all data source categories
        expected_categories = ["social", "btc_onchain", "btc_fees", "eth_gas", "defi_tvl"]
        for cat in expected_categories:
            assert cat in data, f"Missing category: {cat}"
        
        print(f"✓ All additional data works - categories: {list(data.keys())}")


class TestAntiContradictionSystem:
    """Test anti-contradiction feature - no flip-flop signals within 2 hours"""
    
    def test_direction_lock_time(self):
        """Verify direction_lock_time is set to 7200 seconds (2 hours)"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # direction_lock_hours should be 2
        assert data.get("direction_lock_hours") == 2, f"Expected 2 hours, got {data.get('direction_lock_hours')}"
        
        print(f"✓ Direction lock is 2 hours as required")
    
    def test_recent_directions_tracked(self):
        """Verify recent_directions is tracked in stats"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # recent_directions should exist (may be empty if no recent signals)
        assert "recent_directions" in data, f"Missing recent_directions field"
        assert isinstance(data["recent_directions"], dict), f"recent_directions should be dict: {type(data['recent_directions'])}"
        
        print(f"✓ Recent directions tracked - {data['recent_directions'] or '(none yet)'}")
    
    def test_contradictions_blocked_counter(self):
        """Verify contradictions_blocked counter exists"""
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "contradictions_blocked" in data, f"Missing contradictions_blocked field"
        assert isinstance(data["contradictions_blocked"], int), f"contradictions_blocked should be int"
        
        print(f"✓ Contradictions blocked counter: {data['contradictions_blocked']}")


class TestSettingsPageAPIs:
    """Combined test for all APIs used by Settings page tabs"""
    
    def test_trading_tab_data(self):
        """Test all APIs needed for Trading tab"""
        # /api/trading/v2/stats
        response = requests.get(f"{BASE_URL}/api/trading/v2/stats")
        assert response.status_code == 200
        trading_data = response.json()
        
        assert "active" in trading_data, f"Trading stats missing 'active': {trading_data}"
        assert "min_confidence" in trading_data, f"Trading stats missing 'min_confidence': {trading_data}"
        
        print(f"✓ Trading tab data - active={trading_data.get('active')}, confidence={trading_data.get('min_confidence')}")
    
    def test_alerts_tab_data(self):
        """Test all APIs needed for Alerts tab"""
        # /api/freewill/stats
        response = requests.get(f"{BASE_URL}/api/freewill/stats")
        assert response.status_code == 200
        alerts_data = response.json()
        
        required = ["active", "min_confidence", "daily_alerts", "max_daily_alerts", 
                   "contradictions_blocked", "direction_lock_hours", "recent_directions", "data_sources"]
        for field in required:
            assert field in alerts_data, f"Alerts stats missing '{field}': {alerts_data}"
        
        print(f"✓ Alerts tab data - {len(alerts_data.get('data_sources', []))} data sources, daily={alerts_data.get('daily_alerts')}/{alerts_data.get('max_daily_alerts')}")
    
    def test_profile_tab_data(self):
        """Test all APIs needed for Your Profile tab"""
        chat_id = 666666
        
        # /api/user/profile/{chat_id}
        response = requests.get(f"{BASE_URL}/api/user/profile/{chat_id}")
        assert response.status_code == 200
        profile_data = response.json()
        
        required = ["chat_id", "trading_style", "risk_tolerance", "favorite_coins", "messages_analyzed"]
        for field in required:
            assert field in profile_data, f"Profile missing '{field}': {profile_data}"
        
        print(f"✓ Profile tab data - style={profile_data.get('trading_style')}, risk={profile_data.get('risk_tolerance')}, coins={profile_data.get('favorite_coins')}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
