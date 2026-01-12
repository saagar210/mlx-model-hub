# KAS + LocalCrew Deployment Guide

This document covers deployment options for the KAS ecosystem, including integration with LocalCrew.

## Deployment Options

### Option 1: Separate Deployment (Recommended for Development)

Each project runs independently with its own PostgreSQL instance.

**KAS:**
```bash
cd knowledge-activation-system
docker compose up -d
```

**LocalCrew:**
```bash
cd crewai-automation-platform
docker compose up -d
```

**Pros:**
- Independent development and testing
- Easy rollback per project
- No schema conflicts
- Simpler debugging

**Cons:**
- Multiple PostgreSQL instances (more RAM)
- Separate Ollama instances (duplicate model storage)
- Manual cross-project configuration

### Option 2: Unified Deployment (Recommended for Production)

Single PostgreSQL with schema separation, shared Ollama instance.

```bash
cd knowledge-activation-system
docker compose -f docker-compose.unified.yml up -d
```

**Profiles:**
- Default: PostgreSQL + Ollama only
- `--profile kas`: Add KAS API + Web
- `--profile localcrew`: Add LocalCrew API + Web
- `--profile mlflow`: Add MLFlow tracking
- `--profile full`: All services
- `--profile dev`: Add Watchtower auto-updates

**Examples:**
```bash
# Infrastructure only (for local development)
docker compose -f docker-compose.unified.yml up -d

# Full stack
docker compose -f docker-compose.unified.yml --profile full up -d

# KAS only with infrastructure
docker compose -f docker-compose.unified.yml --profile kas up -d

# Everything + auto-updates
docker compose -f docker-compose.unified.yml --profile full --profile dev up -d
```

**Pros:**
- Single PostgreSQL instance (schema separation)
- Shared Ollama (one model cache)
- Cross-service networking built-in
- One command deployment

**Cons:**
- Coupled deployments
- Shared failure domain
- More complex debugging

## Environment Variables

### Required
```bash
POSTGRES_PASSWORD=your_secure_password
```

### Optional
```bash
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
```

### KAS-specific
```bash
KNOWLEDGE_VAULT_PATH=~/Obsidian
KNOWLEDGE_EMBEDDING_MODEL=nomic-embed-text
KNOWLEDGE_RERANK_MODEL=mxbai-rerank-large-v2
```

### LocalCrew-specific
```bash
MLX_MODEL_ID=mlx-community/Qwen2.5-7B-Instruct-4bit
CREW_CONFIDENCE_THRESHOLD=70
```

## Database Schema Separation

The unified deployment uses PostgreSQL schema separation:

| Schema | User | Description |
|--------|------|-------------|
| `kas` | `kas` | Knowledge Activation System tables |
| `localcrew` | `localcrew` | LocalCrew workflow tables |
| `public` | shared | Extensions (vector, uuid-ossp, pg_trgm) |

Cross-schema access is configured to allow LocalCrew to read from KAS for context retrieval.

### Connection Strings

**KAS:**
```
postgresql://kas:kas_localdev@localhost:5432/unified?options=-csearch_path=kas,public
```

**LocalCrew:**
```
postgresql://localcrew:localcrew_localdev@localhost:5432/unified?options=-csearch_path=localcrew,public
```

## Port Mapping

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Database |
| Ollama | 11434 | LLM/Embeddings |
| KAS API | 8000 | Backend API |
| KAS Web | 3000 | Frontend |
| LocalCrew API | 8001 | Backend API |
| LocalCrew Web | 3001 | Frontend |
| MLFlow | 5001 | Experiment tracking |

## Health Checks

All services include health checks. Monitor status:

```bash
docker compose -f docker-compose.unified.yml ps
```

Check individual service health:
```bash
curl http://localhost:8000/health   # KAS
curl http://localhost:8001/health   # LocalCrew
curl http://localhost:11434/        # Ollama
```

## Scaling Considerations

### Memory Requirements
- PostgreSQL: 1-2GB
- Ollama: 8-16GB (depends on models loaded)
- KAS API: 512MB-1GB
- LocalCrew API: 512MB-1GB
- Web frontends: 256MB each

### For M-series Macs
Remove the GPU reservation from ollama service (Metal acceleration is automatic):
```yaml
ollama:
  # Remove the deploy.resources section
  image: ollama/ollama:latest
  ...
```

## Backup Strategy

### Database
```bash
# Backup both schemas
docker exec kas-unified-db pg_dump -U postgres unified > backup.sql

# Backup specific schema
docker exec kas-unified-db pg_dump -U postgres -n kas unified > kas_backup.sql
```

### Ollama Models
Models are stored in the `kas-unified-ollama` volume. To backup:
```bash
docker run --rm -v kas-unified-ollama:/data -v $(pwd):/backup alpine tar czf /backup/ollama_models.tar.gz /data
```

## Troubleshooting

### PostgreSQL Connection Issues
```bash
# Check if database is ready
docker exec kas-unified-db pg_isready -U postgres

# Verify schemas exist
docker exec kas-unified-db psql -U postgres -d unified -c "\dn"

# List tables per schema
docker exec kas-unified-db psql -U postgres -d unified -c "\dt kas.*"
docker exec kas-unified-db psql -U postgres -d unified -c "\dt localcrew.*"
```

### Ollama Model Issues
```bash
# List installed models
docker exec kas-ollama ollama list

# Pull required models
docker exec kas-ollama ollama pull nomic-embed-text
docker exec kas-ollama ollama pull mxbai-rerank-large-v2
```

### Network Issues
```bash
# Check network connectivity
docker network inspect kas-ecosystem

# Test inter-service communication
docker exec kas-api curl http://ollama:11434/
docker exec localcrew-api curl http://kas-api:8000/health
```

## Migration from Separate to Unified

1. Export data from existing databases:
```bash
# KAS
pg_dump -U knowledge knowledge > kas_data.sql

# LocalCrew
pg_dump -U localcrew localcrew > localcrew_data.sql
```

2. Start unified infrastructure:
```bash
docker compose -f docker-compose.unified.yml up -d postgres
```

3. Import data into appropriate schemas:
```bash
# Set search path and import
psql -U kas -d unified -c "SET search_path TO kas" -f kas_data.sql
psql -U localcrew -d unified -c "SET search_path TO localcrew" -f localcrew_data.sql
```

4. Verify data:
```bash
docker exec kas-unified-db psql -U postgres -d unified -c "SELECT count(*) FROM kas.content"
docker exec kas-unified-db psql -U postgres -d unified -c "SELECT count(*) FROM localcrew.executions"
```
