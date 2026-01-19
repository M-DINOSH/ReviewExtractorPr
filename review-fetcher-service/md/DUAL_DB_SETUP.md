# Token Management - Dual Database Setup

> Update (2026-01-18): Token management now uses a single PostgreSQL database with two tables (`clients`, `tokens`). This document is kept for historical reference; use `TOKEN_MANAGEMENT_DATABASE_URL` for the current configuration.

## Architecture Overview

The review-fetcher-service now uses **two separate PostgreSQL databases** for token management, following the same architecture as the token-generation-service:

1. **Client Database** (`postgres-clients:5436`)
   - Stores OAuth client credentials
   - Contains workspace/branch information
   - Table: `clients`

2. **Token Database** (`postgres-tokens:5435`)
   - Stores access/refresh tokens
   - Separate from client credentials for security
   - Table: `tokens`

## Database Configuration

### Environment Variables

```bash
# Client Database
CLIENT_DATABASE_URL=postgresql://client_user:client_password@postgres-clients:5432/token_client_db

# Token Database  
TOKEN_DATABASE_URL=postgresql://token_user:token_password@postgres-tokens:5432/token_service_db
```

### Local Development (outside Docker)

```bash
# Client DB on port 5436
CLIENT_DATABASE_URL=postgresql://client_user:client_password@localhost:5436/token_client_db

# Token DB on port 5435
TOKEN_DATABASE_URL=postgresql://token_user:token_password@localhost:5435/token_service_db
```

## Docker Compose Setup

### Services

```yaml
postgres-clients:
  image: postgres:16-alpine
  ports: ["5436:5432"]
  environment:
    POSTGRES_USER: client_user
    POSTGRES_PASSWORD: client_password
    POSTGRES_DB: token_client_db

postgres-tokens:
  image: postgres:16-alpine
  ports: ["5435:5432"]
  environment:
    POSTGRES_USER: token_user
    POSTGRES_PASSWORD: token_password
    POSTGRES_DB: token_service_db
```

## Alembic Migration Setup

Two separate Alembic configurations manage each database:

### Client Database Migrations

```bash
# Configuration: alembic_clients.ini
# Directory: alembic_clients/
# Manages: clients table

# Generate migration
alembic -c alembic_clients.ini revision --autogenerate -m "description"

# Apply migrations
alembic -c alembic_clients.ini upgrade head

# Rollback
alembic -c alembic_clients.ini downgrade -1
```

### Token Database Migrations

```bash
# Configuration: alembic_tokens.ini
# Directory: alembic_tokens/
# Manages: tokens table

# Generate migration
alembic -c alembic_tokens.ini revision --autogenerate -m "description"

# Apply migrations
alembic -c alembic_tokens.ini upgrade head

# Rollback
alembic -c alembic_tokens.ini downgrade -1
```

### Makefile Commands

Convenient commands for managing both databases:

```bash
# Upgrade both databases
make db-upgrade

# Downgrade both databases
make db-downgrade

# Check current versions
make db-current

# View migration history
make db-history

# Generate new migrations
make db-migrate-clients msg="add new field"
make db-migrate-tokens msg="add token field"
```

## Deployment Steps

### 1. Start Infrastructure

```bash
docker-compose up -d postgres-clients postgres-tokens
```

Wait for health checks to pass.

### 2. Run Migrations

```bash
# Apply all migrations
make db-upgrade

# Or individually:
alembic -c alembic_clients.ini upgrade head
alembic -c alembic_tokens.ini upgrade head
```

### 3. Start Application

```bash
docker-compose up -d review-fetcher
```

The application will:
- Connect to both databases
- Initialize database connections on startup
- Close connections gracefully on shutdown

### 4. Verify Setup

```bash
# Check logs
docker-compose logs review-fetcher

# Should see:
# "Initializing client database..."
# "Client database initialized successfully"
# "Initializing token database..."
# "Token database initialized successfully"
```

## Database Schema

### Clients Table (Client DB)

```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(255) UNIQUE NOT NULL,
    client_secret VARCHAR(512) NOT NULL,
    redirect_uri VARCHAR(512) NOT NULL,
    branch_id VARCHAR(255) UNIQUE NOT NULL,
    workspace_email VARCHAR(255) NOT NULL,
    workspace_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Tokens Table (Token DB)

```sql
CREATE TABLE tokens (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    scope TEXT,
    expires_at TIMESTAMP NOT NULL,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    last_refreshed_at TIMESTAMP
);
```

## Code Structure

```
app/token_management/
├── database/
│   ├── __init__.py
│   └── config.py              # Dual DB config (ClientBase, TokenBase)
├── models/
│   ├── __init__.py
│   ├── client.py              # Client model (uses ClientBase)
│   ├── token.py               # Token model (uses TokenBase)
│   └── schemas.py             # Pydantic schemas
├── services/
│   ├── client_service.py      # Uses get_client_db()
│   ├── token_service.py       # Uses get_token_db()
│   └── oauth_service.py
└── routes.py                   # Uses both get_client_db() and get_token_db()

alembic_clients/               # Client DB migrations
├── versions/
│   └── 001_clients_initial_client_tables.py
├── env.py                     # Uses ClientBase
└── ...

alembic_tokens/                # Token DB migrations
├── versions/
│   └── 001_tokens_initial_token_tables.py
├── env.py                     # Uses TokenBase
└── ...
```

## API Endpoints

All token management endpoints remain the same:

```
POST   /token-management/clients
GET    /token-management/oauth/login/{client_id}
GET    /token-management/auth/callback
POST   /token-management/tokens/refresh
GET    /token-management/tokens/{branch_id}
```

The dual-database architecture is transparent to API consumers.

## Testing

```bash
# Run integration test
python3.11 test_token_integration.py

# Should output:
# ✓ Models (Client, Token) imported
# ✓ Schemas imported
# ✓ Database config imported
# ✓ Services imported (oauth, client, token)
# ✓ Routes imported (token_router)
# ✓ Main app imported
# ✅ ALL TESTS PASSED
```

## Troubleshooting

### Connection Issues

```bash
# Check database health
docker-compose ps postgres-clients postgres-tokens

# Test connections
docker exec -it postgres-clients psql -U client_user -d token_client_db
docker exec -it postgres-tokens psql -U token_user -d token_service_db
```

### Migration Issues

```bash
# Check current migration versions
make db-current

# View migration history
make db-history

# Reset databases (development only!)
docker-compose down -v
docker-compose up -d postgres-clients postgres-tokens
make db-upgrade
```

### Application Logs

```bash
# Real-time logs
docker-compose logs -f review-fetcher

# Database initialization logs
docker-compose logs review-fetcher | grep -i database
```

## Security Notes

1. **Separate Databases**: Client credentials and tokens are isolated
2. **Different Users**: Each DB has its own PostgreSQL user
3. **Network Isolation**: Containers communicate via Docker network
4. **Environment Variables**: Sensitive credentials via env vars
5. **Password Rotation**: Change passwords by updating env vars and restarting

## Production Considerations

1. Use **managed PostgreSQL** (AWS RDS, GCP Cloud SQL, etc.)
2. Enable **SSL/TLS** for database connections
3. Set up **automated backups** for both databases
4. Configure **connection pooling** appropriately
5. Monitor **database metrics** (connections, query performance)
6. Use **secrets management** (Vault, AWS Secrets Manager, etc.)
7. Set appropriate **resource limits** in docker-compose or K8s

## Parity with token-generation-service

This setup now matches the token-generation-service:

- ✅ Two separate databases (clients vs tokens)
- ✅ Separate SQLAlchemy Base classes (ClientBase, TokenBase)
- ✅ Separate Alembic configurations
- ✅ Separate database sessions (get_client_db, get_token_db)
- ✅ All original API endpoints preserved
- ✅ OAuth flow unchanged
- ✅ Token refresh mechanism intact
