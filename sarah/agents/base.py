"""
Base Agent class for Sarah AI
"""

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
import redis.asyncio as redis

from sarah.config import Config

logger = logging.getLogger(__name__)


class MessageType(Enum):
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class AgentMessage:
    id: str
    from_agent: str
    to_agent: str  # Can be "broadcast"
    timestamp: datetime
    message_type: MessageType
    payload: Dict[str, Any]
    priority: Priority = Priority.NORMAL
    requires_response: bool = False
    correlation_id: Optional[str] = None

    def to_json(self) -> str:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['message_type'] = self.message_type.value
        data['priority'] = self.priority.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> 'AgentMessage':
        obj = json.loads(data)
        obj['timestamp'] = datetime.fromisoformat(obj['timestamp'])
        obj['message_type'] = MessageType(obj['message_type'])
        obj['priority'] = Priority(obj['priority'])
        return cls(**obj)


class BaseAgent(ABC):
    """Base class for all Sarah AI agents"""
    
    def __init__(self, name: str, agent_type: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.agent_type = agent_type
        self.redis: Optional[redis.Redis] = None
        self.running = False
        self._handlers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._setup_default_handlers()
        
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting {self.name} agent ({self.agent_type})")
        
        # Connect to Redis
        self.redis = await redis.from_url(
            f"redis://localhost:{Config.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True
        )
        
        # Start heartbeat
        asyncio.create_task(self._heartbeat_loop())
        
        # Start message listener
        asyncio.create_task(self._listen_for_messages())
        
        # Agent-specific initialization
        await self.initialize()
        
        self.running = True
        logger.info(f"{self.name} agent started successfully")
        
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping {self.name} agent")
        self.running = False
        await self.shutdown()
        if self.redis:
            await self.redis.close()
        logger.info(f"{self.name} agent stopped")
        
    @abstractmethod
    async def initialize(self):
        """Initialize agent-specific resources"""
        pass
        
    @abstractmethod
    async def shutdown(self):
        """Cleanup agent-specific resources"""
        pass
        
    async def send_message(self, to_agent: str, message_type: MessageType, 
                         payload: Dict[str, Any], priority: Priority = Priority.NORMAL,
                         requires_response: bool = False) -> Optional[str]:
        """Send a message to another agent"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=self.name,
            to_agent=to_agent,
            timestamp=datetime.now(),
            message_type=message_type,
            payload=payload,
            priority=priority,
            requires_response=requires_response
        )
        
        channel = f"sarah:agent:{to_agent}:commands" if to_agent != "broadcast" else "sarah:broadcast:all"
        await self.redis.publish(channel, message.to_json())
        
        logger.debug(f"{self.name} sent {message_type.value} to {to_agent}")
        return message.id if requires_response else None
        
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a message handler"""
        self._handlers[message_type].append(handler)
        
    async def _listen_for_messages(self):
        """Listen for incoming messages"""
        pubsub = self.redis.pubsub()
        channels = [
            f"sarah:agent:{self.name}:commands",
            "sarah:broadcast:all"
        ]
        await pubsub.subscribe(*channels)
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    agent_message = AgentMessage.from_json(message['data'])
                    await self._handle_message(agent_message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    
    async def _handle_message(self, message: AgentMessage):
        """Handle incoming message"""
        handlers = self._handlers.get(message.message_type, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                if message.requires_response:
                    await self.send_message(
                        message.from_agent,
                        MessageType.ERROR,
                        {"error": str(e)},
                        correlation_id=message.id
                    )
                    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            await self.redis.hset(
                f"sarah:agent:{self.name}:health",
                mapping={
                    "status": "active",
                    "last_heartbeat": datetime.now().isoformat(),
                    "id": self.id
                }
            )
            await self.redis.expire(f"sarah:agent:{self.name}:health", 30)
            await asyncio.sleep(10)
            
    def _setup_default_handlers(self):
        """Setup default message handlers"""
        self.register_handler(MessageType.QUERY, self._handle_query)
        self.register_handler(MessageType.COMMAND, self._handle_command)
        
    async def _handle_query(self, message: AgentMessage):
        """Default query handler"""
        if message.payload.get("type") == "status":
            await self.send_message(
                message.from_agent,
                MessageType.RESPONSE,
                {
                    "status": "active",
                    "name": self.name,
                    "type": self.agent_type
                },
                correlation_id=message.id
            )
            
    async def _handle_command(self, message: AgentMessage):
        """Default command handler - override in subclasses"""
        logger.warning(f"Unhandled command: {message.payload}")