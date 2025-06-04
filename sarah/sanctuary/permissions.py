"""
Permission management system for role-based access control
"""

from typing import List, Dict, Any, Optional, Set
from enum import Enum
import logging
import asyncpg
from datetime import datetime

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Available permissions in the system"""
    # Core permissions
    ADMIN = "admin"
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    
    # Agent permissions
    AGENT_CONTROL = "agent:control"
    AGENT_VIEW = "agent:view"
    AGENT_CREATE = "agent:create"
    AGENT_DELETE = "agent:delete"
    
    # Memory permissions
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"
    MEMORY_SEARCH = "memory:search"
    
    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_METRICS = "system:metrics"
    
    # API permissions
    API_KEY_CREATE = "api:key:create"
    API_KEY_REVOKE = "api:key:revoke"
    API_KEY_VIEW = "api:key:view"
    
    # User management
    USER_CREATE = "user:create"
    USER_MODIFY = "user:modify"
    USER_DELETE = "user:delete"
    USER_VIEW = "user:view"


class Role(str, Enum):
    """Predefined roles with permission sets"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    API_USER = "api_user"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions
    
    Role.USER: {
        Permission.READ,
        Permission.WRITE,
        Permission.AGENT_VIEW,
        Permission.AGENT_CONTROL,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.MEMORY_SEARCH,
        Permission.API_KEY_CREATE,
        Permission.API_KEY_VIEW,
    },
    
    Role.VIEWER: {
        Permission.READ,
        Permission.AGENT_VIEW,
        Permission.MEMORY_READ,
        Permission.MEMORY_SEARCH,
    },
    
    Role.API_USER: {
        Permission.READ,
        Permission.WRITE,
        Permission.AGENT_VIEW,
        Permission.MEMORY_READ,
        Permission.MEMORY_SEARCH,
    }
}


class PermissionManager:
    """
    Manages permissions and role-based access control
    
    Features:
    - Role-based permissions
    - Fine-grained permission checks
    - Permission inheritance
    - Audit logging
    """
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        self.db_pool = db_pool
        
    async def initialize(self, db_pool: asyncpg.Pool) -> None:
        """Initialize permission manager with database"""
        self.db_pool = db_pool
        await self._ensure_permission_tables()
        logger.info("🛡️ Permission manager initialized")
        
    async def _ensure_permission_tables(self) -> None:
        """Ensure permission tables exist"""
        async with self.db_pool.acquire() as conn:
            # Create roles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    permissions JSONB DEFAULT '[]',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS roles_name_idx ON roles(name);
            """)
            
            # Create user_roles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
                    granted_at TIMESTAMPTZ DEFAULT NOW(),
                    granted_by UUID REFERENCES users(id),
                    UNIQUE(user_id, role_id)
                );
                
                CREATE INDEX IF NOT EXISTS user_roles_user_idx ON user_roles(user_id);
                CREATE INDEX IF NOT EXISTS user_roles_role_idx ON user_roles(role_id);
            """)
            
            # Create permission_overrides table for custom permissions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_overrides (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    permission VARCHAR(100) NOT NULL,
                    granted BOOLEAN NOT NULL,
                    granted_at TIMESTAMPTZ DEFAULT NOW(),
                    granted_by UUID REFERENCES users(id),
                    expires_at TIMESTAMPTZ,
                    UNIQUE(user_id, permission)
                );
                
                CREATE INDEX IF NOT EXISTS permission_overrides_user_idx ON permission_overrides(user_id);
            """)
            
            # Create audit log table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_audit_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id),
                    action VARCHAR(100) NOT NULL,
                    resource VARCHAR(255),
                    permission VARCHAR(100),
                    allowed BOOLEAN NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS audit_log_user_idx ON permission_audit_log(user_id);
                CREATE INDEX IF NOT EXISTS audit_log_timestamp_idx ON permission_audit_log(timestamp DESC);
            """)
            
            # Ensure default roles exist
            await self._ensure_default_roles(conn)
            
    async def _ensure_default_roles(self, conn: asyncpg.Connection) -> None:
        """Ensure default roles exist in database"""
        for role in Role:
            permissions = list(ROLE_PERMISSIONS[role])
            
            await conn.execute("""
                INSERT INTO roles (name, description, permissions)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO UPDATE
                SET permissions = $3, updated_at = NOW()
            """, role.value, f"Default {role.value} role", 
                [p.value for p in permissions])
                
    async def grant_role(self, user_id: str, role: Union[Role, str], 
                        granted_by: str) -> bool:
        """Grant a role to a user"""
        role_name = role.value if isinstance(role, Role) else role
        
        async with self.db_pool.acquire() as conn:
            # Get role ID
            role_record = await conn.fetchrow("""
                SELECT id FROM roles WHERE name = $1
            """, role_name)
            
            if not role_record:
                raise ValueError(f"Role '{role_name}' not found")
                
            # Grant role
            try:
                await conn.execute("""
                    INSERT INTO user_roles (user_id, role_id, granted_by)
                    VALUES ($1, $2, $3)
                """, user_id, role_record['id'], granted_by)
                
                logger.info(f"Granted role '{role_name}' to user {user_id}")
                return True
                
            except asyncpg.UniqueViolationError:
                logger.warning(f"User {user_id} already has role '{role_name}'")
                return False
                
    async def revoke_role(self, user_id: str, role: Union[Role, str]) -> bool:
        """Revoke a role from a user"""
        role_name = role.value if isinstance(role, Role) else role
        
        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM user_roles
                WHERE user_id = $1 AND role_id = (
                    SELECT id FROM roles WHERE name = $2
                )
            """, user_id, role_name)
            
        success = result != "DELETE 0"
        if success:
            logger.info(f"Revoked role '{role_name}' from user {user_id}")
            
        return success
        
    async def grant_permission(self, user_id: str, permission: Union[Permission, str],
                             granted_by: str, expires_at: Optional[datetime] = None) -> bool:
        """Grant a specific permission to a user"""
        perm_name = permission.value if isinstance(permission, Permission) else permission
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO permission_overrides 
                (user_id, permission, granted, granted_by, expires_at)
                VALUES ($1, $2, TRUE, $3, $4)
                ON CONFLICT (user_id, permission) DO UPDATE
                SET granted = TRUE, granted_by = $3, expires_at = $4, granted_at = NOW()
            """, user_id, perm_name, granted_by, expires_at)
            
        logger.info(f"Granted permission '{perm_name}' to user {user_id}")
        return True
        
    async def revoke_permission(self, user_id: str, permission: Union[Permission, str],
                              granted_by: str) -> bool:
        """Revoke a specific permission from a user"""
        perm_name = permission.value if isinstance(permission, Permission) else permission
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO permission_overrides 
                (user_id, permission, granted, granted_by)
                VALUES ($1, $2, FALSE, $3)
                ON CONFLICT (user_id, permission) DO UPDATE
                SET granted = FALSE, granted_by = $3, granted_at = NOW()
            """, user_id, perm_name, granted_by)
            
        logger.info(f"Revoked permission '{perm_name}' from user {user_id}")
        return True
        
    async def check_permission(self, user_id: str, permission: Union[Permission, str],
                             resource: Optional[str] = None, 
                             log_attempt: bool = True) -> bool:
        """
        Check if a user has a specific permission
        
        Args:
            user_id: User ID to check
            permission: Permission to check
            resource: Optional resource identifier
            log_attempt: Whether to log this check
            
        Returns:
            True if user has permission
        """
        perm_name = permission.value if isinstance(permission, Permission) else permission
        
        async with self.db_pool.acquire() as conn:
            # First check permission overrides
            override = await conn.fetchrow("""
                SELECT granted FROM permission_overrides
                WHERE user_id = $1 AND permission = $2
                AND (expires_at IS NULL OR expires_at > NOW())
            """, user_id, perm_name)
            
            if override is not None:
                allowed = override['granted']
                
                if log_attempt:
                    await self._log_permission_check(
                        conn, user_id, perm_name, resource, allowed
                    )
                    
                return allowed
                
            # Check user roles
            user_permissions = await conn.fetch("""
                SELECT r.permissions
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = $1
            """, user_id)
            
            # Aggregate all permissions from roles
            all_permissions = set()
            for row in user_permissions:
                all_permissions.update(row['permissions'])
                
            allowed = perm_name in all_permissions
            
            if log_attempt:
                await self._log_permission_check(
                    conn, user_id, perm_name, resource, allowed
                )
                
        return allowed
        
    async def check_any_permission(self, user_id: str, 
                                 permissions: List[Union[Permission, str]]) -> bool:
        """Check if user has any of the specified permissions"""
        for perm in permissions:
            if await self.check_permission(user_id, perm, log_attempt=False):
                return True
        return False
        
    async def check_all_permissions(self, user_id: str,
                                  permissions: List[Union[Permission, str]]) -> bool:
        """Check if user has all of the specified permissions"""
        for perm in permissions:
            if not await self.check_permission(user_id, perm, log_attempt=False):
                return False
        return True
        
    async def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get all permissions for a user"""
        async with self.db_pool.acquire() as conn:
            # Get permissions from roles
            role_perms = await conn.fetch("""
                SELECT r.permissions
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = $1
            """, user_id)
            
            # Aggregate permissions
            permissions = set()
            for row in role_perms:
                permissions.update(row['permissions'])
                
            # Apply permission overrides
            overrides = await conn.fetch("""
                SELECT permission, granted
                FROM permission_overrides
                WHERE user_id = $1
                AND (expires_at IS NULL OR expires_at > NOW())
            """, user_id)
            
            for override in overrides:
                if override['granted']:
                    permissions.add(override['permission'])
                else:
                    permissions.discard(override['permission'])
                    
        return permissions
        
    async def get_user_roles(self, user_id: str) -> List[str]:
        """Get all roles for a user"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT r.name
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = $1
            """, user_id)
            
        return [row['name'] for row in rows]
        
    async def _log_permission_check(self, conn: asyncpg.Connection, user_id: str,
                                  permission: str, resource: Optional[str],
                                  allowed: bool) -> None:
        """Log permission check to audit log"""
        await conn.execute("""
            INSERT INTO permission_audit_log 
            (user_id, action, resource, permission, allowed, metadata)
            VALUES ($1, 'permission_check', $2, $3, $4, $5)
        """, user_id, resource, permission, allowed, {})
        
    async def get_audit_log(self, user_id: Optional[str] = None,
                          hours: int = 24) -> List[Dict[str, Any]]:
        """Get permission audit log"""
        async with self.db_pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch("""
                    SELECT * FROM permission_audit_log
                    WHERE user_id = $1
                    AND timestamp > NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp DESC
                """, user_id, hours)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM permission_audit_log
                    WHERE timestamp > NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp DESC
                """, hours)
                
        return [dict(row) for row in rows]