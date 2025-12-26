# Google Reviews Fetcher Service

A production-ready, scalable microservice for fetching Google Business Profile reviews and publishing them to Kafka.

## Overview

This service receives OAuth access tokens and fetches Google reviews for business accounts, locations, and reviews. It normalizes the data, persists it to PostgreSQL, and publishes to Kafka for downstream processing.

## Architecture

### High-Level Flow
```
POST /sync (access_token)
    ↓
Enqueue Background Task
    ↓
Fetch Accounts → Locations → Reviews
    ↓
Persist to PostgreSQL
    ↓
Publish to Kafka (google.reviews.ingested)
```

### Components
- **FastAPI**: Async web framework for API endpoints
- **PostgreSQL**: Data persistence with deduplication
- **Redis**: Caching for Google API responses
- **Kafka**: Message publishing for reviews
- **Background Tasks**: Async processing of Google API calls

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI (async) |
| HTTP | httpx (async) |
| DB | PostgreSQL |
| ORM | SQLAlchemy 2.0 (async) |
| Cache | Redis |
| Messaging | Kafka |
| Background Jobs | FastAPI BackgroundTasks |

## Prerequisites

- Docker & Docker Compose
- Google Business Profile API quota approval
- Kafka cluster
- PostgreSQL database
- Redis instance

## Quick Start

1. Clone and navigate to the service directory
2. Copy `.env.example` to `.env` and configure
3. Run `docker-compose up --build`

The service will be available at `http://localhost:8000`

## API Usage

### Sync Reviews
```bash
curl -X POST "http://localhost:8000/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29...",
    "client_id": "client123",
    "request_id": "req123",
    "correlation_id": "corr123"
  }'
```

Response:
```json
{
  "job_id": 1,
  "status": "pending",
  "message": "Sync job enqueued"
}
```

## Database Schema

- **sync_jobs**: Tracks sync operations
- **accounts**: Google business accounts
- **locations**: Business locations
- **reviews**: Individual reviews with deduplication

## Kafka Messages

Published to `google.reviews.ingested` topic:

```json
{
  "review_id": "ChdDSUhNMG9nS0VJQ0FnSUR...",
  "location_id": "locations/123456789",
  "account_id": "accounts/123456789",
  "rating": 5,
  "comment": "Great service!",
  "reviewer_name": "John Doe",
  "create_time": "2023-01-01T12:00:00Z",
  "source": "google",
  "ingestion_timestamp": "2023-01-01T12:00:00Z"
}
```

## Scaling

- **Horizontal Scaling**: Stateless design allows multiple instances
- **Background Processing**: Google API calls don't block HTTP responses
- **Caching**: Redis reduces API calls and improves performance
- **Idempotency**: Safe to retry failed operations

## Google Quota Dependency

This service requires Google Business Profile API quota approval. Without it:
- Accounts API returns 403
- Locations API returns 403
- Reviews API returns 403

Once quota is approved, the service works immediately.

## Error Handling

- **401/403**: Invalid or expired tokens
- **429**: Quota exceeded (retries with backoff)
- **Network Errors**: Automatic retries
- **Kafka Failures**: Logged and retried

## Observability

- Structured logging with request correlation
- Health check endpoint: `GET /health`
- Database audit trails
- Kafka delivery confirmation

## Deployment

1. Build Docker image
2. Configure environment variables
3. Deploy to container orchestration (Kubernetes, etc.)
4. Ensure dependencies (DB, Redis, Kafka) are available

## Future Enhancements

- Mock mode for testing
- Celery for advanced background processing
- Metrics and monitoring
- Token refresh handling
- Batch processing optimizations