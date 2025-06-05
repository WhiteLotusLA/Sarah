"""
Integration tests for agent communication
"""

import pytest
import asyncio
import json
from datetime import datetime
from sarah.agents.base import Message, MessageType, Priority


@pytest.mark.integration
class TestAgentCommunication:
    """Test agent-to-agent communication"""

    @pytest.mark.asyncio
    async def test_direct_message_delivery(self, test_agents):
        """Test that messages are delivered between agents"""
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        # Send a test message
        test_payload = {"data": "Hello, worker!"}
        await director.send_message(
            to_agent="test_worker",
            message_type=MessageType.COMMAND,
            payload=test_payload,
        )

        # Wait for message delivery
        await asyncio.sleep(0.1)

        # Check that worker received the message
        assert len(worker.received_messages) == 1
        message = worker.received_messages[0]
        assert message.from_agent == "director"
        assert message.message_type == MessageType.COMMAND
        assert message.payload == test_payload

    @pytest.mark.asyncio
    async def test_broadcast_message(self, test_agents):
        """Test broadcasting messages to all agents"""
        director = test_agents["director"]
        task_agent = test_agents["task"]
        worker = test_agents["test_worker"]

        # Enable message recording for task agent
        task_agent.received_messages = []
        original_process = task_agent.process_message

        async def track_process(msg):
            task_agent.received_messages.append(msg)
            await original_process(msg)

        task_agent.process_message = track_process

        # Broadcast a message
        await director.broadcast_event(
            "system_update", {"status": "maintenance", "duration": 300}
        )

        # Wait for delivery
        await asyncio.sleep(0.1)

        # Both agents should receive the broadcast
        assert len(worker.received_messages) == 1
        assert len(task_agent.received_messages) == 1

        # Verify message content
        for agent in [worker, task_agent]:
            msg = agent.received_messages[0]
            assert msg.from_agent == "director"
            assert msg.message_type == MessageType.EVENT
            assert msg.payload["status"] == "maintenance"

    @pytest.mark.asyncio
    async def test_request_response_pattern(self, test_agents):
        """Test request-response message pattern"""
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        # Send echo request
        correlation_id = await director.send_message(
            to_agent="test_worker", message_type="echo", payload={"data": "Echo this!"}
        )

        # Wait for response
        await asyncio.sleep(0.1)

        # Worker should have received and responded
        assert len(worker.received_messages) == 1

        # Director should have received response
        # (In real implementation, we'd track responses)

    @pytest.mark.asyncio
    async def test_priority_message_ordering(self, test_agents, test_redis):
        """Test that high priority messages are processed first"""
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        # Temporarily stop worker to queue messages
        worker.running = False
        await asyncio.sleep(0.1)

        # Send messages with different priorities
        await director.send_message(
            "test_worker", MessageType.COMMAND, {"order": 1}, priority=Priority.LOW
        )
        await director.send_message(
            "test_worker", MessageType.COMMAND, {"order": 2}, priority=Priority.NORMAL
        )
        await director.send_message(
            "test_worker", MessageType.COMMAND, {"order": 3}, priority=Priority.HIGH
        )
        await director.send_message(
            "test_worker", MessageType.COMMAND, {"order": 4}, priority=Priority.URGENT
        )

        # Clear previous messages and restart worker
        worker.received_messages = []
        worker.running = True
        asyncio.create_task(worker._process_messages())

        # Wait for processing
        await asyncio.sleep(0.5)

        # Messages should be processed in priority order
        assert len(worker.received_messages) >= 4

        # Check order (urgent and high priority should come first)
        orders = [msg.payload["order"] for msg in worker.received_messages[:4]]
        assert orders[0] == 4  # Urgent
        assert orders[1] == 3  # High

    @pytest.mark.asyncio
    async def test_agent_discovery(self, test_agents, test_redis):
        """Test agent discovery mechanism"""
        # Check Redis for registered agents
        agent_keys = []
        async for key in test_redis.scan_iter("agent:*:status"):
            agent_keys.append(key)

        # Should have all test agents registered
        assert len(agent_keys) >= 3

        # Verify agent status
        for agent_id, agent in test_agents.items():
            status = await test_redis.get(f"agent:{agent_id}:status")
            assert status == "online"

    @pytest.mark.asyncio
    async def test_message_persistence(self, test_agents, test_database):
        """Test that messages are persisted to database"""
        director = test_agents["director"]

        # Send a message
        await director.send_message(
            "test_worker", MessageType.COMMAND, {"test": "persistence"}
        )

        # Wait for processing
        await asyncio.sleep(0.2)

        # Check database
        async with test_database.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE from_agent = $1", "director"
            )
            assert count > 0

            # Verify message content
            message = await conn.fetchrow(
                """
                SELECT * FROM messages 
                WHERE from_agent = $1 AND to_agent = $2
                ORDER BY timestamp DESC LIMIT 1
                """,
                "director",
                "test_worker",
            )
            assert message is not None
            assert message["payload"]["test"] == "persistence"


@pytest.mark.integration
class TestAgentCoordination:
    """Test multi-agent coordination scenarios"""

    @pytest.mark.asyncio
    async def test_director_task_coordination(self, test_agents):
        """Test director coordinating with task agent"""
        director = test_agents["director"]
        task_agent = test_agents["task"]

        # Director requests task creation
        await director.send_command(
            "task",
            "create_task",
            {
                "title": "Integration test task",
                "priority": "high",
                "due_date": "2024-12-31",
            },
        )

        # Wait for processing
        await asyncio.sleep(0.2)

        # Task agent should have created the task
        # (In real implementation, check database)

    @pytest.mark.asyncio
    async def test_multi_agent_workflow(self, test_agents):
        """Test a workflow involving multiple agents"""
        director = test_agents["director"]

        # Simulate a complex request that requires multiple agents
        workflow_request = {
            "user_request": "Schedule a meeting and send invitations",
            "steps": [
                {"agent": "calendar", "action": "find_time"},
                {"agent": "calendar", "action": "create_event"},
                {"agent": "email", "action": "send_invitations"},
            ],
        }

        # Director processes the workflow
        # (In real implementation, director would coordinate agents)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_agent_failure_recovery(self, test_agents, test_redis):
        """Test system behavior when an agent fails"""
        worker = test_agents["test_worker"]
        director = test_agents["director"]

        # Simulate agent failure
        await worker.shutdown()

        # Wait for heartbeat timeout
        await asyncio.sleep(2)

        # Director should detect the failure
        status = await test_redis.get(f"agent:test_worker:status")
        assert status != "online"

        # Send message to failed agent
        await director.send_message(
            "test_worker", MessageType.COMMAND, {"test": "recovery"}
        )

        # Message should be queued
        queue_length = await test_redis.llen("queue:test_worker")
        assert queue_length > 0

        # Restart agent
        await worker.start()
        await asyncio.sleep(0.5)

        # Agent should process queued messages
        assert len(worker.received_messages) > 0


@pytest.mark.performance
class TestAgentPerformance:
    """Performance tests for agent communication"""

    @pytest.mark.asyncio
    async def test_message_throughput(self, test_agents, performance_monitor):
        """Test message throughput between agents"""
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        message_count = 100

        # Send many messages
        performance_monitor.start_timer("message_burst")

        for i in range(message_count):
            await director.send_message(
                "test_worker", MessageType.COMMAND, {"index": i, "data": f"Message {i}"}
            )

        # Wait for all messages to be processed
        timeout = 10  # seconds
        start_time = asyncio.get_event_loop().time()

        while len(worker.received_messages) < message_count:
            if asyncio.get_event_loop().time() - start_time > timeout:
                break
            await asyncio.sleep(0.1)

        elapsed = performance_monitor.stop_timer("message_burst")

        # Calculate throughput
        messages_received = len(worker.received_messages)
        throughput = messages_received / elapsed if elapsed > 0 else 0

        # Performance assertions
        assert messages_received >= message_count * 0.95  # Allow 5% loss
        assert throughput >= 10  # At least 10 messages per second

        print(f"\nMessage throughput: {throughput:.2f} msg/sec")
        print(f"Messages sent: {message_count}, received: {messages_received}")

    @pytest.mark.asyncio
    async def test_concurrent_agents(
        self, test_database, test_redis, performance_monitor
    ):
        """Test system performance with many concurrent agents"""
        from sarah.agents.base import BaseAgent

        agent_count = 10
        agents = []

        # Create many worker agents
        class LoadTestAgent(BaseAgent):
            def __init__(self, agent_id):
                super().__init__(f"load_test_{agent_id}", f"Load Test {agent_id}")
                self.message_count = 0

            async def process_message(self, message):
                self.message_count += 1

        # Start agents
        performance_monitor.start_timer("agent_startup")

        for i in range(agent_count):
            agent = LoadTestAgent(i)
            agent.db_pool = test_database
            agent.redis = test_redis
            await agent.start()
            agents.append(agent)

        startup_time = performance_monitor.stop_timer("agent_startup")

        # Send messages to all agents
        performance_monitor.start_timer("broadcast_test")

        for i in range(10):
            for agent in agents:
                await agent.broadcast_event("load_test", {"iteration": i})

        broadcast_time = performance_monitor.stop_timer("broadcast_test")

        # Cleanup
        for agent in agents:
            await agent.shutdown()

        # Performance report
        print(f"\nAgent startup time: {startup_time:.2f}s for {agent_count} agents")
        print(f"Broadcast time: {broadcast_time:.2f}s")
        print(f"Average startup: {startup_time/agent_count:.3f}s per agent")

    @pytest.mark.asyncio
    async def test_message_latency(self, test_agents, performance_monitor):
        """Test message delivery latency"""
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        latencies = []

        for i in range(50):
            # Record send time
            send_time = datetime.utcnow()

            await director.send_message(
                "test_worker", MessageType.COMMAND, {"timestamp": send_time.isoformat()}
            )

            # Wait for message
            while len(worker.received_messages) <= i:
                await asyncio.sleep(0.001)

            # Calculate latency
            receive_time = datetime.utcnow()
            latency = (receive_time - send_time).total_seconds() * 1000  # ms
            latencies.append(latency)

        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)

        # Performance assertions
        assert avg_latency < 50  # Average under 50ms
        assert max_latency < 200  # Max under 200ms

        print(
            f"\nMessage latency - Avg: {avg_latency:.2f}ms, "
            f"Min: {min_latency:.2f}ms, Max: {max_latency:.2f}ms"
        )
