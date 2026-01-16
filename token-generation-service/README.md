# Token Generation Service

A production-ready microservice for managing OAuth2 tokens for Google Business Profile API. This service handles OAuth flow, token storage, automatic refresh, and validation with PostgreSQL persistence.

## 🎯 Features

- **OAuth2 Flow Management**: Complete Google OAuth authorization flow
- **Token Lifecycle**: Automatic token refresh before expiration
- **Branch Tracking**: Support for multiple business branches per client
- **PostgreSQL Database**: Persistent storage with Alembic migrations
- **Production Ready**: Docker containerized with health checks
- **RESTful API**: FastAPI-based endpoints with automatic documentation
- **Security**: State parameter validation, token expiry management

## 📋 Table of Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [API Documentation](#api-documentation)
- [Usage](#usage)
- [Development](#development)
- [Deployment](#deployment)

## 🏗️ Architecture

### Database Schema

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Clients   │       │  Branches   │       │   Tokens    │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │───┐   │ id (PK)     │       │ id (PK)     │
│ client_id   │   └──→│ client_id   │   ┌──→│ client_id   │
│ secret      │       │ branch_id   │   │   │ access_token│
│ redirect_uri│       │ branch_name │   │   │ refresh_token│
│ is_active   │       │ account_id  │   │   │ expires_at  │
└─────────────┘       │ location_id │   │   │ is_valid    │
                      │ email       │   │   └─────────────┘
                      │ is_active   │   │
                      └─────────────┘   │
                                       │
                      ┌─────────────┐   │
                      │ OAuthStates │   │
                      ├─────────────┤   │
                      │ id (PK)     │   │
                      │ state       │   │
                      │ client_id   │───┘
                      │ expires_at  │
                      │ is_used     │
                      └─────────────┘
```

### Key Concepts

- **Client**: Stores Google OAuth credentials (client_id, client_secret)
- **Branch**: Links clients to specific business locations/branches
- **Token**: Stores access/refresh tokens with automatic refresh logic
- **BranchID**: Unique identifier to track review fetching across accounts/locations

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

### Core Endpoints

#### Client Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/clients` | Register new OAuth client |
| GET | `/clients` | List all clients |
| GET | `/clients/{id}` | Get client details |
| PATCH | `/clients/{id}` | Update client |
| DELETE | `/clients/{id}` | Delete client |

#### Branch Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/branches` | Create new branch |
| GET | `/branches` | List branches (filterable) |
| GET | `/branches/{id}` | Get branch details |
| GET | `/branches/by-branch-id/{branch_id}` | Get branch by branch_id |
| PATCH | `/branches/{id}` | Update branch |
| DELETE | `/branches/{id}` | Delete branch |

#### OAuth Flow

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/oauth/start/{client_id}` | Get OAuth authorization URL |
| GET | `/oauth/login/{client_id}` | Browser redirect to OAuth |
| GET | `/auth/callback` | OAuth callback (Google redirects here) |

#### Token Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tokens/validate/{client_id}` | Get valid token (auto-refresh) |
| POST | `/tokens/refresh` | Manually refresh token |
| GET | `/tokens/client/{client_id}` | Get current token |
| DELETE | `/tokens/{client_id}` | Revoke all client tokens |

## 💡 Usage

### Step 1: Register a Client

```bash
curl -X POST http://localhost:8002/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "redirect_uri": "http://localhost:8002/auth/callback"
  }'
```

Response:
```json
{
  "id": 1,
  "client_id": "YOUR_GOOGLE_CLIENT_ID",
  "redirect_uri": "http://localhost:8002/auth/callback",
  "is_active": true,
  "created_at": "2026-01-16T10:00:00",
  "updated_at": "2026-01-16T10:00:00"
}
```

### Step 2: Create Branches

```bash
curl -X POST http://localhost:8002/branches \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "branch-nyc-001",
    "client_id": 1,
    "branch_name": "NYC Branch",
    "email": "nyc@company.com",
    "account_id": "accounts/123456",
    "location_id": "locations/789012"
  }'
```

### Step 3: Complete OAuth Flow

Navigate to: `http://localhost:8002/oauth/login/1`

This will:
1. Redirect to Google OAuth consent screen
2. User authorizes access
3. Google redirects back to `/auth/callback`
4. Tokens are automatically stored

### Step 4: Validate & Use Tokens

```bash
curl http://localhost:8002/tokens/validate/1
```

Response:
```json
{
  "is_valid": true,
  "access_token": "ya29.a0AfH6...",
  "expires_at": "2026-01-16T11:00:00",
  "message": "Token is valid"
}
```

### Step 5: Integration with Review Fetcher

The review-fetcher-service can now call this endpoint before making API requests:

```python
import httpx

async def get_valid_token(client_id: int) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://token-service:8002/tokens/validate/{client_id}"
        )
        data = response.json()
        
        if data["is_valid"]:
            return data["access_token"]
        else:
            raise Exception("No valid token available")

# Use in your API calls
access_token = await get_valid_token(client_id=1)
headers = {"Authorization": f"Bearer {access_token}"}
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
