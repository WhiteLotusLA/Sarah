# Sarah AI Deployment Guide

## Local Development
```bash
# Prerequisites
brew install postgresql@15 redis python@3.11 node@18
brew services start postgresql@15
brew services start redis

# Setup
git clone https://github.com/WhiteLotusLA/Sarah.git
cd Sarah
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database
createdb sarah_db
psql sarah_db < database/schema.sql

# Run
python main.py
```

## Docker Deployment
```yaml
# docker-compose.yml
version: '3.8'
services:
  sarah:
    build: .
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db/sarah
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
      
  db:
    image: timescale/timescaledb-ha:pg15-latest
    environment:
      - POSTGRES_DB=sarah
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
      
  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
```

## Production Mac Mini
```bash
# System setup
sudo pmset -a sleep 0
sudo systemsetup -setcomputersleep Never

# Service management
launchctl load ~/Library/LaunchAgents/com.sarah.ai.plist
launchctl start com.sarah.ai

# Monitoring
tail -f ~/Documents/Projects/Sarah/logs/sarah.log
```

## Environment Variables
```bash
# .env
SARAH_ENV=production
SARAH_LOG_LEVEL=INFO
DATABASE_URL=postgresql://localhost/sarah_db
REDIS_URL=redis://localhost:6380
OLLAMA_HOST=http://localhost:11434
OPENAI_API_KEY=sk-...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
```