// Main application controller for Sarah AI

class App {
  constructor() {
    this.currentPage = "chat";
    this.isAuthenticated = false;
    this.user = null;

    this.initializeEventListeners();
    this.checkAuthentication();
  }

  initializeEventListeners() {
    // Navigation
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        const page = item.dataset.page;
        this.navigateToPage(page);
      });
    });

    // Logout button
    document.getElementById("logoutBtn").addEventListener("click", () => {
      this.logout();
    });

    // Login form
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.login();
      });
    }

    // WebSocket connection events
    websocket.on("connected", () => {
      console.log("Connected to Sarah AI");
      this.showNotification("Connected to Sarah AI", "success");
    });

    websocket.on("disconnected", () => {
      console.log("Disconnected from Sarah AI");
      this.showNotification(
        "Connection lost. Attempting to reconnect...",
        "warning",
      );
    });

    // System notifications
    websocket.on("systemNotification", (notification) => {
      this.showNotification(notification.message, notification.type);
    });
  }

  async checkAuthentication() {
    const token = localStorage.getItem("authToken");
    if (!token) {
      this.showLoginModal();
      return;
    }

    try {
      const user = await api.getCurrentUser();
      this.user = user;
      this.isAuthenticated = true;
      this.updateUserInterface();
      this.connectWebSocket();
    } catch (error) {
      console.error("Authentication check failed:", error);
      this.showLoginModal();
    }
  }

  async login() {
    const username = document.getElementById("loginUsername").value;
    const password = document.getElementById("loginPassword").value;

    try {
      const response = await api.login(username, password);
      this.user = response.user;
      this.isAuthenticated = true;
      this.hideLoginModal();
      this.updateUserInterface();
      this.connectWebSocket();
      this.showNotification("Welcome back!", "success");
    } catch (error) {
      console.error("Login failed:", error);
      this.showNotification(
        "Login failed. Please check your credentials.",
        "error",
      );
    }
  }

  async logout() {
    try {
      await api.logout();
    } finally {
      this.isAuthenticated = false;
      this.user = null;
      websocket.disconnect();
      this.showLoginModal();
      this.showNotification("Logged out successfully", "info");
    }
  }

  connectWebSocket() {
    websocket.connect();
  }

  updateUserInterface() {
    // Update username display
    const usernameElement = document.getElementById("username");
    if (usernameElement && this.user) {
      usernameElement.textContent =
        this.user.username || this.user.email || "User";
    }

    // Update any user-specific UI elements
    if (this.user && this.user.email) {
      const emailInput = document.getElementById("userEmail");
      if (emailInput) {
        emailInput.value = this.user.email;
      }
    }
  }

  navigateToPage(page) {
    // Update active nav item
    document.querySelectorAll(".nav-item").forEach((item) => {
      if (item.dataset.page === page) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    // Show/hide pages
    document.querySelectorAll(".page").forEach((pageElement) => {
      if (pageElement.id === `${page}Page`) {
        pageElement.classList.add("active");
      } else {
        pageElement.classList.remove("active");
      }
    });

    this.currentPage = page;

    // Load page-specific data
    this.loadPageData(page);
  }

  async loadPageData(page) {
    switch (page) {
      case "agents":
        if (window.agentsManager) {
          window.agentsManager.loadAgents();
        }
        break;
      case "tasks":
        if (window.tasksManager) {
          window.tasksManager.loadTasks();
        }
        break;
      case "calendar":
        if (window.calendarManager) {
          window.calendarManager.loadEvents();
        }
        break;
      case "emails":
        if (window.emailsManager) {
          window.emailsManager.loadEmails();
        }
        break;
    }
  }

  showLoginModal() {
    const modal = document.getElementById("loginModal");
    if (modal) {
      modal.classList.add("active");
    }
  }

  hideLoginModal() {
    const modal = document.getElementById("loginModal");
    if (modal) {
      modal.classList.remove("active");
    }
  }

  showNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.innerHTML = `
            <span class="material-icons">${this.getNotificationIcon(type)}</span>
            <span>${message}</span>
        `;

    // Add styles
    const style = document.createElement("style");
    style.textContent = `
            .notification {
                position: fixed;
                bottom: 24px;
                right: 24px;
                background-color: var(--bg-primary);
                color: var(--text-primary);
                padding: 16px 24px;
                border-radius: 8px;
                box-shadow: var(--shadow-lg);
                display: flex;
                align-items: center;
                gap: 12px;
                z-index: 1000;
                animation: slideIn 0.3s ease-out;
            }
            
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            .notification.success {
                border-left: 4px solid var(--success-color);
            }
            
            .notification.error {
                border-left: 4px solid var(--error-color);
            }
            
            .notification.warning {
                border-left: 4px solid var(--warning-color);
            }
            
            .notification.info {
                border-left: 4px solid var(--primary-color);
            }
        `;

    if (!document.querySelector("style[data-notifications]")) {
      style.setAttribute("data-notifications", "true");
      document.head.appendChild(style);
    }

    document.body.appendChild(notification);

    // Remove after 5 seconds
    setTimeout(() => {
      notification.style.animation = "slideOut 0.3s ease-in";
      notification.style.animationFillMode = "forwards";
      setTimeout(() => notification.remove(), 300);
    }, 5000);
  }

  getNotificationIcon(type) {
    switch (type) {
      case "success":
        return "check_circle";
      case "error":
        return "error";
      case "warning":
        return "warning";
      default:
        return "info";
    }
  }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.app = new App();
});
