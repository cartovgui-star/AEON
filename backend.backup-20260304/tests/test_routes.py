"""
Tests for modular route files
Run with: pytest tests/ -v
"""

import pytest
import httpx
import os

# Get API URL from environment or use default
API_URL = os.environ.get("TEST_API_URL", "http://localhost:8001/api")


class TestAccuracyRoutes:
    """Test accuracy tracking endpoints"""
    
    @pytest.mark.asyncio
    async def test_accuracy_stats(self):
        """Test /accuracy endpoint returns valid stats"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/accuracy")
            assert resp.status_code == 200
            data = resp.json()
            assert "overview" in data or "error" not in data
    
    @pytest.mark.asyncio
    async def test_accuracy_pending(self):
        """Test /accuracy/pending returns pending alerts"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/accuracy/pending")
            assert resp.status_code == 200
            data = resp.json()
            assert "pending" in data
    
    @pytest.mark.asyncio
    async def test_leaderboard(self):
        """Test /accuracy/leaderboard returns coin rankings"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/accuracy/leaderboard")
            assert resp.status_code == 200
            data = resp.json()
            assert "leaderboard" in data
            assert "total_symbols" in data


class TestSystemRoutes:
    """Test system endpoints"""
    
    @pytest.mark.asyncio
    async def test_system_health(self):
        """Test /system/health endpoint"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/system/health")
            assert resp.status_code == 200
    
    @pytest.mark.asyncio
    async def test_system_pairs(self):
        """Test /system/pairs returns trading pairs"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/system/pairs")
            assert resp.status_code == 200
            data = resp.json()
            assert "pairs" in data
            assert "total_pairs" in data
            assert data["total_pairs"] >= 40
    
    @pytest.mark.asyncio
    async def test_news(self):
        """Test /system/news returns crypto news"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/system/news?limit=5")
            assert resp.status_code == 200
            data = resp.json()
            assert "news" in data or "error" in data  # May error if rate limited


class TestMTFRoutes:
    """Test multi-timeframe analysis endpoints"""
    
    @pytest.mark.asyncio
    async def test_mtf_analysis(self):
        """Test /mtf/{symbol} returns MTF analysis"""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{API_URL}/mtf/BTC")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)


class TestConfluenceRoutes:
    """Test confluence analysis endpoints"""
    
    @pytest.mark.asyncio
    async def test_confluence(self):
        """Test /confluence/{symbol} returns confluence data"""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{API_URL}/confluence/BTC")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)


class TestLearningRoutes:
    """Test learning system endpoints"""
    
    @pytest.mark.asyncio
    async def test_learning_stats(self):
        """Test /learning/stats returns prediction stats"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/learning/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_learning_open(self):
        """Test /learning/open returns open predictions"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/learning/open")
            assert resp.status_code == 200


class TestBotRoutes:
    """Test bot status endpoints"""
    
    @pytest.mark.asyncio
    async def test_bot_stats(self):
        """Test /bot/stats returns bot statistics"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/bot/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "total_messages" in data or "error" not in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
