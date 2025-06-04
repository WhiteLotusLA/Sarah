"""
Advanced Memory Palace with vector embeddings for semantic search
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

import asyncpg
from sentence_transformers import SentenceTransformer
import numpy as np
from pgvector.asyncpg import register_vector

logger = logging.getLogger(__name__)


class MemoryPalace:
    """
    Sarah's long-term memory system with vector embeddings
    
    Features:
    - Semantic search using vector embeddings
    - Automatic importance scoring
    - Memory consolidation and pruning
    - Context-aware recall
    """
    
    def __init__(self, connection_string: str = "postgresql://localhost/sarah_db"):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
        self.encoder: Optional[SentenceTransformer] = None
        self.initialized = False
        self.embedding_dim = 384  # MiniLM outputs 384 dimensions
        
    async def initialize(self) -> None:
        """Initialize the memory system"""
        logger.info("📚 Initializing Memory Palace...")
        
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Register pgvector extension
            async with self.pool.acquire() as conn:
                await register_vector(conn)
                
            # Initialize sentence encoder
            logger.info("Loading sentence transformer model...")
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Ensure tables exist with proper schema
            await self._ensure_tables()
            
            self.initialized = True
            logger.info("✅ Memory Palace initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Memory Palace: {e}")
            raise
            
    async def _ensure_tables(self) -> None:
        """Ensure memory tables exist with proper schema"""
        async with self.pool.acquire() as conn:
            # Check if memories table exists
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'memories'
                );
            """)
            
            if not exists:
                logger.info("Creating memories table...")
                await conn.execute("""
                    CREATE TABLE memories (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        timestamp TIMESTAMPTZ DEFAULT NOW(),
                        content TEXT NOT NULL,
                        embedding vector(384),
                        metadata JSONB DEFAULT '{}',
                        importance FLOAT DEFAULT 0.5,
                        memory_type VARCHAR(50) DEFAULT 'conversation',
                        access_count INTEGER DEFAULT 0,
                        last_accessed TIMESTAMPTZ DEFAULT NOW(),
                        decay_rate FLOAT DEFAULT 0.01,
                        consolidated BOOLEAN DEFAULT FALSE
                    );
                    
                    CREATE INDEX memories_embedding_idx 
                    ON memories USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                    
                    CREATE INDEX memories_timestamp_idx 
                    ON memories (timestamp DESC);
                    
                    CREATE INDEX memories_importance_idx 
                    ON memories (importance DESC);
                    
                    CREATE INDEX memories_type_idx 
                    ON memories (memory_type);
                """)
            else:
                # Check if embedding column exists
                has_embedding = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'memories' 
                        AND column_name = 'embedding'
                    );
                """)
                
                if not has_embedding:
                    logger.info("Adding embedding column to memories table...")
                    await conn.execute("""
                        ALTER TABLE memories 
                        ADD COLUMN embedding vector(384);
                        
                        CREATE INDEX memories_embedding_idx 
                        ON memories USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100);
                    """)
                    
    async def store(self, content: str, metadata: Dict[str, Any] = None, 
                   memory_type: str = "conversation", importance: float = None) -> str:
        """
        Store a memory with its embedding
        
        Args:
            content: The memory content
            metadata: Additional metadata
            memory_type: Type of memory (conversation, task, knowledge, etc.)
            importance: Manual importance override (0-1)
            
        Returns:
            Memory ID
        """
        if not self.initialized:
            raise RuntimeError("Memory Palace not initialized")
            
        # Generate embedding
        embedding = self.encoder.encode(content).tolist()
        
        # Calculate importance if not provided
        if importance is None:
            importance = await self._calculate_importance(content, metadata)
            
        # Prepare metadata
        if metadata is None:
            metadata = {}
        metadata['timestamp'] = datetime.now().isoformat()
        
        memory_id = str(uuid4())
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO memories 
                (id, content, embedding, metadata, importance, memory_type)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, memory_id, content, embedding, json.dumps(metadata), 
                importance, memory_type)
                
        logger.debug(f"Stored memory {memory_id} with importance {importance:.2f}")
        return memory_id
        
    async def store_interaction(self, user_input: str, response: str, 
                              intent: Dict[str, Any] = None) -> str:
        """Store a conversation interaction"""
        content = f"User: {user_input}\nSarah: {response}"
        
        metadata = {
            'user_input': user_input,
            'response': response,
            'intent': intent or {},
            'interaction_time': datetime.now().isoformat()
        }
        
        # Higher importance for certain intents
        importance = 0.5
        if intent:
            intent_type = intent.get('type', '')
            if intent_type in ['task_creation', 'important_info', 'personal_detail']:
                importance = 0.8
                
        return await self.store(content, metadata, 'conversation', importance)
        
    async def recall(self, query: str, limit: int = 5, 
                    memory_types: List[str] = None,
                    min_similarity: float = 0.5) -> List[Dict[str, Any]]:
        """
        Recall memories based on semantic similarity
        
        Args:
            query: Search query
            limit: Maximum memories to return
            memory_types: Filter by memory types
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of relevant memories with similarity scores
        """
        if not self.initialized:
            raise RuntimeError("Memory Palace not initialized")
            
        # Generate query embedding
        query_embedding = self.encoder.encode(query).tolist()
        
        # Build query with optional filters
        sql_query = """
            WITH recalled AS (
                SELECT 
                    id, content, metadata, importance, memory_type,
                    timestamp, access_count,
                    1 - (embedding <=> $1::vector) as similarity
                FROM memories
                WHERE 1 - (embedding <=> $1::vector) >= $3
        """
        
        params = [query_embedding, limit, min_similarity]
        
        if memory_types:
            sql_query += " AND memory_type = ANY($4)"
            params.append(memory_types)
            
        sql_query += """
                ORDER BY similarity DESC, importance DESC
                LIMIT $2
            )
            UPDATE memories m
            SET access_count = access_count + 1,
                last_accessed = NOW()
            FROM recalled r
            WHERE m.id = r.id
            RETURNING r.*;
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql_query, *params)
            
        memories = []
        for row in rows:
            memory = dict(row)
            # Parse metadata JSON
            memory['metadata'] = json.loads(memory['metadata']) if memory['metadata'] else {}
            memories.append(memory)
            
        logger.debug(f"Recalled {len(memories)} memories for query: {query[:50]}...")
        return memories
        
    async def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """
        Get relevant context for a query, formatted for LLM consumption
        
        Args:
            query: Context query
            max_tokens: Approximate token limit
            
        Returns:
            Formatted context string
        """
        memories = await self.recall(query, limit=10, min_similarity=0.4)
        
        context_parts = []
        total_length = 0
        
        for memory in memories:
            # Format memory for context
            formatted = f"[{memory['timestamp'].strftime('%Y-%m-%d %H:%M')}] {memory['content']}"
            
            # Simple token estimation (4 chars ≈ 1 token)
            if total_length + len(formatted) / 4 > max_tokens:
                break
                
            context_parts.append(formatted)
            total_length += len(formatted)
            
        return "\n\n".join(context_parts)
        
    async def get_conversation_history(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, content, metadata, timestamp, importance
                FROM memories
                WHERE memory_type = 'conversation'
                AND timestamp > NOW() - INTERVAL '%s hours'
                ORDER BY timestamp DESC
                LIMIT %s
            """, hours, limit)
            
        history = []
        for row in rows:
            memory = dict(row)
            memory['metadata'] = json.loads(memory['metadata']) if memory['metadata'] else {}
            history.append(memory)
            
        return history
        
    async def consolidate_memories(self, days_old: int = 7) -> int:
        """
        Consolidate old memories to save space
        
        Args:
            days_old: Consolidate memories older than this
            
        Returns:
            Number of memories consolidated
        """
        async with self.pool.acquire() as conn:
            # Find similar old memories
            result = await conn.execute("""
                WITH old_memories AS (
                    SELECT id, content, embedding, metadata, importance
                    FROM memories
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                    AND consolidated = FALSE
                    AND memory_type = 'conversation'
                ),
                similar_pairs AS (
                    SELECT 
                        m1.id as id1, m2.id as id2,
                        1 - (m1.embedding <=> m2.embedding) as similarity
                    FROM old_memories m1
                    JOIN old_memories m2 ON m1.id < m2.id
                    WHERE 1 - (m1.embedding <=> m2.embedding) > 0.85
                )
                UPDATE memories
                SET consolidated = TRUE
                WHERE id IN (SELECT id2 FROM similar_pairs);
            """, days_old)
            
        count = int(result.split()[-1])
        logger.info(f"Consolidated {count} redundant memories")
        return count
        
    async def _calculate_importance(self, content: str, metadata: Dict[str, Any] = None) -> float:
        """Calculate memory importance score"""
        importance = 0.5
        
        # Content-based importance
        important_keywords = [
            'important', 'remember', 'always', 'never', 'urgent',
            'password', 'secret', 'personal', 'favorite', 'prefer'
        ]
        
        content_lower = content.lower()
        keyword_matches = sum(1 for kw in important_keywords if kw in content_lower)
        importance += min(keyword_matches * 0.1, 0.3)
        
        # Metadata-based importance
        if metadata:
            # Task completion
            if metadata.get('task_completed'):
                importance += 0.2
                
            # User explicitly marked important
            if metadata.get('user_marked_important'):
                importance = max(importance, 0.9)
                
            # Personal information
            if metadata.get('contains_personal_info'):
                importance += 0.2
                
        return min(importance, 1.0)
        
    async def search_by_timeframe(self, start_time: datetime, end_time: datetime,
                                 memory_types: List[str] = None) -> List[Dict[str, Any]]:
        """Search memories within a specific timeframe"""
        sql = """
            SELECT id, content, metadata, timestamp, importance, memory_type
            FROM memories
            WHERE timestamp BETWEEN $1 AND $2
        """
        
        params = [start_time, end_time]
        
        if memory_types:
            sql += " AND memory_type = ANY($3)"
            params.append(memory_types)
            
        sql += " ORDER BY timestamp DESC"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
        memories = []
        for row in rows:
            memory = dict(row)
            memory['metadata'] = json.loads(memory['metadata']) if memory['metadata'] else {}
            memories.append(memory)
            
        return memories
        
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_memories,
                    COUNT(DISTINCT memory_type) as memory_types,
                    AVG(importance) as avg_importance,
                    AVG(access_count) as avg_access_count,
                    MAX(timestamp) as latest_memory,
                    MIN(timestamp) as oldest_memory,
                    SUM(CASE WHEN consolidated THEN 1 ELSE 0 END) as consolidated_count
                FROM memories
            """)
            
        return dict(stats)
        
    async def cleanup(self) -> None:
        """Clean up resources"""
        if self.pool:
            await self.pool.close()
            logger.info("Memory Palace connection pool closed")