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
import json
import base64

from sarah.core.consciousness import Consciousness
from sarah.config import Config
from sarah.api.auth_routes import router as auth_router
from sarah.api.backup_routes import router as backup_router
from sarah.api.rate_limit_routes import router as rate_limit_router
from sarah.api.dependencies import init_auth_dependencies, get_current_user_optional
from sarah.services.backup import backup_service
from sarah.services.rate_limiter import rate_limiter, ThrottleMiddleware
from sarah.agents.voice import VoiceAgent

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
app.include_router(backup_router)
app.include_router(rate_limit_router)

# Global instances
sarah: Optional[Consciousness] = None
db_pool: Optional[asyncpg.Pool] = None
voice_agent: Optional[VoiceAgent] = None


@app.on_event("startup")
async def startup_event():
    """Initialize Sarah on startup"""
    global sarah, db_pool, voice_agent
    logger.info("🌸 Starting Sarah AI...")

    # Initialize database pool
    db_pool = await asyncpg.create_pool("postgresql://localhost/sarah_db")

    # Initialize authentication
    await init_auth_dependencies(db_pool)

    # Initialize Sarah
    sarah = Consciousness()
    await sarah.awaken()

    # Initialize backup service
    await backup_service.initialize()

    # Initialize rate limiter
    await rate_limiter.initialize()

    # Add rate limiting middleware
    app.add_middleware(ThrottleMiddleware, rate_limiter=rate_limiter)

    # Initialize voice agent
    voice_agent = VoiceAgent()
    await voice_agent.initialize()

    logger.info("✨ Sarah AI is ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown"""
    global sarah, db_pool

    # Shutdown services
    await backup_service.shutdown()
    await rate_limiter.shutdown()

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


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket endpoint for voice streaming"""
    await websocket.accept()
    logger.info("Voice WebSocket connection established")

    if not voice_agent:
        await websocket.send_json({"error": "Voice agent not initialized"})
        await websocket.close()
        return

    try:
        while True:
            # Receive message from client
            message = await websocket.receive_json()
            command = message.get("command", "")

            if command == "start_recording":
                # Start voice recording
                await voice_agent.start_recording()
                await websocket.send_json({"status": "recording_started"})

                # Start sending transcriptions
                while voice_agent.is_recording:
                    try:
                        # Get transcription from queue (with timeout)
                        transcription = await asyncio.wait_for(
                            voice_agent.audio_queue.get(), timeout=0.5
                        )
                        await websocket.send_json(transcription)
                    except asyncio.TimeoutError:
                        continue

            elif command == "stop_recording":
                # Stop voice recording
                await voice_agent.stop_recording()
                await websocket.send_json({"status": "recording_stopped"})

            elif command == "transcribe":
                # One-shot transcription
                audio_data = message.get("audio_data", "")
                if audio_data:
                    # Decode base64 audio data
                    try:
                        audio_bytes = base64.b64decode(audio_data)
                        text = await voice_agent.transcribe_audio(audio_bytes)
                        await websocket.send_json(
                            {"type": "transcription", "text": text}
                        )
                    except Exception as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "error": f"Transcription failed: {str(e)}",
                            }
                        )

            elif command == "speak":
                # Text-to-speech
                text = message.get("text", "")
                voice = message.get("voice", "default")
                speed = message.get("speed", 1.0)

                try:
                    audio_path = await voice_agent.text_to_speech(text, voice, speed)
                    # Read audio file and send as base64
                    with open(audio_path, "rb") as f:
                        audio_data = base64.b64encode(f.read()).decode()

                    await websocket.send_json(
                        {"type": "audio", "audio_data": audio_data, "format": "mp3"}
                    )

                    # Clean up
                    audio_path.unlink()

                except Exception as e:
                    await websocket.send_json(
                        {"type": "error", "error": f"TTS failed: {str(e)}"}
                    )

            elif command == "get_voices":
                # Get available voices
                voices = await voice_agent.get_available_voices()
                await websocket.send_json({"type": "voices", "voices": voices})

    except WebSocketDisconnect:
        logger.info("Voice WebSocket connection closed")
        if voice_agent.is_recording:
            await voice_agent.stop_recording()


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
