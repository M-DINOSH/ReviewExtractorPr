# Integration Example with Review Fetcher Service

This document shows how to integrate the token-generation-service with the review-fetcher-service.

## Architecture Overview

```
┌─────────────────────┐
│  Review Fetcher     │
│    Service          │
└──────────┬──────────┘
           │
           │ 1. Request valid token
           ▼
┌─────────────────────┐
│  Token Generation   │
│    Service          │
└──────────┬──────────┘
           │
           │ 2. Check/Refresh token
           ▼
┌─────────────────────┐
│   PostgreSQL        │
│   (Tokens DB)       │
└─────────────────────┘
           │
           │ 3. Return valid token
           ▼
┌─────────────────────┐
│  Review Fetcher     │
│    Service          │
└──────────┬──────────┘
           │
           │ 4. Use token for API
           ▼
┌─────────────────────┐
│  Google Business    │
│   Profile API       │
└─────────────────────┘
```

## Docker Compose Integration

### Combined docker-compose.yml

Create a root-level `docker-compose.yml` that orchestrates both services:

```yaml
version: '3.8'

services:
  # PostgreSQL for Token Service
  token-postgres:
    image: postgres:15-alpine
    container_name: token-postgres
    environment:
      POSTGRES_USER: token_user
      POSTGRES_PASSWORD: token_password
      POSTGRES_DB: token_service_db
    ports:
      - "5433:5432"
    volumes:
      - token_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U token_user -d token_service_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app-network

  # Token Generation Service
  token-service:
    build:
      context: ./token-generation-service
      dockerfile: Dockerfile
    container_name: token-generation-service
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://token_user:token_password@token-postgres:5432/token_service_db
      - HOST=0.0.0.0
      - PORT=8002
      - LOG_LEVEL=INFO
    ports:
      - "8002:8002"
    depends_on:
      token-postgres:
        condition: service_healthy
    volumes:
      - ./token-generation-service/logs:/app/logs
    networks:
      - app-network
    restart: unless-stopped
    command: >
      sh -c "
        echo 'Running database migrations...' &&
        alembic upgrade head &&
        echo 'Starting token service...' &&
        uvicorn src.token_service.api.main:app --host 0.0.0.0 --port 8002
      "

  # Review Fetcher Service
  review-fetcher:
    build:
      context: ./review-fetcher-service
      dockerfile: Dockerfile
    container_name: review-fetcher-service
    environment:
      - ENVIRONMENT=production
      - TOKEN_SERVICE_URL=http://token-service:8002
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    ports:
      - "8001:8000"
    depends_on:
      - token-service
      - kafka
    networks:
      - app-network
    restart: unless-stopped

  # Kafka (for review-fetcher)
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    container_name: zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    networks:
      - app-network

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    networks:
      - app-network

volumes:
  token_postgres_data:
    driver: local

networks:
  app-network:
    driver: bridge
```

## Code Integration in Review Fetcher

### 1. Create Token Client Module

Create `review-fetcher-service/app/services/token_client.py`:

```python
"""
Token Service Client - Handles communication with token-generation-service
"""
import httpx
from typing import Optional
from datetime import datetime
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class TokenServiceClient:
    """Client for token-generation-service"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.TOKEN_SERVICE_URL
        self.timeout = 10
        
    async def get_valid_token(self, client_id: int) -> Optional[str]:
        """
        Get a valid access token for a client
        
        Args:
            client_id: Internal client ID from token service
            
        Returns:
            Valid access token or None
            
        Raises:
            Exception: If token service is unavailable
        """
        url = f"{self.base_url}/tokens/validate/{client_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("is_valid"):
                    logger.info(
                        f"Retrieved valid token for client_id={client_id}, "
                        f"expires_at={data.get('expires_at')}"
                    )
                    return data["access_token"]
                else:
                    logger.warning(
                        f"No valid token for client_id={client_id}: {data.get('message')}"
                    )
                    return None
                    
        except httpx.HTTPError as e:
            logger.error(f"Failed to get token from token service: {str(e)}")
            raise Exception(f"Token service unavailable: {str(e)}")
    
    async def refresh_token(self, client_id: int) -> Optional[str]:
        """
        Manually refresh a token
        
        Args:
            client_id: Internal client ID
            
        Returns:
            New access token or None
        """
        url = f"{self.base_url}/tokens/refresh"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json={"client_internal_id": client_id}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("success"):
                    logger.info(f"Successfully refreshed token for client_id={client_id}")
                    return data["access_token"]
                else:
                    logger.error(f"Token refresh failed: {data.get('message')}")
                    return None
                    
        except httpx.HTTPError as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return None
    
    async def get_branch_info(self, branch_id: str) -> Optional[dict]:
        """
        Get branch information
        
        Args:
            branch_id: Branch identifier
            
        Returns:
            Branch data or None
        """
        url = f"{self.base_url}/branches/by-branch-id/{branch_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Branch {branch_id} not found")
                    return None
                    
        except httpx.HTTPError as e:
            logger.error(f"Failed to get branch info: {str(e)}")
            return None
    
    async def health_check(self) -> bool:
        """
        Check if token service is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        url = f"{self.base_url}/health"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("status") == "healthy"
                    
                return False
                
        except Exception as e:
            logger.error(f"Token service health check failed: {str(e)}")
            return False


# Create singleton instance
token_client = TokenServiceClient()
```

### 2. Update Config

Add to `review-fetcher-service/app/config.py`:

```python
# Token Service Configuration
TOKEN_SERVICE_URL = os.getenv("TOKEN_SERVICE_URL", "http://localhost:8002")
DEFAULT_CLIENT_ID = int(os.getenv("DEFAULT_CLIENT_ID", "1"))
```

### 3. Update Google API Service

Modify `review-fetcher-service/app/services/google_api.py`:

```python
"""
Google API Service with Token Integration
"""
import httpx
from typing import Optional, List
from app.services.token_client import token_client
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class GoogleBusinessAPI:
    """Google Business Profile API client with automatic token management"""
    
    def __init__(self, client_id: int = None):
        self.client_id = client_id or settings.DEFAULT_CLIENT_ID
        self.base_url = "https://mybusiness.googleapis.com/v4"
        self.timeout = 30
    
    async def _get_headers(self) -> dict:
        """Get headers with valid access token"""
        access_token = await token_client.get_valid_token(self.client_id)
        
        if not access_token:
            raise Exception("No valid access token available. Complete OAuth flow first.")
        
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    async def list_accounts(self) -> List[dict]:
        """List all accounts"""
        try:
            headers = await self._get_headers()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/accounts",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                accounts = data.get("accounts", [])
                
                logger.info(f"Retrieved {len(accounts)} accounts")
                return accounts
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to list accounts: {str(e)}")
            raise
    
    async def list_locations(self, account_id: str) -> List[dict]:
        """List locations for an account"""
        try:
            headers = await self._get_headers()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/{account_id}/locations",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                locations = data.get("locations", [])
                
                logger.info(f"Retrieved {len(locations)} locations for {account_id}")
                return locations
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to list locations: {str(e)}")
            raise
    
    async def get_reviews(
        self, 
        location_name: str,
        page_size: int = 50,
        page_token: Optional[str] = None
    ) -> dict:
        """
        Get reviews for a location
        
        Args:
            location_name: Full location resource name (e.g., "accounts/123/locations/456")
            page_size: Number of reviews per page
            page_token: Token for pagination
            
        Returns:
            Reviews data with pagination info
        """
        try:
            headers = await self._get_headers()
            
            params = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/{location_name}/reviews",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                reviews = data.get("reviews", [])
                
                logger.info(f"Retrieved {len(reviews)} reviews for {location_name}")
                
                return {
                    "reviews": reviews,
                    "next_page_token": data.get("nextPageToken"),
                    "total_review_count": data.get("totalReviewCount", len(reviews))
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to get reviews: {str(e)}")
            raise
    
    async def get_all_reviews_for_branch(self, branch_id: str) -> List[dict]:
        """
        Get all reviews for a branch using branch_id
        
        Args:
            branch_id: Branch identifier from token service
            
        Returns:
            List of all reviews
        """
        # Get branch info from token service
        branch = await token_client.get_branch_info(branch_id)
        
        if not branch:
            raise Exception(f"Branch {branch_id} not found")
        
        if not branch.get("location_id"):
            raise Exception(f"Branch {branch_id} has no location_id")
        
        # Use the client_id from branch
        self.client_id = branch["client_id"]
        
        # Fetch all reviews
        all_reviews = []
        page_token = None
        
        while True:
            result = await self.get_reviews(
                location_name=branch["location_id"],
                page_token=page_token
            )
            
            reviews = result["reviews"]
            all_reviews.extend(reviews)
            
            # Add branch_id to each review
            for review in reviews:
                review["branch_id"] = branch_id
                review["branch_name"] = branch.get("branch_name")
            
            page_token = result.get("next_page_token")
            if not page_token:
                break
        
        logger.info(f"Retrieved total {len(all_reviews)} reviews for branch {branch_id}")
        return all_reviews


# Create instance
google_api = GoogleBusinessAPI()
```

### 4. Update API Endpoints

Modify `review-fetcher-service/app/api.py`:

```python
"""
API Endpoints for Review Fetcher
"""
from fastapi import FastAPI, HTTPException
from app.services.google_api import google_api
from app.services.token_client import token_client
from app.config import settings

app = FastAPI(title="Review Fetcher Service")


@app.get("/health")
async def health_check():
    """Health check with token service status"""
    token_service_healthy = await token_client.health_check()
    
    return {
        "status": "healthy",
        "service": "review-fetcher-service",
        "token_service": "healthy" if token_service_healthy else "unhealthy"
    }


@app.get("/reviews/branch/{branch_id}")
async def get_branch_reviews(branch_id: str):
    """Get all reviews for a branch"""
    try:
        reviews = await google_api.get_all_reviews_for_branch(branch_id)
        
        return {
            "success": True,
            "branch_id": branch_id,
            "total_reviews": len(reviews),
            "reviews": reviews
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accounts")
async def list_accounts(client_id: int = settings.DEFAULT_CLIENT_ID):
    """List all Google Business accounts"""
    try:
        google_api.client_id = client_id
        accounts = await google_api.list_accounts()
        
        return {
            "success": True,
            "total": len(accounts),
            "accounts": accounts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/locations/{account_id}")
async def list_locations(
    account_id: str,
    client_id: int = settings.DEFAULT_CLIENT_ID
):
    """List locations for an account"""
    try:
        google_api.client_id = client_id
        locations = await google_api.list_locations(account_id)
        
        return {
            "success": True,
            "account_id": account_id,
            "total": len(locations),
            "locations": locations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Usage Flow

### 1. Start All Services

```bash
# From root directory
docker-compose up -d

# Check all services are running
docker-compose ps
```

### 2. Register Client in Token Service

```bash
curl -X POST http://localhost:8002/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "redirect_uri": "http://localhost:8002/auth/callback"
  }'
```

### 3. Create Branches

```bash
curl -X POST http://localhost:8002/branches \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "branch-001",
    "client_id": 1,
    "branch_name": "Main Branch",
    "email": "manager@company.com"
  }'
```

### 4. Complete OAuth

Navigate to: `http://localhost:8002/oauth/login/1`

### 5. Fetch Reviews

```bash
# Get reviews for a branch
curl http://localhost:8001/reviews/branch/branch-001
```

## Environment Variables Summary

### token-generation-service/.env
```bash
DATABASE_URL=postgresql://token_user:token_password@token-postgres:5432/token_service_db
ENVIRONMENT=production
PORT=8002
```

### review-fetcher-service/.env
```bash
TOKEN_SERVICE_URL=http://token-service:8002
DEFAULT_CLIENT_ID=1
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

## Monitoring Integration

Both services should be monitored together:

```bash
# View all logs
docker-compose logs -f

# View token service logs
docker-compose logs -f token-service

# View review fetcher logs
docker-compose logs -f review-fetcher
```

## Complete Workflow Example

```python
# Complete example: Fetch reviews for multiple branches
import httpx
import asyncio

async def fetch_all_branch_reviews():
    """Fetch reviews for all branches"""
    
    # 1. Get all branches from token service
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8002/branches")
        branches = response.json()
    
    # 2. Fetch reviews for each branch
    all_reviews = []
    
    for branch in branches:
        branch_id = branch["branch_id"]
        
        print(f"Fetching reviews for {branch_id}...")
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"http://localhost:8001/reviews/branch/{branch_id}"
            )
            data = response.json()
            
            if data["success"]:
                reviews = data["reviews"]
                all_reviews.extend(reviews)
                print(f"  → Got {len(reviews)} reviews")
    
    print(f"\nTotal reviews fetched: {len(all_reviews)}")
    return all_reviews

# Run
asyncio.run(fetch_all_branch_reviews())
```

This integration provides a complete, production-ready solution for managing OAuth tokens and fetching Google Business Profile reviews across multiple branches!
