"""
Morning Briefing System Tests - Iteration 35
Tests all briefing API endpoints for the daily 6 AM CT market overview
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBriefingStatus:
    """Test briefing status endpoint"""
    
    def test_get_briefing_status(self):
        """GET /api/briefing/status - Returns scheduler status"""
        response = requests.get(f"{BASE_URL}/api/briefing/status")
        assert response.status_code == 200
        
        data = response.json()
        # Verify required fields
        assert "enabled" in data
        assert "timezone" in data
        assert "scheduled_time" in data
        assert "current_time_ct" in data
        assert "next_briefing" in data
        assert "active_users" in data
        
        # Verify data types and values
        assert isinstance(data["enabled"], bool)
        assert data["timezone"] == "America/Chicago (Central Time)"
        assert data["scheduled_time"] == "6:00 AM CT"
        assert isinstance(data["active_users"], int)
        assert data["active_users"] >= 0
        
        print(f"✅ Status: enabled={data['enabled']}, next briefing={data['next_briefing']}, active_users={data['active_users']}")


class TestBriefingPreview:
    """Test briefing preview endpoint"""
    
    def test_get_briefing_preview(self):
        """GET /api/briefing/preview - Returns preview of today's briefing"""
        response = requests.get(f"{BASE_URL}/api/briefing/preview")
        assert response.status_code == 200
        
        data = response.json()
        # Verify required fields
        assert "preview" in data
        assert "length" in data
        assert "generated_at" in data
        
        preview = data["preview"]
        # Verify preview content structure
        assert "AEON MORNING BRIEFING" in preview
        assert "MARKET STRUCTURE" in preview
        assert "FEAR & GREED INDEX" in preview
        assert "BTC:" in preview
        assert "ETH:" in preview
        
        # Verify length
        assert data["length"] > 500  # Should have substantial content
        
        print(f"✅ Preview generated: {data['length']} chars at {data['generated_at']}")


class TestBriefingMovers:
    """Test overnight movers endpoint"""
    
    def test_get_overnight_movers(self):
        """GET /api/briefing/movers - Returns overnight price movers"""
        response = requests.get(f"{BASE_URL}/api/briefing/movers")
        assert response.status_code == 200
        
        data = response.json()
        # Verify required fields
        assert "gainers" in data
        assert "losers" in data
        assert "high_volume" in data
        
        # Verify data structure
        assert isinstance(data["gainers"], list)
        assert isinstance(data["losers"], list)
        assert isinstance(data["high_volume"], list)
        
        # If there are movers, verify their structure
        for mover_list in [data["gainers"], data["losers"], data["high_volume"]]:
            for mover in mover_list:
                assert "symbol" in mover
                assert "price" in mover
                assert "change_24h" in mover
                assert "volume_24h" in mover
        
        total_movers = len(data["gainers"]) + len(data["losers"])
        print(f"✅ Movers: {len(data['gainers'])} gainers, {len(data['losers'])} losers, {len(data['high_volume'])} high volume")


class TestBriefingSetups:
    """Test setups to watch endpoint"""
    
    def test_get_setups_to_watch(self):
        """GET /api/briefing/setups - Returns potential setups"""
        response = requests.get(f"{BASE_URL}/api/briefing/setups")
        assert response.status_code == 200
        
        data = response.json()
        # Verify required fields
        assert "setups" in data
        assert "count" in data
        
        setups = data["setups"]
        assert isinstance(setups, list)
        assert data["count"] == len(setups)
        
        # If there are setups, verify their structure
        for setup in setups:
            assert "symbol" in setup
            assert "setup" in setup  # Setup type like "OVERSOLD BOUNCE"
            assert "direction" in setup  # LONG/SHORT/WAIT
            assert "reason" in setup
            assert "price" in setup
            assert "rsi" in setup
            assert setup["direction"] in ["LONG", "SHORT", "WAIT"]
        
        print(f"✅ Setups: {data['count']} setups identified")


class TestBriefingToggle:
    """Test briefing toggle endpoint"""
    
    def test_toggle_briefing_on(self):
        """POST /api/briefing/toggle?enabled=true - Enable briefing"""
        response = requests.post(f"{BASE_URL}/api/briefing/toggle?enabled=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["enabled"] == True
        print("✅ Briefing enabled successfully")
    
    def test_toggle_briefing_off(self):
        """POST /api/briefing/toggle?enabled=false - Disable briefing"""
        response = requests.post(f"{BASE_URL}/api/briefing/toggle?enabled=false")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["enabled"] == False
        print("✅ Briefing disabled successfully")
    
    def test_toggle_briefing_restore(self):
        """Re-enable briefing after test"""
        response = requests.post(f"{BASE_URL}/api/briefing/toggle?enabled=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["enabled"] == True
        print("✅ Briefing restored to enabled")


class TestBriefingTest:
    """Test send test briefing endpoint"""
    
    def test_send_test_briefing(self):
        """POST /api/briefing/test - Triggers test briefing send"""
        response = requests.post(f"{BASE_URL}/api/briefing/test")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "message" in data
        assert "test" in data["message"].lower() or "briefing" in data["message"].lower()
        print(f"✅ Test briefing triggered: {data['message']}")


class TestBriefingIntegration:
    """Integration tests for briefing system"""
    
    def test_briefing_workflow(self):
        """Test complete briefing workflow: status -> movers -> setups -> preview"""
        # 1. Check status
        status_res = requests.get(f"{BASE_URL}/api/briefing/status")
        assert status_res.status_code == 200
        status = status_res.json()
        
        # 2. Get movers
        movers_res = requests.get(f"{BASE_URL}/api/briefing/movers")
        assert movers_res.status_code == 200
        movers = movers_res.json()
        
        # 3. Get setups
        setups_res = requests.get(f"{BASE_URL}/api/briefing/setups")
        assert setups_res.status_code == 200
        setups = setups_res.json()
        
        # 4. Get preview (combines all data)
        preview_res = requests.get(f"{BASE_URL}/api/briefing/preview")
        assert preview_res.status_code == 200
        preview = preview_res.json()
        
        # Verify preview contains data from movers and setups
        preview_text = preview["preview"]
        
        # Should contain market structure
        assert "MARKET STRUCTURE" in preview_text
        assert "Overall Bias:" in preview_text
        
        # Should contain fear & greed
        assert "FEAR & GREED" in preview_text
        
        # If there are movers, they should be in preview
        if movers["losers"] or movers["gainers"]:
            assert "OVERNIGHT MOVERS" in preview_text or "MOVERS" in preview_text
        
        # If there are setups, they should be in preview  
        if setups["count"] > 0:
            assert "SETUPS" in preview_text or "WATCH" in preview_text
        
        print(f"✅ Integration test passed: status active, {len(movers['losers'])+len(movers['gainers'])} movers, {setups['count']} setups, preview {preview['length']} chars")
    
    def test_timezone_is_central(self):
        """Verify briefing uses Central Time (Austin, TX)"""
        response = requests.get(f"{BASE_URL}/api/briefing/status")
        assert response.status_code == 200
        
        data = response.json()
        # Must use America/Chicago for Central Time
        assert "America/Chicago" in data["timezone"]
        assert "Central" in data["timezone"]
        
        # Scheduled time should be 6 AM CT
        assert data["scheduled_time"] == "6:00 AM CT"
        
        print(f"✅ Timezone verified: {data['timezone']} at {data['scheduled_time']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
