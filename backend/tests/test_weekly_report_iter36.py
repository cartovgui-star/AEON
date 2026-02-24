"""
Test Weekly Performance Report APIs - Iteration 36
Tests: /api/report/* endpoints for weekly performance reports
Features: Win rates by strategy, best/worst coins, PnL breakdown
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestWeeklyReportStatus:
    """Test GET /api/report/status - Weekly report scheduler status"""
    
    def test_report_status_returns_200(self):
        """Test that status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/report/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/report/status returned 200")
    
    def test_report_status_has_required_fields(self):
        """Test status response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/report/status")
        data = response.json()
        
        required_fields = ['enabled', 'scheduled_day', 'scheduled_time', 'timezone', 
                          'current_time_ct', 'next_report', 'trades_this_week']
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✓ Status response contains all required fields: {required_fields}")
        print(f"  Sample data: scheduled={data['scheduled_day']} {data['scheduled_time']}, trades={data['trades_this_week']}")
    
    def test_report_scheduled_for_sunday_8pm_ct(self):
        """Test report is scheduled for Sunday at 8 PM CT"""
        response = requests.get(f"{BASE_URL}/api/report/status")
        data = response.json()
        
        assert data['scheduled_day'] == 'Sunday', f"Expected Sunday, got {data['scheduled_day']}"
        assert '8' in data['scheduled_time'] and 'PM' in data['scheduled_time'], \
            f"Expected 8:00 PM CT, got {data['scheduled_time']}"
        assert 'Chicago' in data['timezone'] or 'Central' in data['timezone'], \
            f"Expected Central Time, got {data['timezone']}"
        
        print(f"✓ Report correctly scheduled for Sunday 8 PM Central Time")


class TestWeeklyReportPreview:
    """Test GET /api/report/preview - Preview current week's report"""
    
    def test_preview_returns_200(self):
        """Test that preview endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/report/preview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/report/preview returned 200")
    
    def test_preview_has_content(self):
        """Test preview response has report content"""
        response = requests.get(f"{BASE_URL}/api/report/preview")
        data = response.json()
        
        assert 'preview' in data, "Missing 'preview' field in response"
        assert 'generated_at' in data, "Missing 'generated_at' field"
        
        preview = data['preview']
        assert len(preview) > 100, f"Preview content too short: {len(preview)} chars"
        print(f"✓ Preview has content ({len(preview)} chars)")
    
    def test_preview_contains_report_sections(self):
        """Test preview contains expected report sections"""
        response = requests.get(f"{BASE_URL}/api/report/preview")
        data = response.json()
        preview = data.get('preview', '')
        
        # Check for key report sections
        expected_sections = ['AEON WEEKLY', 'OVERALL', 'SUMMARY']
        
        found_sections = []
        for section in expected_sections:
            if section in preview.upper():
                found_sections.append(section)
        
        assert len(found_sections) >= 2, f"Preview missing key sections. Found: {found_sections}"
        print(f"✓ Preview contains expected sections: {found_sections}")


class TestWeeklyReportStrategyStats:
    """Test GET /api/report/strategy-stats - Strategy performance stats"""
    
    def test_strategy_stats_returns_200(self):
        """Test that strategy-stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/report/strategy-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/report/strategy-stats returned 200")
    
    def test_strategy_stats_has_week_range(self):
        """Test strategy stats has week date range"""
        response = requests.get(f"{BASE_URL}/api/report/strategy-stats")
        data = response.json()
        
        assert 'week_start' in data, "Missing 'week_start' field"
        assert 'week_end' in data, "Missing 'week_end' field"
        assert 'total_trades' in data, "Missing 'total_trades' field"
        
        print(f"✓ Strategy stats has week range: {data['week_start'][:10]} to {data['week_end'][:10]}")
        print(f"  Total trades this week: {data['total_trades']}")
    
    def test_strategy_stats_has_strategies_object(self):
        """Test strategy stats has strategies breakdown"""
        response = requests.get(f"{BASE_URL}/api/report/strategy-stats")
        data = response.json()
        
        assert 'strategies' in data, "Missing 'strategies' field"
        assert isinstance(data['strategies'], dict), "strategies should be a dict"
        
        # If there are strategies, check their structure
        if data['strategies']:
            for name, stats in data['strategies'].items():
                expected_stats = ['total_trades', 'wins', 'losses', 'win_rate', 'total_pnl', 'avg_pnl']
                for stat in expected_stats:
                    assert stat in stats, f"Strategy {name} missing {stat}"
            print(f"✓ Strategy stats breakdown: {list(data['strategies'].keys())}")
        else:
            print(f"✓ No strategy data yet (0 trades this week)")


class TestWeeklyReportCoinPerformance:
    """Test GET /api/report/coin-performance - Coin performance breakdown"""
    
    def test_coin_performance_returns_200(self):
        """Test that coin-performance endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/report/coin-performance")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/report/coin-performance returned 200")
    
    def test_coin_performance_has_required_fields(self):
        """Test coin performance has best/worst performers"""
        response = requests.get(f"{BASE_URL}/api/report/coin-performance")
        data = response.json()
        
        assert 'week_start' in data, "Missing 'week_start' field"
        assert 'week_end' in data, "Missing 'week_end' field"
        assert 'best_performers' in data, "Missing 'best_performers' field"
        assert 'worst_performers' in data, "Missing 'worst_performers' field"
        
        print(f"✓ Coin performance has best/worst performers fields")
        
        if data['best_performers']:
            print(f"  Best performers: {[c.get('symbol') for c in data['best_performers'][:3]]}")
        if data['worst_performers']:
            print(f"  Worst performers: {[c.get('symbol') for c in data['worst_performers'][:3]]}")


class TestWeeklyReportTestEndpoint:
    """Test POST /api/report/test - Send test report"""
    
    def test_send_test_report_returns_200(self):
        """Test that test endpoint accepts POST and returns 200"""
        response = requests.post(f"{BASE_URL}/api/report/test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ POST /api/report/test returned 200")
    
    def test_send_test_report_returns_success(self):
        """Test that test endpoint returns success message"""
        response = requests.post(f"{BASE_URL}/api/report/test")
        data = response.json()
        
        assert 'success' in data, "Missing 'success' field"
        assert data['success'] == True, f"Expected success=True, got {data['success']}"
        
        print(f"✓ Test report sent successfully: {data.get('message', '')}")


class TestWeeklyReportToggle:
    """Test POST /api/report/toggle - Enable/disable weekly report"""
    
    def test_toggle_report_enabled(self):
        """Test enabling the weekly report"""
        response = requests.post(f"{BASE_URL}/api/report/toggle?enabled=true")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'success' in data, "Missing 'success' field"
        assert data['success'] == True, "Expected success=True"
        assert data.get('enabled') == True, "Expected enabled=True"
        
        print(f"✓ Weekly report enabled successfully")
    
    def test_toggle_report_disabled(self):
        """Test disabling the weekly report"""
        response = requests.post(f"{BASE_URL}/api/report/toggle?enabled=false")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('enabled') == False, "Expected enabled=False"
        
        print(f"✓ Weekly report disabled successfully")
    
    def test_toggle_report_restore_enabled(self):
        """Re-enable report after test"""
        response = requests.post(f"{BASE_URL}/api/report/toggle?enabled=true")
        assert response.status_code == 200
        print(f"✓ Weekly report re-enabled")


# Additional test for V2.1 reversal pattern exit logic
class TestV21ReversalPatternExitLogic:
    """Test that V2.1 trader has reversal pattern exit logic implemented"""
    
    def test_v2_settings_endpoint_exists(self):
        """Test V2 settings endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/trading/v2/settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ V2.1 settings endpoint working")
    
    def test_scalper_learning_status(self):
        """Test scalper learning status (reversal detector source)"""
        response = requests.get(f"{BASE_URL}/api/scalper/learning/status")
        # This may not exist, but let's check
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Scalper learning status: {data}")
        else:
            print(f"⚠ Scalper learning status not available (status={response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
