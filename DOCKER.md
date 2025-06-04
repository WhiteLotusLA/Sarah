# Docker Setup for Sarah AI

This guide explains how to run Sarah AI using Docker containers.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- (Optional) NVIDIA GPU with Docker GPU support for Ollama

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sarah-ai.git
cd sarah-ai
```

2. Copy environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start all services:
```bash
docker-compose up -d
```

4. Access Sarah AI:
- Frontend: http://localhost
- API: http://localhost/api/v1
- API Docs: http://localhost/docs

## Services

### Core Services

- **sarah-backend**: Main FastAPI application
- **postgres**: PostgreSQL with pgvector extension
- **redis**: Redis for pub/sub messaging
- **nginx**: Web server and reverse proxy

### Optional Services

- **ollama**: Local AI model runtime
- **prometheus**: Metrics collection (monitoring profile)
- **grafana**: Metrics visualization (monitoring profile)

## Development Setup

For development with hot reload:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This will:
- Mount source code for live reload
- Expose database ports for direct access
- Enable debug mode

## Production Deployment

1. Set secure passwords in `.env`:
```env
POSTGRES_PASSWORD=<strong-password>
JWT_SECRET_KEY=<random-secret-key>
ENCRYPTION_KEY=<32-byte-key>
```

2. Build and start services:
```bash
docker-compose build
docker-compose up -d
```

3. Enable monitoring (optional):
```bash
docker-compose --profile monitoring up -d
```

## Container Management

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f sarah-backend
```

### Restart services
```bash
# All services
docker-compose restart

# Specific service
docker-compose restart sarah-backend
```

### Stop services
```bash
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Update containers
```bash
docker-compose pull
docker-compose build sarah-backend
docker-compose up -d
```

## Health Checks

All services include health checks. View status:

```bash
docker-compose ps
```

Health endpoints:
- Backend: http://localhost/health
- Postgres: Automatic via pg_isready
- Redis: Automatic via redis-cli ping

## Volumes

Persistent data is stored in Docker volumes:

- `postgres_data`: Database files
- `redis_data`: Redis persistence
- `ollama_data`: AI models
- `prometheus_data`: Metrics data
- `grafana_data`: Dashboards

Local mounts:
- `./logs`: Application logs
- `./data`: Application data
- `./frontend`: Static files

## Networking

All services communicate via the `sarah-network` bridge network:

- Internal service discovery by container name
- Isolated from host network
- Nginx exposes ports 80/443

## GPU Support

For Ollama with GPU acceleration:

1. Install NVIDIA Container Toolkit
2. Ensure Docker can access GPU:
```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

3. Ollama will automatically use GPU if available

## Troubleshooting

### Database connection issues
```bash
# Check if postgres is healthy
docker-compose ps postgres

# View postgres logs
docker-compose logs postgres

# Connect to postgres
docker exec -it sarah-postgres psql -U sarah -d sarah_db
```

### Backend not starting
```bash
# Check logs
docker-compose logs sarah-backend

# Verify environment variables
docker-compose config

# Rebuild image
docker-compose build --no-cache sarah-backend
```

### Permission issues
```bash
# Fix log directory permissions
sudo chown -R 1000:1000 ./logs ./data
```

### Reset everything
```bash
# Stop and remove everything
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Start fresh
docker-compose up -d
```

## Security Considerations

1. Change default passwords in production
2. Use HTTPS with proper certificates
3. Limit exposed ports in production
4. Regularly update base images
5. Scan images for vulnerabilities:
```bash
docker scan sarah-backend:latest
```

## Monitoring

Access monitoring dashboards:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

Key metrics:
- Request rate and latency
- Error rates
- Resource usage
- Agent status

## Backup and Restore

### Backup
```bash
# Backup database
docker exec sarah-postgres pg_dump -U sarah sarah_db > backup.sql

# Backup volumes
docker run --rm -v sarah_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data
```

### Restore
```bash
# Restore database
docker exec -i sarah-postgres psql -U sarah sarah_db < backup.sql

# Restore volumes
docker run --rm -v sarah_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-backup.tar.gz -C /
```