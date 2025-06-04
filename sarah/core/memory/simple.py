"""
Simple Memory Palace - Without vector embeddings for initial setup
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import logging
from pathlib import Path

from sarah.config import Config

logger = logging.getLogger(__name__)


class SimpleMemory:
    """Simple JSON-based memory storage"""

    def __init__(self):
        self.memory_file = Config.MEMORY_DIR / "simple_memory.json"
        self.memories = self._load_memories()

    def _load_memories(self) -> List[Dict[str, Any]]:
        """Load memories from disk"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading memories: {e}")
        return []

    def save_to_disk(self):
        """Save memories to disk"""
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.memories, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memories: {e}")

    def load_from_disk(self):
        """Reload memories from disk"""
        self.memories = self._load_memories()

    def store(self, data: Dict[str, Any]):
        """Store a memory"""
        memory = {
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "id": len(self.memories),
        }
        self.memories.append(memory)

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple recall based on keyword matching"""
        results = []
        query_lower = query.lower()

        for memory in reversed(self.memories):  # Most recent first
            memory_str = json.dumps(memory).lower()
            if query_lower in memory_str:
                results.append(memory)
                if len(results) >= limit:
                    break

        return results

    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get most recent memories"""
        return list(reversed(self.memories[-count:]))


class SimpleMemoryPalace:
    """Simple in-memory storage for initial testing"""

    def __init__(self):
        self.memories = []
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the memory system"""
        logger.info("📚 Initializing Simple Memory Palace...")
        self.initialized = True
        logger.info("✅ Simple Memory Palace initialized")

    async def store_interaction(
        self, user_input: str, response: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store an interaction in memory"""
        memory = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "response": response,
            "id": len(self.memories),
        }
        self.memories.append(memory)
        logger.debug(f"Stored memory #{memory['id']}")

    async def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple recall based on keyword matching"""
        results = []
        query_lower = query.lower()

        for memory in reversed(self.memories):  # Most recent first
            if query_lower in memory["user_input"].lower():
                results.append(memory)
                if len(results) >= limit:
                    break

        return results

    async def get_conversation_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        # For simple implementation, just return last N memories
        return list(reversed(self.memories[-50:]))
