"""Tests for Voice agent functionality."""

import pytest
import asyncio
import tempfile
import base64
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from sarah.agents.voice import VoiceAgent
from sarah.services.audio_stream import AudioStreamService, AudioConfig


class TestVoiceAgent:
    """Test suite for VoiceAgent."""

    @pytest.fixture
    def voice_agent(self):
        """Create a VoiceAgent instance for testing."""
        agent = VoiceAgent("test_voice_agent")
        return agent

    @pytest.fixture
    def mock_whisper_model(self):
        """Mock Whisper model."""
        model = Mock()
        model.transcribe = Mock(return_value={"text": "Hello, Sarah"})
        return model

    @pytest.mark.asyncio
    async def test_initialization(self, voice_agent):
        """Test agent initialization."""
        with patch("whisper.load_model") as mock_load:
            mock_load.return_value = Mock()

            await voice_agent.initialize()

            assert voice_agent.state == "running"
            assert voice_agent.whisper_model is not None
            mock_load.assert_called_once_with("base")

    @pytest.mark.asyncio
    async def test_transcribe_audio(self, voice_agent, mock_whisper_model):
        """Test audio transcription."""
        voice_agent.whisper_model = mock_whisper_model

        # Create mock audio data
        audio_data = b"fake_audio_data"

        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            mock_file = Mock()
            mock_file.name = "/tmp/test.wav"
            mock_tmp.return_value.__enter__.return_value = mock_file

            result = await voice_agent.transcribe_audio(audio_data)

            assert result == "Hello, Sarah"
            mock_whisper_model.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_to_speech_macos(self, voice_agent):
        """Test text-to-speech on macOS."""
        text = "Hello, user"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock subprocess
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            with patch("pydub.AudioSegment.from_file") as mock_audio:
                mock_segment = Mock()
                mock_segment.export = Mock()
                mock_audio.return_value = mock_segment

                result = await voice_agent.text_to_speech(text)

                assert isinstance(result, Path)
                assert result.suffix == ".mp3"
                mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_available_voices(self, voice_agent):
        """Test getting available TTS voices."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock subprocess with voice list
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(
                return_value=(
                    b"Alex    en_US    # Most people...\nSamantha    en_US    # American...",
                    b"",
                )
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            voices = await voice_agent.get_available_voices()

            assert "Alex" in voices
            assert "Samantha" in voices

    @pytest.mark.asyncio
    async def test_handle_command_transcribe(self, voice_agent, mock_whisper_model):
        """Test handling transcribe command."""
        voice_agent.whisper_model = mock_whisper_model

        audio_data = base64.b64encode(b"fake_audio").decode()
        result = await voice_agent.handle_command(
            "transcribe", {"audio_data": audio_data}
        )

        assert "transcription" in result
        assert result["transcription"] == "Hello, Sarah"

    @pytest.mark.asyncio
    async def test_handle_command_speak(self, voice_agent):
        """Test handling speak command."""
        with patch.object(voice_agent, "text_to_speech") as mock_tts:
            mock_tts.return_value = Path("/tmp/output.mp3")

            result = await voice_agent.handle_command(
                "speak", {"text": "Hello", "voice": "Alex", "speed": 1.0}
            )

            assert "audio_file" in result
            assert result["audio_file"] == "/tmp/output.mp3"

    @pytest.mark.asyncio
    async def test_start_stop_recording(self, voice_agent):
        """Test starting and stopping recording."""
        with patch.object(voice_agent, "audio_stream") as mock_stream:
            mock_stream.start_stream = Mock()
            mock_stream.stop_stream = Mock()

            # Start recording
            await voice_agent.start_recording()
            assert voice_agent.is_recording is True
            mock_stream.start_stream.assert_called_once()

            # Stop recording
            await voice_agent.stop_recording()
            assert voice_agent.is_recording is False
            mock_stream.stop_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_voice_command(self, voice_agent):
        """Test processing voice command messages."""
        with patch.object(voice_agent, "handle_command") as mock_handle:
            mock_handle.return_value = {"result": "success"}

            with patch.object(voice_agent, "send_message") as mock_send:
                message = {
                    "type": "voice_command",
                    "command": "transcribe",
                    "data": {"audio_data": "test"},
                    "sender": "test_sender",
                    "request_id": "123",
                }

                await voice_agent.process_message(message)

                mock_handle.assert_called_once_with(
                    "transcribe", {"audio_data": "test"}
                )
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status(self, voice_agent):
        """Test getting agent status."""
        voice_agent.whisper_model = Mock()
        voice_agent.is_recording = True

        status = await voice_agent.get_status()

        assert status["agent_id"] == "test_voice_agent"
        assert status["state"] == "running"
        assert status["whisper_model"] == "base"
        assert status["model_loaded"] is True
        assert status["is_recording"] is True


class TestAudioStreamService:
    """Test suite for AudioStreamService."""

    @pytest.fixture
    def audio_config(self):
        """Create audio configuration."""
        return AudioConfig(
            rate=16000,
            chunk_size=1024,
            silence_threshold=500.0,
            silence_duration=1.0,
            min_speech_duration=0.5,
        )

    @pytest.fixture
    def audio_stream(self, audio_config):
        """Create AudioStreamService instance."""
        with patch("pyaudio.PyAudio"):
            service = AudioStreamService(audio_config)
            return service

    def test_initialization(self, audio_stream, audio_config):
        """Test audio stream initialization."""
        assert audio_stream.config == audio_config
        assert audio_stream.is_recording is False
        assert audio_stream.stream is None
        assert len(audio_stream.callbacks) == 0

    def test_add_remove_callback(self, audio_stream):
        """Test adding and removing callbacks."""
        callback = Mock()

        audio_stream.add_callback(callback)
        assert callback in audio_stream.callbacks

        audio_stream.remove_callback(callback)
        assert callback not in audio_stream.callbacks

    def test_start_stop_stream(self, audio_stream):
        """Test starting and stopping audio stream."""
        with patch.object(audio_stream.pyaudio, "open") as mock_open:
            mock_stream = Mock()
            mock_open.return_value = mock_stream

            # Start stream
            audio_stream.start_stream()
            assert audio_stream.stream is not None
            assert audio_stream.is_recording is True
            mock_stream.start_stream.assert_called_once()

            # Stop stream
            audio_stream.stop_stream()
            assert audio_stream.stream is None
            assert audio_stream.is_recording is False
            mock_stream.stop_stream.assert_called_once()
            mock_stream.close.assert_called_once()

    def test_get_audio_devices(self, audio_stream):
        """Test getting audio input devices."""
        with patch.object(
            audio_stream.pyaudio, "get_host_api_info_by_index"
        ) as mock_api:
            mock_api.return_value = {"deviceCount": 2}

            with patch.object(
                audio_stream.pyaudio, "get_device_info_by_index"
            ) as mock_device:
                mock_device.side_effect = [
                    {"maxInputChannels": 2, "name": "Microphone"},
                    {"maxInputChannels": 0, "name": "Speaker"},
                ]

                devices = audio_stream.get_audio_devices()

                assert len(devices) == 1
                assert devices[0] == (0, "Microphone")

    def test_get_current_volume(self, audio_stream):
        """Test getting current volume level."""
        import numpy as np

        # Add some audio data to buffer
        audio_stream.audio_buffer.extend(
            np.array([1000, -1000, 500, -500], dtype=np.int16)
        )

        volume = audio_stream.get_current_volume()

        assert 0 <= volume <= 100
        assert volume > 0  # Should have some volume with this data

    def test_save_buffer_to_file(self, audio_stream):
        """Test saving audio buffer to file."""
        import numpy as np

        # Add some audio data to buffer
        audio_stream.audio_buffer.extend(
            np.array([1000, -1000, 500, -500], dtype=np.int16)
        )

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("wave.open") as mock_wave:
                mock_writer = Mock()
                mock_wave.return_value.__enter__.return_value = mock_writer

                audio_stream.save_buffer_to_file(tmp_path)

                mock_writer.setnchannels.assert_called_once_with(1)
                mock_writer.setframerate.assert_called_once_with(16000)
                mock_writer.writeframes.assert_called_once()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_voice_activity_detection(self, audio_stream):
        """Test voice activity detection logic."""
        import numpy as np

        # Mock callback
        callback = AsyncMock()
        audio_stream.add_callback(callback)

        # Simulate speech (high RMS)
        loud_audio = np.array([3000] * 1024, dtype=np.int16)
        await audio_stream._process_audio_chunk(loud_audio)

        assert audio_stream.is_speaking is True
        assert len(audio_stream.speech_buffer) == 1

        # Simulate silence (low RMS)
        quiet_audio = np.array([100] * 1024, dtype=np.int16)

        # Need enough silence to trigger end of speech
        for _ in range(20):  # 20 chunks * 1024/16000 = ~1.3 seconds
            await audio_stream._process_audio_chunk(quiet_audio)

        # Speech should have ended and callback triggered
        assert audio_stream.is_speaking is False
        assert len(audio_stream.speech_buffer) == 0
        callback.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
