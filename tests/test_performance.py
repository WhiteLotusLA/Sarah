"""
Performance tests for Sarah AI system
"""

import pytest
import asyncio
import time
import psutil
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import statistics
from sarah.agents.base import BaseAgent, MessageType, Priority


@pytest.mark.performance
class TestSystemPerformance:
    """Test overall system performance characteristics"""

    @pytest.mark.asyncio
    async def test_startup_performance(
        self, test_database, test_redis, performance_monitor
    ):
        """Test system startup time with multiple agents"""
        from sarah.agents.director import DirectorAgent
        from sarah.agents.task import TaskAgent
        from sarah.agents.calendar import CalendarAgent

        agents = []

        # Measure startup time
        performance_monitor.start_timer("full_system_startup")

        # Start core agents
        for agent_class in [DirectorAgent, TaskAgent, CalendarAgent]:
            start = time.time()
            agent = agent_class()
            agent.db_pool = test_database
            agent.redis = test_redis
            await agent.start()
            agents.append(agent)

            agent_time = time.time() - start
            performance_monitor.metrics[f"{agent.name}_startup"] = [agent_time]

        total_time = performance_monitor.stop_timer("full_system_startup")

        # Cleanup
        for agent in agents:
            await agent.shutdown()

        # Performance assertions
        assert total_time < 5.0  # Should start in under 5 seconds

        # Report
        print(f"\nSystem startup time: {total_time:.2f}s")
        for agent in agents:
            agent_time = performance_monitor.metrics[f"{agent.name}_startup"][0]
            print(f"  {agent.name}: {agent_time:.2f}s")

    @pytest.mark.asyncio
    async def test_memory_usage(self, test_database, test_redis):
        """Test memory usage under load"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        agents = []

        # Create many agents
        for i in range(20):
            agent = BaseAgent(f"memory_test_{i}", f"Memory Test {i}")
            agent.db_pool = test_database
            agent.redis = test_redis
            await agent.start()
            agents.append(agent)

        # Send many messages
        for _ in range(100):
            for agent in agents:
                await agent.broadcast_event("memory_test", {"data": "x" * 1000})

        # Wait for processing
        await asyncio.sleep(2)

        # Check memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Cleanup
        for agent in agents:
            await agent.shutdown()

        # Memory should not grow excessively
        assert memory_increase < 500  # Less than 500MB increase

        print(
            f"\nMemory usage - Initial: {initial_memory:.1f}MB, "
            f"Final: {final_memory:.1f}MB, Increase: {memory_increase:.1f}MB"
        )

    @pytest.mark.asyncio
    async def test_cpu_usage(self, test_agents, performance_monitor):
        """Test CPU usage under various loads"""
        import multiprocessing

        cpu_count = multiprocessing.cpu_count()
        process = psutil.Process(os.getpid())

        # Baseline CPU
        process.cpu_percent()  # First call to initialize
        await asyncio.sleep(0.1)
        baseline_cpu = process.cpu_percent()

        # Generate load
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        performance_monitor.start_timer("cpu_load_test")

        # Send many messages concurrently
        tasks = []
        for i in range(1000):
            task = director.send_message(
                "test_worker", MessageType.COMMAND, {"index": i, "data": "x" * 100}
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Measure CPU during load
        load_cpu = process.cpu_percent()
        elapsed = performance_monitor.stop_timer("cpu_load_test")

        # CPU usage should be reasonable
        assert load_cpu < 90 * cpu_count  # Less than 90% per core

        print(
            f"\nCPU usage - Baseline: {baseline_cpu:.1f}%, "
            f"Under load: {load_cpu:.1f}%, Cores: {cpu_count}"
        )

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load(self, test_agents, performance_monitor):
        """Test system behavior under sustained load"""
        director = test_agents["director"]
        worker = test_agents["test_worker"]

        duration = 10  # seconds
        message_rate = 100  # messages per second

        metrics = {"sent": 0, "received": 0, "latencies": [], "errors": 0}

        start_time = time.time()

        # Generate sustained load
        while time.time() - start_time < duration:
            send_time = time.time()

            try:
                await director.send_message(
                    "test_worker",
                    MessageType.COMMAND,
                    {"timestamp": send_time, "index": metrics["sent"]},
                )
                metrics["sent"] += 1

                # Control rate
                elapsed = time.time() - send_time
                sleep_time = (1.0 / message_rate) - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                metrics["errors"] += 1

        # Wait for all messages to be processed
        await asyncio.sleep(2)

        # Calculate metrics
        metrics["received"] = len(worker.received_messages)

        # Calculate latencies for received messages
        for msg in worker.received_messages[-100:]:  # Last 100 messages
            if "timestamp" in msg.payload:
                latency = (time.time() - msg.payload["timestamp"]) * 1000
                metrics["latencies"].append(latency)

        # Performance analysis
        success_rate = (
            metrics["received"] / metrics["sent"] if metrics["sent"] > 0 else 0
        )
        avg_latency = (
            statistics.mean(metrics["latencies"]) if metrics["latencies"] else 0
        )
        p95_latency = (
            statistics.quantiles(metrics["latencies"], n=20)[18]
            if len(metrics["latencies"]) > 20
            else 0
        )

        # Assertions
        assert success_rate > 0.95  # At least 95% delivery
        assert avg_latency < 100  # Average under 100ms
        assert p95_latency < 500  # 95th percentile under 500ms

        print(f"\nSustained load test:")
        print(f"  Duration: {duration}s")
        print(f"  Target rate: {message_rate} msg/s")
        print(f"  Messages sent: {metrics['sent']}")
        print(f"  Messages received: {metrics['received']}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average latency: {avg_latency:.1f}ms")
        print(f"  95th percentile: {p95_latency:.1f}ms")
        print(f"  Errors: {metrics['errors']}")


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database operation performance"""

    @pytest.mark.asyncio
    async def test_memory_storage_performance(self, test_database, performance_monitor):
        """Test memory storage and retrieval performance"""
        from sarah.core.memory.memory_palace import MemoryPalace

        palace = MemoryPalace(test_database)
        await palace.initialize()

        # Test write performance
        memories = []
        performance_monitor.start_timer("memory_write")

        for i in range(100):
            memory_id = await palace.store_memory(
                f"Test memory {i}",
                memory_type="test",
                importance=0.5,
                metadata={"index": i},
            )
            memories.append(memory_id)

        write_time = performance_monitor.stop_timer("memory_write")
        write_rate = 100 / write_time

        # Test read performance
        performance_monitor.start_timer("memory_read")

        for memory_id in memories[:50]:
            memory = await palace.get_memory(memory_id)
            assert memory is not None

        read_time = performance_monitor.stop_timer("memory_read")
        read_rate = 50 / read_time

        # Test search performance
        performance_monitor.start_timer("memory_search")

        results = await palace.search_memories("Test memory", limit=20)

        search_time = performance_monitor.stop_timer("memory_search")

        # Performance assertions
        assert write_rate > 10  # At least 10 writes per second
        assert read_rate > 50  # At least 50 reads per second
        assert search_time < 1  # Search under 1 second

        print(f"\nMemory performance:")
        print(f"  Write rate: {write_rate:.1f} memories/s")
        print(f"  Read rate: {read_rate:.1f} memories/s")
        print(f"  Search time: {search_time:.3f}s")

    @pytest.mark.asyncio
    async def test_concurrent_database_access(self, test_database, performance_monitor):
        """Test database performance with concurrent access"""

        async def database_operation(index):
            async with test_database.acquire() as conn:
                # Simulate various operations
                await conn.fetchval("SELECT COUNT(*) FROM messages")
                await conn.execute(
                    "INSERT INTO messages (from_agent, to_agent, message_type, payload) "
                    "VALUES ($1, $2, $3, $4)",
                    f"agent_{index}",
                    "test",
                    "test",
                    {"data": index},
                )
                await conn.fetchval("SELECT MAX(timestamp) FROM messages")

        # Test concurrent operations
        performance_monitor.start_timer("concurrent_db")

        tasks = []
        for i in range(50):
            tasks.append(database_operation(i))

        await asyncio.gather(*tasks)

        concurrent_time = performance_monitor.stop_timer("concurrent_db")

        # Should handle concurrent access efficiently
        assert concurrent_time < 5  # Under 5 seconds for 50 concurrent operations

        print(f"\nConcurrent database access: {concurrent_time:.2f}s for 50 operations")


@pytest.mark.performance
class TestScalabilityLimits:
    """Test system scalability limits"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_agent_scalability(self, test_database, test_redis):
        """Test how many agents the system can handle"""
        agents = []
        max_agents = 0

        try:
            # Keep adding agents until system struggles
            for i in range(100):
                agent = BaseAgent(f"scale_test_{i}", f"Scale Test {i}")
                agent.db_pool = test_database
                agent.redis = test_redis
                await agent.start()
                agents.append(agent)
                max_agents = i + 1

                # Check if system is still responsive
                start = time.time()
                await test_redis.ping()
                response_time = time.time() - start

                if response_time > 1.0:  # If Redis takes over 1s to respond
                    break

        finally:
            # Cleanup
            for agent in agents:
                await agent.shutdown()

        # Should handle at least 50 agents
        assert max_agents >= 50

        print(f"\nAgent scalability: System handled {max_agents} concurrent agents")

    @pytest.mark.asyncio
    async def test_message_queue_limits(self, test_agents, test_redis):
        """Test message queue capacity limits"""
        director = test_agents["director"]

        # Stop worker to queue messages
        worker = test_agents["test_worker"]
        await worker.shutdown()

        # Fill queue
        queue_size = 0
        try:
            for i in range(10000):
                await director.send_message(
                    "test_worker", MessageType.COMMAND, {"index": i}
                )
                queue_size = i + 1

                # Check queue size
                current_size = await test_redis.llen("queue:test_worker")
                if current_size != queue_size:
                    break

        except Exception:
            pass

        # Should handle at least 1000 queued messages
        assert queue_size >= 1000

        print(f"\nMessage queue capacity: {queue_size} messages")

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, test_agents, performance_monitor):
        """Test handling of many concurrent requests"""
        director = test_agents["director"]

        # Simulate many concurrent user requests
        async def simulate_request(index):
            return await director.send_message(
                "test_worker",
                MessageType.QUERY,
                {"request_id": index, "data": f"Request {index}"},
            )

        performance_monitor.start_timer("concurrent_requests")

        # Send many requests concurrently
        tasks = []
        for i in range(500):
            tasks.append(simulate_request(i))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = performance_monitor.stop_timer("concurrent_requests")

        # Count successes
        successes = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successes / len(tasks)

        # Should handle most requests successfully
        assert success_rate > 0.95

        print(
            f"\nConcurrent requests: {successes}/{len(tasks)} successful "
            f"in {elapsed:.2f}s ({len(tasks)/elapsed:.1f} req/s)"
        )
