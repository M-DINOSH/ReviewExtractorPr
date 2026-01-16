# API Flow Documentation

## Complete OAuth Flow

### 1. Client Registration

**Endpoint**: `POST /clients`

Register your Google OAuth credentials:

```bash
curl -X POST http://localhost:8002/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "123456789.apps.googleusercontent.com",
    "client_secret": "GOCSPX-abc123xyz",
    "redirect_uri": "http://localhost:8002/auth/callback"
  }'
```

**Response**:
```json
{
  "id": 1,
  "client_id": "123456789.apps.googleusercontent.com",
  "redirect_uri": "http://localhost:8002/auth/callback",
  "is_active": true,
  "created_at": "2026-01-16T10:00:00",
  "updated_at": "2026-01-16T10:00:00"
}
```

### 2. Branch Creation

**Endpoint**: `POST /branches`

Create branches to track different business locations:

```bash
curl -X POST http://localhost:8002/branches \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "branch-001",
    "client_id": 1,
    "branch_name": "Downtown Branch",
    "email": "downtown@company.com",
    "account_id": "accounts/123456789",
    "location_id": "locations/987654321",
    "description": "Main downtown location"
  }'
```

**Response**:
```json
{
  "id": 1,
  "branch_id": "branch-001",
  "client_id": 1,
  "branch_name": "Downtown Branch",
  "account_id": "accounts/123456789",
  "location_id": "locations/987654321",
  "email": "downtown@company.com",
  "description": "Main downtown location",
  "is_active": true,
  "created_at": "2026-01-16T10:05:00",
  "updated_at": "2026-01-16T10:05:00"
}
```

### 3. Start OAuth Flow

**Option A: Get Authorization URL** (for programmatic flow)

**Endpoint**: `GET /oauth/start/{client_id}`

```bash
curl http://localhost:8002/oauth/start/1
```

**Response**:
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
  "state": "550e8400-e29b-41d4-a716-446655440000"
}
```

Then redirect user to the `auth_url`.

**Option B: Direct Browser Redirect** (simpler)

**Endpoint**: `GET /oauth/login/{client_id}`

Navigate to: `http://localhost:8002/oauth/login/1`

This automatically redirects to Google OAuth consent screen.

### 4. User Authorization

User sees Google consent screen:
- Reviews requested permissions
- Clicks "Allow"

### 5. OAuth Callback

**Endpoint**: `GET /auth/callback` (Google redirects here)

Google redirects to:
```
http://localhost:8002/auth/callback?code=4/0AbC123...&state=550e8400-e29b-41d4-a716-446655440000
```

**Response**:
```json
{
  "success": true,
  "message": "OAuth flow completed successfully",
  "client_id": "123456789.apps.googleusercontent.com",
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_at": "2026-01-16T11:00:00"
}
```

**What happens internally**:
1. Validates state parameter
2. Exchanges code for tokens with Google
3. Stores tokens in database
4. Returns success response

### 6. Token Validation & Usage

**Endpoint**: `GET /tokens/validate/{client_id}`

Get a valid access token (auto-refreshes if needed):

```bash
curl http://localhost:8002/tokens/validate/1
```

**Response** (valid token):
```json
{
  "is_valid": true,
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_at": "2026-01-16T11:00:00",
  "message": "Token is valid"
}
```

**Response** (needs OAuth):
```json
{
  "is_valid": false,
  "message": "No valid token available. Please complete OAuth flow."
}
```

## Token Lifecycle

### Auto-Refresh Mechanism

When `/tokens/validate/{client_id}` is called:

```
┌─────────────────────┐
│  Token Exists?      │
└─────────┬───────────┘
          │
    ┌─────▼─────┐
    │   Yes     │
    └─────┬─────┘
          │
┌─────────▼───────────┐
│ Expires in < 5 min? │
└─────────┬───────────┘
          │
    ┌─────▼─────┐
    │   No      │────────────> Return existing token
    └───────────┘
          
    ┌─────▼─────┐
    │   Yes     │
    └─────┬─────┘
          │
┌─────────▼───────────┐
│ Has refresh token?  │
└─────────┬───────────┘
          │
    ┌─────▼─────┐
    │   Yes     │
    └─────┬─────┘
          │
┌─────────▼───────────┐
│ Call Google to      │
│ refresh token       │
└─────────┬───────────┘
          │
    ┌─────▼─────┐
    │  Success  │────────────> Return new token
    └───────────┘
```

### Manual Token Refresh

**Endpoint**: `POST /tokens/refresh`

Force refresh a token:

```bash
curl -X POST http://localhost:8002/tokens/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "client_internal_id": 1
  }'
```

**Response**:
```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_at": "2026-01-16T12:00:00"
}
```

## Integration Example: Review Fetcher Service

### Python Integration

```python
import httpx
from typing import Optional

class TokenClient:
    def __init__(self, token_service_url: str = "http://token-service:8002"):
        self.base_url = token_service_url
        
    async def get_valid_token(self, client_id: int) -> Optional[str]:
        """
        Get a valid access token, automatically refreshed if needed
        
        Args:
            client_id: Internal client ID from token service
            
        Returns:
            Valid access token or None
        """
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.base_url}/tokens/validate/{client_id}"
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data["is_valid"]:
                    return data["access_token"]
            
            return None
    
    async def make_google_api_request(
        self, 
        client_id: int,
        endpoint: str
    ):
        """
        Make a Google API request with automatic token handling
        
        Args:
            client_id: Internal client ID
            endpoint: Google API endpoint
        """
        # Get valid token
        access_token = await self.get_valid_token(client_id)
        
        if not access_token:
            raise Exception("No valid token available")
        
        # Make API request
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json()


# Usage example
token_client = TokenClient()

# Fetch reviews for a location
async def fetch_reviews(client_id: int, location_id: str):
    endpoint = f"https://mybusiness.googleapis.com/v4/{location_id}/reviews"
    
    try:
        reviews = await token_client.make_google_api_request(
            client_id=client_id,
            endpoint=endpoint
        )
        return reviews
    except Exception as e:
        print(f"Failed to fetch reviews: {e}")
        return None
```

### Docker Compose Integration

```yaml
version: '3.8'

services:
  # Token Service
  token-service:
    image: token-generation-service:latest
    networks:
      - app-network
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/token_db
    
  # Review Fetcher Service
  review-fetcher:
    image: review-fetcher-service:latest
    networks:
      - app-network
    environment:
      - TOKEN_SERVICE_URL=http://token-service:8002
    depends_on:
      - token-service

networks:
  app-network:
    driver: bridge
```

## Branch Tracking Use Cases

### Use Case 1: Multi-Location Business

A restaurant chain with multiple locations:

```bash
# Create branch for each location
curl -X POST http://localhost:8002/branches \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "restaurant-nyc-001",
    "client_id": 1,
    "branch_name": "NYC Times Square",
    "account_id": "accounts/123",
    "location_id": "locations/456",
    "email": "nyc@restaurant.com"
  }'

curl -X POST http://localhost:8002/branches \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "restaurant-la-001",
    "client_id": 1,
    "branch_name": "LA Downtown",
    "account_id": "accounts/123",
    "location_id": "locations/789",
    "email": "la@restaurant.com"
  }'
```

### Use Case 2: Query Branches by Account

Get all branches for an account:

```bash
curl "http://localhost:8002/branches?client_id=1"
```

### Use Case 3: Branch-Specific Token Usage

When fetching reviews, track which branch initiated the request:

```python
async def fetch_reviews_for_branch(branch_id: str):
    # Get branch info
    branch = await get_branch_by_id(branch_id)
    
    # Get token for branch's client
    token = await get_valid_token(branch.client_id)
    
    # Fetch reviews for branch's location
    reviews = await fetch_google_reviews(
        location_id=branch.location_id,
        access_token=token
    )
    
    # Tag reviews with branch_id
    for review in reviews:
        review["branch_id"] = branch_id
    
    return reviews
```

## Error Handling

### Common Error Responses

**Client Not Found** (404):
```json
{
  "detail": "Client not found"
}
```

**Invalid OAuth State** (400):
```json
{
  "detail": "Invalid or expired OAuth state"
}
```

**Token Refresh Failed** (500):
```json
{
  "detail": "Failed to refresh token: invalid_grant"
}
```

**No Valid Token** (200, but is_valid=false):
```json
{
  "is_valid": false,
  "message": "No valid token available. Please complete OAuth flow."
}
```

## Rate Limiting & Best Practices

### Token Validation

- ✅ Call `/tokens/validate` before each API request
- ✅ Cache the token for a few minutes (but check expiry)
- ❌ Don't cache for too long (token may expire)

### Token Refresh

- ✅ Let auto-refresh handle it (5-minute buffer)
- ✅ Use manual refresh only when needed
- ❌ Don't refresh on every request

### Branch Management

- ✅ Create branches for logical groupings
- ✅ Use meaningful branch_id (e.g., "branch-nyc-001")
- ✅ Link account_id and location_id when known
- ❌ Don't create duplicate branches

## Monitoring & Debugging

### Check Token Status

```bash
curl http://localhost:8002/tokens/client/1
```

### List All Branches

```bash
curl http://localhost:8002/branches
```

### Health Check

```bash
curl http://localhost:8002/health
```

### Database Inspection

```bash
# Connect to database
docker exec -it token-service-postgres psql -U token_user -d token_service_db

# Check tokens
SELECT id, client_id, expires_at, is_valid FROM tokens;

# Check branches
SELECT branch_id, branch_name, account_id, location_id FROM branches;
```
