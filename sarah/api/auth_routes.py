"""
Authentication API routes
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
import asyncpg  # type: ignore

from sarah.sanctuary.auth import AuthManager
from sarah.sanctuary.permissions import PermissionManager, Role
from sarah.api.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_admin,
    init_auth_dependencies,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Global instances
auth_manager: Optional[AuthManager] = None
permission_manager: Optional[PermissionManager] = None


# Request/Response models
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    roles: List[str]
    permissions: List[str]


class APIKeyRequest(BaseModel):
    name: str
    permissions: Optional[List[str]] = None
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    api_key: str
    name: str
    created_at: datetime


@router.on_event("startup")
async def startup():
    """Initialize auth system on startup"""
    global auth_manager, permission_manager

    # Get database pool (this should be passed from main app)
    # For now, create a new pool
    pool = await asyncpg.create_pool("postgresql://localhost/sarah_db")

    auth_manager = AuthManager()
    await auth_manager.initialize(pool)

    permission_manager = PermissionManager()
    await permission_manager.initialize(pool)

    # Initialize dependencies
    await init_auth_dependencies(pool)


@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest):
    """Register a new user"""
    if not auth_manager or not permission_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized",
        )

    try:
        # Create user
        user = await auth_manager.create_user(
            username=request.username, email=request.email, password=request.password
        )

        # Grant default user role
        await permission_manager.grant_role(
            user["id"], Role.USER, user["id"]  # Self-granted
        )

        # Get user details
        roles = await permission_manager.get_user_roles(user["id"])
        permissions = await permission_manager.get_user_permissions(user["id"])

        return UserResponse(
            id=str(user["id"]),
            username=user["username"],
            email=user["email"],
            is_active=user["is_active"],
            is_admin=user["is_admin"],
            created_at=user["created_at"],
            last_login=None,
            roles=roles,
            permissions=list(permissions),
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login and get access token"""
    if not auth_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized",
        )

    # Authenticate user
    user = await auth_manager.authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Create access token
    access_token = auth_manager.create_access_token(
        str(user["id"]), {"username": user["username"], "is_admin": user["is_admin"]}
    )

    # Create session
    await auth_manager.create_session(str(user["id"]), access_token)

    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(user["id"]),
            "username": user["username"],
            "email": user["email"],
            "is_admin": user["is_admin"],
        },
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    if not auth_manager or not permission_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized",
        )

    # Get full user details
    user_details = await auth_manager.get_user_by_id(user["user_id"])
    if not user_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get roles and permissions
    roles = await permission_manager.get_user_roles(user["user_id"])
    permissions = await permission_manager.get_user_permissions(user["user_id"])

    return UserResponse(
        id=user["user_id"],
        username=user_details["username"],
        email=user_details["email"],
        is_active=user_details["is_active"],
        is_admin=user_details["is_admin"],
        created_at=user_details["created_at"],
        last_login=user_details.get("last_login"),
        roles=roles,
        permissions=list(permissions),
    )


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyRequest, user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new API key"""
    if not auth_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized",
        )

    # Create API key
    api_key = await auth_manager.create_api_key(
        user["user_id"], request.name, request.permissions, request.expires_in_days
    )

    return APIKeyResponse(api_key=api_key, name=request.name, created_at=datetime.now())


@router.post("/logout")
async def logout(user: Dict[str, Any] = Depends(get_current_user)):
    """Logout current user"""
    # In a real implementation, we would revoke the session
    # For now, just return success
    return {"message": "Logged out successfully"}


@router.post("/users/{user_id}/roles/{role}")
async def grant_role(
    user_id: str, role: str, admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Grant a role to a user (admin only)"""
    if not permission_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Permission system not initialized",
        )

    success = await permission_manager.grant_role(user_id, role, admin_user["user_id"])

    if success:
        return {"message": f"Role '{role}' granted to user {user_id}"}
    else:
        return {"message": f"User already has role '{role}'"}


@router.delete("/users/{user_id}/roles/{role}")
async def revoke_role(
    user_id: str, role: str, admin_user: Dict[str, Any] = Depends(require_admin)
):
    """Revoke a role from a user (admin only)"""
    if not permission_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Permission system not initialized",
        )

    success = await permission_manager.revoke_role(user_id, role)

    if success:
        return {"message": f"Role '{role}' revoked from user {user_id}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User does not have role '{role}'",
        )


