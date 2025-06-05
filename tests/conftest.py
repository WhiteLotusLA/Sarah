"""
Pytest configuration and fixtures for integration tests
"""

import pytest
import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator
import asyncpg
import redis.asyncio as redis
from unittest.mock import Mock, AsyncMock, patch
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_database() -> AsyncGenerator[asyncpg.Pool, None]:
    """Create a test database and clean up after tests"""
    # Use test database URL
    database_url = os.getenv(
        "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sarah_test"
    )

    # Create connection pool
    pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=5,
        command_timeout=60,
    )

    # Create test schema
    async with pool.acquire() as conn:
        # Drop existing test data
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.execute("CREATE SCHEMA public")

        # Create pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Create test tables
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                embedding vector(384),
                memory_type VARCHAR(50),
                importance FLOAT DEFAULT 0.5,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                status VARCHAR(20) DEFAULT 'offline',
                last_heartbeat TIMESTAMPTZ,
                metadata JSONB DEFAULT '{}'
            )
        """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                from_agent VARCHAR(50),
                to_agent VARCHAR(50),
                message_type VARCHAR(50),
                payload JSONB,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        """
        )

    yield pool

    # Cleanup
    await pool.close()


@pytest.fixture
async def test_redis() -> AsyncGenerator[redis.Redis, None]:
    """Create a test Redis connection"""
    redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")

    # Create Redis client
    client = await redis.from_url(redis_url, decode_responses=True)

    # Clear test database
    await client.flushdb()

    yield client

    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
def mock_ollama():
    """Mock Ollama service for tests"""
    with patch("sarah.services.ai_service.ollama_service") as mock:
        mock.is_available.return_value = True
        mock.generate = AsyncMock(return_value="Test AI response")
        mock.generate_embedding = AsyncMock(
            return_value=[0.1] * 384  # Mock embedding vector
        )
        yield mock


@pytest.fixture
async def test_agents(test_database, test_redis):
    """Create test agent instances"""
    from sarah.agents.base import BaseAgent
    from sarah.agents.director import DirectorAgent
    from sarah.agents.task import TaskAgent

    # Create test agents
    agents = {}

    # Director agent
    director = DirectorAgent()
    director.db_pool = test_database
    director.redis = test_redis
    await director.start()
    agents["director"] = director

    # Task agent
    task_agent = TaskAgent()
    task_agent.db_pool = test_database
    task_agent.redis = test_redis
    await task_agent.start()
    agents["task"] = task_agent

    # Test worker agent
    class TestWorkerAgent(BaseAgent):
        def __init__(self):
            super().__init__("test_worker", "Test Worker")
            self.received_messages = []

        async def process_message(self, message):
            self.received_messages.append(message)

            # Echo back for testing
            if message.message_type == "echo":
                await self.send_response(
                    message, {"echo": message.payload.get("data", "empty")}
                )

    worker = TestWorkerAgent()
    worker.db_pool = test_database
    worker.redis = test_redis
    await worker.start()
    agents["test_worker"] = worker

    yield agents

    # Cleanup
    for agent in agents.values():
        await agent.shutdown()


@pytest.fixture
def sample_messages():
    """Sample messages for testing"""
    return {
        "command": {
            "from_agent": "director",
            "to_agent": "task",
            "message_type": "command",
            "command": "create_task",
            "payload": {
                "title": "Test task",
                "description": "A test task",
                "priority": "medium",
            },
        },
        "query": {
            "from_agent": "director",
            "to_agent": "test_worker",
            "message_type": "query",
            "query": "status",
            "payload": {},
        },
        "event": {
            "from_agent": "task",
            "to_agent": "director",
            "message_type": "event",
            "event": "task_completed",
            "payload": {"task_id": "123", "title": "Completed task"},
        },
    }


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests"""
    import time

    class PerformanceMonitor:
        def __init__(self):
            self.metrics = {}
            self.timers = {}

        def start_timer(self, name: str):
            self.timers[name] = time.time()

        def stop_timer(self, name: str) -> float:
            if name not in self.timers:
                return 0.0

            elapsed = time.time() - self.timers[name]
            if name not in self.metrics:
                self.metrics[name] = []
            self.metrics[name].append(elapsed)
            return elapsed

        def get_average(self, name: str) -> float:
            if name not in self.metrics or not self.metrics[name]:
                return 0.0
            return sum(self.metrics[name]) / len(self.metrics[name])

        def get_report(self) -> dict:
            report = {}
            for name, times in self.metrics.items():
                report[name] = {
                    "count": len(times),
                    "total": sum(times),
                    "average": self.get_average(name),
                    "min": min(times) if times else 0,
                    "max": max(times) if times else 0,
                }
            return report

    return PerformanceMonitor()


# Markers for different test types
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
