// Tasks management for Sarah AI

class TasksManager {
  constructor() {
    this.tasksList = document.getElementById("tasksList");
    this.addTaskBtn = document.getElementById("addTaskBtn");
    this.filterBtns = document.querySelectorAll(".filter-btn[data-filter]");
    this.currentFilter = "all";
    this.tasks = [];

    this.initializeEventListeners();
  }

  initializeEventListeners() {
    // Add task button
    if (this.addTaskBtn) {
      this.addTaskBtn.addEventListener("click", () => this.showAddTaskDialog());
    }

    // Filter buttons
    this.filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const filter = btn.dataset.filter;
        this.setFilter(filter);
      });
    });

    // WebSocket task updates
    websocket.on("taskUpdate", (update) => {
      this.handleTaskUpdate(update);
    });
  }

  async loadTasks() {
    try {
      const filters =
        this.currentFilter !== "all" ? { status: this.currentFilter } : {};
      const tasks = await api.getTasks(filters);
      this.tasks = tasks;
      this.renderTasks();
    } catch (error) {
      console.error("Failed to load tasks:", error);
      this.tasksList.innerHTML =
        '<div class="error">Failed to load tasks</div>';
    }
  }

  renderTasks() {
    this.tasksList.innerHTML = "";

    const filteredTasks = this.filterTasks(this.tasks);

    if (filteredTasks.length === 0) {
      this.tasksList.innerHTML =
        '<div class="empty-state">No tasks found</div>';
      return;
    }

    filteredTasks.forEach((task) => {
      const taskElement = this.createTaskElement(task);
      this.tasksList.appendChild(taskElement);
    });
  }

  createTaskElement(task) {
    const div = document.createElement("div");
    div.className = "task-item";
    div.dataset.taskId = task.id;

    const isCompleted = task.status === "completed";
    const priorityClass = task.priority || "medium";

    div.innerHTML = `
            <input type="checkbox" class="task-checkbox" ${isCompleted ? "checked" : ""}>
            <div class="task-content">
                <div class="task-title ${isCompleted ? "completed" : ""}">${task.title}</div>
                ${task.due_date ? `<div class="task-due">Due: ${this.formatDate(task.due_date)}</div>` : ""}
            </div>
            <span class="task-priority ${priorityClass}">${priorityClass}</span>
        `;

    // Checkbox change handler
    const checkbox = div.querySelector(".task-checkbox");
    checkbox.addEventListener("change", () => {
      this.toggleTaskStatus(task.id, checkbox.checked);
    });

    return div;
  }

  filterTasks(tasks) {
    if (this.currentFilter === "all") return tasks;

    return tasks.filter((task) => {
      switch (this.currentFilter) {
        case "pending":
          return task.status === "pending";
        case "completed":
          return task.status === "completed";
        case "overdue":
          return (
            task.status === "pending" &&
            task.due_date &&
            new Date(task.due_date) < new Date()
          );
        default:
          return true;
      }
    });
  }

  setFilter(filter) {
    this.currentFilter = filter;

    // Update button states
    this.filterBtns.forEach((btn) => {
      if (btn.dataset.filter === filter) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    this.renderTasks();
  }

  async toggleTaskStatus(taskId, completed) {
    try {
      await api.updateTask(taskId, {
        status: completed ? "completed" : "pending",
      });

      // Update local task
      const task = this.tasks.find((t) => t.id === taskId);
      if (task) {
        task.status = completed ? "completed" : "pending";
        this.renderTasks();
      }
    } catch (error) {
      console.error("Failed to update task:", error);
      app.showNotification("Failed to update task", "error");
    }
  }

  async showAddTaskDialog() {
    // Simple prompt for now
    const title = prompt("Enter task title:");
    if (!title) return;

    try {
      const task = await api.createTask({
        title,
        status: "pending",
        priority: "medium",
      });
      this.tasks.unshift(task);
      this.renderTasks();
      app.showNotification("Task created successfully", "success");
    } catch (error) {
      console.error("Failed to create task:", error);
      app.showNotification("Failed to create task", "error");
    }
  }

  handleTaskUpdate(update) {
    const { task_id, task } = update;

    // Update or add task
    const index = this.tasks.findIndex((t) => t.id === task_id);
    if (index >= 0) {
      this.tasks[index] = task;
    } else {
      this.tasks.unshift(task);
    }

    this.renderTasks();
  }

  formatDate(dateString) {
    const date = new Date(dateString);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    if (date.toDateString() === today.toDateString()) {
      return "Today";
    } else if (date.toDateString() === tomorrow.toDateString()) {
      return "Tomorrow";
    } else {
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
    }
  }
}

// Add styles
const style = document.createElement("style");
style.textContent = `
    .task-title.completed {
        text-decoration: line-through;
        color: var(--text-tertiary);
    }
    
    .empty-state {
        text-align: center;
        padding: 48px;
        color: var(--text-secondary);
    }
`;
document.head.appendChild(style);

// Initialize tasks manager when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.tasksManager = new TasksManager();
});
