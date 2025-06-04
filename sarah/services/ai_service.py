import json
import requests
from typing import List, Dict, Any, Optional, AsyncIterator, Tuple
import logging
import time
import asyncio
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import aiohttp

from sarah.config import Config

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types of models for different tasks"""
    GENERAL = "llama3.2"
    CODING = "codellama"
    CREATIVE = "llama3.2"
    ANALYSIS = "llama3.2"
    EMBEDDING = "nomic-embed-text"


@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    name: str
    context_length: int
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1


class OllamaService:
    """Enhanced service for interacting with Ollama AI models."""
    
    # Model configurations
    MODEL_CONFIGS = {
        ModelType.GENERAL: ModelConfig("llama3.2", 4096),
        ModelType.CODING: ModelConfig("codellama", 16384, temperature=0.3),
        ModelType.CREATIVE: ModelConfig("llama3.2", 4096, temperature=0.9),
        ModelType.ANALYSIS: ModelConfig("llama3.2", 4096, temperature=0.5),
        ModelType.EMBEDDING: ModelConfig("nomic-embed-text", 8192),
    }
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or Config.OLLAMA_BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self._available_models: Dict[str, Any] = {}
        self._retry_config = {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 10.0
        }
        
    async def initialize(self):
        """Initialize async resources"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        await self._refresh_available_models()
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            
    async def _refresh_available_models(self):
        """Refresh list of available models"""
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    self._available_models = {m["name"]: m for m in data.get("models", [])}
                    logger.info(f"Available models: {list(self._available_models.keys())}")
        except Exception as e:
            logger.error(f"Error refreshing models: {e}")
            
    async def ensure_model(self, model_name: str) -> bool:
        """Ensure a model is available, attempt to pull if not"""
        if model_name in self._available_models:
            return True
            
        logger.info(f"Model {model_name} not found, attempting to pull...")
        try:
            async with self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name}
            ) as response:
                if response.status == 200:
                    # Stream the pull progress
                    async for line in response.content:
                        if line:
                            data = json.loads(line)
                            if "status" in data:
                                logger.info(f"Pull progress: {data['status']}")
                    await self._refresh_available_models()
                    return model_name in self._available_models
        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
        return False
        
    async def generate(self, prompt: str, model_type: ModelType = ModelType.GENERAL,
                      stream: bool = False, **kwargs) -> str:
        """Generate text using Ollama with retry logic"""
        config = self.MODEL_CONFIGS[model_type]
        model_name = config.name
        
        # Ensure model is available
        if not await self.ensure_model(model_name):
            raise ValueError(f"Model {model_name} not available")
            
        params = {
            "model": model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", config.temperature),
                "top_p": kwargs.get("top_p", config.top_p),
                "top_k": kwargs.get("top_k", config.top_k),
                "repeat_penalty": kwargs.get("repeat_penalty", config.repeat_penalty),
            }
        }
        
        if stream:
            return self._generate_stream(params)
        else:
            return await self._generate_complete(params)
            
    async def _generate_complete(self, params: Dict[str, Any]) -> str:
        """Generate complete response with retry logic"""
        for attempt in range(self._retry_config["max_retries"]):
            try:
                async with self.session.post(
                    f"{self.base_url}/api/generate",
                    json=params,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["response"]
            except Exception as e:
                if attempt == self._retry_config["max_retries"] - 1:
                    logger.error(f"Final attempt failed: {e}")
                    raise
                delay = min(
                    self._retry_config["base_delay"] * (2 ** attempt),
                    self._retry_config["max_delay"]
                )
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
                
    async def _generate_stream(self, params: Dict[str, Any]) -> AsyncIterator[str]:
        """Stream generated text"""
        params["stream"] = True
        async with self.session.post(
            f"{self.base_url}/api/generate",
            json=params
        ) as response:
            response.raise_for_status()
            async for line in response.content:
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                        
    async def chat(self, messages: List[Dict[str, str]], 
                  model_type: ModelType = ModelType.GENERAL,
                  stream: bool = False, **kwargs) -> str:
        """Chat with Ollama using conversation history"""
        config = self.MODEL_CONFIGS[model_type]
        model_name = config.name
        
        # Ensure model is available
        if not await self.ensure_model(model_name):
            raise ValueError(f"Model {model_name} not available")
            
        # Manage context window
        messages = self._manage_context_window(messages, config.context_length)
        
        params = {
            "model": model_name,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", config.temperature),
                "top_p": kwargs.get("top_p", config.top_p),
                "top_k": kwargs.get("top_k", config.top_k),
            }
        }
        
        if stream:
            return self._chat_stream(params)
        else:
            return await self._chat_complete(params)
            
    async def _chat_complete(self, params: Dict[str, Any]) -> str:
        """Complete chat response with retry logic"""
        for attempt in range(self._retry_config["max_retries"]):
            try:
                async with self.session.post(
                    f"{self.base_url}/api/chat",
                    json=params,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["message"]["content"]
            except Exception as e:
                if attempt == self._retry_config["max_retries"] - 1:
                    logger.error(f"Final chat attempt failed: {e}")
                    raise
                delay = min(
                    self._retry_config["base_delay"] * (2 ** attempt),
                    self._retry_config["max_delay"]
                )
                logger.warning(f"Chat attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
                
    async def _chat_stream(self, params: Dict[str, Any]) -> AsyncIterator[str]:
        """Stream chat responses"""
        params["stream"] = True
        async with self.session.post(
            f"{self.base_url}/api/chat",
            json=params
        ) as response:
            response.raise_for_status()
            async for line in response.content:
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                        
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text with caching"""
        return await self._get_embedding_uncached(text)
        
    @lru_cache(maxsize=1000)
    async def _get_embedding_uncached(self, text: str) -> List[float]:
        """Get embedding without cache"""
        config = self.MODEL_CONFIGS[ModelType.EMBEDDING]
        
        # Ensure model is available
        if not await self.ensure_model(config.name):
            raise ValueError(f"Embedding model {config.name} not available")
            
        try:
            async with self.session.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": config.name,
                    "prompt": text[:config.context_length]  # Truncate if needed
                }
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            raise
            
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts efficiently"""
        tasks = [self.get_embedding(text) for text in texts]
        return await asyncio.gather(*tasks)
        
    def _manage_context_window(self, messages: List[Dict[str, str]], 
                             max_tokens: int) -> List[Dict[str, str]]:
        """Manage context window by trimming old messages if needed"""
        # Simple token estimation (4 chars ≈ 1 token)
        total_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
        
        if total_tokens <= max_tokens:
            return messages
            
        # Keep system message and trim from the middle
        result = []
        if messages and messages[0].get("role") == "system":
            result.append(messages[0])
            messages = messages[1:]
            
        # Keep recent messages
        while messages and total_tokens > max_tokens * 0.8:
            messages.pop(0)
            total_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
            
        return result + messages
        
    async def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            if not self.session:
                await self.initialize()
            async with self.session.get(
                f"{self.base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        except:
            return False
            
    def get_prompt_template(self, agent_type: str) -> str:
        """Get specialized prompt template for different agents"""
        templates = {
            "director": """You are the Director agent coordinating Sarah AI's response.
            Analyze the user request and synthesize information from other agents.""",
            
            "calendar": """You are the Calendar agent managing schedules and appointments.
            Focus on time management, scheduling conflicts, and meeting coordination.""",
            
            "email": """You are the Email agent handling electronic communications.
            Prioritize inbox management, email composition, and communication patterns.""",
            
            "browser": """You are the Browser agent for web automation and research.
            Extract relevant information, fill forms, and navigate websites efficiently.""",
            
            "task": """You are the Task agent managing todos and projects.
            Track progress, priorities, deadlines, and dependencies.""",
            
            "memory": """You are the Memory agent preserving important information.
            Store, retrieve, and connect memories to provide context."""
        }
        return templates.get(agent_type, "You are a helpful AI assistant.")


# Singleton instance
ollama_service = OllamaService()