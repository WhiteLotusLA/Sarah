# Sarah AI Frontend

A lightweight, pure HTML/CSS/JavaScript frontend for the Sarah AI personal assistant system.

## Features

- **No Build Process Required**: Pure vanilla JavaScript - just open index.html
- **Real-time Communication**: WebSocket integration for live updates
- **Responsive Design**: Works on desktop and mobile devices
- **Multiple Views**: Chat, Agents, Tasks, Calendar, Emails, and Settings
- **Modern UI**: Clean, minimalist design with Material Icons

## Setup

1. Ensure the Sarah AI backend is running on `http://localhost:8000`

2. Open `index.html` in a modern web browser

3. Login with your Sarah AI credentials

## File Structure

```
frontend/
├── index.html          # Main HTML file
├── css/
│   └── style.css      # All styles
├── js/
│   ├── api.js         # REST API client
│   ├── websocket.js   # WebSocket client
│   ├── app.js         # Main application controller
│   ├── auth.js        # Authentication module
│   ├── chat.js        # Chat interface
│   ├── agents.js      # Agent management
│   ├── tasks.js       # Task management
│   ├── calendar.js    # Calendar view
│   └── emails.js      # Email management
└── assets/            # Images and other assets
```

## API Configuration

The frontend expects the backend API to be available at:
- REST API: `http://localhost:8000/api/v1`
- WebSocket: `ws://localhost:8000/ws`

To change the backend URL, edit the `API_BASE_URL` constant in `js/api.js`.

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Development

To modify the frontend:

1. Edit the HTML, CSS, or JavaScript files directly
2. Refresh the browser to see changes
3. Use browser DevTools for debugging

## Security Notes

- Authentication tokens are stored in localStorage
- All API requests include the auth token in headers
- WebSocket connections include the token as a query parameter
- HTTPS should be used in production