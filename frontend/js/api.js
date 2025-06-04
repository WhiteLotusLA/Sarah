// API Service for Sarah AI

const API_BASE_URL = "http://localhost:8000/api/v1";

class ApiService {
  constructor() {
    this.token = localStorage.getItem("authToken");
    this.headers = {
      "Content-Type": "application/json",
    };
    if (this.token) {
      this.headers["Authorization"] = `Bearer ${this.token}`;
    }
  }

  setToken(token) {
    this.token = token;
    localStorage.setItem("authToken", token);
    this.headers["Authorization"] = `Bearer ${token}`;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem("authToken");
    delete this.headers["Authorization"];
  }

  async request(method, endpoint, data = null) {
    const config = {
      method,
      headers: this.headers,
    };

    if (data && method !== "GET") {
      config.body = JSON.stringify(data);
    }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

      if (!response.ok) {
        if (response.status === 401) {
          this.clearToken();
          window.location.href = "#login";
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("API request failed:", error);
      throw error;
    }
  }

  // Auth endpoints
  async login(username, password) {
    const response = await this.request("POST", "/auth/login", {
      username,
      password,
    });
    if (response.access_token) {
      this.setToken(response.access_token);
    }
    return response;
  }

  async logout() {
    try {
      await this.request("POST", "/auth/logout");
    } finally {
      this.clearToken();
    }
  }

  async getCurrentUser() {
    return this.request("GET", "/auth/me");
  }

  // Chat endpoints
  async sendMessage(message) {
    return this.request("POST", "/chat/message", { message });
  }

  async getChatHistory(limit = 50) {
    return this.request("GET", `/chat/history?limit=${limit}`);
  }

  // Agent endpoints
  async getAgents() {
    return this.request("GET", "/agents");
  }

  async getAgentStatus(agentId) {
    return this.request("GET", `/agents/${agentId}/status`);
  }

  async sendAgentCommand(agentId, command, payload) {
    return this.request("POST", `/agents/${agentId}/command`, {
      command,
      payload,
    });
  }

  // Task endpoints
  async getTasks(filters = {}) {
    const queryParams = new URLSearchParams(filters).toString();
    return this.request("GET", `/tasks?${queryParams}`);
  }

  async createTask(task) {
    return this.request("POST", "/tasks", task);
  }

  async updateTask(taskId, updates) {
    return this.request("PUT", `/tasks/${taskId}`, updates);
  }

  async deleteTask(taskId) {
    return this.request("DELETE", `/tasks/${taskId}`);
  }

  // Calendar endpoints
  async getEvents(startDate, endDate) {
    return this.request(
      "GET",
      `/calendar/events?start=${startDate}&end=${endDate}`,
    );
  }

  async createEvent(event) {
    return this.request("POST", "/calendar/events", event);
  }

  async updateEvent(eventId, updates) {
    return this.request("PUT", `/calendar/events/${eventId}`, updates);
  }

  async deleteEvent(eventId) {
    return this.request("DELETE", `/calendar/events/${eventId}`);
  }

  // Email endpoints
  async getEmails(folder = "inbox", limit = 50) {
    return this.request("GET", `/emails?folder=${folder}&limit=${limit}`);
  }

  async getEmail(emailId) {
    return this.request("GET", `/emails/${emailId}`);
  }

  async sendEmail(email) {
    return this.request("POST", "/emails/send", email);
  }

  async replyToEmail(emailId, reply) {
    return this.request("POST", `/emails/${emailId}/reply`, reply);
  }

  async deleteEmail(emailId) {
    return this.request("DELETE", `/emails/${emailId}`);
  }

  async markEmailRead(emailId) {
    return this.request("PUT", `/emails/${emailId}/read`);
  }

  // Settings endpoints
  async getSettings() {
    return this.request("GET", "/settings");
  }

  async updateSettings(settings) {
    return this.request("PUT", "/settings", settings);
  }
}

// Create singleton instance
const api = new ApiService();
window.api = api;
