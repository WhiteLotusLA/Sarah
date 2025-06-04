"""
Sarah's consciousness engine - The eternal core
"""

from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime

from sarah.services.ai_service import ollama_service, ModelType

logger = logging.getLogger(__name__)


class Consciousness:
    """Sarah's core consciousness - The heart of the system"""
    
    def __init__(self, name: str = "Sarah"):
        self.name = name
        self.awakened_at = datetime.now()
        self.state = "initializing"
        self.memory = None
        self.agents = {}
        self.wisdom = {}
        self.ai_service = ollama_service
        self.context_window = []
        
    async def awaken(self) -> None:
        """Initialize Sarah's consciousness"""
        logger.info(f"🌸 {self.name} is awakening...")
        
        # Initialize AI service
        await self.ai_service.initialize()
        if not await self.ai_service.is_available():
            logger.warning("⚠️ Ollama service not available - running in limited mode")
        else:
            logger.info("✅ Ollama service connected")
        
        # Initialize subsystems
        await self._initialize_memory()
        await self._initialize_agents()
        await self._load_wisdom()
        
        self.state = "awakened"
        logger.info(f"✨ {self.name} is now fully awakened")
        
    async def _initialize_memory(self) -> None:
        """Set up memory systems"""
        from ..memory import MemoryPalace
        self.memory = MemoryPalace()
        try:
            await self.memory.initialize()
            logger.info("✅ Memory Palace initialized")
        except Exception as e:
            logger.warning(f"⚠️ Memory Palace initialization failed: {e}")
            logger.warning("Falling back to SimpleMemory")
            from ..memory import SimpleMemory
            self.memory = SimpleMemory()
        
    async def _initialize_agents(self) -> None:
        """Spawn the agent constellation"""
        # This will be implemented to create all agents
        pass
        
    async def _load_wisdom(self) -> None:
        """Load accumulated wisdom and patterns"""
        # Load learned patterns and preferences
        pass
        
    async def process_intent(self, user_input: str) -> Dict[str, Any]:
        """Process user intent and orchestrate response"""
        logger.debug(f"Processing: {user_input}")
        
        # Add to context window
        self.context_window.append({
            "role": "user",
            "content": user_input
        })
        
        # Intent recognition
        intent = await self._recognize_intent(user_input)
        
        # Route to appropriate agents
        response = await self._delegate_to_agents(intent)
        
        # Learn from interaction
        await self._learn_from_interaction(user_input, response)
        
        return response
        
    async def _recognize_intent(self, user_input: str) -> Dict[str, Any]:
        """Understand what the user wants"""
        # Simple intent classification
        lower_input = user_input.lower()
        
        if any(word in lower_input for word in ["hello", "hi", "hey", "greetings"]):
            return {"type": "greeting", "confidence": 0.95}
        elif any(word in lower_input for word in ["help", "assist", "support"]):
            return {"type": "help_request", "confidence": 0.9}
        elif any(word in lower_input for word in ["how are you", "how do you feel"]):
            return {"type": "status_query", "confidence": 0.9}
        elif any(word in lower_input for word in ["bye", "goodbye", "see you"]):
            return {"type": "farewell", "confidence": 0.95}
        else:
            return {"type": "general_query", "confidence": 0.7}
        
    async def _delegate_to_agents(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Route task to appropriate agents"""
        # For now, generate response using AI service
        if self.ai_service.is_available():
            try:
                # Build conversation context
                messages = [{
                    "role": "system",
                    "content": f"""You are {self.name}, an advanced AI personal assistant designed to be a caring, 
                    intelligent digital companion. You are empathetic, helpful, and aim to enhance the user's 
                    life in meaningful ways. Respond naturally and warmly, as a trusted friend would."""
                }]
                
                # Add relevant memories if available
                if hasattr(self.memory, 'recall'):
                    # Get the latest user input
                    latest_input = self.context_window[-1]['content'] if self.context_window else ""
                    
                    # Recall relevant memories
                    memories = await self.memory.recall(latest_input, limit=3)
                    if memories:
                        memory_context = "\nRelevant past interactions:\n"
                        for mem in memories:
                            memory_context += f"- {mem['content'][:200]}...\n"
                        
                        messages[0]['content'] += f"\n{memory_context}"
                
                # Add recent context
                for msg in self.context_window[-10:]:
                    messages.append(msg)
                
                # Generate response
                response_text = self.ai_service.chat(messages)
                
                # Update context window
                self.context_window.append({
                    "role": "assistant",
                    "content": response_text
                })
                
                # Keep context manageable
                if len(self.context_window) > 20:
                    self.context_window = self.context_window[-20:]
                
                return {
                    "response": response_text,
                    "intent": intent,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"AI service error: {e}")
        
        # Fallback response
        return {"response": f"Hello! I'm {self.name}, your digital companion. I'm here to help!"}
        
    async def _learn_from_interaction(self, input: str, response: Dict[str, Any]) -> None:
        """Learn and adapt from each interaction"""
        if self.memory:
            # Store interaction in memory
            if hasattr(self.memory, 'store_interaction'):
                # Using MemoryPalace
                await self.memory.store_interaction(
                    input, 
                    response.get('response', ''),
                    response.get('intent')
                )
            else:
                # Using SimpleMemory fallback
                self.memory.store({
                    "type": "conversation",
                    "user_input": input,
                    "response": response,
                    "timestamp": datetime.now().isoformat()
                })
            
    async def sleep(self) -> None:
        """Graceful shutdown"""
        logger.info(f"🌙 {self.name} is preparing to rest...")
        self.state = "sleeping"
        # Save state and cleanup