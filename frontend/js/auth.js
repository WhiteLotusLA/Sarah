// Authentication module for Sarah AI

class AuthManager {
  constructor() {
    this.token = localStorage.getItem("authToken");
    this.user = null;
    this.refreshInterval = null;
  }

  async login(username, password) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Login failed");
      }

      const data = await response.json();
      this.token = data.access_token;
      this.user = data.user;

      // Store token
      localStorage.setItem("authToken", this.token);

      // Update API service
      api.setToken(this.token);

      // Start token refresh
      this.startTokenRefresh();

      return data;
    } catch (error) {
      console.error("Login error:", error);
      throw error;
    }
  }

  async logout() {
    try {
      if (this.token) {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${this.token}`,
          },
        });
      }
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      this.clearAuth();
    }
  }

  async getCurrentUser() {
    if (!this.token) {
      throw new Error("Not authenticated");
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          this.clearAuth();
        }
        throw new Error("Failed to get user info");
      }

      const user = await response.json();
      this.user = user;
      return user;
    } catch (error) {
      console.error("Get user error:", error);
      throw error;
    }
  }

  async refreshToken() {
    if (!this.token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        this.token = data.access_token;
        localStorage.setItem("authToken", this.token);
        api.setToken(this.token);
      } else if (response.status === 401) {
        this.clearAuth();
      }
    } catch (error) {
      console.error("Token refresh error:", error);
    }
  }

  startTokenRefresh() {
    // Refresh token every 20 minutes
    this.refreshInterval = setInterval(
      () => {
        this.refreshToken();
      },
      20 * 60 * 1000,
    );
  }

  stopTokenRefresh() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }

  clearAuth() {
    this.token = null;
    this.user = null;
    localStorage.removeItem("authToken");
    api.clearToken();
    this.stopTokenRefresh();

    // Redirect to login
    if (window.app) {
      window.app.showLoginModal();
    }
  }

  isAuthenticated() {
    return !!this.token;
  }

  hasPermission(permission) {
    if (!this.user) return false;
    if (this.user.is_admin) return true;
    return this.user.permissions && this.user.permissions.includes(permission);
  }
}

// Create singleton instance
const auth = new AuthManager();
window.auth = auth;
