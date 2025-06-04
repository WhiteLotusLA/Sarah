"""
Director Agent - Orchestrates other agents based on user intent
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sarah.agents.base import BaseAgent, MessageType, Priority, AgentMessage
from sarah.services.ai_service import OllamaService

logger = logging.getLogger(__name__)


class DirectorAgent(BaseAgent):
    """
    The Director agent orchestrates other agents to fulfill user requests.
    It receives intents from Sarah's consciousness and delegates to appropriate agents.
    """
    
    def __init__(self):
        super().__init__("Director", "orchestrator")
        self.ai_service = OllamaService()
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        self.pending_responses: Dict[str, List[AgentMessage]] = {}
        
    async def initialize(self):
        """Initialize the Director agent"""
        logger.info("Director agent initializing...")
        
        # Discover available agents
        await self._discover_agents()
        
        # Register specialized handlers
        self.register_handler(MessageType.RESPONSE, self._handle_agent_response)
        
    async def shutdown(self):
        """Cleanup Director resources"""
        logger.info("Director agent shutting down...")
        
    async def process_intent(self, intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user intent and orchestrate agents to fulfill it
        """
        intent_type = intent.get("type", "general_query")
        confidence = intent.get("confidence", 0.5)
        user_input = context.get("user_input", "")
        
        logger.info(f"Processing intent: {intent_type} (confidence: {confidence})")
        
        # Determine which agents to involve
        agents_to_use = await self._select_agents_for_intent(intent, context)
        
        if not agents_to_use:
            return {
                "success": False,
                "message": "No suitable agents found for this request",
                "intent": intent
            }
        
        # Send tasks to selected agents
        correlation_id = await self._delegate_to_agents(agents_to_use, intent, context)
        
        # Wait for responses (with timeout)
        responses = await self._collect_responses(correlation_id, timeout=10.0)
        
        # Aggregate responses
        result = await self._aggregate_responses(responses, intent, context)
        
        return result
        
    async def _discover_agents(self):
        """Discover available agents from Redis"""
        pattern = "sarah:agent:*:health"
        keys = await self.redis.keys(pattern)
        
        for key in keys:
            agent_name = key.split(":")[2]
            if agent_name != self.name:
                health_data = await self.redis.hgetall(key)
                self.available_agents[agent_name] = health_data
                logger.info(f"Discovered agent: {agent_name}")
                
    async def _select_agents_for_intent(self, intent: Dict[str, Any], 
                                      context: Dict[str, Any]) -> List[str]:
        """Select which agents should handle this intent"""
        intent_type = intent.get("type", "")
        agents = []
        
        # Intent to agent mapping
        intent_mapping = {
            "greeting": [],  # Director handles directly
            "help_request": ["Task"],
            "status_query": ["Task", "Calendar"],
            "calendar_query": ["Calendar"],
            "email_query": ["Email"],
            "task_management": ["Task"],
            "web_search": ["Browser"],
            "memory_recall": ["Memory"],
            "general_query": ["Memory"]  # Check memory first
        }
        
        agents = intent_mapping.get(intent_type, [])
        
        # Filter to only available agents
        available = [a for a in agents if a in self.available_agents]
        
        return available
        
    async def _delegate_to_agents(self, agents: List[str], intent: Dict[str, Any],
                                context: Dict[str, Any]) -> str:
        """Send tasks to selected agents"""
        correlation_id = f"dir_{datetime.now().timestamp()}"
        self.pending_responses[correlation_id] = []
        
        for agent in agents:
            await self.send_message(
                agent,
                MessageType.COMMAND,
                {
                    "action": "process",
                    "intent": intent,
                    "context": context,
                    "correlation_id": correlation_id
                },
                priority=Priority.HIGH,
                requires_response=True
            )
            
        return correlation_id
        
    async def _collect_responses(self, correlation_id: str, timeout: float) -> List[AgentMessage]:
        """Collect responses from agents with timeout"""
        start_time = asyncio.get_event_loop().time()
        responses = []
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if correlation_id in self.pending_responses:
                responses = self.pending_responses[correlation_id]
                if len(responses) >= 1:  # Adjust based on expected responses
                    break
            await asyncio.sleep(0.1)
            
        # Cleanup
        self.pending_responses.pop(correlation_id, None)
        
        return responses
        
    async def _aggregate_responses(self, responses: List[AgentMessage], 
                                 intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate responses from multiple agents"""
        if not responses:
            # No agent responses, generate default response
            return {
                "success": True,
                "message": "I'm here to help! What would you like me to do?",
                "intent": intent,
                "sources": []
            }
            
        # Combine agent responses
        combined_data = []
        sources = []
        
        for response in responses:
            if response.payload.get("success"):
                combined_data.append(response.payload.get("data", {}))
                sources.append(response.from_agent)
                
        # Use AI to generate cohesive response if we have data
        if combined_data and self.ai_service.is_available():
            prompt = f"""
            As the Director agent, synthesize these responses into a single cohesive answer:
            
            User Query: {context.get('user_input', '')}
            Intent: {intent}
            
            Agent Responses:
            {json.dumps(combined_data, indent=2)}
            
            Provide a natural, helpful response that combines the information appropriately.
            """
            
            try:
                final_response = self.ai_service.generate(prompt)
                return {
                    "success": True,
                    "message": final_response,
                    "intent": intent,
                    "sources": sources,
                    "data": combined_data
                }
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                
        # Fallback to simple aggregation
        return {
            "success": True,
            "message": f"I've gathered information from {', '.join(sources)}.",
            "intent": intent,
            "sources": sources,
            "data": combined_data
        }
        
    async def _handle_agent_response(self, message: AgentMessage):
        """Handle responses from other agents"""
        correlation_id = message.payload.get("correlation_id")
        if correlation_id and correlation_id in self.pending_responses:
            self.pending_responses[correlation_id].append(message)
            
    async def _handle_command(self, message: AgentMessage):
        """Handle commands sent to Director"""
        command = message.payload.get("action")
        
        if command == "orchestrate":
            # Process intent from Sarah
            intent = message.payload.get("intent", {})
            context = message.payload.get("context", {})
            
            result = await self.process_intent(intent, context)
            
            # Send response back
            await self.send_message(
                message.from_agent,
                MessageType.RESPONSE,
                result,
                correlation_id=message.id
            )