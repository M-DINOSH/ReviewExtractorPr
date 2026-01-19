# Token Management Integration Guide

## How to Use Token Management with Review-Fetcher

This guide shows how to integrate the token management endpoints with your existing review-fetcher workflow.

## Step-by-Step OAuth Flow

### Step 1: Register an OAuth Client

Create a new OAuth client in the system (one-time setup per branch/workspace):

```bash
curl -X POST http://localhost:8084/token-management/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "redirect_uri": "http://localhost:8084/token-management/auth/callback",
    "branch_id": "branch-123",
    "workspace_email": "workspace@example.com",
    "workspace_name": "My Workspace"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Client created successfully",
  "client_id": 1,
  "client_oauth_id": "YOUR_GOOGLE_CLIENT_ID",
  "branch_id": 1,
  "branch_identifier": "branch-123",
  "email": "workspace@example.com",
  "workspace_name": "My Workspace",
  "redirect_uri": "http://localhost:8084/token-management/auth/callback",
  "created_at": "2024-01-01T10:00:00"
}
```

**Note:** Save the `client_id` (1 in this example) for next steps.

### Step 2: Initiate OAuth Login

Direct the user to authenticate with Google:

```bash
# In your web browser, navigate to:
http://localhost:8084/token-management/oauth/login/1

# This redirects to Google OAuth consent screen
# User grants permission to access Google My Business API
# Google redirects back to: http://localhost:8084/token-management/auth/callback?code=AUTH_CODE
```

### Step 3: OAuth Callback (Automatic)

The system automatically handles the callback:
- Exchanges authorization code for tokens
- Stores access_token and refresh_token in database
- Returns response to the browser/client

**Response at callback:**
```json
{
  "success": true,
  "message": "OAuth flow completed successfully",
  "client_id": "YOUR_GOOGLE_CLIENT_ID",
  "branch_id": "branch-123",
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_at": "2024-01-01T11:00:00"
}
```

### Step 4: Get Token for API Requests

When you need to make API calls to Google My Business, fetch the current access token:

```bash
curl http://localhost:8084/token-management/tokens/branch-123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "success": true,
  "message": "Token retrieved successfully",
  "client_id": 1,
  "branch_id": "branch-123",
  "access_token": "ya29.a0AfH6SMBx...",
  "refresh_token": "1//0gw5...",
  "expires_at": "2024-01-01T11:00:00",
  "token_type": "Bearer"
}
```

**Key Point:** The token is automatically refreshed if expiring within 5 minutes!

### Step 5: Use Token with Review-Fetcher API

Use the access_token from Step 4 with review-fetcher's existing Google API:

```bash
# Example: Fetch reviews (existing review-fetcher endpoint)
curl -X POST http://localhost:8084/api/v1/reviews/search \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.a0AfH6SMBx...",  # From token management
    "location_id": "12345",
    "limit": 100
  }'
```

## Complete Integration Example

### Scenario: Automated Review Fetching

```
1. Setup (One-time)
   ├─ Register OAuth client with branch_id
   └─ User completes OAuth flow

2. Daily Workflow
   ├─ Get current token: GET /token-management/tokens/{branch_id}
   │  (Auto-refreshes if needed)
   ├─ Fetch reviews: POST /api/v1/reviews/search
   │  (Using token from step 2)
   └─ Store results in database

3. Token Refresh (Automatic)
   └─ Token service refreshes when expiring
```

### Python Example

```python
import requests
from datetime import datetime

class ReviewFetcher:
    def __init__(self, branch_id: str, api_url: str = "http://localhost:8084"):
        self.branch_id = branch_id
        self.api_url = api_url
    
    def get_access_token(self) -> str:
        """Get current access token (auto-refreshes if needed)"""
        response = requests.get(
            f"{self.api_url}/token-management/tokens/{self.branch_id}"
        )
        response.raise_for_status()
        data = response.json()
        
        if not data["success"]:
            raise Exception(f"Failed to get token: {data.get('message')}")
        
        token = data["access_token"]
        expires_at = datetime.fromisoformat(data["expires_at"])
        
        print(f"Token obtained, expires at: {expires_at}")
        return token
    
    def fetch_reviews(self, location_id: str, limit: int = 100) -> dict:
        """Fetch reviews using token management"""
        # Get current token (auto-refreshed if needed)
        access_token = self.get_access_token()
        
        # Use token to fetch reviews
        response = requests.post(
            f"{self.api_url}/api/v1/reviews/search",
            headers={"Content-Type": "application/json"},
            json={
                "access_token": access_token,
                "location_id": location_id,
                "limit": limit
            }
        )
        response.raise_for_status()
        return response.json()


# Usage
if __name__ == "__main__":
    fetcher = ReviewFetcher(branch_id="branch-123")
    
    # This automatically refreshes token if needed!
    reviews = fetcher.fetch_reviews(location_id="12345")
    print(f"Fetched {len(reviews)} reviews")
```

### Node.js Example

```javascript
class ReviewFetcher {
  constructor(branchId, apiUrl = 'http://localhost:8084') {
    this.branchId = branchId;
    this.apiUrl = apiUrl;
  }
  
  async getAccessToken() {
    const response = await fetch(
      `${this.apiUrl}/token-management/tokens/${this.branchId}`
    );
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(`Failed to get token: ${data.message}`);
    }
    
    const expiresAt = new Date(data.expires_at);
    console.log(`Token obtained, expires at: ${expiresAt}`);
    
    return data.access_token;
  }
  
  async fetchReviews(locationId, limit = 100) {
    // Get current token (auto-refreshed if needed)
    const accessToken = await this.getAccessToken();
    
    // Use token to fetch reviews
    const response = await fetch(
      `${this.apiUrl}/api/v1/reviews/search`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access_token: accessToken,
          location_id: locationId,
          limit: limit
        })
      }
    );
    
    return response.json();
  }
}

// Usage
(async () => {
  const fetcher = new ReviewFetcher('branch-123');
  const reviews = await fetcher.fetchReviews('12345');
  console.log(`Fetched ${reviews.length} reviews`);
})();
```

## API Reference Quick Start

### Authentication

Most endpoints don't require explicit authentication (auth is handled internally).

### Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/token-management/clients` | Register OAuth client |
| GET | `/token-management/oauth/login/{client_id}` | Start OAuth flow |
| GET | `/token-management/auth/callback` | OAuth callback (automatic) |
| POST | `/token-management/tokens/refresh` | Refresh token (manual) |
| GET | `/token-management/tokens/{branch_id}` | Get current token |

### Error Handling

All endpoints return structured JSON responses:

```json
{
  "success": false,
  "message": "Error description"
}
```

Common errors:

```
404 - Client not found
400 - Missing authorization code
400 - Client already registered
500 - Failed to exchange code
500 - Failed to refresh token
```

## Token Expiration & Refresh

### Automatic Refresh

The system automatically refreshes tokens when:
- `ensure_valid_token()` is called
- Token expires within 5 minutes

**No action needed** - Just call the token endpoint!

### Manual Refresh

If needed, manually refresh a token:

```bash
curl -X POST http://localhost:8084/token-management/tokens/refresh \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1}'
```

## Troubleshooting

### Token Not Found

**Problem:** `404 - Client/Branch not found`

**Solutions:**
1. Check branch_id is correct
2. Verify client was registered with POST /token-management/clients
3. Check database: `SELECT * FROM clients;`

### Token Refresh Failed

**Problem:** `500 - Failed to refresh token`

**Solutions:**
1. Check if refresh_token exists in database
2. Verify Google OAuth credentials haven't changed
3. Check application logs for detailed error

### Authorization Code Invalid

**Problem:** `400 - Failed to exchange code`

**Solutions:**
1. Ensure authorization code wasn't used before (one-time use)
2. Check code hasn't expired (expires in ~10 minutes)
3. Verify redirect_uri matches Google OAuth settings
4. Check client_id and client_secret are correct

## Production Deployment

### Environment Setup

```bash
# .env file
TOKEN_MANAGEMENT_DATABASE_URL=postgresql://token_user:token_password@db.example.com:5432/tokens
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

### Database Migration

```bash
# Before first deployment
docker exec review-fetcher-service alembic -c alembic_tokens.ini upgrade head

# Verify migration
docker exec postgres-tokens psql -U token_user -d token_service_db \
  -c "SELECT * FROM alembic_version;"
```

### Monitoring

Monitor these metrics:
- Token refresh success rate
- Token expiry distribution
- OAuth callback latency
- Database connection pool usage

### Backup Strategy

```bash
# Daily backup of token database
pg_dump -U token_user postgresql://db.example.com:5432/token_service_db \
  | gzip > /backups/tokens-$(date +%Y%m%d).sql.gz

# Restore if needed
zcat /backups/tokens-20240101.sql.gz | \
  psql -U token_user postgresql://db.example.com:5432/token_service_db
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Deploy Review Fetcher

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build Docker image
        run: docker build -t review-fetcher:latest .
      
      - name: Start services
        run: docker-compose up -d
      
      - name: Initialize token database
        run: |
          docker exec review-fetcher-service \
            alembic -c alembic_tokens.ini upgrade head
      
      - name: Run tests
        run: docker-compose exec review-fetcher-service pytest
      
      - name: Push to registry
        run: docker push review-fetcher:latest
```

## FAQ

**Q: Can I use the same token for multiple branches?**
A: No, each branch needs its own OAuth client registration.

**Q: What happens if I don't refresh tokens?**
A: The system automatically refreshes them. Just call the token endpoint!

**Q: Can I revoke a token?**
A: Yes, the token service has revoke_token() method. Contact support for API endpoint.

**Q: How long do tokens last?**
A: Typically 1 hour. Refresh tokens last until revoked.

**Q: Can I see token history?**
A: Token service doesn't store history by default. Implement logging for audit trail.

**Q: How many tokens per client?**
A: Only 1 valid token at a time. Creating new token invalidates old ones.
