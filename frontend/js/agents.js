// Agent management for Sarah AI

class AgentsManager {
  constructor() {
    this.agentsGrid = document.getElementById("agentsGrid");
    this.refreshBtn = document.getElementById("refreshAgentsBtn");
    this.agents = [];

    this.initializeEventListeners();
  }

  initializeEventListeners() {
    if (this.refreshBtn) {
      this.refreshBtn.addEventListener("click", () => this.loadAgents());
    }

    // WebSocket agent updates
    websocket.on("agentUpdate", (update) => {
      this.handleAgentUpdate(update);
    });
  }

  async loadAgents() {
    try {
      // Show loading state
      this.agentsGrid.innerHTML =
        '<div class="loading">Loading agents...</div>';

      const agents = await api.getAgents();
      this.agents = agents;
      this.renderAgents();

      // Subscribe to agent updates
      agents.forEach((agent) => {
        websocket.subscribeToAgent(agent.id);
      });
    } catch (error) {
      console.error("Failed to load agents:", error);
      this.agentsGrid.innerHTML =
        '<div class="error">Failed to load agents</div>';
    }
  }

  renderAgents() {
    this.agentsGrid.innerHTML = "";

    this.agents.forEach((agent) => {
      const card = this.createAgentCard(agent);
      this.agentsGrid.appendChild(card);
    });
  }

  createAgentCard(agent) {
    const card = document.createElement("div");
    card.className = "agent-card";
    card.dataset.agentId = agent.id;

    const statusClass = agent.status === "online" ? "online" : "";

    card.innerHTML = `
            <div class="agent-header">
                <h3 class="agent-name">${agent.name}</h3>
                <div class="agent-status">
                    <span class="agent-status-indicator ${statusClass}"></span>
                    <span>${agent.status}</span>
                </div>
            </div>
            <p class="agent-description">${agent.description || ""}</p>
            <div class="agent-stats">
                <div class="stat-item">
                    <div class="stat-label">Messages</div>
                    <div class="stat-value">${agent.stats?.messages || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Tasks</div>
                    <div class="stat-value">${agent.stats?.tasks || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Uptime</div>
                    <div class="stat-value">${this.formatUptime(agent.uptime)}</div>
                </div>
            </div>
            <div class="agent-actions">
                <button class="action-btn" onclick="agentsManager.viewAgentDetails('${agent.id}')">
                    <span class="material-icons">visibility</span>
                    Details
                </button>
                <button class="action-btn" onclick="agentsManager.restartAgent('${agent.id}')">
                    <span class="material-icons">restart_alt</span>
                    Restart
                </button>
            </div>
        `;

    return card;
  }

  handleAgentUpdate(update) {
    const { agent_id, status, stats } = update;

    // Update agent in our local list
    const agent = this.agents.find((a) => a.id === agent_id);
    if (agent) {
      agent.status = status;
      if (stats) {
        agent.stats = stats;
      }
    }

    // Update UI
    const card = this.agentsGrid.querySelector(`[data-agent-id="${agent_id}"]`);
    if (card) {
      // Update status indicator
      const statusIndicator = card.querySelector(".agent-status-indicator");
      const statusText = card.querySelector(".agent-status span:last-child");

      if (status === "online") {
        statusIndicator.classList.add("online");
      } else {
        statusIndicator.classList.remove("online");
      }
      statusText.textContent = status;

      // Update stats if provided
      if (stats) {
        if (stats.messages !== undefined) {
          card.querySelector(
            ".stat-item:nth-child(1) .stat-value",
          ).textContent = stats.messages;
        }
        if (stats.tasks !== undefined) {
          card.querySelector(
            ".stat-item:nth-child(2) .stat-value",
          ).textContent = stats.tasks;
        }
      }
    }
  }

  formatUptime(seconds) {
    if (!seconds) return "0s";

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
      return `${days}d ${hours}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  }

  async viewAgentDetails(agentId) {
    try {
      const details = await api.getAgentStatus(agentId);
      // TODO: Show details in a modal
      console.log("Agent details:", details);
    } catch (error) {
      console.error("Failed to get agent details:", error);
    }
  }

  async restartAgent(agentId) {
    if (!confirm("Are you sure you want to restart this agent?")) {
      return;
    }

    try {
      await api.sendAgentCommand(agentId, "restart", {});
      app.showNotification("Agent restart initiated", "success");
    } catch (error) {
      console.error("Failed to restart agent:", error);
      app.showNotification("Failed to restart agent", "error");
    }
  }
}

// Add styles for agent cards
const style = document.createElement("style");
style.textContent = `
    .agent-card {
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .agent-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    
    .agent-description {
        color: var(--text-secondary);
        font-size: 14px;
        margin: 12px 0;
    }
    
    .agent-actions {
        display: flex;
        gap: 8px;
        margin-top: 16px;
    }
    
    .action-btn {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        padding: 8px;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        background-color: transparent;
        color: var(--text-primary);
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .action-btn:hover {
        background-color: var(--bg-tertiary);
    }
    
    .action-btn .material-icons {
        font-size: 18px;
    }
    
    .loading, .error {
        text-align: center;
        padding: 48px;
        color: var(--text-secondary);
    }
    
    .error {
        color: var(--error-color);
    }
`;
document.head.appendChild(style);

// Initialize agents manager when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.agentsManager = new AgentsManager();
});
