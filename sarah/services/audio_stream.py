"""Audio streaming service for real-time voice capture and processing."""

import asyncio
import io
import wave
import struct
import threading
from typing import Optional, Callable, List, Tuple
from collections import deque
import numpy as np
import pyaudio
from dataclasses import dataclass
import logging


@dataclass
class AudioConfig:
    """Audio configuration parameters."""

    format: int = pyaudio.paInt16
    channels: int = 1
    rate: int = 16000  # 16kHz is good for speech
    chunk_size: int = 1024
    record_seconds: float = 5.0

    # Voice Activity Detection (VAD) parameters
    silence_threshold: float = 500.0  # RMS threshold for silence
    silence_duration: float = 1.0  # Seconds of silence before stopping
    min_speech_duration: float = 0.5  # Minimum speech duration to process


class AudioStreamService:
    """Service for handling audio streaming and voice activity detection."""

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_recording = False
        self.audio_buffer = deque(
            maxlen=int(self.config.rate * 10)
        )  # 10 seconds buffer
        self.callbacks: List[Callable] = []
        self.logger = logging.getLogger(__name__)

        # Voice activity detection state
        self.is_speaking = False
        self.silence_start = None
        self.speech_buffer = []

    def add_callback(self, callback: Callable):
        """Add a callback for when speech is detected."""
        self.callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """Remove a callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def start_stream(self):
        """Start the audio stream."""
        if self.stream is not None:
            return

        try:
            self.stream = self.pyaudio.open(
                format=self.config.format,
                channels=self.config.channels,
                rate=self.config.rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
                stream_callback=self._audio_callback,
            )

            self.stream.start_stream()
            self.is_recording = True
            self.logger.info("Audio stream started")

        except Exception as e:
            self.logger.error(f"Failed to start audio stream: {e}")
            raise

    def stop_stream(self):
        """Stop the audio stream."""
        if self.stream is None:
            return

        self.is_recording = False
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        self.logger.info("Audio stream stopped")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream."""
        if status:
            self.logger.warning(f"Audio stream status: {status}")

        # Convert byte data to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)

        # Add to buffer
        self.audio_buffer.extend(audio_data)

        # Perform voice activity detection
        asyncio.create_task(self._process_audio_chunk(audio_data))

        return (in_data, pyaudio.paContinue)

    async def _process_audio_chunk(self, audio_chunk: np.ndarray):
        """Process audio chunk for voice activity detection."""
        # Calculate RMS (Root Mean Square) for volume level
        rms = np.sqrt(np.mean(audio_chunk**2))

        # Voice activity detection
        if rms > self.config.silence_threshold:
            # Speech detected
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_buffer = []
                self.logger.debug("Speech started")

            self.speech_buffer.append(audio_chunk)
            self.silence_start = None

        else:
            # Silence detected
            if self.is_speaking:
                if self.silence_start is None:
                    self.silence_start = asyncio.get_event_loop().time()
                    self.speech_buffer.append(audio_chunk)
                else:
                    # Check if silence duration exceeded
                    silence_duration = (
                        asyncio.get_event_loop().time() - self.silence_start
                    )

                    if silence_duration >= self.config.silence_duration:
                        # End of speech detected
                        self.is_speaking = False

                        # Check if speech was long enough
                        speech_duration = (
                            len(self.speech_buffer)
                            * self.config.chunk_size
                            / self.config.rate
                        )

                        if speech_duration >= self.config.min_speech_duration:
                            # Process the speech
                            await self._process_speech(self.speech_buffer)

                        self.speech_buffer = []
                        self.silence_start = None
                        self.logger.debug("Speech ended")
                    else:
                        # Still within silence threshold, keep buffering
                        self.speech_buffer.append(audio_chunk)

    async def _process_speech(self, speech_chunks: List[np.ndarray]):
        """Process detected speech."""
        # Combine all chunks
        audio_data = np.concatenate(speech_chunks)

        # Convert to bytes
        audio_bytes = audio_data.tobytes()

        # Create WAV format in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self.config.channels)
            wav_file.setsampwidth(self.pyaudio.get_sample_size(self.config.format))
            wav_file.setframerate(self.config.rate)
            wav_file.writeframes(audio_bytes)

        wav_buffer.seek(0)
        wav_data = wav_buffer.read()

        # Call all registered callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(wav_data)
                else:
                    callback(wav_data)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    def get_audio_devices(self) -> List[Tuple[int, str]]:
        """Get list of available audio input devices."""
        devices = []
        info = self.pyaudio.get_host_api_info_by_index(0)
        num_devices = info.get("deviceCount", 0)

        for i in range(num_devices):
            device_info = self.pyaudio.get_device_info_by_index(i)
            if device_info.get("maxInputChannels", 0) > 0:
                devices.append((i, device_info.get("name", f"Device {i}")))

        return devices

    def set_input_device(self, device_index: int):
        """Set the input device for recording."""
        # Stop current stream if running
        if self.stream:
            self.stop_stream()

        # Update configuration
        self.input_device_index = device_index

        # Restart stream if it was running
        if self.is_recording:
            self.start_stream()

    def get_current_volume(self) -> float:
        """Get current audio input volume level (0-100)."""
        if not self.audio_buffer:
            return 0.0

        # Get recent audio data
        recent_data = list(self.audio_buffer)[-self.config.chunk_size :]
        if not recent_data:
            return 0.0

        # Calculate RMS
        audio_array = np.array(recent_data)
        rms = np.sqrt(np.mean(audio_array**2))

        # Normalize to 0-100 range
        max_value = 32768  # Max value for 16-bit audio
        volume = (rms / max_value) * 100

        return min(volume, 100.0)

    def save_buffer_to_file(self, filename: str):
        """Save current audio buffer to a WAV file."""
        if not self.audio_buffer:
            return

        audio_data = np.array(self.audio_buffer, dtype=np.int16)

        with wave.open(filename, "wb") as wav_file:
            wav_file.setnchannels(self.config.channels)
            wav_file.setsampwidth(self.pyaudio.get_sample_size(self.config.format))
            wav_file.setframerate(self.config.rate)
            wav_file.writeframes(audio_data.tobytes())

    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.stream:
            self.stop_stream()
        self.pyaudio.terminate()
