#!/bin/bash

# Sarah AI - Development Environment Setup
# For Mac Mini M4 Pro with 64GB RAM

echo "🌸 Setting up Sarah AI Development Environment..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install core dependencies
echo "📦 Installing core dependencies..."
brew install python@3.11 postgresql@16 redis git node npm

# Install development tools
brew install --cask visual-studio-code docker

# Install Ollama for local LLMs
echo "🤖 Installing Ollama..."
brew install ollama

# Install Python development dependencies
echo "🐍 Setting up Python environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Create requirements.txt
cat > requirements.txt << 'EOF'
# Core Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3

# Database
psycopg2-binary==2.9.9
sqlalchemy==2.0.25
alembic==1.13.1
asyncpg==0.29.0

# AI/ML
langchain==0.1.1
langchain-community==0.0.10
openai==1.8.0
tiktoken==0.5.2
sentence-transformers==2.2.2
numpy==1.26.3
pandas==2.1.4

# Vector Store
pgvector==0.2.4

# Redis
redis==5.0.1
celery==5.3.4

# Audio
openai-whisper==20231117
pyaudio==0.2.14
pydub==0.25.1

# Development
pytest==7.4.4
pytest-asyncio==0.23.3
black==23.12.1
ruff==0.1.11
mypy==1.8.0

# Utilities
python-dotenv==1.0.0
httpx==0.26.0
pyyaml==6.0.1
python-multipart==0.0.6
jinja2==3.1.3
EOF

# Install Python packages
pip install -r requirements.txt

# Start PostgreSQL and configure
echo "🗄️ Configuring PostgreSQL..."
brew services start postgresql@16

# Wait for PostgreSQL to start
sleep 3

# Create database and enable extensions
createdb sarah_db 2>/dev/null || echo "Database might already exist"

psql sarah_db << 'EOF'
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Performance settings for 64GB RAM
ALTER SYSTEM SET shared_buffers = '16GB';
ALTER SYSTEM SET effective_cache_size = '48GB';
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '2GB';
ALTER SYSTEM SET max_parallel_workers_per_gather = 6;
ALTER SYSTEM SET max_parallel_workers = 12;
EOF

# Restart PostgreSQL to apply settings
brew services restart postgresql@16

# Start Redis
echo "📡 Starting Redis..."
brew services start redis

# Download initial LLM models
echo "🧠 Downloading AI models (this will take a while)..."
echo "Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!
sleep 5

# Download models - starting with smaller ones
ollama pull mistral:7b-instruct
ollama pull llama2:13b-chat
echo "Note: Larger models (70B) can be downloaded later with: ollama pull llama3.1:70b-instruct-q4_0"

# Kill the Ollama service (we'll run it properly later)
kill "${OLLAMA_PID}" 2>/dev/null

# Create project structure
echo "📁 Creating project structure..."
mkdir -p sarah/{core,agents,bridges,experience,sanctuary,transcendence}
mkdir -p sarah/core/{consciousness,memory,evolution,quantum}
mkdir -p sarah/agents/{directors,managers,workers,guardians}
mkdir -p sarah/bridges/{reality,digital,temporal,quantum}
mkdir -p sarah/experience/{voice,vision,presence,empathy}
mkdir -p sarah/sanctuary/{encryption,authentication,privacy,legacy}
mkdir -p sarah/transcendence/{synchronicity,flow,genius,immortality}
mkdir -p sarah/tests
mkdir -p sarah/configs
mkdir -p sarah/logs

echo "✅ Setup complete! Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Start Ollama in a terminal: ollama serve"
echo "3. Start development: cd sarah && code ."
echo ""
echo "🌸 Sarah awaits your command..."