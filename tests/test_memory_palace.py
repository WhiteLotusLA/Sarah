"""
Unit tests for MemoryPalace
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from sarah.core.memory.memory_palace import MemoryPalace


@pytest.fixture
async def memory_palace():
    """Create a test MemoryPalace instance"""
    palace = MemoryPalace("postgresql://localhost/sarah_test_db")
    # Mock the database connection and encoder
    palace.pool = AsyncMock()
    palace.encoder = Mock()
    palace.encoder.encode = Mock(return_value=np.zeros(384))
    palace.initialized = True
    yield palace
    # Cleanup
    if palace.pool:
        await palace.cleanup()


@pytest.mark.asyncio
async def test_memory_palace_initialization():
    """Test MemoryPalace initialization"""
    with patch('asyncpg.create_pool') as mock_pool:
        with patch('sentence_transformers.SentenceTransformer') as mock_encoder:
            palace = MemoryPalace()
            
            # Mock pool
            mock_pool.return_value = AsyncMock()
            mock_pool.return_value.acquire = AsyncMock()
            
            # Initialize
            await palace.initialize()
            
            assert palace.initialized
            assert palace.pool is not None
            assert palace.encoder is not None


@pytest.mark.asyncio
async def test_store_memory(memory_palace):
    """Test storing a memory"""
    # Mock database execute
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Store memory
    memory_id = await memory_palace.store(
        "This is a test memory",
        {"test": True},
        "test_type",
        0.8
    )
    
    assert memory_id is not None
    assert mock_conn.execute.called


@pytest.mark.asyncio
async def test_store_interaction(memory_palace):
    """Test storing a conversation interaction"""
    # Mock database execute
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Store interaction
    memory_id = await memory_palace.store_interaction(
        "Hello Sarah",
        "Hello! How can I help you today?",
        {"type": "greeting", "confidence": 0.95}
    )
    
    assert memory_id is not None
    assert mock_conn.execute.called


@pytest.mark.asyncio
async def test_recall_memories(memory_palace):
    """Test recalling memories"""
    # Mock database fetch
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Mock query results
    mock_rows = [
        {
            'id': '123',
            'content': 'Test memory',
            'metadata': '{"test": true}',
            'importance': 0.7,
            'memory_type': 'test',
            'timestamp': datetime.now(),
            'access_count': 1,
            'similarity': 0.85
        }
    ]
    mock_conn.fetch.return_value = mock_rows
    
    # Recall memories
    memories = await memory_palace.recall("test query", limit=5)
    
    assert len(memories) == 1
    assert memories[0]['content'] == 'Test memory'
    assert memories[0]['metadata']['test'] is True


@pytest.mark.asyncio
async def test_get_conversation_history(memory_palace):
    """Test getting conversation history"""
    # Mock database fetch
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Mock query results
    mock_rows = [
        {
            'id': '123',
            'content': 'User: Hello\nSarah: Hi there!',
            'metadata': '{"user_input": "Hello"}',
            'timestamp': datetime.now(),
            'importance': 0.5
        }
    ]
    mock_conn.fetch.return_value = mock_rows
    
    # Get history
    history = await memory_palace.get_conversation_history(hours=24)
    
    assert len(history) == 1
    assert 'Hello' in history[0]['content']


@pytest.mark.asyncio
async def test_calculate_importance():
    """Test importance calculation"""
    palace = MemoryPalace()
    
    # Test basic importance
    importance = await palace._calculate_importance("Normal message", {})
    assert importance == 0.5
    
    # Test with important keywords
    importance = await palace._calculate_importance("Remember this important thing", {})
    assert importance > 0.5
    
    # Test with task completion
    importance = await palace._calculate_importance(
        "Task done", 
        {"task_completed": True}
    )
    assert importance >= 0.7
    
    # Test with user marked important
    importance = await palace._calculate_importance(
        "Message", 
        {"user_marked_important": True}
    )
    assert importance >= 0.9


@pytest.mark.asyncio
async def test_get_context(memory_palace):
    """Test getting formatted context"""
    # Mock recall method
    memory_palace.recall = AsyncMock()
    memory_palace.recall.return_value = [
        {
            'content': 'Memory 1 content',
            'timestamp': datetime.now() - timedelta(hours=1)
        },
        {
            'content': 'Memory 2 content',
            'timestamp': datetime.now() - timedelta(hours=2)
        }
    ]
    
    # Get context
    context = await memory_palace.get_context("test query", max_tokens=1000)
    
    assert 'Memory 1 content' in context
    assert 'Memory 2 content' in context
    assert memory_palace.recall.called


@pytest.mark.asyncio
async def test_memory_consolidation(memory_palace):
    """Test memory consolidation"""
    # Mock database execute
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.execute.return_value = "UPDATE 5"
    
    # Consolidate memories
    count = await memory_palace.consolidate_memories(days_old=7)
    
    assert count == 5
    assert mock_conn.execute.called


@pytest.mark.asyncio
async def test_search_by_timeframe(memory_palace):
    """Test searching memories by timeframe"""
    # Mock database fetch
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    start_time = datetime.now() - timedelta(days=1)
    end_time = datetime.now()
    
    mock_rows = [
        {
            'id': '123',
            'content': 'Recent memory',
            'metadata': '{}',
            'timestamp': datetime.now() - timedelta(hours=6),
            'importance': 0.6,
            'memory_type': 'conversation'
        }
    ]
    mock_conn.fetch.return_value = mock_rows
    
    # Search by timeframe
    memories = await memory_palace.search_by_timeframe(
        start_time, 
        end_time,
        ['conversation']
    )
    
    assert len(memories) == 1
    assert memories[0]['content'] == 'Recent memory'


@pytest.mark.asyncio
async def test_get_statistics(memory_palace):
    """Test getting memory statistics"""
    # Mock database fetchrow
    mock_conn = AsyncMock()
    memory_palace.pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    mock_stats = {
        'total_memories': 100,
        'memory_types': 3,
        'avg_importance': 0.65,
        'avg_access_count': 2.5,
        'latest_memory': datetime.now(),
        'oldest_memory': datetime.now() - timedelta(days=30),
        'consolidated_count': 10
    }
    mock_conn.fetchrow.return_value = mock_stats
    
    # Get statistics
    stats = await memory_palace.get_statistics()
    
    assert stats['total_memories'] == 100
    assert stats['memory_types'] == 3
    assert stats['avg_importance'] == 0.65


# Add numpy import at the top of the file
import numpy as np