# Sarah AI Database Schema

## PostgreSQL with TimescaleDB & pgvector

### Core Tables

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    summary TEXT
);

-- Messages table (TimescaleDB hypertable)
CREATE TABLE messages (
    id UUID DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (timestamp, id)
);
SELECT create_hypertable('messages', 'timestamp');

-- Memories table with vector embeddings
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(384), -- for all-MiniLM-L6-v2
    importance FLOAT DEFAULT 0.5,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    memory_type VARCHAR(50) -- 'conversation', 'task', 'fact', 'preference'
);

-- Agents table
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'inactive',
    last_heartbeat TIMESTAMPTZ,
    config JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}'
);

-- Tasks table
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    due_date TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID REFERENCES agents(id),
    assigned_to UUID REFERENCES agents(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent messages table (for inter-agent communication)
CREATE TABLE agent_messages (
    id UUID DEFAULT gen_random_uuid(),
    from_agent_id UUID REFERENCES agents(id),
    to_agent_id UUID REFERENCES agents(id),
    message_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed BOOLEAN DEFAULT false,
    PRIMARY KEY (timestamp, id)
);
SELECT create_hypertable('agent_messages', 'timestamp');

-- Indexes
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_memories_user_timestamp ON memories (user_id, timestamp DESC);
CREATE INDEX idx_messages_conversation ON messages (conversation_id, timestamp DESC);
CREATE INDEX idx_tasks_user_status ON tasks (user_id, status);
CREATE INDEX idx_agent_messages_to_agent ON agent_messages (to_agent_id, processed, timestamp DESC);
```

## Redis Structure

```
# Agent pub/sub channels
agent:{agent_id}:commands
agent:{agent_id}:responses
agent:broadcast

# User session data
session:{session_id}

# Task queues
queue:high_priority
queue:normal_priority
queue:low_priority

# Agent health
agent:{agent_id}:health

# Rate limiting
rate_limit:{user_id}:{endpoint}
```