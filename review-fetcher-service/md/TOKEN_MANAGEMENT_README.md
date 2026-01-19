# Token Management Integration into Review-Fetcher-Service

## Overview

The token generation service has been successfully integrated into the review-fetcher-service as a self-contained module `app/token_management/`. This integration provides OAuth client management and token lifecycle management without modifying existing review-fetcher functionality.

## Architecture

### Directory Structure

```
app/token_management/
├── __init__.py                      # Package exports
├── routes.py                        # API endpoints
├── models/
│   ├── __init__.py                 # Model exports
│   ├── database.py                 # SQLAlchemy models (Client, Token)
│   └── schemas.py                  # Pydantic request/response schemas
├── services/
│   ├── __init__.py                 # Service exports
│   ├── client_service.py           # Client CRUD operations
│   ├── token_service.py            # Token lifecycle management
│   ├── oauth_service.py            # Google OAuth integration
│   └── google_oauth.py             # Helper functions
└── database/
    ├── __init__.py                 # Database exports
    └── config.py                   # Database configuration (separate DB)

alembic_tokens/                      # Token database migrations
├── env.py                          # Alembic environment configuration
├── script.py.mako                  # Migration template
└── versions/
    └── 001_initial_token_management_tables.py

alembic_tokens.ini                  # Alembic configuration
```

### Database Architecture

**Separate Database for Tokens:**
- **URL**: `postgresql://token_user:token_password@localhost:5435/token_service_db`
- **Purpose**: Isolates token data from review-fetcher's main database
- **Tables**:
  - `clients`: OAuth client registration (client_id, client_secret, branch_id, workspace info)
  - `tokens`: Access and refresh tokens with expiry tracking

### API Endpoints

All endpoints are prefixed with `/token-management/`

#### 1. Register OAuth Client
```
POST /token-management/clients
Content-Type: application/json

{
  "client_id": "google-client-id",
  "client_secret": "google-client-secret",
  "redirect_uri": "http://localhost:8084/token-management/auth/callback",
  "branch_id": "unique-branch-identifier",
  "workspace_email": "admin@workspace.com",
  "workspace_name": "My Workspace"
}

Response:
{
  "success": true,
  "message": "Client created successfully",
  "client_id": 1,
  "branch_id": "unique-branch-identifier",
  "email": "admin@workspace.com"
}
```

#### 2. Initiate OAuth Flow
```
GET /token-management/oauth/login/{client_id}

Redirects to Google OAuth consent screen
```

#### 3. OAuth Callback
```
GET /token-management/auth/callback?code=authorization_code

Response:
{
  "success": true,
  "message": "OAuth flow completed successfully",
  "client_id": "google-client-id",
  "branch_id": "branch-id",
  "access_token": "access-token-string",
  "expires_at": "2024-01-01T12:00:00"
}
```

#### 4. Refresh Access Token
```
POST /token-management/tokens/refresh
Content-Type: application/json

{
  "client_id": 1
}

Response:
{
  "success": true,
  "message": "Token refreshed successfully",
  "client_id": 1,
  "access_token": "new-access-token",
  "refresh_token": "new-refresh-token",
  "expires_at": "2024-01-01T13:00:00"
}
```

#### 5. Get Token by Branch ID
```
GET /token-management/tokens/{branch_id}

Response:
{
  "success": true,
  "message": "Token retrieved successfully",
  "client_id": 1,
  "branch_id": "branch-id",
  "access_token": "access-token",
  "expires_at": "2024-01-01T13:00:00"
}
```

## Key Features

### Automatic Token Refresh
The `ensure_valid_token()` method automatically refreshes tokens when they're expiring within 5 minutes, preventing token expiration errors in production.

### Client Management
- Register multiple OAuth clients with workspace information
- Track branch_id for multi-tenant scenarios
- Store workspace email and name for audit trails

### Secure Token Storage
- Tokens stored in the shared token management PostgreSQL database (clients + tokens)
- Refresh tokens stored securely
- Token expiry tracking with is_valid and is_revoked flags

### Database Migrations
Alembic migrations manage schema evolution:
```bash
# Apply migrations to token database
alembic -c alembic_tokens.ini upgrade head

# Create new migration
alembic -c alembic_tokens.ini revision --autogenerate -m "describe_changes"
```

## Integration with Review-Fetcher

### How Review-Fetcher Uses Tokens

1. **Client Registration**: Review-fetcher creates OAuth clients via POST /token-management/clients
2. **OAuth Flow**: Routes user through OAuth login with GET /token-management/oauth/login/{client_id}
3. **Token Retrieval**: Uses GET /token-management/tokens/{branch_id} to fetch current access token
4. **Automatic Refresh**: Token service handles automatic refresh when tokens expire

### Environment Configuration

```bash
# Required in docker-compose or .env
TOKEN_MANAGEMENT_DATABASE_URL=postgresql://token_user:token_password@localhost:5435/token_service_db

# Optional Google OAuth credentials
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Docker Deployment

### Docker Compose Setup

The service includes `postgres-tokens` database container:

```yaml
postgres-tokens:
  image: postgres:16-alpine
  ports:
    - "5435:5432"
  environment:
    POSTGRES_USER: token_user
    POSTGRES_PASSWORD: token_password
    POSTGRES_DB: token_service_db
  volumes:
    - postgres_tokens_data:/var/lib/postgresql/data
```

### Running Services

```bash
# Start all services including token database
docker-compose up -d

# Initialize token database schema
docker exec review-fetcher-service alembic -c alembic_tokens.ini upgrade head

# View logs
docker-compose logs -f review-fetcher-service
```

## Development

### Installation

```bash
# Install all dependencies
pip install -r requirements.txt

# Key dependencies added:
# - sqlalchemy==2.0.23     (ORM)
# - psycopg2-binary==2.9.11 (PostgreSQL driver)
# - alembic==1.13.0        (Database migrations)
```

### Testing Locally

1. Start PostgreSQL:
```bash
docker run -d \
  --name postgres-tokens \
  -p 5435:5432 \
  -e POSTGRES_USER=token_user \
  -e POSTGRES_PASSWORD=token_password \
  -e POSTGRES_DB=token_service_db \
  postgres:16-alpine
```

2. Apply migrations:
```bash
alembic -c alembic_tokens.ini upgrade head
```

3. Start review-fetcher:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8084
```

4. Test endpoints:
```bash
# Register a client
curl -X POST http://localhost:8084/token-management/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "test-client",
    "client_secret": "test-secret",
    "redirect_uri": "http://localhost:8084/token-management/auth/callback",
    "branch_id": "branch-1",
    "workspace_email": "test@example.com",
    "workspace_name": "Test"
  }'
```

## Production Considerations

### Database Backups
```bash
# Backup token database
pg_dump -U token_user -h localhost -p 5435 token_service_db > token_backup.sql

# Restore
psql -U token_user -h localhost -p 5435 token_service_db < token_backup.sql
```

### Monitoring
- Monitor token expiry: Check `tokens.expires_at` for expired tokens
- Monitor refresh failures: Check application logs for refresh_token_failed errors
- Monitor client status: Track `clients.is_active` flag

### Security Hardening
- Use environment variables for client secrets (never commit to git)
- Enable SSL/TLS for database connections
- Implement API rate limiting
- Use JWT or API keys for service-to-service authentication
- Rotate client secrets periodically
- Enable database encryption at rest

## Troubleshooting

### Token Refresh Fails
```
Error: "No refresh token available"
Solution: User needs to complete OAuth flow again with offline access
```

### Database Connection Refused
```
Error: "could not connect to server: Connection refused"
Solution: Ensure postgres-tokens container is running on port 5435
```

### Migration Errors
```bash
# Reset database
docker exec postgres-tokens psql -U token_user -d token_service_db \
  -c "DROP TABLE IF EXISTS alembic_version, tokens, clients CASCADE;"

# Reapply migrations
alembic -c alembic_tokens.ini upgrade head
```

## Files Modified/Created

### Created Files:
- `app/token_management/` (complete module)
- `alembic_tokens/` (migration directory)
- `alembic_tokens.ini` (Alembic config)
- `app/token_management/routes.py` (API endpoints)
- `app/token_management/models/database.py` (SQLAlchemy models)
- `app/token_management/models/schemas.py` (Pydantic schemas)
- `app/token_management/services/oauth_service.py` (OAuth logic)
- `app/token_management/services/client_service.py` (Client CRUD)
- `app/token_management/services/token_service.py` (Token lifecycle)
- `app/token_management/database/config.py` (Database config)

### Modified Files:
- `app/main.py` (added token_router import and inclusion)
- `docker-compose.yml` (added postgres-tokens service)
- `requirements.txt` (added SQLAlchemy, psycopg2, Alembic)

### Unmodified Review-Fetcher Files:
All existing review-fetcher files remain unchanged, ensuring backwards compatibility.

## Next Steps

1. **Deploy to Production**: Use docker-compose for containerized deployment
2. **Configure OAuth**: Set up Google OAuth credentials in environment
3. **Test Integration**: Verify token flow with existing review-fetcher API
4. **Monitor Performance**: Track token refresh rates and latency
5. **Plan Token Rotation**: Implement token rotation policy

## Support

For issues or questions about token management integration, check:
- Application logs in `docker-compose logs review-fetcher-service`
- Database logs in `docker-compose logs postgres-tokens`
- Alembic migrations status: `alembic -c alembic_tokens.ini current`
