"""
Authentication and authorization system for Sarah
"""

import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncpg  # type: ignore

from sarah.config import Config

logger = logging.getLogger(__name__)

# JWT configuration
JWT_SECRET_KEY = (
    Config.JWT_SECRET_KEY
    if hasattr(Config, "JWT_SECRET_KEY")
    else secrets.token_urlsafe(32)
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class AuthManager:
    """
    Manages authentication and authorization for Sarah

    Features:
    - JWT token generation and validation
    - API key management
    - User authentication with bcrypt
    - Role-based access control
    - Session management
    """

    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        self.db_pool = db_pool
        self.secret_key = JWT_SECRET_KEY
        self.algorithm = JWT_ALGORITHM

    async def initialize(self, db_pool: asyncpg.Pool) -> None:
        """Initialize auth manager with database connection"""
        self.db_pool = db_pool
        await self._ensure_auth_tables()
        logger.info("🔐 Auth manager initialized")

    async def _ensure_auth_tables(self) -> None:
        """Ensure authentication tables exist"""
        async with self.db_pool.acquire() as conn:
            # Create users table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    last_login TIMESTAMPTZ,
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS users_username_idx ON users(username);
                CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);
            """
            )

            # Create API keys table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    key_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    permissions JSONB DEFAULT '[]',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    last_used TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ,
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS api_keys_user_idx ON api_keys(user_id);
                CREATE INDEX IF NOT EXISTS api_keys_hash_idx ON api_keys(key_hash);
            """
            )

            # Create sessions table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL,
                    device_info JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                );
                
                CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS sessions_token_idx ON sessions(token_hash);
            """
            )

    async def create_user(
        self, username: str, email: str, password: str, is_admin: bool = False
    ) -> Dict[str, Any]:
        """Create a new user"""
        # Hash password
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        async with self.db_pool.acquire() as conn:
            try:
                user = await conn.fetchrow(
                    """
                    INSERT INTO users (username, email, password_hash, is_admin)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, username, email, is_active, is_admin, created_at
                """,
                    username,
                    email,
                    password_hash.decode("utf-8"),
                    is_admin,
                )

                logger.info(f"Created user: {username}")
                return dict(user)

            except asyncpg.UniqueViolationError:
                raise ValueError("Username or email already exists")

    async def authenticate_user(
        self, username: str, password: str
    ) -> Optional[Dict[str, Any]]:
        """Authenticate a user with username and password"""
        async with self.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, username, email, password_hash, is_active, is_admin
                FROM users
                WHERE username = $1 OR email = $1
            """,
                username,
            )

            if not user:
                return None

            if not user["is_active"]:
                logger.warning(f"Inactive user attempted login: {username}")
                return None

            # Verify password
            if bcrypt.checkpw(
                password.encode("utf-8"), user["password_hash"].encode("utf-8")
            ):
                # Update last login
                await conn.execute(
                    """
                    UPDATE users SET last_login = NOW() WHERE id = $1
                """,
                    user["id"],
                )

                user_dict = dict(user)
                user_dict.pop("password_hash")  # Don't return password hash
                return user_dict

        return None

    def create_access_token(
        self, user_id: str, additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a JWT access token"""
        payload = {
            "user_id": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.now(timezone.utc),
            "type": "access",
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
    ) -> str:
        """Create an API key for a user"""
        # Generate secure API key
        api_key = f"sk-{secrets.token_urlsafe(32)}"
        key_hash = bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt())

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_keys (user_id, key_hash, name, permissions, expires_at)
                VALUES ($1, $2, $3, $4, $5)
            """,
                user_id,
                key_hash.decode("utf-8"),
                name,
                permissions or [],
                expires_at,
            )

        logger.info(f"Created API key '{name}' for user {user_id}")
        return api_key

    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Verify an API key and return associated user and permissions"""
        async with self.db_pool.acquire() as conn:
            # Get all active API keys (we need to check each hash)
            keys = await conn.fetch(
                """
                SELECT k.*, u.username, u.email, u.is_admin
                FROM api_keys k
                JOIN users u ON k.user_id = u.id
                WHERE k.is_active = TRUE
                AND u.is_active = TRUE
                AND (k.expires_at IS NULL OR k.expires_at > NOW())
            """
            )

            for key_record in keys:
                if bcrypt.checkpw(
                    api_key.encode("utf-8"), key_record["key_hash"].encode("utf-8")
                ):
                    # Update last used
                    await conn.execute(
                        """
                        UPDATE api_keys SET last_used = NOW() WHERE id = $1
                    """,
                        key_record["id"],
                    )

                    return {
                        "user_id": str(key_record["user_id"]),
                        "username": key_record["username"],
                        "email": key_record["email"],
                        "is_admin": key_record["is_admin"],
                        "permissions": key_record["permissions"],
                        "api_key_name": key_record["name"],
                    }

        return None

    async def create_session(
        self, user_id: str, token: str, device_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a session for a user"""
        token_hash = bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)

        async with self.db_pool.acquire() as conn:
            session = await conn.fetchrow(
                """
                INSERT INTO sessions (user_id, token_hash, device_info, expires_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """,
                user_id,
                token_hash.decode("utf-8"),
                device_info or {},
                expires_at,
            )

        return str(session["id"])

    async def verify_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a session token"""
        # First verify JWT
        payload = self.verify_token(token)
        if not payload:
            return None

        # Then check if session is still active
        async with self.db_pool.acquire() as conn:
            # We need to check all sessions since we can't reverse the hash
            sessions = await conn.fetch(
                """
                SELECT s.*, u.username, u.email, u.is_admin
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.user_id = $1
                AND s.is_active = TRUE
                AND s.expires_at > NOW()
                AND u.is_active = TRUE
            """,
                payload["user_id"],
            )

            # For now, just verify the user has an active session
            if sessions:
                return {
                    "user_id": payload["user_id"],
                    "username": sessions[0]["username"],
                    "email": sessions[0]["email"],
                    "is_admin": sessions[0]["is_admin"],
                }

        return None

    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE sessions SET is_active = FALSE WHERE id = $1
            """,
                session_id,
            )

        return result != "UPDATE 0"

    async def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key"""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE api_keys SET is_active = FALSE WHERE id = $1
            """,
                key_id,
            )

        return result != "UPDATE 0"

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        async with self.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, username, email, is_active, is_admin, created_at, last_login
                FROM users
                WHERE id = $1
            """,
                user_id,
            )

        return dict(user) if user else None


# Convenience functions
def create_access_token(user_id: str, additional_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a JWT access token (convenience function)"""
    auth = AuthManager()
    return auth.create_access_token(user_id, additional_claims)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a JWT token (convenience function)"""
    auth = AuthManager()
    return auth.verify_token(token)
