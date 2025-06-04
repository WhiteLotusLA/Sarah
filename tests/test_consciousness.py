"""
Unit tests for Sarah's Consciousness engine
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from sarah.core.consciousness import Consciousness


@pytest.fixture
async def consciousness():
    """Create a test Consciousness instance"""
    sarah = Consciousness("TestSarah")
    # Mock AI service
    sarah.ai_service = Mock()
    sarah.ai_service.is_available = Mock(return_value=True)
    sarah.ai_service.chat = Mock(return_value="Test response")
    yield sarah


@pytest.mark.asyncio
async def test_consciousness_initialization(consciousness):
    """Test Consciousness initialization"""
    assert consciousness.name == "TestSarah"
    assert consciousness.state == "initializing"
    assert consciousness.awakened_at is not None


@pytest.mark.asyncio
async def test_awaken():
    """Test awakening process"""
    with patch('sarah.core.consciousness.ollama_service') as mock_ai:
        mock_ai.initialize = AsyncMock()
        mock_ai.is_available = AsyncMock(return_value=True)
        
        sarah = Consciousness()
        
        # Mock memory initialization
        with patch.object(sarah, '_initialize_memory', AsyncMock()):
            with patch.object(sarah, '_initialize_agents', AsyncMock()):
                with patch.object(sarah, '_load_wisdom', AsyncMock()):
                    await sarah.awaken()
        
        assert sarah.state == "awakened"


@pytest.mark.asyncio
async def test_intent_recognition(consciousness):
    """Test intent recognition"""
    # Test greeting
    intent = await consciousness._recognize_intent("Hello Sarah!")
    assert intent['type'] == 'greeting'
    assert intent['confidence'] >= 0.9
    
    # Test help request
    intent = await consciousness._recognize_intent("Can you help me?")
    assert intent['type'] == 'help_request'
    
    # Test status query
    intent = await consciousness._recognize_intent("How are you feeling?")
    assert intent['type'] == 'status_query'
    
    # Test farewell
    intent = await consciousness._recognize_intent("Goodbye!")
    assert intent['type'] == 'farewell'
    
    # Test general query
    intent = await consciousness._recognize_intent("What's the weather?")
    assert intent['type'] == 'general_query'


@pytest.mark.asyncio
async def test_process_intent(consciousness):
    """Test processing user intent"""
    # Mock memory
    consciousness.memory = Mock()
    consciousness.memory.store_interaction = AsyncMock()
    
    # Process intent
    response = await consciousness.process_intent("Hello Sarah!")
    
    assert 'response' in response
    assert 'intent' in response
    assert 'timestamp' in response
    assert response['response'] == "Test response"


@pytest.mark.asyncio
async def test_context_window_management(consciousness):
    """Test context window management"""
    # Add messages to context
    for i in range(25):
        consciousness.context_window.append({
            "role": "user",
            "content": f"Message {i}"
        })
    
    # Process a new message
    await consciousness.process_intent("New message")
    
    # Check context window is trimmed
    assert len(consciousness.context_window) <= 20


@pytest.mark.asyncio
async def test_delegate_to_agents_with_memory(consciousness):
    """Test delegation with memory recall"""
    # Mock memory with recall
    consciousness.memory = Mock()
    consciousness.memory.recall = AsyncMock(return_value=[
        {
            'content': 'Previous interaction about weather',
            'similarity': 0.85
        }
    ])
    
    # Add context
    consciousness.context_window = [{
        "role": "user",
        "content": "What's the weather like?"
    }]
    
    # Delegate
    response = await consciousness._delegate_to_agents({"type": "general_query"})
    
    assert 'response' in response
    assert consciousness.memory.recall.called


@pytest.mark.asyncio
async def test_learn_from_interaction_with_memory_palace(consciousness):
    """Test learning with MemoryPalace"""
    # Mock MemoryPalace
    consciousness.memory = Mock()
    consciousness.memory.store_interaction = AsyncMock()
    
    # Learn from interaction
    response = {
        'response': 'Test response',
        'intent': {'type': 'greeting'}
    }
    await consciousness._learn_from_interaction("Hello", response)
    
    assert consciousness.memory.store_interaction.called


@pytest.mark.asyncio
async def test_learn_from_interaction_with_simple_memory(consciousness):
    """Test learning with SimpleMemory fallback"""
    # Mock SimpleMemory (no store_interaction method)
    consciousness.memory = Mock()
    consciousness.memory.store = Mock()
    
    # Learn from interaction
    response = {
        'response': 'Test response',
        'intent': {'type': 'greeting'}
    }
    await consciousness._learn_from_interaction("Hello", response)
    
    assert consciousness.memory.store.called


@pytest.mark.asyncio
async def test_sleep(consciousness):
    """Test sleep/shutdown process"""
    await consciousness.sleep()
    assert consciousness.state == "sleeping"


@pytest.mark.asyncio
async def test_ai_service_unavailable(consciousness):
    """Test behavior when AI service is unavailable"""
    # Make AI service unavailable
    consciousness.ai_service.is_available = Mock(return_value=False)
    
    # Process intent
    response = await consciousness.process_intent("Hello")
    
    # Should return fallback response
    assert "digital companion" in response['response']


@pytest.mark.asyncio
async def test_ai_service_error(consciousness):
    """Test error handling in AI service"""
    # Make AI service throw error
    consciousness.ai_service.chat = Mock(side_effect=Exception("AI Error"))
    
    # Process intent
    response = await consciousness.process_intent("Hello")
    
    # Should return fallback response
    assert "digital companion" in response['response']


@pytest.mark.asyncio
async def test_memory_initialization_failure():
    """Test graceful fallback when MemoryPalace fails"""
    sarah = Consciousness()
    
    # Mock MemoryPalace to fail
    with patch('sarah.core.memory.MemoryPalace') as mock_palace:
        mock_palace.return_value.initialize = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        
        await sarah._initialize_memory()
        
        # Should fall back to SimpleMemory
        assert sarah.memory is not None
        assert hasattr(sarah.memory, 'store')  # SimpleMemory has store method