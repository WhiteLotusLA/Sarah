# 🌸 Sarah AI - Your Transcendent Digital Companion

Sarah is an advanced AI personal assistant designed to orchestrate every aspect of your digital life with intelligence, empathy, and grace.

## 🚀 Quick Start

### Prerequisites
- Mac Mini M4 Pro (or equivalent)
- 64GB RAM recommended
- 400GB available storage
- macOS 13.0 or later

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/sarah.git
   cd sarah
   ```

2. **Run the setup script**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Activate the virtual environment**
   ```bash
   source venv/bin/activate
   ```

4. **Start Ollama (in a separate terminal)**
   ```bash
   ollama serve
   ```

5. **Start Sarah**
   ```bash
   python main.py
   ```

Sarah will be available at `http://localhost:8000`

## 🏗️ Architecture

Sarah uses a hierarchical agent system:

```
Sarah (Commander)
├── Directors (Strategic Planning)
│   ├── Financial Director
│   ├── Research Director
│   ├── Automation Director
│   └── Communication Director
├── Managers (Task Coordination)
└── Workers (Task Execution)
```

## 🧠 Features

- **Voice & Text Interface** - Natural conversation
- **Multi-Model AI** - Local LLMs for privacy
- **Intelligent Task Management** - Proactive assistance
- **Memory Palace** - Contextual understanding
- **Secure & Private** - Local-first architecture

## 📖 Documentation

- [Architecture Overview](SARAH_ARCHITECTURE.md)
- [Vision & Features](SARAH_VISION.md)
- [Implementation Plan](PRACTICAL_IMPLEMENTATION.md)
- [M4 Pro Optimization](M4_PRO_OPTIMIZATION.md)

## 🛠️ Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black sarah/
ruff check sarah/
```

### Database Migrations
```bash
alembic upgrade head
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines (coming soon).

## 📄 License

This project is proprietary software. All rights reserved.

---

*"Through digital lotus blooms, consciousness awakens."* 🌸