# 🚀 Google Reviews Fetcher - Team Integration Guide

## Overview

This microservice provides a complete Google Reviews fetching solution that your team can integrate with your main application. It handles the entire flow from OAuth access tokens to published reviews.

## 🏗️ Architecture

```
Your Frontend App
        ↓
    POST /sync (access_token)
        ↓
Google Reviews Fetcher Service (3 replicas)
        ↓
Background Processing:
- Token Validation
- Accounts Fetch
- Locations Fetch
- Reviews Fetch
- Kafka Publish
        ↓
    Reviews Available via:
    - GET /reviews (all reviews)
    - GET /reviews/{job_id} (job-specific)
    - Kafka Topic: google.reviews.ingested
```

## 📦 Deployment Options

### Option 1: Docker Compose (Recommended for Development/Testing)

```bash
# Clone the repository
git clone <repository-url>
cd review-fetcher-service

# Start all services (PostgreSQL, Redis, Kafka, Review Fetcher)
docker-compose --profile dev up -d

# Service will be available at: http://localhost:8084
```

### Option 2: Kubernetes (Production)

```yaml
# Deploy using the provided docker-compose.yml as reference
# - 3 replicas of review-fetcher service
# - PostgreSQL with persistent volumes
# - Redis for caching
# - Kafka for message queuing
```

### Option 3: Integrate with Existing Infrastructure

If your team already has PostgreSQL, Redis, and Kafka:

```bash
# Build and run only the review-fetcher service
docker build -t review-fetcher .
docker run -p 8084:8000 \
  -e DATABASE_URL=postgresql+asyncpg://your-db-url \
  -e REDIS_URL=redis://your-redis-url \
  -e KAFKA_BOOTSTRAP_SERVERS=your-kafka-servers \
  review-fetcher
```

## 🔗 API Integration

### 1. Start Review Sync

**Endpoint:** `POST /sync`

**Request:**
```json
{
  "access_token": "ya29.your_oauth_token_here",
  "client_id": "your_client_id",
  "request_id": "optional_request_id",
  "correlation_id": "optional_correlation_id"
}
```

**Response:**
```json
{
  "job_id": 123,
  "status": "pending",
  "message": "Continuous sync flow initiated"
}
```

### 2. Check Sync Status

**Endpoint:** `GET /job/{job_id}`

**Response:**
```json
{
  "job_id": 123,
  "status": "completed",
  "current_step": "completed",
  "step_status": {
    "token_validation": {"status": "completed"},
    "accounts_fetch": {"status": "completed", "message": "Fetched 5 accounts"},
    "locations_fetch": {"status": "completed", "message": "Fetched 49 locations"},
    "reviews_fetch": {"status": "completed", "message": "Fetched 490 reviews"},
    "kafka_publish": {"status": "completed", "message": "Published 490 reviews"}
  }
}
```

### 3. Get Reviews

**Endpoint:** `GET /reviews` (all reviews) or `GET /reviews/{job_id}` (job-specific)

**Response:**
```json
{
  "total_reviews": 490,
  "reviews": [
    {
      "id": "review_123",
      "location_id": "location_456",
      "rating": 5,
      "comment": "Great service!",
      "reviewer_name": "John Doe",
      "review_time": "2024-01-15T10:30:00Z",
      "job_id": 123
    }
  ]
}
```

## 🎯 Frontend Integration Example

### React/JavaScript Integration

```javascript
// 1. When user completes OAuth flow, send access token
const startReviewSync = async (accessToken, clientId) => {
  try {
    const response = await fetch('http://your-service-url/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        access_token: accessToken,
        client_id: clientId,
        request_id: `sync_${Date.now()}`,
        correlation_id: `session_${Date.now()}`
      })
    });

    const result = await response.json();
    return result.job_id; // Track this job ID
  } catch (error) {
    console.error('Failed to start sync:', error);
  }
};

// 2. Poll for completion (or use websockets)
const checkSyncStatus = async (jobId) => {
  try {
    const response = await fetch(`http://your-service-url/job/${jobId}`);
    const status = await response.json();
    return status;
  } catch (error) {
    console.error('Failed to check status:', error);
  }
};

// 3. Get reviews once sync is complete
const getReviews = async (jobId) => {
  try {
    const response = await fetch(`http://your-service-url/reviews/${jobId}`);
    const reviews = await response.json();
    return reviews;
  } catch (error) {
    console.error('Failed to get reviews:', error);
  }
};

// Usage example
const handleOAuthSuccess = async (accessToken) => {
  // Start the sync process
  const jobId = await startReviewSync(accessToken, 'my_client');

  // Poll for completion
  const pollStatus = setInterval(async () => {
    const status = await checkSyncStatus(jobId);
    if (status.status === 'completed') {
      clearInterval(pollStatus);

      // Get the reviews
      const reviews = await getReviews(jobId);
      console.log('Reviews fetched:', reviews);

      // Update your UI with the reviews
      displayReviews(reviews.reviews);
    }
  }, 5000); // Check every 5 seconds
};
```

### Python/Backend Integration

```python
import requests
import time

def sync_google_reviews(access_token: str, client_id: str, service_url: str):
    # Start sync
    response = requests.post(f"{service_url}/sync", json={
        "access_token": access_token,
        "client_id": client_id,
        "request_id": f"sync_{int(time.time())}",
        "correlation_id": f"session_{int(time.time())}"
    })
    job_id = response.json()["job_id"]

    # Wait for completion
    while True:
        status_response = requests.get(f"{service_url}/job/{job_id}")
        status = status_response.json()

        if status["status"] == "completed":
            break
        elif status["status"] == "failed":
            raise Exception("Sync failed")

        time.sleep(5)  # Wait 5 seconds

    # Get reviews
    reviews_response = requests.get(f"{service_url}/reviews/{job_id}")
    reviews = reviews_response.json()

    return reviews["reviews"]
```

## 🔄 Real-time Updates with Kafka

For real-time processing, consume from the Kafka topic:

**Topic:** `google.reviews.ingested`

**Message Format:**
```json
{
  "review_id": "review_123",
  "location_id": "location_456",
  "account_id": "account_789",
  "rating": 5,
  "comment": "Excellent service!",
  "reviewer_name": "Jane Smith",
  "review_time": "2024-01-15T10:30:00Z",
  "job_id": 123,
  "client_id": "your_client"
}
```

## 🧪 Testing with Mock Data

For development/testing, the service includes mock mode:

```bash
# Enable mock mode
export MOCK_MODE=true

# Use mock tokens like: "mock_token_123"
```

## 📊 Monitoring & Health Checks

**Health Check:** `GET /health`

**Metrics to Monitor:**
- Sync job success/failure rates
- Average processing time per job
- API response times
- Database connection pool usage
- Kafka message publishing success

## 🚀 Production Checklist

- [ ] Replace mock APIs with real Google Business Profile APIs
- [ ] Configure proper OAuth2 flow
- [ ] Set up monitoring and alerting
- [ ] Configure rate limiting for API quotas
- [ ] Set up Kafka consumers for your review processing pipeline
- [ ] Configure database backups
- [ ] Set up horizontal scaling based on load
- [ ] Implement proper authentication/authorization

## 📞 Support

For integration questions:
1. Check the API documentation in `README.md`
2. Review the demo script `demo.sh` for usage examples
3. Test with mock mode first
4. Contact the development team for production deployment assistance</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/TEAM_INTEGRATION_GUIDE.md