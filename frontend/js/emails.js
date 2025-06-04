// Email management for Sarah AI

class EmailsManager {
  constructor() {
    this.emailsList = document.getElementById("emailsList");
    this.composeBtn = document.getElementById("composeEmailBtn");
    this.filterBtns = document.querySelectorAll(".filter-btn[data-folder]");
    this.currentFolder = "inbox";
    this.emails = [];

    this.initializeEventListeners();
  }

  initializeEventListeners() {
    // Compose button
    if (this.composeBtn) {
      this.composeBtn.addEventListener("click", () => this.showComposeDialog());
    }

    // Folder filter buttons
    this.filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const folder = btn.dataset.folder;
        this.setFolder(folder);
      });
    });

    // WebSocket email notifications
    websocket.on("emailNotification", (notification) => {
      this.handleEmailNotification(notification);
    });
  }

  async loadEmails() {
    try {
      this.emailsList.innerHTML =
        '<div class="loading">Loading emails...</div>';

      const emails = await api.getEmails(this.currentFolder);
      this.emails = emails;
      this.renderEmails();
    } catch (error) {
      console.error("Failed to load emails:", error);
      this.emailsList.innerHTML =
        '<div class="error">Failed to load emails</div>';
    }
  }

  renderEmails() {
    this.emailsList.innerHTML = "";

    if (this.emails.length === 0) {
      this.emailsList.innerHTML =
        '<div class="empty-state">No emails in this folder</div>';
      return;
    }

    this.emails.forEach((email) => {
      const emailElement = this.createEmailElement(email);
      this.emailsList.appendChild(emailElement);
    });
  }

  createEmailElement(email) {
    const div = document.createElement("div");
    div.className = `email-item ${email.is_read ? "" : "unread"}`;
    div.dataset.emailId = email.id;

    const priorityIcon = this.getPriorityIcon(email.priority);
    const categoryBadge = this.getCategoryBadge(email.category);

    div.innerHTML = `
            <div class="email-header">
                <div class="email-from">
                    <strong>${email.from_name || email.from_address}</strong>
                    ${priorityIcon}
                </div>
                <div class="email-meta">
                    ${categoryBadge}
                    <span class="email-time">${this.formatEmailTime(email.received_at)}</span>
                </div>
            </div>
            <div class="email-subject">${email.subject}</div>
            <div class="email-preview">${email.body_preview}</div>
            ${email.has_attachments ? '<span class="attachment-indicator">📎</span>' : ""}
        `;

    div.addEventListener("click", () => this.openEmail(email.id));

    return div;
  }

  getPriorityIcon(priority) {
    switch (priority) {
      case "urgent":
        return '<span class="priority-icon urgent">🔴</span>';
      case "high":
        return '<span class="priority-icon high">🟡</span>';
      default:
        return "";
    }
  }

  getCategoryBadge(category) {
    if (!category) return "";

    const colors = {
      work: "#2563eb",
      personal: "#7c3aed",
      newsletter: "#06b6d4",
      notification: "#10b981",
      social: "#f59e0b",
      promotional: "#ef4444",
    };

    const color = colors[category] || "#6b7280";

    return `<span class="category-badge" style="background-color: ${color}">${category}</span>`;
  }

  formatEmailTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) {
      return "Just now";
    } else if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000);
      return `${minutes}m ago`;
    } else if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } else {
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
    }
  }

  setFolder(folder) {
    this.currentFolder = folder;

    // Update button states
    this.filterBtns.forEach((btn) => {
      if (btn.dataset.folder === folder) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    this.loadEmails();
  }

  async openEmail(emailId) {
    try {
      const email = await api.getEmail(emailId);

      // Mark as read
      if (!email.is_read) {
        await api.markEmailRead(emailId);

        // Update UI
        const emailElement = this.emailsList.querySelector(
          `[data-email-id="${emailId}"]`,
        );
        if (emailElement) {
          emailElement.classList.remove("unread");
        }
      }

      // TODO: Show email in detail view
      console.log("Email details:", email);
    } catch (error) {
      console.error("Failed to open email:", error);
    }
  }

  async showComposeDialog() {
    // Simple prompts for now
    const to = prompt("To:");
    if (!to) return;

    const subject = prompt("Subject:");
    if (!subject) return;

    const body = prompt("Message:");
    if (!body) return;

    try {
      await api.sendEmail({
        to: [to],
        subject,
        body,
      });

      app.showNotification("Email sent successfully", "success");
    } catch (error) {
      console.error("Failed to send email:", error);
      app.showNotification("Failed to send email", "error");
    }
  }

  handleEmailNotification(notification) {
    app.showNotification(
      `New email from ${notification.from}: ${notification.subject}`,
      "info",
    );

    // Reload emails if viewing inbox
    if (this.currentFolder === "inbox") {
      this.loadEmails();
    }
  }
}

// Add email-specific styles
const style = document.createElement("style");
style.textContent = `
    .email-item {
        padding: 16px;
        border-bottom: 1px solid var(--border-color);
        cursor: pointer;
        transition: background-color 0.2s;
        position: relative;
    }
    
    .email-item:hover {
        background-color: var(--bg-tertiary);
    }
    
    .email-item.unread {
        background-color: var(--bg-secondary);
    }
    
    .email-item.unread .email-subject {
        font-weight: 600;
    }
    
    .email-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }
    
    .email-from {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .email-meta {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .email-subject {
        font-weight: 500;
        margin-bottom: 4px;
    }
    
    .email-preview {
        color: var(--text-secondary);
        font-size: 14px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .email-time {
        font-size: 14px;
        color: var(--text-tertiary);
    }
    
    .priority-icon {
        font-size: 12px;
    }
    
    .category-badge {
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 12px;
        color: white;
        font-weight: 500;
    }
    
    .attachment-indicator {
        position: absolute;
        right: 16px;
        top: 50%;
        transform: translateY(-50%);
    }
`;
document.head.appendChild(style);

// Initialize emails manager when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.emailsManager = new EmailsManager();
});
