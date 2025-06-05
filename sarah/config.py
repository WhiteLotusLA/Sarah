"""
Sarah configuration management
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load port configuration
env_path = Path(__file__).parent.parent / ".sarah_ports.env"
load_dotenv(env_path)


class Config:
    """Central configuration for Sarah"""

    # Core ports
    MAIN_PORT = int(os.getenv("SARAH_MAIN_PORT", "8001"))
    WEBSOCKET_PORT = int(os.getenv("SARAH_WEBSOCKET_PORT", "8002"))
    API_PORT = int(os.getenv("SARAH_API_PORT", "8003"))
    ADMIN_PORT = int(os.getenv("SARAH_ADMIN_PORT", "8004"))

    # Database
    POSTGRES_PORT = int(os.getenv("SARAH_POSTGRES_PORT", "5433"))
    REDIS_PORT = int(os.getenv("SARAH_REDIS_PORT", "6380"))
    VECTOR_DB_PORT = int(os.getenv("SARAH_VECTOR_DB_PORT", "8200"))

    # AI Services
    OLLAMA_PORT = int(os.getenv("SARAH_OLLAMA_PORT", "11434"))
    OLLAMA_BASE_URL = f"http://localhost:{OLLAMA_PORT}"

    # Frontend
    UI_PORT = int(os.getenv("SARAH_UI_PORT", "3457"))
    DEV_UI_PORT = int(os.getenv("SARAH_DEV_UI_PORT", "5174"))

    # Logging
    LOG_LEVEL = os.getenv("SARAH_LOG_LEVEL", "INFO")
    LOG_DIR = Path(os.getenv("SARAH_LOG_DIR", "logs"))

    # Memory
    MEMORY_DIR = Path(os.getenv("SARAH_MEMORY_DIR", "data/memory"))

    # Security
    JWT_SECRET_KEY = os.getenv("SARAH_JWT_SECRET_KEY", None)
    MASTER_KEY = os.getenv("SARAH_MASTER_KEY", None)
    SESSION_TIMEOUT_HOURS = int(os.getenv("SARAH_SESSION_TIMEOUT_HOURS", "24"))

    # Ensure directories exist
    LOG_DIR.mkdir(exist_ok=True, parents=True)
    MEMORY_DIR.mkdir(exist_ok=True, parents=True)

    @classmethod
    def get_agent_port(cls, agent_name: str) -> int:
        """Get port for a specific agent"""
        env_key = f"SARAH_{agent_name.upper()}_AGENT_PORT"
        default_ports = {
            "DIRECTOR": 8100,
            "CALENDAR": 8101,
            "EMAIL": 8102,
            "BROWSER": 8103,
            "MEMORY": 8104,
            "TASK": 8105,
            "HOME": 8106,
            "HEALTH": 8107,
            "FINANCE": 8108,
            "LEARNING": 8109,
            "CREATIVE": 8110,
        }
        return int(os.getenv(env_key, default_ports.get(agent_name.upper(), 8199)))


# Create a default instance for compatibility
config = Config()
