# Token Generation Service - Quick Start Guide

## Overview

This service manages OAuth2 tokens for Google Business Profile API with automatic refresh and PostgreSQL persistence.

## Quick Start (5 minutes)

### 1. Start the Service

```bash
cd token-generation-service
docker-compose up -d
```

Wait for services to start (~30 seconds):
```bash
docker-compose logs -f token-service
# Wait for "Application startup complete"
```

### 2. Verify Service is Running

```bash
curl http://localhost:8002/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Token Generation Service",
  "version": "1.0.0",
  "timestamp": "2026-01-16T10:00:00",
  "database": "connected"
}
```

### 3. Register Your OAuth Client

Replace with your Google OAuth credentials:

```bash
curl -X POST http://localhost:8002/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "redirect_uri": "http://localhost:8002/auth/callback"
  }'
```

Note the `id` in the response (e.g., `"id": 1`).

### 4. Create a Branch

```bash
curl -X POST http://localhost:8002/branches \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "main-branch",
    "client_id": 1,
    "branch_name": "Main Location",
    "email": "manager@company.com"
  }'
```

### 5. Complete OAuth Flow

Open in browser:
```
http://localhost:8002/oauth/login/1
```

This will:
- Redirect to Google OAuth
- Ask for authorization
- Redirect back and store tokens
- Show success message

### 6. Get Valid Token

```bash
curl http://localhost:8002/tokens/validate/1
```

Response includes valid access token:
```json
{
  "is_valid": true,
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_at": "2026-01-16T11:00:00",
  "message": "Token is valid"
}
```

## 🎉 Done!

Your token service is now running and can:
- ✅ Manage OAuth tokens
- ✅ Automatically refresh before expiry
- ✅ Track multiple branches
- ✅ Provide valid tokens to other services

## Next Steps

### View API Documentation

Open in browser:
- Swagger UI: http://localhost:8002/docs
- ReDoc: http://localhost:8002/redoc

### Integrate with Review Fetcher

Add to your review-fetcher service:

```python
async def get_access_token(client_id: int) -> str:
    """Get a valid access token from token service"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://token-service:8002/tokens/validate/{client_id}"
        )
        data = response.json()
        
        if not data["is_valid"]:
            raise Exception("No valid token available")
        
        return data["access_token"]
```

### Common Commands

```bash
# View logs
docker-compose logs -f token-service

# Restart service
docker-compose restart token-service

# Stop services
docker-compose down

# Stop and remove data
docker-compose down -v
```

## Troubleshooting

**Problem**: "Client not found"
- **Solution**: Make sure you registered the client first (Step 3)

**Problem**: "Invalid or expired OAuth state"
- **Solution**: The OAuth flow timed out. Start again from Step 5

**Problem**: Database connection error
- **Solution**: Check PostgreSQL is running: `docker-compose ps postgres`

**Problem**: Token not refreshing
- **Solution**: Make sure you completed OAuth with `access_type=offline` (handled automatically)

## Production Deployment

1. **Copy environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Update .env with production values**:
   ```bash
   ENVIRONMENT=production
   DATABASE_URL=postgresql://user:pass@your-db-host:5432/dbname
   SECRET_KEY=your-strong-random-secret-key-here
   ```

3. **Update docker-compose.yml redirect URI**:
   ```yaml
   environment:
     - DEFAULT_REDIRECT_URI=https://your-domain.com/auth/callback
   ```

4. **Deploy**:
   ```bash
   docker-compose up -d
   ```

## Architecture Flow

```
┌──────────────┐    1. Register    ┌──────────────────┐
│   Admin      │─────────────────>│  Token Service   │
│              │                   │                  │
└──────────────┘                   └────────┬─────────┘
                                            │
┌──────────────┐    2. OAuth      ┌────────▼─────────┐
│   Browser    │<────Redirect─────│   /oauth/login   │
│              │                   └────────┬─────────┘
└──────┬───────┘                            │
       │                                    │
       │    3. Authorize                    │
       ▼                                    │
┌──────────────┐                   ┌────────▼─────────┐
│    Google    │────Callback──────>│  /auth/callback  │
│    OAuth     │                   │                  │
└──────────────┘                   └────────┬─────────┘
                                            │
                                   ┌────────▼─────────┐
                                   │   PostgreSQL     │
                                   │  (Store tokens)  │
                                   └────────┬─────────┘
                                            │
┌──────────────┐   4. Get Token    ┌────────▼─────────┐
│   Review     │<──────────────────│  /tokens/validate│
│   Fetcher    │   (Auto-refresh)  │                  │
└──────────────┘                   └──────────────────┘
```

## Support

- **Documentation**: See [README.md](README.md)
- **API Docs**: http://localhost:8002/docs
- **Logs**: `docker-compose logs token-service`
