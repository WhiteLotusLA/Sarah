// Chat functionality for Sarah AI

class ChatManager {
  constructor() {
    this.messagesContainer = document.getElementById("messagesContainer");
    this.messageInput = document.getElementById("messageInput");
    this.sendBtn = document.getElementById("sendBtn");
    this.messages = [];

    this.initializeEventListeners();
    this.loadChatHistory();
  }

  initializeEventListeners() {
    // Send button click
    this.sendBtn.addEventListener("click", () => this.sendMessage());

    // Enter key to send (Shift+Enter for new line)
    this.messageInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Auto-resize textarea
    this.messageInput.addEventListener("input", () => {
      this.messageInput.style.height = "auto";
      this.messageInput.style.height = this.messageInput.scrollHeight + "px";
    });

    // WebSocket message handler
    websocket.on("chatResponse", (response) => {
      this.addMessage(response.message, "assistant", response.timestamp);
    });
  }

  async loadChatHistory() {
    try {
      const history = await api.getChatHistory();
      this.messages = history.messages || [];
      this.renderMessages();
    } catch (error) {
      console.error("Failed to load chat history:", error);
    }
  }

  async sendMessage() {
    const message = this.messageInput.value.trim();
    if (!message) return;

    // Disable send button
    this.sendBtn.disabled = true;

    // Add user message to chat
    this.addMessage(message, "user");

    // Clear input
    this.messageInput.value = "";
    this.messageInput.style.height = "auto";

    try {
      // Send via WebSocket if connected, otherwise use API
      if (websocket.isConnected) {
        websocket.sendChatMessage(message);
      } else {
        const response = await api.sendMessage(message);
        this.addMessage(response.message, "assistant", response.timestamp);
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      this.addMessage(
        "Sorry, I encountered an error. Please try again.",
        "assistant",
      );
    } finally {
      this.sendBtn.disabled = false;
      this.messageInput.focus();
    }
  }

  addMessage(content, role, timestamp = null) {
    const message = {
      content,
      role,
      timestamp: timestamp || new Date().toISOString(),
    };

    this.messages.push(message);
    this.renderMessage(message);
    this.scrollToBottom();

    // Remove welcome message if present
    const welcomeMessage =
      this.messagesContainer.querySelector(".welcome-message");
    if (welcomeMessage) {
      welcomeMessage.remove();
    }
  }

  renderMessages() {
    // Clear container except welcome message
    const welcomeMessage =
      this.messagesContainer.querySelector(".welcome-message");
    this.messagesContainer.innerHTML = "";
    if (welcomeMessage && this.messages.length === 0) {
      this.messagesContainer.appendChild(welcomeMessage);
    }

    // Render all messages
    this.messages.forEach((message) => this.renderMessage(message));
    this.scrollToBottom();
  }

  renderMessage(message) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${message.role}`;

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    // Convert markdown-style formatting
    const formattedContent = this.formatMessage(message.content);
    contentDiv.innerHTML = formattedContent;

    const timeDiv = document.createElement("div");
    timeDiv.className = "message-time";
    timeDiv.textContent = this.formatTimestamp(message.timestamp);

    contentDiv.appendChild(timeDiv);
    messageDiv.appendChild(contentDiv);

    this.messagesContainer.appendChild(messageDiv);
  }

  formatMessage(content) {
    // Basic markdown formatting
    return content
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`(.*?)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br>");
  }

  formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // Today: show time only
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    }

    // Yesterday
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
      return (
        "Yesterday " +
        date.toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        })
      );
    }

    // Within a week: show day name
    if (diff < 7 * 24 * 60 * 60 * 1000) {
      return date.toLocaleDateString("en-US", {
        weekday: "short",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    }

    // Older: show full date
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  }

  scrollToBottom() {
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }
}

// Initialize chat when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.chatManager = new ChatManager();
});
