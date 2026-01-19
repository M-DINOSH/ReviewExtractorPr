# Quick Start - Review Fetcher Service

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Make (optional, for convenience commands)

## Fast Deployment (Docker)

### 1. Start Everything

```bash
# Build and start all services
docker-compose up --build -d

# Check services are running
docker-compose ps
```

Expected services:
- `zookeeper` - Kafka coordination
- `kafka` - Message broker
- `kafka-ui` - Kafka monitoring (http://localhost:8080)
- `postgres-tokens` - Token management DB (clients + tokens, port 5435)
- `review-fetcher` - Main application (port 8084)

### 2. Run Database Migrations

```bash
# Using make (recommended)
make db-upgrade

# Or manually (unified DB):
alembic -c alembic_tokens.ini upgrade head
```

### 3. Verify Deployment

```bash
# Check application logs
docker-compose logs review-fetcher

# Test health endpoint
curl http://localhost:8084/api/v1/health

# View API docs
open http://localhost:8084/docs
```

## API Quick Reference

### Token Management Endpoints

```bash
# Base URL
BASE_URL=http://localhost:8084

# 1. Register OAuth Client
curl -X POST "$BASE_URL/token-management/clients" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your-google-client-id",
    "client_secret": "your-google-client-secret",
    "redirect_uri": "https://yourdomain.com/callback",
    "branch_id": "branch-uuid-123",
    "workspace_email": "manager@example.com",
    "workspace_name": "Main Branch"
  }'

# 2. Start OAuth Flow (browser)
open "$BASE_URL/token-management/oauth/login/1"

# 3. Get Token by Branch
curl "$BASE_URL/token-management/tokens/branch-uuid-123"

# 4. Refresh Token
curl -X POST "$BASE_URL/token-management/tokens/refresh" \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1}'
```

### Review Fetcher Endpoints

```bash
# Submit fetch job
curl -X POST "$BASE_URL/api/v1/fetch/job/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.a0...",
    "job_metadata": {"branch": "main", "region": "US"}
  }'

# Check job status
curl "$BASE_URL/api/v1/fetch/job/{job_id}/status"

# SSE stream (real-time events)
curl -N "$BASE_URL/api/v1/fetch/job/{job_id}/stream"
```

## Development Workflow

### Local Development (without Docker)

1. **Start databases only:**
   ```bash
   docker-compose up -d postgres-clients postgres-tokens kafka
   ```

2. **Install dependencies:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run migrations:**
   ```bash
   make db-upgrade
   ```

4. **Start application:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Testing

```bash
# Integration test
python3.11 test_token_integration.py

# Unit tests (if available)
pytest tests/ -v
```

## Common Commands

```bash
# View logs
docker-compose logs -f review-fetcher      # Application logs
docker-compose logs -f kafka               # Kafka logs

# Restart service
docker-compose restart review-fetcher

# Stop everything
docker-compose down

# Clean everything (⚠️ removes volumes/data)
docker-compose down -v

# Database operations
make db-upgrade          # Apply all migrations
make db-downgrade        # Rollback migrations
make db-current          # Show current versions
make db-history          # Show migration history
```

## Database Access

```bash
# Client database
docker exec -it postgres-clients psql -U client_user -d token_client_db

# Token database
docker exec -it postgres-tokens psql -U token_user -d token_service_db

# Useful SQL commands
\dt                      # List tables
\d clients              # Describe clients table
\d tokens               # Describe tokens table
SELECT * FROM clients;   # View clients
SELECT * FROM tokens;    # View tokens
```

## Environment Variables

Key variables (see `.env.example`):

```bash
# Service
LOG_LEVEL=INFO
ENVIRONMENT=development

# Token management database
TOKEN_MANAGEMENT_DATABASE_URL=postgresql://token_user:token_password@postgres-tokens:5432/token_service_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Feature flags
MOCK_GOOGLE_API=true    # Use mock data (true) or real Google API (false)
```

## Monitoring

- **Application**: http://localhost:8084/docs
- **Kafka UI**: http://localhost:8080
- **Kafka Topics**: accounts, locations, reviews

```bash
# Watch Kafka messages
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic accounts \
  --from-beginning
```

## Troubleshooting

### Services won't start

```bash
# Check service status
docker-compose ps

# View specific service logs
docker-compose logs postgres-clients
docker-compose logs postgres-tokens
docker-compose logs review-fetcher
```

### Database connection errors

```bash
# Verify databases are healthy
docker-compose ps | grep postgres

# Test connections
docker exec postgres-clients pg_isready -U client_user
docker exec postgres-tokens pg_isready -U token_user

# Re-run migrations
make db-upgrade
```

### Port conflicts

If ports are already in use, edit `docker-compose.yml`:

```yaml
# Change external ports (left side)
postgres-clients:
  ports: ["5437:5432"]  # Changed from 5436

postgres-tokens:
  ports: ["5438:5432"]  # Changed from 5435

review-fetcher:
  ports: ["8085:8000"]  # Changed from 8084
```

## Production Deployment

For production, see:
- [DUAL_DB_SETUP.md](DUAL_DB_SETUP.md) - Database architecture
- [DEPLOYMENT_CHECKLIST.md](md/DEPLOYMENT_CHECKLIST.md) - Production checklist
- [DOCKER_GUIDE.md](md/DOCKER_GUIDE.md) - Docker best practices

Key production changes:
1. Use managed PostgreSQL (RDS, Cloud SQL)
2. Enable SSL for database connections
3. Use secrets management (not env files)
4. Set up monitoring and alerting
5. Configure resource limits
6. Enable auto-scaling
7. Set up backups and disaster recovery

## Next Steps

1. ✅ Deploy and verify services are running
2. ✅ Run database migrations
3. ⚠️  Register your OAuth client
4. ⚠️  Complete OAuth flow to get tokens
5. ⚠️  Submit test fetch job
6. ⚠️  Monitor Kafka topics for events
7. ⚠️  Check SSE stream for real-time updates

## Support

- API Documentation: http://localhost:8084/docs
- Architecture: [ARCHITECTURE_OVERVIEW.md](md/ARCHITECTURE_OVERVIEW.md)
- Integration: [INTEGRATION_GUIDE.md](md/INTEGRATION_GUIDE.md)
- End-to-End Flow: [END_TO_END_FLOW.md](md/END_TO_END_FLOW.md)
