"""
Test Suite for 24/7 Continuous Learning Engine - Iteration 37
Tests all API endpoints and verifies learning engine functionality
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLearningStatus:
    """Tests for GET /api/learning/status endpoint"""
    
    def test_learning_status_returns_200(self):
        """Learning status endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/status returns 200")
    
    def test_learning_status_has_required_fields(self):
        """Learning status should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/status")
        data = response.json()
        
        # Check required fields
        assert "active" in data, "Missing 'active' field"
        assert "knowledge_stats" in data, "Missing 'knowledge_stats' field"
        assert "last_cycles" in data, "Missing 'last_cycles' field"
        assert "daily_insights_count" in data, "Missing 'daily_insights_count' field"
        assert "current_time_ct" in data, "Missing 'current_time_ct' field"
        assert "next_daily_summary" in data, "Missing 'next_daily_summary' field"
        
        print(f"✓ Learning status has all required fields")
    
    def test_learning_status_knowledge_stats_structure(self):
        """Knowledge stats should have the right structure"""
        response = requests.get(f"{BASE_URL}/api/learning/status")
        data = response.json()
        
        knowledge_stats = data.get("knowledge_stats", {})
        assert "patterns_learned" in knowledge_stats, "Missing 'patterns_learned'"
        assert "coins_analyzed" in knowledge_stats, "Missing 'coins_analyzed'"
        assert "sessions_tracked" in knowledge_stats, "Missing 'sessions_tracked'"
        assert "optimizations_run" in knowledge_stats, "Missing 'optimizations_run'"
        
        # All values should be non-negative integers
        assert isinstance(knowledge_stats["patterns_learned"], int)
        assert isinstance(knowledge_stats["coins_analyzed"], int)
        assert isinstance(knowledge_stats["sessions_tracked"], int)
        assert isinstance(knowledge_stats["optimizations_run"], int)
        
        print(f"✓ Knowledge stats structure is valid: patterns={knowledge_stats['patterns_learned']}, coins={knowledge_stats['coins_analyzed']}")
    
    def test_learning_status_last_cycles_structure(self):
        """Last cycles should have the right structure"""
        response = requests.get(f"{BASE_URL}/api/learning/status")
        data = response.json()
        
        last_cycles = data.get("last_cycles", {})
        assert "pattern_learning" in last_cycles, "Missing 'pattern_learning'"
        assert "market_analysis" in last_cycles, "Missing 'market_analysis'"
        assert "sentiment_tracking" in last_cycles, "Missing 'sentiment_tracking'"
        assert "optimization" in last_cycles, "Missing 'optimization'"
        assert "daily_summary" in last_cycles, "Missing 'daily_summary'"
        
        print(f"✓ Last cycles structure is valid")


class TestLearningRecommendations:
    """Tests for GET /api/learning/recommendations endpoint"""
    
    def test_recommendations_returns_200(self):
        """Recommendations endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/recommendations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/recommendations returns 200")
    
    def test_recommendations_has_required_fields(self):
        """Recommendations should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/recommendations")
        data = response.json()
        
        assert "pattern_recommendations" in data, "Missing 'pattern_recommendations'"
        assert "optimal_times" in data, "Missing 'optimal_times'"
        assert "sentiment_insights" in data, "Missing 'sentiment_insights'"
        assert "optimization_suggestions" in data, "Missing 'optimization_suggestions'"
        assert "insights" in data, "Missing 'insights'"
        
        print(f"✓ Recommendations has all required fields")
    
    def test_recommendations_pattern_structure(self):
        """Pattern recommendations should have correct structure"""
        response = requests.get(f"{BASE_URL}/api/learning/recommendations")
        data = response.json()
        
        pattern_recs = data.get("pattern_recommendations", {})
        assert "coins_to_favor" in pattern_recs, "Missing 'coins_to_favor'"
        assert "coins_to_avoid" in pattern_recs, "Missing 'coins_to_avoid'"
        assert "best_patterns" in pattern_recs, "Missing 'best_patterns'"
        assert "worst_patterns" in pattern_recs, "Missing 'worst_patterns'"
        assert "optimal_timeframes" in pattern_recs, "Missing 'optimal_timeframes'"
        
        # All should be lists
        assert isinstance(pattern_recs["coins_to_favor"], list)
        assert isinstance(pattern_recs["coins_to_avoid"], list)
        assert isinstance(pattern_recs["best_patterns"], list)
        assert isinstance(pattern_recs["worst_patterns"], list)
        
        print(f"✓ Pattern recommendations structure is valid")


class TestLearningInsights:
    """Tests for GET /api/learning/insights endpoint"""
    
    def test_insights_returns_200(self):
        """Insights endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/insights")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/insights returns 200")
    
    def test_insights_has_required_fields(self):
        """Insights should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/insights")
        data = response.json()
        
        assert "insights" in data, "Missing 'insights' field"
        assert "count" in data, "Missing 'count' field"
        assert "generated_at" in data, "Missing 'generated_at' field"
        
        # Insights should be a list
        assert isinstance(data["insights"], list)
        # Count should match list length
        assert data["count"] == len(data["insights"])
        
        print(f"✓ Insights has all required fields, count={data['count']}")


class TestForceLearningCycle:
    """Tests for POST /api/learning/force-cycle endpoint"""
    
    def test_force_cycle_returns_200(self):
        """Force cycle endpoint should return 200"""
        response = requests.post(f"{BASE_URL}/api/learning/force-cycle")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ POST /api/learning/force-cycle returns 200")
    
    def test_force_cycle_has_required_fields(self):
        """Force cycle response should have required fields"""
        response = requests.post(f"{BASE_URL}/api/learning/force-cycle")
        data = response.json()
        
        assert "success" in data, "Missing 'success' field"
        assert "patterns_learned" in data, "Missing 'patterns_learned' field"
        assert "insights_generated" in data, "Missing 'insights_generated' field"
        assert "timestamp" in data, "Missing 'timestamp' field"
        
        assert data["success"] == True, "Force cycle should return success=true"
        
        print(f"✓ Force cycle completed successfully, patterns={data['patterns_learned']}, insights={data['insights_generated']}")


class TestSummaryPreview:
    """Tests for GET /api/learning/summary/preview endpoint"""
    
    def test_summary_preview_returns_200(self):
        """Summary preview endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/summary/preview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/summary/preview returns 200")
    
    def test_summary_preview_has_required_fields(self):
        """Summary preview should have required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/summary/preview")
        data = response.json()
        
        assert "preview" in data, "Missing 'preview' field"
        assert "length" in data, "Missing 'length' field"
        assert "generated_at" in data, "Missing 'generated_at' field"
        
        # Preview should be a non-empty string
        assert isinstance(data["preview"], str)
        assert len(data["preview"]) > 0
        
        print(f"✓ Summary preview generated, length={data['length']}")
    
    def test_summary_preview_content(self):
        """Summary preview should contain expected content"""
        response = requests.get(f"{BASE_URL}/api/learning/summary/preview")
        data = response.json()
        
        preview = data.get("preview", "")
        
        # Should contain AEON LEARNING SUMMARY header
        assert "AEON LEARNING SUMMARY" in preview, "Missing AEON LEARNING SUMMARY header"
        # Should contain the signature quote
        assert "Every trade teaches" in preview, "Missing signature quote"
        
        print(f"✓ Summary preview contains expected content")


class TestLearnedPatterns:
    """Tests for GET /api/learning/patterns endpoint"""
    
    def test_patterns_returns_200(self):
        """Patterns endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/patterns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/patterns returns 200")
    
    def test_patterns_has_required_fields(self):
        """Patterns should have required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/patterns")
        data = response.json()
        
        assert "patterns" in data, "Missing 'patterns' field"
        assert "total_patterns" in data, "Missing 'total_patterns' field"
        
        # Patterns should be a list
        assert isinstance(data["patterns"], list)
        # Count should match list length
        assert data["total_patterns"] == len(data["patterns"])
        
        print(f"✓ Patterns has required fields, total={data['total_patterns']}")


class TestCoinAnalysis:
    """Tests for GET /api/learning/coins endpoint"""
    
    def test_coins_returns_200(self):
        """Coins endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/coins")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/coins returns 200")
    
    def test_coins_has_required_fields(self):
        """Coins should have required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/coins")
        data = response.json()
        
        assert "coins" in data, "Missing 'coins' field"
        assert "total_coins" in data, "Missing 'total_coins' field"
        assert "best_performers" in data, "Missing 'best_performers' field"
        assert "worst_performers" in data, "Missing 'worst_performers' field"
        
        # All should be lists
        assert isinstance(data["coins"], list)
        assert isinstance(data["best_performers"], list)
        assert isinstance(data["worst_performers"], list)
        
        print(f"✓ Coins has required fields, total={data['total_coins']}")


class TestSessionAnalysis:
    """Tests for GET /api/learning/sessions endpoint"""
    
    def test_sessions_returns_200(self):
        """Sessions endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/learning/sessions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/learning/sessions returns 200")
    
    def test_sessions_has_required_fields(self):
        """Sessions should have required fields"""
        response = requests.get(f"{BASE_URL}/api/learning/sessions")
        data = response.json()
        
        assert "sessions" in data, "Missing 'sessions' field"
        assert "best_hours" in data, "Missing 'best_hours' field"
        assert "worst_hours" in data, "Missing 'worst_hours' field"
        assert "best_days" in data, "Missing 'best_days' field"
        assert "worst_days" in data, "Missing 'worst_days' field"
        
        # Sessions should be a dict
        assert isinstance(data["sessions"], dict)
        
        print(f"✓ Sessions has required fields")


class TestSelfHealerRegistration:
    """Tests that continuous learning is registered with self-healer"""
    
    def test_learning_registered_in_system_health(self):
        """Continuous learning should be registered in system health"""
        response = requests.get(f"{BASE_URL}/api/system/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        services = data.get("services", {})
        
        assert "continuous_learning" in services, "continuous_learning not registered with self-healer"
        
        learning_service = services["continuous_learning"]
        assert learning_service.get("name") == "continuous_learning"
        
        print(f"✓ Continuous learning registered with self-healer, status={learning_service.get('status')}")


class TestLearningToggle:
    """Tests for POST /api/learning/toggle endpoint"""
    
    def test_toggle_enable_returns_200(self):
        """Toggle enable should return 200"""
        response = requests.post(f"{BASE_URL}/api/learning/toggle?enabled=true")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("enabled") == True
        
        print(f"✓ Toggle enabled=true works correctly")
    
    def test_toggle_disable_and_reenable(self):
        """Toggle disable and re-enable should work"""
        # Disable
        response = requests.post(f"{BASE_URL}/api/learning/toggle?enabled=false")
        assert response.status_code == 200
        data = response.json()
        assert data.get("enabled") == False
        print(f"✓ Toggle disabled")
        
        # Verify status shows disabled
        status_response = requests.get(f"{BASE_URL}/api/learning/status")
        status = status_response.json()
        assert status.get("active") == False
        print(f"✓ Status shows active=false")
        
        # Re-enable
        response = requests.post(f"{BASE_URL}/api/learning/toggle?enabled=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("enabled") == True
        print(f"✓ Toggle re-enabled")
        
        # Verify status shows enabled
        status_response = requests.get(f"{BASE_URL}/api/learning/status")
        status = status_response.json()
        assert status.get("active") == True
        print(f"✓ Status shows active=true")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
