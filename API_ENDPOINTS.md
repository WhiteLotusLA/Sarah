# Sarah AI API Endpoints

## Authentication
```
POST   /api/auth/login          {username, password} -> {token}
POST   /api/auth/logout         
POST   /api/auth/refresh        {refresh_token} -> {token}
POST   /api/auth/register       {username, email, password}
```

## Core Interaction
```
POST   /api/chat                {message} -> {response, intent, confidence}
WS     /ws                      Real-time bidirectional communication
GET    /api/conversations       List user conversations
GET    /api/conversations/:id   Get conversation history
DELETE /api/conversations/:id   Delete conversation
```

## Agents
```
GET    /api/agents              List all agents and status
GET    /api/agents/:id          Get agent details
POST   /api/agents/:id/command  Send command to specific agent
GET    /api/agents/:id/health   Get agent health metrics
```

## Tasks
```
GET    /api/tasks               List tasks with filters
POST   /api/tasks               Create new task
PUT    /api/tasks/:id           Update task
DELETE /api/tasks/:id           Delete task
POST   /api/tasks/:id/complete  Mark task complete
```

## Memory
```
POST   /api/memory/search       {query} -> {memories[]}
POST   /api/memory/store        {content, type, metadata}
GET    /api/memory/recent       Get recent memories
DELETE /api/memory/:id          Delete specific memory
```

## User Settings
```
GET    /api/settings            Get user settings
PUT    /api/settings            Update settings
GET    /api/settings/agents     Get agent preferences
PUT    /api/settings/agents     Update agent preferences
```

## System
```
GET    /api/health              System health check
GET    /api/metrics             System metrics
GET    /api/version             API version info
```