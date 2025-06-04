# Sarah AI Agent Communication Protocol

## Message Structure

```python
@dataclass
class AgentMessage:
    id: str
    from_agent: str
    to_agent: str  # Can be "broadcast"
    timestamp: datetime
    message_type: MessageType
    payload: Dict[str, Any]
    priority: Priority
    requires_response: bool
    correlation_id: Optional[str]

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
```

## Agent Hierarchy & Responsibilities

### Sarah (Consciousness)
- Routes intents to Director
- Maintains conversation context
- Final response aggregation

### Director Agent
- Orchestrates other agents
- Delegates tasks based on intent
- Monitors agent health

### Worker Agents
- **Calendar**: Meeting scheduling, reminders
- **Email**: Read, compose, categorize
- **Browser**: Web automation, data extraction
- **Task**: Todo management, project tracking
- **Memory**: Store and retrieve memories
- **Home**: IoT device control
- **Finance**: Budget tracking, bill reminders

## Communication Patterns

### Request-Response
```
User -> Sarah -> Director -> Agent -> Director -> Sarah -> User
```

### Event Broadcasting
```
Agent -> Redis Pub/Sub -> All Subscribed Agents
```

### Escalation
```
Worker -> Manager -> Director -> Sarah -> User
```

## Redis Channel Structure

```
# Command channels
sarah:agent:{agent_id}:commands
sarah:agent:{agent_id}:responses

# Event channels
sarah:events:system
sarah:events:user:{user_id}

# Broadcast channel
sarah:broadcast:all
```