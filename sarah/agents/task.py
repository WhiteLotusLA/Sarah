"""
Task Agent - Manages todos, projects, and task tracking
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncpg

from sarah.agents.base import BaseAgent, AgentMessage
from sarah.core.memory import MemoryPalace

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status options"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    DEFERRED = "deferred"


class TaskPriority(str, Enum):
    """Task priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class Task:
    """Represents a task or todo item"""
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    project_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    assignee: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    recurrence_pattern: Optional[Dict[str, Any]] = None
    dependencies: List[str] = field(default_factory=list)
    attachments: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_overdue(self) -> bool:
        """Check if task is overdue"""
        if self.due_date and self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return datetime.now(timezone.utc) > self.due_date
        return False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value,
            'priority': self.priority.value,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'project_id': self.project_id,
            'parent_task_id': self.parent_task_id,
            'tags': self.tags,
            'assignee': self.assignee,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
            'recurrence_pattern': self.recurrence_pattern,
            'dependencies': self.dependencies,
            'attachments': self.attachments,
            'metadata': self.metadata,
            'is_overdue': self.is_overdue()
        }


@dataclass
class Project:
    """Represents a project containing multiple tasks"""
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    status: str = "active"  # active, completed, archived
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskAgent(BaseAgent):
    """
    Manages tasks, todos, and project tracking
    
    Capabilities:
    - Create, update, delete tasks
    - Project management
    - Task dependencies and subtasks
    - Recurring tasks
    - Smart task prioritization
    - Natural language task parsing
    - Integration with calendar for due dates
    """
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        super().__init__("task", "Task Manager")
        self.db_pool = db_pool
        self.memory: Optional[MemoryPalace] = None
        
    async def initialize(self, db_pool: Optional[asyncpg.Pool] = None) -> None:
        """Initialize the task agent"""
        await super().start()
        
        if db_pool:
            self.db_pool = db_pool
            
        # Initialize memory for intelligent task suggestions
        self.memory = MemoryPalace()
        try:
            await self.memory.initialize()
        except Exception as e:
            logger.warning(f"Memory initialization failed: {e}")
            self.memory = None
            
        # Ensure database tables exist
        if self.db_pool:
            await self._ensure_tables()
            
        # Register command handlers
        self.register_handler("create_task", self._handle_create_task)
        self.register_handler("update_task", self._handle_update_task)
        self.register_handler("delete_task", self._handle_delete_task)
        self.register_handler("get_tasks", self._handle_get_tasks)
        self.register_handler("complete_task", self._handle_complete_task)
        self.register_handler("create_project", self._handle_create_project)
        self.register_handler("parse_task", self._handle_parse_task)
        
        logger.info("📋 Task agent initialized")
        
    async def _ensure_tables(self) -> None:
        """Ensure task tables exist"""
        async with self.db_pool.acquire() as conn:
            # Tasks table is already created in the main schema
            # Add projects table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    due_date TIMESTAMPTZ,
                    tags TEXT[],
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS projects_status_idx ON projects(status);
                CREATE INDEX IF NOT EXISTS projects_due_date_idx ON projects(due_date);
            """)
            
            # Add columns to tasks table if they don't exist
            await conn.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='project_id') THEN
                        ALTER TABLE tasks ADD COLUMN project_id UUID REFERENCES projects(id);
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='parent_task_id') THEN
                        ALTER TABLE tasks ADD COLUMN parent_task_id UUID REFERENCES tasks(id);
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='tags') THEN
                        ALTER TABLE tasks ADD COLUMN tags TEXT[] DEFAULT '{}';
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='estimated_hours') THEN
                        ALTER TABLE tasks ADD COLUMN estimated_hours FLOAT;
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='actual_hours') THEN
                        ALTER TABLE tasks ADD COLUMN actual_hours FLOAT;
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='recurrence_pattern') THEN
                        ALTER TABLE tasks ADD COLUMN recurrence_pattern JSONB;
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='dependencies') THEN
                        ALTER TABLE tasks ADD COLUMN dependencies UUID[] DEFAULT '{}';
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='tasks' AND column_name='attachments') THEN
                        ALTER TABLE tasks ADD COLUMN attachments JSONB DEFAULT '[]';
                    END IF;
                END $$;
            """)
            
    async def create_task(self, task: Task) -> Task:
        """Create a new task"""
        if not self.db_pool:
            raise RuntimeError("Database not initialized")
            
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO tasks (
                    title, description, status, priority, due_date,
                    project_id, parent_task_id, tags, assignee,
                    estimated_hours, recurrence_pattern, dependencies,
                    attachments, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING *
            """, task.title, task.description, task.status.value, 
                task.priority.value, task.due_date, task.project_id,
                task.parent_task_id, task.tags, task.assignee,
                task.estimated_hours, json.dumps(task.recurrence_pattern) if task.recurrence_pattern else None,
                task.dependencies, json.dumps(task.attachments), 
                json.dumps(task.metadata))
                
        created_task = self._row_to_task(row)
        
        # Store in memory for learning
        if self.memory:
            await self.memory.store(
                f"Created task: {task.title}",
                {
                    'task_id': str(created_task.id),
                    'task': created_task.to_dict()
                },
                'task_creation'
            )
            
        logger.info(f"Created task: {created_task.title}")
        return created_task
        
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> Task:
        """Update an existing task"""
        if not self.db_pool:
            raise RuntimeError("Database not initialized")
            
        # Build update query dynamically
        set_clauses = []
        params = []
        param_count = 1
        
        field_mapping = {
            'title': 'title',
            'description': 'description',
            'status': 'status',
            'priority': 'priority',
            'due_date': 'due_date',
            'project_id': 'project_id',
            'parent_task_id': 'parent_task_id',
            'tags': 'tags',
            'assignee': 'assignee',
            'estimated_hours': 'estimated_hours',
            'actual_hours': 'actual_hours',
            'recurrence_pattern': 'recurrence_pattern',
            'dependencies': 'dependencies',
            'attachments': 'attachments',
            'metadata': 'metadata'
        }
        
        for key, value in updates.items():
            if key in field_mapping:
                set_clauses.append(f"{field_mapping[key]} = ${param_count}")
                
                # Handle special cases
                if key in ['status', 'priority'] and isinstance(value, str):
                    params.append(value)
                elif key in ['recurrence_pattern', 'attachments', 'metadata']:
                    params.append(json.dumps(value) if value else None)
                else:
                    params.append(value)
                    
                param_count += 1
                
        # Always update updated_at
        set_clauses.append(f"updated_at = ${param_count}")
        params.append(datetime.now(timezone.utc))
        param_count += 1
        
        # Add task_id as last parameter
        params.append(task_id)
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                UPDATE tasks 
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count}
                RETURNING *
            """, *params)
            
        if not row:
            raise ValueError(f"Task {task_id} not found")
            
        updated_task = self._row_to_task(row)
        logger.info(f"Updated task: {updated_task.title}")
        return updated_task
        
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task"""
        if not self.db_pool:
            raise RuntimeError("Database not initialized")
            
        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM tasks WHERE id = $1
            """, task_id)
            
        success = result != "DELETE 0"
        if success:
            logger.info(f"Deleted task: {task_id}")
        return success
        
    async def complete_task(self, task_id: str) -> Task:
        """Mark a task as completed"""
        updates = {
            'status': TaskStatus.COMPLETED.value,
            'completed_at': datetime.now(timezone.utc)
        }
        
        task = await self.update_task(task_id, updates)
        
        # Store completion in memory
        if self.memory:
            await self.memory.store(
                f"Completed task: {task.title}",
                {
                    'task_id': str(task.id),
                    'task': task.to_dict(),
                    'completion_time': task.completed_at.isoformat()
                },
                'task_completion',
                importance=0.7
            )
            
        # Check for recurring tasks
        if task.recurrence_pattern:
            await self._create_recurring_task(task)
            
        return task
        
    async def get_tasks(self, filters: Dict[str, Any] = None) -> List[Task]:
        """Get tasks with optional filters"""
        if not self.db_pool:
            raise RuntimeError("Database not initialized")
            
        # Build query with filters
        where_clauses = []
        params = []
        param_count = 1
        
        if filters:
            if 'status' in filters:
                where_clauses.append(f"status = ${param_count}")
                params.append(filters['status'])
                param_count += 1
                
            if 'priority' in filters:
                where_clauses.append(f"priority = ${param_count}")
                params.append(filters['priority'])
                param_count += 1
                
            if 'project_id' in filters:
                where_clauses.append(f"project_id = ${param_count}")
                params.append(filters['project_id'])
                param_count += 1
                
            if 'assignee' in filters:
                where_clauses.append(f"assignee = ${param_count}")
                params.append(filters['assignee'])
                param_count += 1
                
            if 'tags' in filters and filters['tags']:
                where_clauses.append(f"tags && ${param_count}")
                params.append(filters['tags'])
                param_count += 1
                
            if 'due_before' in filters:
                where_clauses.append(f"due_date <= ${param_count}")
                params.append(filters['due_before'])
                param_count += 1
                
            if 'due_after' in filters:
                where_clauses.append(f"due_date >= ${param_count}")
                params.append(filters['due_after'])
                param_count += 1
                
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM tasks
                {where_clause}
                ORDER BY 
                    CASE priority 
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END,
                    due_date ASC NULLS LAST,
                    created_at DESC
            """, *params)
            
        return [self._row_to_task(row) for row in rows]
        
    async def get_upcoming_tasks(self, days: int = 7) -> List[Task]:
        """Get tasks due in the next N days"""
        due_before = datetime.now(timezone.utc) + timedelta(days=days)
        
        filters = {
            'status': TaskStatus.TODO.value,
            'due_before': due_before
        }
        
        return await self.get_tasks(filters)
        
    async def get_overdue_tasks(self) -> List[Task]:
        """Get overdue tasks"""
        filters = {
            'status': TaskStatus.TODO.value,
            'due_before': datetime.now(timezone.utc)
        }
        
        tasks = await self.get_tasks(filters)
        return [t for t in tasks if t.is_overdue()]
        
    async def create_project(self, project: Project) -> Project:
        """Create a new project"""
        if not self.db_pool:
            raise RuntimeError("Database not initialized")
            
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO projects (name, description, status, due_date, tags, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
            """, project.name, project.description, project.status,
                project.due_date, project.tags, json.dumps(project.metadata))
                
        created_project = self._row_to_project(row)
        logger.info(f"Created project: {created_project.name}")
        return created_project
        
    async def parse_natural_language_task(self, text: str) -> Task:
        """Parse natural language into a task"""
        # This is a simple implementation - could be enhanced with NLP
        task = Task()
        task.title = text
        
        # Extract priority
        if any(word in text.lower() for word in ['urgent', 'critical', 'asap']):
            task.priority = TaskPriority.CRITICAL
        elif any(word in text.lower() for word in ['high priority', 'important']):
            task.priority = TaskPriority.HIGH
        elif 'low priority' in text.lower():
            task.priority = TaskPriority.LOW
            
        # Extract due date (simple patterns)
        import re
        
        # Tomorrow
        if 'tomorrow' in text.lower():
            task.due_date = datetime.now(timezone.utc) + timedelta(days=1)
            
        # Next week
        elif 'next week' in text.lower():
            task.due_date = datetime.now(timezone.utc) + timedelta(weeks=1)
            
        # In N days
        days_match = re.search(r'in (\d+) days?', text.lower())
        if days_match:
            days = int(days_match.group(1))
            task.due_date = datetime.now(timezone.utc) + timedelta(days=days)
            
        # Extract tags
        tag_matches = re.findall(r'#(\w+)', text)
        if tag_matches:
            task.tags = tag_matches
            
        # Use memory to learn patterns if available
        if self.memory:
            similar_tasks = await self.memory.recall(text, limit=3, memory_types=['task_creation'])
            # Could analyze similar tasks to improve parsing
            
        return task
        
    async def _create_recurring_task(self, original_task: Task) -> Optional[Task]:
        """Create next instance of a recurring task"""
        if not original_task.recurrence_pattern:
            return None
            
        pattern = original_task.recurrence_pattern
        new_task = Task(
            title=original_task.title,
            description=original_task.description,
            priority=original_task.priority,
            project_id=original_task.project_id,
            tags=original_task.tags,
            assignee=original_task.assignee,
            estimated_hours=original_task.estimated_hours,
            recurrence_pattern=original_task.recurrence_pattern
        )
        
        # Calculate next due date based on pattern
        if pattern.get('frequency') == 'daily':
            interval = timedelta(days=pattern.get('interval', 1))
        elif pattern.get('frequency') == 'weekly':
            interval = timedelta(weeks=pattern.get('interval', 1))
        elif pattern.get('frequency') == 'monthly':
            # Simplified - proper month handling would be more complex
            interval = timedelta(days=30 * pattern.get('interval', 1))
        else:
            return None
            
        new_task.due_date = original_task.due_date + interval if original_task.due_date else None
        
        return await self.create_task(new_task)
        
    def _row_to_task(self, row: asyncpg.Record) -> Task:
        """Convert database row to Task object"""
        return Task(
            id=str(row['id']),
            title=row['title'],
            description=row['description'],
            status=TaskStatus(row['status']),
            priority=TaskPriority(row['priority']),
            due_date=row['due_date'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            completed_at=row.get('completed_at'),
            project_id=str(row['project_id']) if row.get('project_id') else None,
            parent_task_id=str(row['parent_task_id']) if row.get('parent_task_id') else None,
            tags=row.get('tags', []),
            assignee=row.get('assignee'),
            estimated_hours=row.get('estimated_hours'),
            actual_hours=row.get('actual_hours'),
            recurrence_pattern=json.loads(row['recurrence_pattern']) if row.get('recurrence_pattern') else None,
            dependencies=[str(d) for d in row.get('dependencies', [])],
            attachments=json.loads(row['attachments']) if row.get('attachments') else [],
            metadata=json.loads(row['metadata']) if row.get('metadata') else {}
        )
        
    def _row_to_project(self, row: asyncpg.Record) -> Project:
        """Convert database row to Project object"""
        return Project(
            id=str(row['id']),
            name=row['name'],
            description=row['description'],
            status=row['status'],
            created_at=row['created_at'],
            due_date=row['due_date'],
            tags=row.get('tags', []),
            metadata=json.loads(row['metadata']) if row.get('metadata') else {}
        )
        
    # Command handlers
    async def _handle_create_task(self, message: AgentMessage) -> None:
        """Handle create_task command"""
        task_data = message.data.get('task', {})
        
        # Create task from data
        task = Task(**task_data)
        created = await self.create_task(task)
        
        await self.send_message(
            message.from_agent,
            "task_created",
            {'task': created.to_dict()}
        )
        
    async def _handle_update_task(self, message: AgentMessage) -> None:
        """Handle update_task command"""
        task_id = message.data['task_id']
        updates = message.data['updates']
        
        updated = await self.update_task(task_id, updates)
        
        await self.send_message(
            message.from_agent,
            "task_updated",
            {'task': updated.to_dict()}
        )
        
    async def _handle_delete_task(self, message: AgentMessage) -> None:
        """Handle delete_task command"""
        task_id = message.data['task_id']
        
        success = await self.delete_task(task_id)
        
        await self.send_message(
            message.from_agent,
            "task_deleted",
            {'success': success, 'task_id': task_id}
        )
        
    async def _handle_get_tasks(self, message: AgentMessage) -> None:
        """Handle get_tasks command"""
        filters = message.data.get('filters', {})
        
        tasks = await self.get_tasks(filters)
        
        await self.send_message(
            message.from_agent,
            "tasks_response",
            {
                'tasks': [t.to_dict() for t in tasks],
                'count': len(tasks)
            }
        )
        
    async def _handle_complete_task(self, message: AgentMessage) -> None:
        """Handle complete_task command"""
        task_id = message.data['task_id']
        
        completed = await self.complete_task(task_id)
        
        await self.send_message(
            message.from_agent,
            "task_completed",
            {'task': completed.to_dict()}
        )
        
    async def _handle_create_project(self, message: AgentMessage) -> None:
        """Handle create_project command"""
        project_data = message.data.get('project', {})
        
        project = Project(**project_data)
        created = await self.create_project(project)
        
        await self.send_message(
            message.from_agent,
            "project_created",
            {'project': {
                'id': str(created.id),
                'name': created.name,
                'description': created.description,
                'status': created.status,
                'created_at': created.created_at.isoformat(),
                'due_date': created.due_date.isoformat() if created.due_date else None,
                'tags': created.tags,
                'metadata': created.metadata
            }}
        )
        
    async def _handle_parse_task(self, message: AgentMessage) -> None:
        """Handle parse_task command"""
        text = message.data['text']
        
        task = await self.parse_natural_language_task(text)
        
        await self.send_message(
            message.from_agent,
            "task_parsed",
            {'task': task.to_dict()}
        )