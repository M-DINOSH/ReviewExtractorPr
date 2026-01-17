# Token Generation Service

A production-ready microservice for managing OAuth2 tokens for Google Business Profile API. This service handles OAuth flow, token storage, automatic refresh, and validation with PostgreSQL persistence.

## 🎯 Features

- **OAuth2 Flow Management**: Complete Google OAuth authorization flow with Google Business Profile API
- **Token Lifecycle**: Automatic token refresh 5 minutes before expiration
- **Workspace Integration**: Single-step client registration with workspace info (email, name, branch_id)
- **PostgreSQL Database**: Persistent storage with Alembic migrations (clients + tokens tables)
- **Production Ready**: Docker containerized with health checks
- **RESTful API**: FastAPI-based with automatic documentation (Swagger/ReDoc)
- **Review Fetcher Integration**: Pull-based token retrieval endpoint for external services
- **Security**: Token expiry management, secure credential storage, cascade delete on client removal

## 📋 Table of Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [API Documentation](#api-documentation)
- [Usage](#usage)
- [Development](#development)
- [Deployment](#deployment)

## 🏗️ Architecture

### Database Schema (Simplified - 2 Tables)

```
┌─────────────────────────────┐        ┌─────────────────────┐
│          Clients            │        │       Tokens        │
├─────────────────────────────┤        ├─────────────────────┤
│ id (PK)                     │        │ id (PK)             │
│ client_id (Google)          │        │ client_id (FK)  ────┼─→
│ client_secret               │        │ access_token        │
│ redirect_uri                │        │ refresh_token       │
│ branch_id (unique)          │────┐   │ expires_at          │
│ workspace_email             │    │   │ is_valid            │
│ workspace_name              │    │   │ is_revoked          │
│ is_active                   │    │   │ token_type (Bearer) │
│ created_at                  │    │   │ scope               │
│ updated_at                  │    │   │ last_refreshed_at   │
└─────────────────────────────┘    │   │ created_at          │
                                   │   │ updated_at          │
                                   │   └─────────────────────┘
                                   │
                                   └── (Cascade Delete)
```

### Key Concepts

- **Client**: Single table storing both Google OAuth credentials + workspace info (branch_id, email, workspace name)
- **Token**: Stores access/refresh tokens per client with expiry tracking and auto-refresh logic
- **Branch ID**: Unique identifier (UUID) passed at registration to track review fetching for specific branches
- **Auto-Refresh**: Tokens automatically refresh 5 minutes before expiration when requested

## 🚀 Setup

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Google Cloud Project with OAuth credentials

### Quick Start with Docker

1. **Clone and navigate to the service**:
   ```bash
   cd token-generation-service
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify health**:
   ```bash
   curl http://localhost:8002/health
   ```

The service will be available at `http://localhost:8002`

### Local Development Setup

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL** (or use Docker):
   ```bash
   docker run -d \
     --name token-postgres \
     -e POSTGRES_USER=token_user \
     -e POSTGRES_PASSWORD=token_password \
     -e POSTGRES_DB=token_service_db \
     -p 5432:5432 \
     postgres:15-alpine
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit DATABASE_URL to use localhost:5432
   ```

5. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Start the service**:
   ```bash
   uvicorn src.token_service.api.main:app --reload --port 8002
   ```

## 📚 API Documentation

Once running, access interactive API documentation:

- **Swagger UI**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc

### Core Endpoints (4 Main APIs)

| Method | Endpoint | Description | Used By |
|--------|----------|-------------|----------|
| POST | `/clients` | Register OAuth client + workspace info | Admin/Setup |
| GET | `/oauth/login/{client_id}` | Redirect to Google OAuth consent | User Browser |
| GET | `/auth/callback` | OAuth callback (Google redirects here) | Google |
| GET | `/tokens/{branch_id}` | Get valid token (auto-refreshes if near expiry) | review-fetcher-service |
| POST | `/tokens/refresh` | Manually refresh expired token | External Services |
| GET | `/health` | Health check (database connection) | Monitoring |

**Note**: 
- `{client_id}` = internal database ID (returned from POST /clients)
- `{branch_id}` = unique branch identifier (passed in POST /clients)

## 💡 Usage

### Step 1: Register Client + Workspace (Single Request)

This single endpoint registers the OAuth client and workspace info together:

```bash
curl -X POST http://localhost:8002/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "1034365909240-xxxxx.apps.googleusercontent.com",
    "client_secret": "GOCSPX-xxxxxxxxxxxxx",
    "redirect_uri": "http://localhost:8002/auth/callback",
    "branch_id": "uuid-12345",
    "workspace_email": "workspace@company.com",
    "workspace_name": "Company Workspace"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Client created successfully",
  "client_id": 1,
  "client_oauth_id": "1034365909240-xxxxx.apps.googleusercontent.com",
  "branch_id": 1,
  "branch_identifier": "uuid-12345",
  "email": "workspace@company.com",
  "workspace_name": "Company Workspace",
  "redirect_uri": "http://localhost:8002/auth/callback",
  "created_at": "2026-01-16T16:13:05.364170"
}
```

### Step 2: Start OAuth Flow

Navigate user's browser to this URL:

```
http://localhost:8002/oauth/login/1
```

This endpoint:
1. Fetches the client's OAuth credentials
2. Redirects to Google OAuth consent screen
3. User grants permission for `business.manage` scope
4. Google redirects back to `/auth/callback`

### Step 3: OAuth Callback (Automatic)

Google automatically redirects here with the authorization code. The service:
1. Exchanges code for access + refresh tokens
2. Stores tokens in database
3. Returns tokens to client

```json
{
  "success": true,
  "message": "OAuth flow completed successfully",
  "client_id": "1034365909240-xxxxx.apps.googleusercontent.com",
  "branch_id": "uuid-12345",
  "access_token": "ya29.a0AU...",
  "expires_at": "2026-01-16T17:16:52.120354"
}
```

### Step 4: Review Fetcher Service - Get Valid Token

The review-fetcher-service calls this to get a valid access token:

```bash
curl http://localhost:8002/tokens/uuid-12345
```

Response (with auto-refresh if needed):
```json
{
  "success": true,
  "message": "Token retrieved successfully",
  "client_id": 1,
  "branch_id": "uuid-12345",
  "access_token": "ya29.a0AU...",
  "refresh_token": null,
  "expires_at": "2026-01-16T18:16:52.120354",
  "token_type": "Bearer"
}
```

### Step 5: Python Integration Example

```python
import httpx

async def get_valid_token(branch_id: str) -> str:
    """Get valid access token for a branch from token service"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://token-service:8002/tokens/{branch_id}"
        )
        data = response.json()
        
        if data["success"]:
            return data["access_token"]
        else:
            raise Exception(f"Failed to get token: {data.get('message')}")

# Use in your API calls
access_token = await get_valid_token(branch_id="uuid-12345")
headers = {"Authorization": f"Bearer {access_token}"}

# Call Google Business Profile API
async with httpx.AsyncClient() as client:
    response = await client.get(
        "https://businessprofiles.googleapis.com/v1/accounts/123/locations/456",
        headers=headers
    )
```

## 🛠️ Development

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback:
```bash
alembic downgrade -1
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black src/

# Lint
flake8 src/

# Type checking
mypy src/
```

## 🚢 Deployment

### Docker Deployment

```bash
# Build image
docker build -t token-generation-service:latest .

# Run with external database
docker run -d \
  --name token-service \
  -p 8002:8002 \
  -e DATABASE_URL=postgresql://user:pass@db-host:5432/dbname \
  -e ENVIRONMENT=production \
  token-generation-service:latest
```

### Production Checklist

- [ ] Set strong `SECRET_KEY` in environment
- [ ] Configure production database credentials
- [ ] Set `ENVIRONMENT=production`
- [ ] Enable HTTPS for redirect URIs
- [ ] Configure proper CORS origins
- [ ] Set up database backups
- [ ] Configure monitoring and alerting
- [ ] Review and set appropriate `TOKEN_EXPIRY_BUFFER`
- [ ] Set up log aggregation

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `ENVIRONMENT` | Environment (development/production) | development |
| `PORT` | Service port | 8002 |
| `GOOGLE_AUTH_URL` | Google OAuth auth endpoint | https://accounts.google.com/o/oauth2/v2/auth |
| `GOOGLE_TOKEN_URL` | Google token endpoint | https://oauth2.googleapis.com/token |
| `GOOGLE_SCOPE` | OAuth scope | business.manage |
| `TOKEN_EXPIRY_BUFFER` | Seconds before expiry to refresh | 300 |
| `SECRET_KEY` | Application secret key | Required in production |
| `LOG_LEVEL` | Logging level | INFO |

## 🔒 Security Considerations

1. **Client Secrets**: Stored securely in database, never exposed in API responses
2. **State Parameter**: Random UUID validation prevents CSRF attacks
3. **Token Expiry**: Automatic refresh 5 minutes before expiration
4. **Database**: Uses parameterized queries (SQLAlchemy ORM)
5. **HTTPS**: Use HTTPS in production for redirect URIs
6. **Environment**: Store sensitive data in environment variables, not code

## 🌐 Integration with Other Services

### With review-fetcher-service

```yaml
# docker-compose.yml
services:
  token-service:
    # ... token service config
    networks:
      - app-network
  
  review-fetcher:
    environment:
      - TOKEN_SERVICE_URL=http://token-service:8002
    networks:
      - app-network
```

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8002/health
```

### Logs

```bash
# Docker logs
docker-compose logs -f token-service

# Specific time range
docker-compose logs --since 1h token-service
```

## 🤝 Contributing

1. Follow PEP 8 style guide
2. Add tests for new features
3. Update documentation
4. Create meaningful commit messages

## 📝 License

MIT License - See LICENSE file for details

## 🆘 Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres
```

### OAuth Callback Errors

- Verify redirect URI matches Google Console configuration
- Check state parameter is valid and not expired
- Ensure client credentials are correct

### Token Refresh Failures

- Verify refresh token exists in database
- Check client credentials are valid
- Review Google API quota limits

## 📞 Support

For issues and questions:
- Check logs: `docker-compose logs token-service`
- Review API docs: http://localhost:8002/docs
- Check database state with SQL client

---

**Built with ❤️ using FastAPI, PostgreSQL, and Docker**
