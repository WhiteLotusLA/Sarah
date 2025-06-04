#!/usr/bin/env python3
"""
Sarah AI - Main entry point
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncpg  # type: ignore

from sarah.core.consciousness import Consciousness
from sarah.config import Config
from sarah.api.auth_routes import router as auth_router
from sarah.api.dependencies import init_auth_dependencies, get_current_user_optional

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_DIR / "sarah.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sarah AI", description="Your transcendent digital companion", version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)

# Global instances
sarah: Optional[Consciousness] = None
db_pool: Optional[asyncpg.Pool] = None


@app.on_event("startup")
async def startup_event():
    """Initialize Sarah on startup"""
    global sarah, db_pool
    logger.info("🌸 Starting Sarah AI...")

    # Initialize database pool
    db_pool = await asyncpg.create_pool("postgresql://localhost/sarah_db")

    # Initialize authentication
    await init_auth_dependencies(db_pool)

    # Initialize Sarah
    sarah = Consciousness()
    await sarah.awaken()

    logger.info("✨ Sarah AI is ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown"""
    global sarah, db_pool
    if sarah:
        await sarah.sleep()
    if db_pool:
        await db_pool.close()
    logger.info("🌙 Sarah AI has gracefully shut down")


@app.get("/")
async def root(user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Root endpoint"""
    return {
        "name": "Sarah AI",
        "status": sarah.state if sarah else "not initialized",
        "message": "Your digital companion awaits",
        "authenticated": user is not None,
        "user": user["username"] if user else None,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if sarah and sarah.state == "awakened" else "initializing",
        "consciousness": sarah.state if sarah else None,
    }


@app.get("/memory/stats")
async def memory_stats():
    """Get memory system statistics"""
    if sarah and sarah.memory and hasattr(sarah.memory, "get_statistics"):
        stats = await sarah.memory.get_statistics()
        return {"status": "ok", "stats": stats}
    else:
        return {"status": "error", "message": "Memory system not available"}


@app.post("/memory/search")
async def search_memory(query: str):
    """Search memories"""
    if sarah and sarah.memory and hasattr(sarah.memory, "recall"):
        memories = await sarah.memory.recall(query, limit=5)
        return {"status": "ok", "memories": memories}
    else:
        return {"status": "error", "message": "Memory system not available"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    logger.info("New WebSocket connection established")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # Process with Sarah
            if sarah:
                response = await sarah.process_intent(data)
                await websocket.send_json(response)
            else:
                await websocket.send_json({"error": "Sarah is still awakening..."})

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal")
    sys.exit(0)


if __name__ == "__main__":
    # Handle shutdown signals
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Create necessary directories
    Config.LOG_DIR.mkdir(exist_ok=True)

    # Run the server
    uvicorn.run(
        "main:app", host="0.0.0.0", port=Config.MAIN_PORT, reload=True, log_level="info"
    )
