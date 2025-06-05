"""Voice agent for speech-to-text and text-to-speech functionality."""

import io
import json
import asyncio
import tempfile
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path
import numpy as np
import whisper
from pydub import AudioSegment
from pydub.playback import play

from sarah.agents.base import BaseAgent
from sarah.services.audio_stream import AudioStreamService, AudioConfig


class VoiceAgent(BaseAgent):
    """Agent for handling voice input/output with Whisper and TTS."""

    def __init__(self, agent_id: str = "voice_agent"):
        super().__init__(agent_id)
        self.whisper_model: Optional[whisper.Whisper] = None
        self.model_size = "base"  # Options: tiny, base, small, medium, large
        self.is_recording = False
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self.audio_stream: Optional[AudioStreamService] = None

    async def initialize(self):
        """Initialize the voice agent."""
        await super().initialize()
        self.logger.info("Loading Whisper model...")
        try:
            self.whisper_model = whisper.load_model(self.model_size)
            self.logger.info(f"Whisper model '{self.model_size}' loaded successfully")

            # Initialize audio stream service
            self.audio_stream = AudioStreamService()
            self.audio_stream.add_callback(self._on_speech_detected)

        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def handle_command(
        self, command: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle voice-specific commands."""
        try:
            if command == "transcribe":
                # Transcribe audio data
                audio_data = data.get("audio_data")
                if not audio_data:
                    return {"error": "No audio data provided"}

                result = await self.transcribe_audio(audio_data)
                return {"transcription": result}

            elif command == "speak":
                # Convert text to speech
                text = data.get("text", "")
                voice = data.get("voice", "default")
                speed = data.get("speed", 1.0)

                audio_file = await self.text_to_speech(text, voice, speed)
                return {"audio_file": str(audio_file)}

            elif command == "start_recording":
                # Start continuous recording
                await self.start_recording()
                return {"status": "recording_started"}

            elif command == "stop_recording":
                # Stop recording
                await self.stop_recording()
                return {"status": "recording_stopped"}

            elif command == "get_available_voices":
                # Get list of available TTS voices
                voices = await self.get_available_voices()
                return {"voices": voices}

            else:
                return {"error": f"Unknown command: {command}"}

        except Exception as e:
            self.logger.error(f"Error handling command {command}: {e}")
            return {"error": str(e)}

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio data to text using Whisper."""
        if not self.whisper_model:
            raise RuntimeError("Whisper model not loaded")

        # Save audio data to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(audio_data)
            tmp_path = tmp_file.name

        try:
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(
                tmp_path,
                fp16=False,  # Use FP32 for better compatibility
                language="en",  # Auto-detect language if None
                task="transcribe",
            )

            return result["text"].strip()

        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    async def text_to_speech(
        self, text: str, voice: str = "default", speed: float = 1.0
    ) -> Path:
        """Convert text to speech using system TTS."""
        # For now, use macOS 'say' command as a simple TTS solution
        # In production, integrate with more advanced TTS like Azure, Google Cloud TTS, or Eleven Labs

        output_file = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False)
        output_path = Path(output_file.name)
        output_file.close()

        try:
            # Use macOS 'say' command
            cmd = ["say", "-o", str(output_path), "-r", str(int(200 * speed))]

            # Add voice if specified and not default
            if voice != "default":
                cmd.extend(["-v", voice])

            cmd.append(text)

            # Run TTS command
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise RuntimeError(f"TTS failed: {stderr.decode()}")

            # Convert AIFF to MP3 for smaller file size
            mp3_path = output_path.with_suffix(".mp3")
            audio = AudioSegment.from_file(str(output_path), format="aiff")
            audio.export(str(mp3_path), format="mp3")

            # Remove AIFF file
            output_path.unlink()

            return mp3_path

        except Exception as e:
            # Clean up on error
            output_path.unlink(missing_ok=True)
            raise e

    async def get_available_voices(self) -> List[str]:
        """Get list of available TTS voices."""
        # For macOS, get system voices
        try:
            process = await asyncio.create_subprocess_exec(
                "say",
                "-v",
                "?",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ["default"]

            # Parse voice list
            voices = []
            for line in stdout.decode().strip().split("\n"):
                if line:
                    # Format: "Voice Name    Language  # Comment"
                    parts = line.split()
                    if parts:
                        voice_name = parts[0]
                        voices.append(voice_name)

            return voices if voices else ["default"]

        except Exception as e:
            self.logger.error(f"Failed to get voice list: {e}")
            return ["default"]

    async def start_recording(self):
        """Start continuous audio recording."""
        if self.is_recording or not self.audio_stream:
            return

        self.is_recording = True
        self.audio_stream.start_stream()
        self.logger.info("Started audio recording")

    async def stop_recording(self):
        """Stop audio recording."""
        if not self.is_recording or not self.audio_stream:
            return

        self.is_recording = False
        self.audio_stream.stop_stream()
        self.logger.info("Stopped audio recording")

    async def _on_speech_detected(self, audio_data: bytes):
        """Callback when speech is detected."""
        try:
            # Transcribe the audio
            text = await self.transcribe_audio(audio_data)

            if text:
                # Send transcription to director
                await self.send_message(
                    {
                        "type": "voice_transcription",
                        "text": text,
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                    "director_agent",
                )

                # Also put in queue for any listeners
                await self.audio_queue.put({"type": "transcription", "text": text})

        except Exception as e:
            self.logger.error(f"Error processing speech: {e}")

    async def process_message(self, message: Dict[str, Any]):
        """Process incoming messages."""
        message_type = message.get("type", "")

        if message_type == "voice_command":
            # Handle voice commands from other agents
            command = message.get("command", "")
            data = message.get("data", {})

            result = await self.handle_command(command, data)

            # Send response back
            await self.send_message(
                {
                    "type": "voice_response",
                    "request_id": message.get("request_id"),
                    "result": result,
                },
                message.get("sender"),
            )

        elif message_type == "transcribe_request":
            # Direct transcription request
            audio_data = message.get("audio_data")
            if audio_data:
                try:
                    text = await self.transcribe_audio(audio_data)
                    await self.send_message(
                        {
                            "type": "transcription_result",
                            "text": text,
                            "request_id": message.get("request_id"),
                        },
                        message.get("sender"),
                    )
                except Exception as e:
                    await self.send_message(
                        {
                            "type": "transcription_error",
                            "error": str(e),
                            "request_id": message.get("request_id"),
                        },
                        message.get("sender"),
                    )

    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        status = await super().get_status()
        status.update(
            {
                "whisper_model": self.model_size,
                "model_loaded": self.whisper_model is not None,
                "is_recording": self.is_recording,
                "audio_queue_size": self.audio_queue.qsize(),
            }
        )
        return status
