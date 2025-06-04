"""
FastAPI dependencies for authentication and authorization
"""

from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader
import asyncpg  # type: ignore

from sarah.sanctuary.auth import AuthManager, verify_token
from sarah.sanctuary.permissions import PermissionManager, Permission

# Security schemes
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Global instances
auth_manager: Optional[AuthManager] = None
permission_manager: Optional[PermissionManager] = None
db_pool: Optional[asyncpg.Pool] = None


async def init_auth_dependencies(pool: asyncpg.Pool):
    """Initialize authentication dependencies"""
    global auth_manager, permission_manager, db_pool

    db_pool = pool

    auth_manager = AuthManager()
    await auth_manager.initialize(pool)

    permission_manager = PermissionManager()
    await permission_manager.initialize(pool)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token or API key

    Returns:
        User information dictionary
    """
    if not auth_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication system not initialized",
        )

    # Try API key first
    if api_key:
        user_info = await auth_manager.verify_api_key(api_key)
        if user_info:
            return user_info

    # Try JWT token
    if credentials:
        # Verify token
        user_info = await auth_manager.verify_session(credentials.credentials)
        if user_info:
            return user_info

    # No valid authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user if available (optional auth)

    Returns:
        User information dictionary or None
    """
    try:
        return await get_current_user(credentials, api_key)
    except HTTPException:
        return None


class RequirePermission:
    """Dependency to check if user has required permission"""

    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(
        self, user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has permission"""
        if not permission_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Permission system not initialized",
            )

        # Admins have all permissions
        if user.get("is_admin"):
            return user

        # Check specific permission
        has_permission = await permission_manager.check_permission(
            user["user_id"], self.permission
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.permission.value}",
            )

        return user


class RequireAnyPermission:
    """Dependency to check if user has any of the required permissions"""

    def __init__(self, permissions: List[Permission]):
        self.permissions = permissions

    async def __call__(
        self, user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has any permission"""
        if not permission_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Permission system not initialized",
            )

        # Admins have all permissions
        if user.get("is_admin"):
            return user

        # Check permissions
        has_permission = await permission_manager.check_any_permission(
            user["user_id"], self.permissions
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires one of {[p.value for p in self.permissions]}",
            )

        return user


class RequireAllPermissions:
    """Dependency to check if user has all required permissions"""

    def __init__(self, permissions: List[Permission]):
        self.permissions = permissions

    async def __call__(
        self, user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has all permissions"""
        if not permission_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Permission system not initialized",
            )

        # Admins have all permissions
        if user.get("is_admin"):
            return user

        # Check permissions
        has_permissions = await permission_manager.check_all_permissions(
            user["user_id"], self.permissions
        )

        if not has_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires all of {[p.value for p in self.permissions]}",
            )

        return user


# Convenience dependencies
require_admin = RequirePermission(Permission.ADMIN)
require_read = RequirePermission(Permission.READ)
require_write = RequirePermission(Permission.WRITE)
require_memory_read = RequirePermission(Permission.MEMORY_READ)
require_memory_write = RequirePermission(Permission.MEMORY_WRITE)
require_agent_control = RequirePermission(Permission.AGENT_CONTROL)
