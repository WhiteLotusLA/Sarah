"""
Unit tests for BaseAgent
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import json

from sarah.agents.base import BaseAgent, AgentMessage, AgentStatus


@pytest.fixture
async def redis_mock():
    """Mock Redis connection"""
    redis = AsyncMock()
    redis.publish = AsyncMock()
    redis.subscribe = AsyncMock()
    redis.get = AsyncMock()
    redis.set = AsyncMock()
    return redis


@pytest.fixture
async def base_agent(redis_mock):
    """Create a test BaseAgent instance"""
    with patch('redis.asyncio.Redis.from_url', return_value=redis_mock):
        agent = BaseAgent("test_agent", "Test Agent")
        agent.redis = redis_mock
        yield agent
        # Cleanup
        await agent.shutdown()


@pytest.mark.asyncio
async def test_agent_initialization(base_agent):
    """Test BaseAgent initialization"""
    assert base_agent.agent_id == "test_agent"
    assert base_agent.name == "Test Agent"
    assert base_agent.status == AgentStatus.INITIALIZING
    assert base_agent.heartbeat_interval == 30


@pytest.mark.asyncio
async def test_agent_startup(base_agent):
    """Test agent startup process"""
    # Mock Redis pubsub
    pubsub_mock = AsyncMock()
    base_agent.redis.pubsub.return_value = pubsub_mock
    
    # Start agent
    await base_agent.start()
    
    assert base_agent.status == AgentStatus.RUNNING
    assert base_agent.redis.publish.called


@pytest.mark.asyncio
async def test_send_message(base_agent):
    """Test sending a message"""
    base_agent.status = AgentStatus.RUNNING
    
    # Send message
    await base_agent.send_message(
        "other_agent",
        "test_command",
        {"data": "test"}
    )
    
    # Check Redis publish was called
    assert base_agent.redis.publish.called
    call_args = base_agent.redis.publish.call_args
    assert call_args[0][0] == "sarah:agents:other_agent"
    
    # Verify message format
    message_data = json.loads(call_args[0][1])
    assert message_data['from_agent'] == "test_agent"
    assert message_data['command'] == "test_command"
    assert message_data['data'] == {"data": "test"}


@pytest.mark.asyncio
async def test_broadcast_message(base_agent):
    """Test broadcasting a message"""
    base_agent.status = AgentStatus.RUNNING
    
    # Broadcast message
    await base_agent.broadcast("test_event", {"info": "broadcast"})
    
    # Check Redis publish was called
    assert base_agent.redis.publish.called
    call_args = base_agent.redis.publish.call_args
    assert call_args[0][0] == "sarah:broadcast"


@pytest.mark.asyncio
async def test_handle_message(base_agent):
    """Test message handling"""
    # Create a test message
    message = AgentMessage(
        from_agent="other_agent",
        to_agent="test_agent",
        command="test_command",
        data={"test": "data"},
        timestamp=datetime.now()
    )
    
    # Mock handler
    handler_called = False
    async def test_handler(msg):
        nonlocal handler_called
        handler_called = True
        assert msg.command == "test_command"
    
    base_agent.handlers["test_command"] = test_handler
    
    # Handle message
    await base_agent._handle_message(message)
    
    assert handler_called


@pytest.mark.asyncio
async def test_heartbeat(base_agent):
    """Test heartbeat mechanism"""
    base_agent.status = AgentStatus.RUNNING
    base_agent.heartbeat_interval = 0.1  # Fast heartbeat for testing
    
    # Start heartbeat
    heartbeat_task = asyncio.create_task(base_agent._heartbeat_loop())
    
    # Wait for at least one heartbeat
    await asyncio.sleep(0.15)
    
    # Check Redis set was called with heartbeat
    assert base_agent.redis.set.called
    call_args = base_agent.redis.set.call_args
    assert call_args[0][0] == "sarah:agents:test_agent:heartbeat"
    
    # Cancel heartbeat
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_register_handler(base_agent):
    """Test handler registration"""
    # Define handler
    async def my_handler(message):
        pass
    
    # Register handler
    base_agent.register_handler("my_command", my_handler)
    
    assert "my_command" in base_agent.handlers
    assert base_agent.handlers["my_command"] == my_handler


@pytest.mark.asyncio
async def test_get_agent_status(base_agent):
    """Test getting agent status"""
    # Mock Redis get
    base_agent.redis.get.return_value = json.dumps({
        "status": "running",
        "last_seen": datetime.now().isoformat()
    })
    
    # Get status
    status = await base_agent.get_agent_status("other_agent")
    
    assert status is not None
    assert status["status"] == "running"


@pytest.mark.asyncio
async def test_shutdown(base_agent):
    """Test agent shutdown"""
    base_agent.status = AgentStatus.RUNNING
    
    # Mock pubsub
    base_agent.pubsub = AsyncMock()
    base_agent.pubsub.unsubscribe = AsyncMock()
    base_agent.pubsub.close = AsyncMock()
    
    # Shutdown
    await base_agent.shutdown()
    
    assert base_agent.status == AgentStatus.STOPPED
    assert base_agent.redis.publish.called
    assert base_agent.pubsub.close.called


@pytest.mark.asyncio
async def test_message_parsing():
    """Test AgentMessage parsing"""
    message_data = {
        "from_agent": "sender",
        "to_agent": "receiver",
        "command": "test",
        "data": {"key": "value"},
        "timestamp": datetime.now().isoformat()
    }
    
    message = AgentMessage(**message_data)
    
    assert message.from_agent == "sender"
    assert message.to_agent == "receiver"
    assert message.command == "test"
    assert message.data == {"key": "value"}


@pytest.mark.asyncio
async def test_error_handling_in_message_handler(base_agent):
    """Test error handling when message handler fails"""
    # Create handler that raises error
    async def failing_handler(msg):
        raise Exception("Handler error")
    
    base_agent.handlers["fail_command"] = failing_handler
    
    # Create message
    message = AgentMessage(
        from_agent="other",
        to_agent="test_agent",
        command="fail_command",
        data={},
        timestamp=datetime.now()
    )
    
    # Should not raise exception
    await base_agent._handle_message(message)
    
    # Agent should still be running
    assert base_agent.status == AgentStatus.RUNNING