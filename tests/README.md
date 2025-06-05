# Sarah AI Integration Tests

This directory contains integration and performance tests for the Sarah AI system.

## Test Structure

### Unit Tests
- `test_base_agent.py` - Tests for the BaseAgent class
- `test_consciousness.py` - Tests for the Consciousness system
- `test_memory_palace.py` - Tests for the MemoryPalace
- `test_email_agent.py` - Tests for the Email agent
- `test_browser_agent.py` - Tests for the Browser agent

### Integration Tests
- `test_agent_communication.py` - Tests for agent-to-agent communication
- `test_message_flow.py` - Tests for complete message flows
- `test_performance.py` - Performance and scalability tests

### Configuration
- `conftest.py` - Pytest fixtures and configuration

## Running Tests

### Prerequisites

1. Ensure PostgreSQL is running with the test database:
```bash
createdb sarah_test
```

2. Ensure Redis is running

3. Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov
```

### Running All Tests
```bash
pytest
```

### Running Specific Test Categories

#### Unit tests only:
```bash
pytest -m "not integration and not performance"
```

#### Integration tests:
```bash
pytest -m integration
```

#### Performance tests:
```bash
pytest -m performance
```

#### Slow tests (including performance):
```bash
pytest -m slow
```

### Running with Coverage
```bash
pytest --cov=sarah --cov-report=html
```

### Running Specific Test Files
```bash
# Run agent communication tests
pytest tests/test_agent_communication.py

# Run a specific test
pytest tests/test_agent_communication.py::TestAgentCommunication::test_direct_message_delivery
```

## Test Environment Variables

Set these environment variables to customize test behavior:

- `TEST_DATABASE_URL` - PostgreSQL connection URL for tests (default: `postgresql://postgres:postgres@localhost:5432/sarah_test`)
- `TEST_REDIS_URL` - Redis connection URL for tests (default: `redis://localhost:6379/15`)

## Writing New Tests

### Integration Test Template
```python
@pytest.mark.integration
class TestNewFeature:
    @pytest.mark.asyncio
    async def test_feature(self, test_agents, test_database):
        # Test implementation
        pass
```

### Performance Test Template
```python
@pytest.mark.performance
class TestFeaturePerformance:
    @pytest.mark.asyncio
    async def test_performance(self, test_agents, performance_monitor):
        performance_monitor.start_timer("operation")
        # Perform operation
        elapsed = performance_monitor.stop_timer("operation")
        assert elapsed < 1.0  # Assert performance requirement
```

## Test Fixtures

### `test_database`
Provides a clean PostgreSQL database connection pool for tests.

### `test_redis`
Provides a clean Redis connection for tests.

### `test_agents`
Provides initialized test agents (director, task, test_worker).

### `mock_ollama`
Mocks the Ollama AI service for tests.

### `performance_monitor`
Provides performance measurement utilities.

### `sample_messages`
Provides sample message templates for testing.

## Performance Benchmarks

Expected performance benchmarks:

- **Message Throughput**: > 10 messages/second
- **Message Latency**: < 50ms average, < 200ms max
- **Agent Startup**: < 1 second per agent
- **Memory Search**: < 1 second for vector similarity search
- **Concurrent Agents**: Support for 50+ concurrent agents
- **Message Queue**: Support for 1000+ queued messages

## Continuous Integration

These tests are designed to run in CI/CD pipelines. Ensure your CI environment has:

1. PostgreSQL with pgvector extension
2. Redis
3. Sufficient resources for performance tests

Example GitHub Actions configuration:

```yaml
- name: Run Tests
  env:
    TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/sarah_test
    TEST_REDIS_URL: redis://localhost:6379/0
  run: |
    pytest -m "not slow" --cov=sarah
```

## Troubleshooting

### Common Issues

1. **Database connection errors**: Ensure PostgreSQL is running and the test database exists
2. **Redis connection errors**: Ensure Redis is running
3. **Timeout errors**: Increase timeout values in slow network environments
4. **Memory errors**: Ensure sufficient RAM for performance tests

### Debug Mode

Run tests with verbose output:
```bash
pytest -vv -s
```

### Cleanup

If tests fail and leave data behind:
```bash
# Clear test database
psql sarah_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Clear Redis test database
redis-cli -n 15 FLUSHDB
```