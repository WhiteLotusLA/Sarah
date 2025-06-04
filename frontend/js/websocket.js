// WebSocket Service for Sarah AI

class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectInterval = 5000;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.listeners = new Map();
    this.isConnected = false;
    this.messageQueue = [];
  }

  connect() {
    const wsUrl = "ws://localhost:8000/ws";
    const token = localStorage.getItem("authToken");

    if (token) {
      this.ws = new WebSocket(`${wsUrl}?token=${token}`);
    } else {
      this.ws = new WebSocket(wsUrl);
    }

    this.ws.onopen = () => {
      console.log("WebSocket connected");
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.updateConnectionStatus(true);

      // Send any queued messages
      while (this.messageQueue.length > 0) {
        const message = this.messageQueue.shift();
        this.send(message);
      }

      this.emit("connected");
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      this.emit("error", error);
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
      this.isConnected = false;
      this.updateConnectionStatus(false);
      this.emit("disconnected");

      // Attempt to reconnect
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(
          `Reconnecting in ${this.reconnectInterval}ms... (attempt ${this.reconnectAttempts})`,
        );
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(message) {
    if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      // Queue message if not connected
      this.messageQueue.push(message);
    }
  }

  handleMessage(data) {
    const { type, payload } = data;

    switch (type) {
      case "chat_response":
        this.emit("chatResponse", payload);
        break;

      case "agent_update":
        this.emit("agentUpdate", payload);
        break;

      case "task_update":
        this.emit("taskUpdate", payload);
        break;

      case "calendar_update":
        this.emit("calendarUpdate", payload);
        break;

      case "email_notification":
        this.emit("emailNotification", payload);
        break;

      case "system_notification":
        this.emit("systemNotification", payload);
        break;

      default:
        console.log("Unknown message type:", type);
        this.emit("message", data);
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
  }

  updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById("connectionStatus");
    const statusText = document.getElementById("connectionText");

    if (statusIndicator) {
      if (connected) {
        statusIndicator.classList.add("connected");
      } else {
        statusIndicator.classList.remove("connected");
      }
    }

    if (statusText) {
      statusText.textContent = connected ? "Connected" : "Disconnected";
    }
  }

  // Helper methods for common message types
  sendChatMessage(message) {
    this.send({
      type: "chat_message",
      payload: { message },
    });
  }

  subscribeToAgent(agentId) {
    this.send({
      type: "subscribe_agent",
      payload: { agent_id: agentId },
    });
  }

  unsubscribeFromAgent(agentId) {
    this.send({
      type: "unsubscribe_agent",
      payload: { agent_id: agentId },
    });
  }
}

// Create singleton instance
const websocket = new WebSocketService();
window.websocket = websocket;
