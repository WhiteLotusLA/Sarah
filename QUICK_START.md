# Sarah AI Quick Start Guide

## Current Status
- ✅ Ollama installed with llama3.2 and nomic-embed-text models
- ✅ Basic consciousness engine with Ollama integration
- ✅ Simple memory system (JSON-based)
- ✅ FastAPI server running on port 8001
- ✅ PostgreSQL 17 installed and running
- ⏳ Database schema pending
- ⏳ Redis setup pending
- ⏳ Agent system pending

## Running Sarah

```bash
cd /Users/calvindevereaux/Documents/Projects/Sarah
source venv/bin/activate  # If using venv
python main.py
```

## Testing
```bash
# Test API
curl http://localhost:8001/

# Test WebSocket (use wscat or similar)
wscat -c ws://localhost:8001/ws
> {"message": "Hello Sarah!"}
```

## Next Steps
1. Install pgvector extension
2. Set up database schema
3. Install and configure Redis
4. Implement agent base class
5. Build Director agent

## Ports Configuration
See `.sarah_ports.env` for all port assignments