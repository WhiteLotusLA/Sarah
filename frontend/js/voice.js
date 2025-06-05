/**
 * Voice interface module for Sarah AI
 */

class VoiceInterface {
  constructor() {
    this.ws = null;
    this.isRecording = false;
    this.isConnected = false;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.recordButton = null;
    this.statusElement = null;
    this.transcriptionElement = null;
    this.voiceSelect = null;

    // Audio context for visualization
    this.audioContext = null;
    this.analyser = null;
    this.visualizationCanvas = null;
    this.visualizationCtx = null;
    this.animationId = null;
  }

  async initialize() {
    console.log("Initializing voice interface...");

    // Get DOM elements
    this.recordButton = document.getElementById("record-button");
    this.statusElement = document.getElementById("voice-status");
    this.transcriptionElement = document.getElementById("transcription");
    this.voiceSelect = document.getElementById("voice-select");
    this.visualizationCanvas = document.getElementById("audio-visualization");

    if (this.visualizationCanvas) {
      this.visualizationCtx = this.visualizationCanvas.getContext("2d");
    }

    // Set up event listeners
    if (this.recordButton) {
      this.recordButton.addEventListener("click", () => this.toggleRecording());
    }

    // Connect to voice WebSocket
    await this.connectWebSocket();

    // Request microphone permissions
    await this.requestMicrophonePermission();

    // Load available voices
    await this.loadAvailableVoices();
  }

  async connectWebSocket() {
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/voice`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("Voice WebSocket connected");
        this.isConnected = true;
        this.updateStatus("Connected", "success");
      };

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.handleWebSocketMessage(data);
      };

      this.ws.onerror = (error) => {
        console.error("Voice WebSocket error:", error);
        this.updateStatus("Connection error", "error");
      };

      this.ws.onclose = () => {
        console.log("Voice WebSocket disconnected");
        this.isConnected = false;
        this.updateStatus("Disconnected", "error");

        // Attempt to reconnect after 3 seconds
        setTimeout(() => this.connectWebSocket(), 3000);
      };
    } catch (error) {
      console.error("Failed to connect to voice WebSocket:", error);
      this.updateStatus("Failed to connect", "error");
    }
  }

  async requestMicrophonePermission() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Set up audio visualization
      this.setupAudioVisualization(stream);

      // Set up media recorder
      this.setupMediaRecorder(stream);

      this.updateStatus("Microphone ready", "success");
    } catch (error) {
      console.error("Microphone permission denied:", error);
      this.updateStatus("Microphone access denied", "error");
      if (this.recordButton) {
        this.recordButton.disabled = true;
      }
    }
  }

  setupAudioVisualization(stream) {
    if (!this.visualizationCanvas) return;

    this.audioContext = new (window.AudioContext ||
      window.webkitAudioContext)();
    this.analyser = this.audioContext.createAnalyser();

    const source = this.audioContext.createMediaStreamSource(stream);
    source.connect(this.analyser);

    this.analyser.fftSize = 2048;
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      this.animationId = requestAnimationFrame(draw);

      this.analyser.getByteTimeDomainData(dataArray);

      this.visualizationCtx.fillStyle = "rgb(240, 240, 240)";
      this.visualizationCtx.fillRect(
        0,
        0,
        this.visualizationCanvas.width,
        this.visualizationCanvas.height,
      );

      this.visualizationCtx.lineWidth = 2;
      this.visualizationCtx.strokeStyle = this.isRecording
        ? "rgb(255, 0, 0)"
        : "rgb(0, 0, 0)";

      this.visualizationCtx.beginPath();

      const sliceWidth = (this.visualizationCanvas.width * 1.0) / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * this.visualizationCanvas.height) / 2;

        if (i === 0) {
          this.visualizationCtx.moveTo(x, y);
        } else {
          this.visualizationCtx.lineTo(x, y);
        }

        x += sliceWidth;
      }

      this.visualizationCtx.lineTo(
        this.visualizationCanvas.width,
        this.visualizationCanvas.height / 2,
      );
      this.visualizationCtx.stroke();
    };

    draw();
  }

  setupMediaRecorder(stream) {
    const mimeType = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/ogg";

    this.mediaRecorder = new MediaRecorder(stream, { mimeType });

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(this.audioChunks, { type: mimeType });
      this.audioChunks = [];

      // Convert to base64 and send for transcription
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64Audio = reader.result.split(",")[1];
        this.sendCommand("transcribe", { audio_data: base64Audio });
      };
      reader.readAsDataURL(audioBlob);
    };
  }

  async toggleRecording() {
    if (this.isRecording) {
      await this.stopRecording();
    } else {
      await this.startRecording();
    }
  }

  async startRecording() {
    if (!this.isConnected || !this.mediaRecorder) {
      this.updateStatus("Not ready to record", "error");
      return;
    }

    try {
      // Start continuous recording mode
      this.sendCommand("start_recording");

      // Start local recording for backup
      this.mediaRecorder.start(100); // Collect data every 100ms

      this.isRecording = true;
      this.recordButton.textContent = "Stop Recording";
      this.recordButton.classList.add("recording");
      this.updateStatus("Recording...", "info");
    } catch (error) {
      console.error("Failed to start recording:", error);
      this.updateStatus("Failed to start recording", "error");
    }
  }

  async stopRecording() {
    try {
      // Stop continuous recording mode
      this.sendCommand("stop_recording");

      // Stop local recording
      if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
        this.mediaRecorder.stop();
      }

      this.isRecording = false;
      this.recordButton.textContent = "Start Recording";
      this.recordButton.classList.remove("recording");
      this.updateStatus("Processing...", "info");
    } catch (error) {
      console.error("Failed to stop recording:", error);
      this.updateStatus("Failed to stop recording", "error");
    }
  }

  async loadAvailableVoices() {
    if (!this.isConnected) return;

    this.sendCommand("get_voices");
  }

  sendCommand(command, data = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("WebSocket not connected");
      return;
    }

    const message = {
      command: command,
      ...data,
    };

    this.ws.send(JSON.stringify(message));
  }

  handleWebSocketMessage(data) {
    switch (data.type) {
      case "transcription":
        this.displayTranscription(data.text);
        // Also send to main chat
        if (window.app && window.app.chat) {
          window.app.chat.addMessage(data.text, "user");
          // Process with Sarah
          window.app.chat.sendMessage(data.text);
        }
        break;

      case "audio":
        // Play TTS audio
        this.playAudio(data.audio_data, data.format);
        break;

      case "voices":
        // Update voice select options
        this.updateVoiceOptions(data.voices);
        break;

      case "error":
        console.error("Voice error:", data.error);
        this.updateStatus(`Error: ${data.error}`, "error");
        break;

      default:
        if (data.status) {
          this.updateStatus(data.status, "info");
        }
    }
  }

  displayTranscription(text) {
    if (this.transcriptionElement) {
      const transcriptionDiv = document.createElement("div");
      transcriptionDiv.className = "transcription-item";
      transcriptionDiv.textContent = text;

      this.transcriptionElement.insertBefore(
        transcriptionDiv,
        this.transcriptionElement.firstChild,
      );

      // Keep only last 10 transcriptions
      while (this.transcriptionElement.children.length > 10) {
        this.transcriptionElement.removeChild(
          this.transcriptionElement.lastChild,
        );
      }
    }

    this.updateStatus("Transcription complete", "success");
  }

  playAudio(base64Audio, format) {
    const audio = new Audio();
    audio.src = `data:audio/${format};base64,${base64Audio}`;
    audio.play().catch((error) => {
      console.error("Failed to play audio:", error);
    });
  }

  updateVoiceOptions(voices) {
    if (!this.voiceSelect) return;

    // Clear existing options
    this.voiceSelect.innerHTML = "";

    // Add default option
    const defaultOption = document.createElement("option");
    defaultOption.value = "default";
    defaultOption.textContent = "Default Voice";
    this.voiceSelect.appendChild(defaultOption);

    // Add voice options
    voices.forEach((voice) => {
      const option = document.createElement("option");
      option.value = voice;
      option.textContent = voice;
      this.voiceSelect.appendChild(option);
    });
  }

  updateStatus(message, type = "info") {
    if (this.statusElement) {
      this.statusElement.textContent = message;
      this.statusElement.className = `voice-status ${type}`;
    }
  }

  // Public API for text-to-speech
  async speak(text, voice = "default", speed = 1.0) {
    if (!this.isConnected) {
      console.error("Voice interface not connected");
      return;
    }

    this.sendCommand("speak", { text, voice, speed });
  }

  destroy() {
    // Stop recording if active
    if (this.isRecording) {
      this.stopRecording();
    }

    // Close WebSocket
    if (this.ws) {
      this.ws.close();
    }

    // Stop audio visualization
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }

    // Close audio context
    if (this.audioContext) {
      this.audioContext.close();
    }
  }
}

// Export for use in other modules
window.VoiceInterface = VoiceInterface;
