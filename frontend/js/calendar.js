// Calendar management for Sarah AI

class CalendarManager {
  constructor() {
    this.calendarGrid = document.getElementById("calendarGrid");
    this.eventsList = document.getElementById("eventsList");
    this.currentMonthElement = document.getElementById("currentMonth");
    this.prevMonthBtn = document.getElementById("prevMonthBtn");
    this.nextMonthBtn = document.getElementById("nextMonthBtn");
    this.addEventBtn = document.getElementById("addEventBtn");

    this.currentDate = new Date();
    this.events = [];

    this.initializeEventListeners();
  }

  initializeEventListeners() {
    if (this.prevMonthBtn) {
      this.prevMonthBtn.addEventListener("click", () => this.previousMonth());
    }

    if (this.nextMonthBtn) {
      this.nextMonthBtn.addEventListener("click", () => this.nextMonth());
    }

    if (this.addEventBtn) {
      this.addEventBtn.addEventListener("click", () =>
        this.showAddEventDialog(),
      );
    }

    // WebSocket calendar updates
    websocket.on("calendarUpdate", (update) => {
      this.handleCalendarUpdate(update);
    });
  }

  async loadEvents() {
    try {
      const startDate = new Date(
        this.currentDate.getFullYear(),
        this.currentDate.getMonth(),
        1,
      );
      const endDate = new Date(
        this.currentDate.getFullYear(),
        this.currentDate.getMonth() + 1,
        0,
      );

      const events = await api.getEvents(
        startDate.toISOString(),
        endDate.toISOString(),
      );

      this.events = events;
      this.renderCalendar();
      this.renderEventsList();
    } catch (error) {
      console.error("Failed to load events:", error);
    }
  }

  renderCalendar() {
    // Update month display
    this.currentMonthElement.textContent = this.currentDate.toLocaleDateString(
      "en-US",
      {
        month: "long",
        year: "numeric",
      },
    );

    // Clear grid
    this.calendarGrid.innerHTML = "";

    // Add day headers
    const dayHeaders = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    dayHeaders.forEach((day) => {
      const header = document.createElement("div");
      header.className = "calendar-day-header";
      header.textContent = day;
      this.calendarGrid.appendChild(header);
    });

    // Get first day of month and number of days
    const firstDay = new Date(
      this.currentDate.getFullYear(),
      this.currentDate.getMonth(),
      1,
    );
    const lastDay = new Date(
      this.currentDate.getFullYear(),
      this.currentDate.getMonth() + 1,
      0,
    );
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    // Add empty cells for days before month starts
    for (let i = 0; i < startingDayOfWeek; i++) {
      const emptyDay = document.createElement("div");
      emptyDay.className = "calendar-day empty";
      this.calendarGrid.appendChild(emptyDay);
    }

    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const dayElement = document.createElement("div");
      dayElement.className = "calendar-day";

      const date = new Date(
        this.currentDate.getFullYear(),
        this.currentDate.getMonth(),
        day,
      );
      const isToday = this.isToday(date);

      if (isToday) {
        dayElement.classList.add("today");
      }

      // Count events for this day
      const dayEvents = this.getEventsForDate(date);

      dayElement.innerHTML = `
                <div class="day-number">${day}</div>
                ${dayEvents.length > 0 ? `<div class="event-indicator">${dayEvents.length}</div>` : ""}
            `;

      dayElement.addEventListener("click", () => this.showDayEvents(date));

      this.calendarGrid.appendChild(dayElement);
    }
  }

  renderEventsList() {
    const upcomingEvents = this.getUpcomingEvents();

    this.eventsList.innerHTML = "<h4>Upcoming Events</h4>";

    if (upcomingEvents.length === 0) {
      this.eventsList.innerHTML +=
        '<p class="no-events">No upcoming events</p>';
      return;
    }

    upcomingEvents.forEach((event) => {
      const eventElement = this.createEventElement(event);
      this.eventsList.appendChild(eventElement);
    });
  }

  createEventElement(event) {
    const div = document.createElement("div");
    div.className = "event-item";

    const startDate = new Date(event.start_time);
    const timeStr = startDate.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

    div.innerHTML = `
            <div class="event-time">${timeStr}</div>
            <div class="event-details">
                <div class="event-title">${event.title}</div>
                ${event.location ? `<div class="event-location">${event.location}</div>` : ""}
            </div>
        `;

    return div;
  }

  getEventsForDate(date) {
    return this.events.filter((event) => {
      const eventDate = new Date(event.start_time);
      return eventDate.toDateString() === date.toDateString();
    });
  }

  getUpcomingEvents() {
    const now = new Date();
    const upcoming = this.events.filter((event) => {
      return new Date(event.start_time) >= now;
    });

    return upcoming
      .sort((a, b) => {
        return new Date(a.start_time) - new Date(b.start_time);
      })
      .slice(0, 10);
  }

  isToday(date) {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  }

  previousMonth() {
    this.currentDate.setMonth(this.currentDate.getMonth() - 1);
    this.loadEvents();
  }

  nextMonth() {
    this.currentDate.setMonth(this.currentDate.getMonth() + 1);
    this.loadEvents();
  }

  async showAddEventDialog() {
    // Simple prompt for now
    const title = prompt("Enter event title:");
    if (!title) return;

    const dateStr = prompt("Enter date (YYYY-MM-DD):");
    if (!dateStr) return;

    const timeStr = prompt("Enter time (HH:MM):");
    if (!timeStr) return;

    try {
      const startTime = new Date(`${dateStr}T${timeStr}`);
      const endTime = new Date(startTime);
      endTime.setHours(endTime.getHours() + 1);

      const event = await api.createEvent({
        title,
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
      });

      this.events.push(event);
      this.renderCalendar();
      this.renderEventsList();

      app.showNotification("Event created successfully", "success");
    } catch (error) {
      console.error("Failed to create event:", error);
      app.showNotification("Failed to create event", "error");
    }
  }

  showDayEvents(date) {
    const events = this.getEventsForDate(date);
    if (events.length === 0) return;

    // TODO: Show events in a modal
    console.log(`Events for ${date.toDateString()}:`, events);
  }

  handleCalendarUpdate(update) {
    // Reload events when we get an update
    this.loadEvents();
  }
}

// Add calendar-specific styles
const style = document.createElement("style");
style.textContent = `
    .calendar-controls {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 24px;
    }
    
    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 1px;
        background-color: var(--border-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        overflow: hidden;
    }
    
    .calendar-day-header {
        background-color: var(--bg-tertiary);
        padding: 12px;
        text-align: center;
        font-weight: 600;
        font-size: 14px;
    }
    
    .calendar-day {
        background-color: var(--bg-primary);
        padding: 8px;
        min-height: 80px;
        cursor: pointer;
        position: relative;
        transition: background-color 0.2s;
    }
    
    .calendar-day:hover {
        background-color: var(--bg-secondary);
    }
    
    .calendar-day.empty {
        background-color: var(--bg-tertiary);
        cursor: default;
    }
    
    .calendar-day.today {
        background-color: #e0e7ff;
    }
    
    .day-number {
        font-weight: 500;
    }
    
    .event-indicator {
        position: absolute;
        bottom: 4px;
        right: 4px;
        background-color: var(--primary-color);
        color: white;
        font-size: 12px;
        padding: 2px 6px;
        border-radius: 12px;
    }
    
    .events-list {
        margin-top: 24px;
    }
    
    .event-item {
        display: flex;
        gap: 12px;
        padding: 12px;
        background-color: var(--bg-secondary);
        border-radius: 6px;
        margin-bottom: 8px;
    }
    
    .event-time {
        font-weight: 500;
        color: var(--primary-color);
        min-width: 80px;
    }
    
    .event-title {
        font-weight: 500;
    }
    
    .event-location {
        font-size: 14px;
        color: var(--text-secondary);
    }
    
    .no-events {
        color: var(--text-secondary);
        text-align: center;
        padding: 24px;
    }
`;
document.head.appendChild(style);

// Initialize calendar manager when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.calendarManager = new CalendarManager();
});
