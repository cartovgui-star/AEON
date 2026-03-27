"""
ITERATION 44: Unified Engine System Tests
Tests for the /api/engines/* routes - 7-engine management system
- Engine Status API
- Signal Submission & Validation
- Signal Rejection (low confidence, insufficient confluences)
- Trade Tracking
- Global Stats
- Validation Test API
- Per-engine validation rules (Elite 90%/5, Dual 82%/4, Day Trader 70%/2)
"""

import pytest
import requests
import os
import uuid
from typing import Dict, Any

# Get BASE_URL from environment - MUST use external URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# All 7 engine names
ENGINE_NAMES = [
    "autonomous_trader_v2",
    "free_will_v2", 
    "dual_engine",
    "yolo_engine",
    "vwap_scalper",
    "elite_strategy",
    "day_trader"
]

# Engine-specific validation rules
ENGINE_RULES = {
    "elite_strategy": {"min_confidence": 90.0, "min_confluences": 5},
    "dual_engine": {"min_confidence": 82.0, "min_confluences": 4},
    "day_trader": {"min_confidence": 70.0, "min_confluences": 2},
    "autonomous_trader_v2": {"min_confidence": 80.0, "min_confluences": 3},
    "free_will_v2": {"min_confidence": 75.0, "min_confluences": 2},
    "yolo_engine": {"min_confidence": 75.0, "min_confluences": 2},
    "vwap_scalper": {"min_confidence": 70.0, "min_confluences": 3}
}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def create_valid_signal(engine: str, symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """Create a valid signal that should pass validation for a given engine"""
    rules = ENGINE_RULES.get(engine, ENGINE_RULES["autonomous_trader_v2"])
    return {
        "symbol": symbol,
        "direction": "long",
        "entry_price": 100000.0,
        "position_size": 500.0,
        "leverage": 10.0,
        "stop_loss": 98000.0,  # 2% stop
        "take_profit": 106000.0,  # 6% target = 3:1 R:R
        "confidence": rules["min_confidence"] + 2,  # Above threshold
        "confluences": rules["min_confluences"] + 1,  # Above threshold
        "reason": "TEST_signal_valid",
        "engine": engine
    }


def create_low_confidence_signal(engine: str) -> Dict[str, Any]:
    """Create a signal with LOW confidence - should be rejected"""
    rules = ENGINE_RULES.get(engine, ENGINE_RULES["autonomous_trader_v2"])
    return {
        "symbol": "ETHUSDT",
        "direction": "long",
        "entry_price": 3500.0,
        "position_size": 500.0,
        "leverage": 10.0,
        "stop_loss": 3400.0,
        "take_profit": 3700.0,
        "confidence": rules["min_confidence"] - 5,  # BELOW threshold
        "confluences": rules["min_confluences"] + 1,  # Above threshold
        "reason": "TEST_low_confidence",
        "engine": engine
    }


def create_low_confluence_signal(engine: str) -> Dict[str, Any]:
    """Create a signal with LOW confluences - should be rejected"""
    rules = ENGINE_RULES.get(engine, ENGINE_RULES["autonomous_trader_v2"])
    return {
        "symbol": "SOLUSDT",
        "direction": "short",
        "entry_price": 200.0,
        "position_size": 500.0,
        "leverage": 10.0,
        "stop_loss": 210.0,
        "take_profit": 180.0,
        "confidence": rules["min_confidence"] + 2,  # Above threshold
        "confluences": rules["min_confluences"] - 1,  # BELOW threshold
        "reason": "TEST_low_confluences",
        "engine": engine
    }


class TestEngineStatusAPI:
    """Tests for /api/engines/status - should return all 7 engines"""
    
    def test_get_all_engines_status(self, api_client):
        """GET /api/engines/status should return all 7 engines"""
        response = api_client.get(f"{BASE_URL}/api/engines/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "engines" in data, "Response should have 'engines' key"
        assert "timestamp" in data, "Response should have 'timestamp' key"
        
        engines = data["engines"]
        # Verify all 7 engines are present
        for engine_name in ENGINE_NAMES:
            assert engine_name in engines, f"Engine {engine_name} not found in status"
            engine_data = engines[engine_name]
            assert "engine" in engine_data
            assert "config" in engine_data
            assert "stats" in engine_data
        
        print(f"✅ All 7 engines present: {list(engines.keys())}")
    
    def test_get_individual_engine_status(self, api_client):
        """GET /api/engines/status/{engine_name} should return engine details"""
        engine = "elite_strategy"
        response = api_client.get(f"{BASE_URL}/api/engines/status/{engine}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["engine"] == engine
        assert "config" in data
        assert "stats" in data
        assert data["config"]["min_confidence"] == 90.0
        assert data["config"]["min_confluences"] == 5
        
        print(f"✅ Elite Strategy config verified: {data['config']}")
    
    def test_invalid_engine_returns_error(self, api_client):
        """GET /api/engines/status/invalid_engine should return 400"""
        response = api_client.get(f"{BASE_URL}/api/engines/status/invalid_engine")
        assert response.status_code == 400


class TestSignalSubmissionAPI:
    """Tests for /api/engines/signal - signal submission and validation"""
    
    def test_submit_valid_signal_executes(self, api_client):
        """POST /api/engines/signal with valid signal should execute"""
        signal = create_valid_signal("autonomous_trader_v2", f"TEST_{uuid.uuid4().hex[:8]}USDT")
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "success", f"Expected success, got {data.get('status')}"
        assert data["result"]["action"] == "EXECUTE", f"Expected EXECUTE, got {data['result'].get('action')}"
        
        # Verify execution plan is present
        result = data["result"]
        assert "execution_plan" in result
        assert "trade" in result
        
        print(f"✅ Signal executed: {result['trade']['symbol']} {result['trade']['direction']}")
        return result.get("trade", {}).get("trade_id")
    
    def test_submit_low_confidence_rejected(self, api_client):
        """POST /api/engines/signal with low confidence should be rejected"""
        signal = create_low_confidence_signal("autonomous_trader_v2")
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        
        assert response.status_code == 200  # API returns 200 with rejection status
        
        data = response.json()
        assert data["status"] == "rejected", f"Expected rejected, got {data.get('status')}"
        assert data["result"]["action"] == "REJECT"
        
        # Verify issues list contains confidence reason
        issues = data["result"].get("issues", [])
        confidence_issues = [i for i in issues if "confidence" in i.lower()]
        assert len(confidence_issues) > 0, f"Expected confidence rejection issue, got: {issues}"
        
        print(f"✅ Low confidence signal correctly rejected: {issues}")
    
    def test_submit_low_confluences_rejected(self, api_client):
        """POST /api/engines/signal with insufficient confluences should be rejected"""
        signal = create_low_confluence_signal("elite_strategy")  # Elite needs 5 confluences
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "rejected"
        
        issues = data["result"].get("issues", [])
        confluence_issues = [i for i in issues if "confluence" in i.lower()]
        assert len(confluence_issues) > 0, f"Expected confluence rejection issue, got: {issues}"
        
        print(f"✅ Low confluences signal correctly rejected: {issues}")


class TestEngineSpecificValidation:
    """Tests for specific engine validation thresholds"""
    
    def test_elite_strategy_90_confidence_5_confluences(self, api_client):
        """Elite Strategy requires 90% confidence and 5 confluences"""
        # Test signal with 89% confidence - should fail
        signal = {
            "symbol": "TEST_ELITE_BTC",
            "direction": "long",
            "entry_price": 100000.0,
            "position_size": 500.0,
            "leverage": 10.0,
            "stop_loss": 98000.0,
            "take_profit": 106000.0,
            "confidence": 89.0,  # Below 90%
            "confluences": 5,    # Meets requirement
            "reason": "TEST_elite_89_conf",
            "engine": "elite_strategy"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        assert any("confidence" in i.lower() for i in data["result"]["issues"])
        print("✅ Elite Strategy correctly rejects 89% confidence")
        
        # Test signal with 91% confidence, 4 confluences - should fail
        signal["confidence"] = 91.0
        signal["confluences"] = 4  # Below 5
        signal["symbol"] = "TEST_ELITE_BTC2"
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        assert any("confluence" in i.lower() for i in data["result"]["issues"])
        print("✅ Elite Strategy correctly rejects 4 confluences")
    
    def test_dual_engine_82_confidence_4_confluences(self, api_client):
        """Dual Engine requires 82% confidence and 4 confluences"""
        # Test signal with 81% confidence - should fail
        signal = {
            "symbol": "TEST_DUAL_ETH",
            "direction": "short",
            "entry_price": 3500.0,
            "position_size": 500.0,
            "leverage": 15.0,
            "stop_loss": 3600.0,
            "take_profit": 3200.0,
            "confidence": 81.0,  # Below 82%
            "confluences": 4,    # Meets requirement
            "reason": "TEST_dual_81_conf",
            "engine": "dual_engine"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        print("✅ Dual Engine correctly rejects 81% confidence")
        
        # Test signal with 83% confidence, 3 confluences - should fail
        signal["confidence"] = 83.0
        signal["confluences"] = 3  # Below 4
        signal["symbol"] = "TEST_DUAL_ETH2"
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        assert any("confluence" in i.lower() for i in data["result"]["issues"])
        print("✅ Dual Engine correctly rejects 3 confluences")
    
    def test_day_trader_70_confidence_2_confluences(self, api_client):
        """Day Trader requires 70% confidence and 2 confluences"""
        # Test signal with 69% confidence - should fail
        signal = {
            "symbol": "TEST_DAY_SOL",
            "direction": "long",
            "entry_price": 200.0,
            "position_size": 500.0,
            "leverage": 20.0,
            "stop_loss": 190.0,
            "take_profit": 230.0,
            "confidence": 69.0,  # Below 70%
            "confluences": 2,    # Meets requirement
            "reason": "TEST_day_69_conf",
            "engine": "day_trader"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        print("✅ Day Trader correctly rejects 69% confidence")
        
        # Test signal with 71% confidence, 2 confluences - should pass
        signal["confidence"] = 71.0
        signal["confluences"] = 2
        signal["symbol"] = f"TEST_DAY_{uuid.uuid4().hex[:6]}"
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "success"
        assert data["result"]["action"] == "EXECUTE"
        print("✅ Day Trader correctly accepts 71%/2 signal")


class TestTradeTrackingAPI:
    """Tests for /api/engines/trades/open - open trade tracking"""
    
    def test_get_all_open_trades(self, api_client):
        """GET /api/engines/trades/open should return open trades list"""
        response = api_client.get(f"{BASE_URL}/api/engines/trades/open")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "trades" in data
        assert isinstance(data["trades"], list)
        
        print(f"✅ Open trades endpoint working. Total: {data['total']}")
    
    def test_open_trades_after_signal(self, api_client):
        """Verify trade appears in open trades after signal execution"""
        # Submit a valid signal
        symbol = f"TEST_TRACK_{uuid.uuid4().hex[:8]}"
        signal = create_valid_signal("free_will_v2", symbol)
        
        submit_response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        assert submit_response.status_code == 200
        
        submit_data = submit_response.json()
        if submit_data["status"] == "success":
            # Check open trades
            trades_response = api_client.get(f"{BASE_URL}/api/engines/trades/open")
            trades_data = trades_response.json()
            
            # Verify our trade is in the list
            trade_symbols = [t.get("symbol") for t in trades_data["trades"]]
            assert symbol in trade_symbols, f"Trade {symbol} not found in open trades"
            
            print(f"✅ Trade {symbol} correctly appears in open trades")


class TestEngineStatsAPI:
    """Tests for /api/engines/stats/global - statistics endpoint"""
    
    def test_get_global_stats(self, api_client):
        """GET /api/engines/stats/global should return trade counts"""
        response = api_client.get(f"{BASE_URL}/api/engines/stats/global")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "global" in data
        assert "by_engine" in data
        
        global_stats = data["global"]
        assert "total_trades" in global_stats
        assert "total_open" in global_stats
        assert "total_blocked" in global_stats
        
        print(f"✅ Global stats: trades={global_stats['total_trades']}, open={global_stats['total_open']}, blocked={global_stats['total_blocked']}")
    
    def test_stats_per_engine(self, api_client):
        """GET /api/engines/stats/{engine} should return engine-specific stats"""
        for engine in ["elite_strategy", "day_trader", "dual_engine"]:
            response = api_client.get(f"{BASE_URL}/api/engines/stats/{engine}")
            
            assert response.status_code == 200, f"Failed for {engine}"
            
            data = response.json()
            assert "engine" in data
            assert "total_trades" in data
            assert "blocked_trades" in data
            
            print(f"✅ Stats for {engine}: total={data['total_trades']}, blocked={data['blocked_trades']}")


class TestValidationTestAPI:
    """Tests for /api/engines/validation/test - explains why signals would fail"""
    
    def test_validation_test_endpoint(self, api_client):
        """POST /api/engines/validation/test should explain validation results"""
        signal = {
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry_price": 100000.0,
            "position_size": 500.0,
            "leverage": 10.0,
            "stop_loss": 99000.0,
            "take_profit": 103000.0,
            "confidence": 85.0,
            "confluences": 3,
            "reason": "TEST_validation_check",
            "engine": "elite_strategy"  # 85% < 90% required
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/validation/test", json=signal)
        
        assert response.status_code == 200
        
        data = response.json()
        assert "would_execute" in data
        assert "issues" in data
        assert "analysis" in data
        
        analysis = data["analysis"]
        assert "confidence_required" in analysis
        assert "confidence_provided" in analysis
        assert "confluences_required" in analysis
        assert "confluences_provided" in analysis
        assert "rr_ratio" in analysis
        
        # Elite requires 90%, we sent 85% - should not execute
        assert data["would_execute"] == False
        assert analysis["confidence_required"] == 90.0
        assert analysis["confidence_provided"] == 85.0
        
        print(f"✅ Validation test explains why signal fails: {data['issues']}")
    
    def test_validation_explains_rr_ratio(self, api_client):
        """Validation test should explain R:R ratio issues"""
        signal = {
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry_price": 100000.0,
            "position_size": 500.0,
            "leverage": 10.0,
            "stop_loss": 98000.0,  # 2% risk
            "take_profit": 102000.0,  # 2% reward = 1:1 R:R (below 1.5:1 minimum)
            "confidence": 85.0,
            "confluences": 4,
            "reason": "TEST_bad_rr",
            "engine": "day_trader"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/validation/test", json=signal)
        data = response.json()
        
        assert data["would_execute"] == False
        
        # Should have R:R issue
        rr_issues = [i for i in data["issues"] if "R:R" in i or "ratio" in i.lower()]
        assert len(rr_issues) > 0, f"Expected R:R rejection, got: {data['issues']}"
        
        print(f"✅ Validation explains R:R issue: {rr_issues}")


class TestEngineConfigAPI:
    """Tests for /api/engines/config - engine configurations"""
    
    def test_get_all_configs(self, api_client):
        """GET /api/engines/config should return all engine configs"""
        response = api_client.get(f"{BASE_URL}/api/engines/config")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # All 7 engines should be present
        for engine in ENGINE_NAMES:
            assert engine in data, f"Missing config for {engine}"
            config = data[engine]
            assert "min_confidence" in config
            assert "min_confluences" in config
            assert "max_leverage" in config
        
        # Verify specific values
        assert data["elite_strategy"]["min_confidence"] == 90.0
        assert data["elite_strategy"]["min_confluences"] == 5
        assert data["dual_engine"]["min_confidence"] == 82.0
        assert data["dual_engine"]["min_confluences"] == 4
        assert data["day_trader"]["min_confidence"] == 70.0
        assert data["day_trader"]["min_confluences"] == 2
        
        print("✅ All engine configs verified")
    
    def test_get_individual_config(self, api_client):
        """GET /api/engines/config/{engine} should return engine config"""
        response = api_client.get(f"{BASE_URL}/api/engines/config/yolo_engine")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["engine"] == "yolo_engine"
        assert data["max_leverage"] == 125  # YOLO has highest leverage
        assert data["risk_profile"] == "aggressive"
        
        print(f"✅ YOLO engine config: leverage={data['max_leverage']}, risk={data['risk_profile']}")


class TestBlacklistCooldownAPI:
    """Tests for /api/engines/blacklist and /api/engines/cooldown"""
    
    def test_get_blacklist(self, api_client):
        """GET /api/engines/blacklist/{engine} should return blacklisted symbols"""
        response = api_client.get(f"{BASE_URL}/api/engines/blacklist/dual_engine")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "engine" in data
        assert "blacklisted" in data
        assert isinstance(data["blacklisted"], list)
        
        print(f"✅ Blacklist for dual_engine: {data['blacklisted']}")
    
    def test_add_to_blacklist(self, api_client):
        """POST /api/engines/blacklist/{engine} should add symbol to blacklist"""
        test_symbol = f"TEST_BL_{uuid.uuid4().hex[:6]}"
        
        response = api_client.post(
            f"{BASE_URL}/api/engines/blacklist/vwap_scalper",
            json={"symbol": test_symbol, "hours": 24}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        
        # Verify it's in the blacklist
        get_response = api_client.get(f"{BASE_URL}/api/engines/blacklist/vwap_scalper")
        blacklist_data = get_response.json()
        
        assert test_symbol in blacklist_data["blacklisted"]
        
        # Clean up - remove from blacklist
        api_client.delete(f"{BASE_URL}/api/engines/blacklist/vwap_scalper/{test_symbol}")
        
        print(f"✅ Successfully added and verified {test_symbol} in blacklist")
    
    def test_get_cooldown(self, api_client):
        """GET /api/engines/cooldown/{engine} should return symbols in cooldown"""
        response = api_client.get(f"{BASE_URL}/api/engines/cooldown/autonomous_trader_v2")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "engine" in data
        assert "in_cooldown" in data
        
        print(f"✅ Cooldown for autonomous_trader_v2: {data['in_cooldown']}")


class TestSignalEdgeCases:
    """Test edge cases for signal validation"""
    
    def test_invalid_direction_rejected(self, api_client):
        """Signal with invalid direction should be rejected"""
        signal = {
            "symbol": "BTCUSDT",
            "direction": "sideways",  # Invalid
            "entry_price": 100000.0,
            "position_size": 500.0,
            "leverage": 10.0,
            "stop_loss": 98000.0,
            "take_profit": 106000.0,
            "confidence": 85.0,
            "confluences": 4,
            "engine": "day_trader"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        assert any("direction" in i.lower() for i in data["result"]["issues"])
        print("✅ Invalid direction correctly rejected")
    
    def test_no_stop_loss_rejected(self, api_client):
        """Signal without stop loss should be rejected"""
        signal = {
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry_price": 100000.0,
            "position_size": 500.0,
            "leverage": 10.0,
            "stop_loss": 0,  # No stop loss
            "take_profit": 106000.0,
            "confidence": 85.0,
            "confluences": 4,
            "engine": "day_trader"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        assert any("stop" in i.lower() for i in data["result"]["issues"])
        print("✅ No stop loss correctly rejected")
    
    def test_position_size_below_minimum_rejected(self, api_client):
        """Signal with position size < $100 should be rejected"""
        signal = {
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry_price": 100000.0,
            "position_size": 50.0,  # Below $100 minimum
            "leverage": 10.0,
            "stop_loss": 98000.0,
            "take_profit": 106000.0,
            "confidence": 85.0,
            "confluences": 4,
            "engine": "day_trader"
        }
        
        response = api_client.post(f"{BASE_URL}/api/engines/signal", json=signal)
        data = response.json()
        
        assert data["status"] == "rejected"
        assert any("$100" in i or "minimum" in i.lower() for i in data["result"]["issues"])
        print("✅ Position size below minimum correctly rejected")


class TestValidationStats:
    """Tests for /api/engines/validation/stats"""
    
    def test_get_validation_stats(self, api_client):
        """GET /api/engines/validation/stats should return validation statistics"""
        response = api_client.get(f"{BASE_URL}/api/engines/validation/stats")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "total_validations" in data
        assert "total_blocked" in data
        assert "blocking_rate" in data
        
        print(f"✅ Validation stats: total={data['total_validations']}, blocked={data['total_blocked']}, rate={data['blocking_rate']}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
