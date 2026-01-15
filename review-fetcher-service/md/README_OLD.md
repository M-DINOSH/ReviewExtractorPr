# Review Fetcher Microservice

> NOTE: This is a historical/legacy document. Some details may be outdated.
> For current usage, see `review-fetcher-service/README.md`, `review-fetcher-service/run.md`, and `review-fetcher-service/flow.md`.

Production-ready microservice for fetching reviews from Google Business Profile API using event-driven Kafka architecture.

## What This Service Does

The Review Fetcher is an **async, event-driven microservice** that:
1. **Accepts fetch requests** via HTTP API (`POST /api/v1/review-fetch`)
2. **Queues jobs** in a bounded in-memory buffer (prevents overload)
3. **Publishes events** to Kafka topics at rate-limited intervals
4. **Processes events** through three worker stages (Accounts → Locations → Reviews)
5. **Applies intelligent rate limiting** to respect Google API quotas
6. **Retries failed requests** with exponential backoff
7. **Outputs clean reviews data** to `reviews-raw` Kafka topic

## Architecture Overview

```
┌─────────────────────────────────────┐
│  FastAPI HTTP API                   │
│  POST /api/v1/review-fetch          │ ← Clients submit fetch jobs
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Bounded Deque Buffer (Max 10K)     │ ← Accepts up to 10,000 jobs
│  Returns 429 Too Many Requests      │   if full, refuses new ones
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Producer Loop (Every 100ms)        │ ← Batches jobs and publishes
│  Rate-limited Kafka publishing      │   to Kafka topics
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────────┬──────────────┐
    │          │              │              │
    ▼          ▼              ▼              ▼
[fetch-accounts] [fetch-locations] [fetch-reviews] [reviews-dlq]
    │              │                 │              (Dead Letter)
    ▼              ▼                 ▼
┌─────────┐  ┌──────────┐  ┌────────────────┐
│ Account │  │ Location │  │ Review Worker  │
│ Worker  │  │ Worker   │  │ (Deduplicates)│
└────┬────┘  └────┬─────┘  └────────┬───────┘
     │            │                 │
     └────────────┴─────────────────┘
                  │
                  ▼
         [reviews-raw topic]
         (Output for downstream systems)
```

## Quick Start

### Prerequisites
- **Docker & Docker Compose** installed
- **Python 3.11+** (for local development)

### Build & Run with Docker

```bash
cd review-fetcher-service

# Development mode (mock data, no real Kafka needed)
docker compose --profile dev up --build

# Service will be available at: http://localhost:8084
```

**What happens:**
- Service starts on port 8084
- Mock Kafka is enabled (no real broker needed)
- Mock Google API is enabled (fake review data)
- All background workers start automatically
- You can immediately test the API

### First API Call

```bash
# Submit a fetch job
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.test_token",
    "account_id": "123456"
  }'

# Response:
# {
#   "job_id": "abc123",
#   "status": "queued",
#   "created_at": "2025-01-07T12:34:56Z"
# }
```

### Check Service Health

```bash
curl http://localhost:8084/health

# Response:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "timestamp": "2025-01-07T12:34:56Z"
# }
```

## API Reference

### 1. Submit Fetch Job

**Endpoint:** `POST /api/v1/review-fetch`

**Purpose:** Queue a new review fetch job

**Request:**
```json
{
  "access_token": "ya29.xxxxx",
  "account_id": "123456"
}
```

**Parameters:**
- `access_token` (string, required): Google OAuth token (starts with `ya29`)
- `account_id` (string, required): Google Business Profile account ID

**Response (Success - 200):**
```json
{
  "job_id": "abc123def456",
  "status": "queued",
  "message": "Fetch job created",
  "created_at": "2025-01-07T12:34:56Z"
}
```

**Response (Queue Full - 429):**
```json
{
  "detail": "Job queue is full, try again later"
}
```

---

### 2. Health Check

**Endpoint:** `GET /health`

**Purpose:** Check if service is running and healthy

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-07T12:34:56Z"
}
```

---

### 3. Get Metrics

**Endpoint:** `GET /metrics`

**Purpose:** View queue stats and worker metrics

**Response:**
```json
{
  "queue": {
    "size": 5,
    "max_size": 10000,
    "usage_percent": 0.05
  },
  "workers": {
    "account_worker": {
      "processed": 42,
      "failed": 2,
      "status": "running"
    },
    "location_worker": {
      "processed": 38,
      "failed": 1,
      "status": "running"
    },
    "review_worker": {
      "processed": 35,
      "failed": 0,
      "status": "running"
    }
  }
}
```

---

### 4. API Documentation

**Endpoint:** `GET /docs`

**Purpose:** Interactive Swagger UI for testing all endpoints

**Access:** http://localhost:8084/docs

## Configuration

### Environment Variables

Set these in `docker-compose.yml` to customize behavior:

| Variable | Default | Purpose | Example |
|----------|---------|---------|---------|
| `LOG_LEVEL` | `INFO` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MOCK_GOOGLE_API` | `true` | Use fake data for testing | `true` or `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address | `kafka:9092` or `kafka1:9092,kafka2:9092` |

### Rate Limiting Config

In `app/config.py`:
```python
token_bucket_capacity = 100      # Max burst tokens
refill_rate = 10.0               # 10 tokens/second
```

**What this means:**
- Each worker can **burst 100 requests** at once
- Then refills at **10 requests/second**
- Google API limit: **10 req/sec**, so this is safe

### Retry Config

In `app/config.py`:
```python
max_retries = 3                  # Try 3 times max
initial_backoff_ms = 100         # Start with 100ms wait
max_backoff_ms = 10000           # Cap at 10 seconds
backoff_multiplier = 2.0         # Double wait time each retry
```

**Retry schedule for a failed request:**
1. Immediate failure
2. Wait 100ms → Retry
3. Wait 200ms → Retry
4. Wait 400ms → Retry
5. Fail permanently → Dead Letter Queue

### Queue Config

In `app/config.py`:
```python
max_size = 10000                 # Max jobs in memory
burst_check_interval_sec = 0.1   # Check queue every 100ms
```

## Project Structure

```
review-fetcher-service/
├── app/
│   ├── main.py                    # FastAPI app + background tasks
│   ├── api.py                     # HTTP endpoints
│   ├── config.py                  # Settings management
│   ├── models.py                  # Data models (Pydantic)
│   ├── deque_buffer.py            # In-memory job queue
│   ├── kafka_producer.py          # Kafka producer + mock impl
│   ├── rate_limiter.py            # Token bucket rate limiter
│   ├── retry.py                   # Exponential backoff retry
│   ├── observers/                 # Event observers (lifecycle)
│   ├── kafka_consumers/           # Kafka consumer workers
│   │   ├── base.py                # Base consumer + mock impl
│   │   ├── account_worker.py      # Fetch accounts worker
│   │   ├── location_worker.py     # Fetch locations worker
│   │   └── review_worker.py       # Fetch reviews + dedup worker
│   └── services/
│       └── google_api.py          # Google Business Profile API client
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Key Features Explained

### 1. **Request Buffering** (Deque Buffer)
- Accepts up to **10,000 concurrent fetch jobs** in memory
- Uses **FIFO (First-In-First-Out)** queuing
- Returns **HTTP 429** if buffer is full (prevents memory exhaustion)
- Fast enqueue/dequeue with O(1) operations

### 2. **Rate Limiting** (Token Bucket Algorithm)
- **Per-worker rate limiting** (separate limits for accounts, locations, reviews)
- **Respects Google API quotas**: 10 requests/second, 1000/day
- **Smooth traffic** with burst tolerance (100 token capacity)
- Prevents overwhelming downstream Google APIs

### 3. **Retry Logic** (Exponential Backoff)
- **Max 3 retries** per failed request
- **Backoff schedule**: 100ms → 200ms → 400ms (doubles each time)
- **Prevents cascading failures** by spacing retries out
- **Dead Letter Queue** for permanently failed jobs

### 4. **Event-Driven Processing** (Kafka Workers)
Three worker stages process reviews in parallel:

| Worker | Input Topic | Task | Output Topic |
|--------|------------|------|--------------|
| **Account Worker** | `fetch-accounts` | Retrieves business accounts | `fetch-locations` |
| **Location Worker** | `fetch-locations` | Lists locations per account | `fetch-reviews` |
| **Review Worker** | `fetch-reviews` | Fetches reviews + deduplicates | `reviews-raw` |

### 5. **Deduplication** (Review Worker)
- Tracks **already-seen reviews** per job using review IDs
- Prevents **duplicate reviews** in output
- Maintains **in-memory cache** of seen review hashes
- Clears cache when job completes

### 6. **Pagination** (Review Worker)
- Handles **large review datasets** by fetching in pages
- Prevents **timeout issues** with large accounts
- **100 reviews per page** by default

## Production Setup

### Enable Real Google API & Kafka

**Step 1: Get Google OAuth Token**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project with **Business Profile API** enabled
3. Create OAuth 2.0 credentials (Service Account or Web)
4. Copy the access token (starts with `ya29`)

**Step 2: Setup Kafka Broker**
- Deploy Kafka cluster (e.g., on AWS MSK, Confluent Cloud, or self-hosted)
- Get broker address: `kafka-broker:9092`

**Step 3: Update Configuration**

Edit `docker-compose.yml`:
```yaml
environment:
  LOG_LEVEL: "INFO"                           # Change to WARNING in prod
  MOCK_GOOGLE_API: "false"                    # Enable real API
  KAFKA_BOOTSTRAP_SERVERS: "kafka-broker:9092"  # Your Kafka broker
```

**Step 4: Start Service**
```bash
docker compose --profile dev up
```

**Step 5: Monitor & Test**
```bash
# Check health
curl http://localhost:8084/health

# Submit a real fetch job
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.your_real_token",
    "account_id": "your_account_id"
  }'

# View metrics
curl http://localhost:8084/metrics | python -m json.tool
```

### Production Best Practices

1. **Use environment variables** - Never hardcode secrets
2. **Set LOG_LEVEL to WARNING** - Reduce log noise in production
3. **Monitor Kafka topics** - Check for messages in `reviews-raw`
4. **Setup alerting** - Alert on queue size > 8000
5. **Use load balancer** - Distribute requests across instances
6. **Enable persistence** - Use external database for job state (future enhancement)
7. **SSL/TLS** - Use HTTPS in production
8. **Rate limit clients** - Prevent abuse at API gateway level

## Development

### Local Setup (Without Docker)

```bash
# 1. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run service locally
PYTHONPATH=. python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Flags:**
- `--reload`: Auto-restart on code changes
- `--host 0.0.0.0`: Listen on all interfaces
- `--port 8000`: Use port 8000

### Testing Locally

```bash
# 1. Start service (from above)
PYTHONPATH=. python -m uvicorn app.main:app --reload

# 2. In another terminal, test it
curl -X POST http://localhost:8000/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "ya29.test", "account_id": "123"}'

# 3. Check health
curl http://localhost:8000/health

# 4. View API docs
open http://localhost:8000/docs
```

### Code Quality Checks

```bash
# Verify Python syntax
python -m py_compile app/*.py app/**/*.py

# Run type checking (optional - requires mypy)
mypy app/
```

## Dependencies

### Core Technologies
- **FastAPI** - Web framework for REST API
- **uvicorn** - ASGI server (runs the app)
- **aiokafka** - Async Kafka client for event streaming
- **pydantic** - Data validation and serialization
- **httpx** - Async HTTP client for Google API calls
- **structlog** - Structured JSON logging
- **tenacity** - Retry library with exponential backoff

See `requirements.txt` for versions.

## Troubleshooting

### "Queue is full" (429 error)

**Problem:** Getting `Job queue is full, try again later`

**Causes:**
1. Workers are processing too slowly
2. Google API is rate limiting or down
3. Kafka broker is not responding

**Solutions:**
1. Increase queue size in `app/config.py`: `max_size = 20000`
2. Check worker logs: `docker logs review-fetcher` (if Docker)
3. Verify Kafka is running: `curl kafka-broker:9092` (should fail but respond)
4. Wait a few seconds and retry

---

### "Token validation failed" (401 error)

**Problem:** Token is invalid or expired

**Causes:**
1. Token doesn't start with `ya29`
2. Token is expired (OAuth tokens expire after 1 hour)
3. Service account doesn't have Business Profile API access

**Solutions:**
1. Generate a fresh OAuth token from Google Cloud Console
2. Verify Business Profile API is enabled in your project
3. Grant service account the `businessprofile.viewer` role

---

### "Worker not processing messages"

**Problem:** Jobs are queued but not being fetched

**Causes:**
1. Kafka is not running (in production mode)
2. Worker crashed silently
3. Rate limiter is throttling (no tokens available)

**Solutions:**
1. Check Kafka status: `docker ps` (if using Docker)
2. View logs: `docker logs review-fetcher`
3. Check metrics endpoint: `curl http://localhost:8084/metrics`
4. Restart service: `docker compose restart` (if Docker)

---

### "High memory usage"

**Problem:** Service is using lots of RAM

**Causes:**
1. Queue is full of unprocessed jobs
2. Review worker dedup cache is too large
3. Memory leak in worker

**Solutions:**
1. Check queue size: `curl http://localhost:8084/metrics` → `queue.size`
2. Reduce `max_size` in config if it's too large
3. Restart service to clear in-memory caches
4. Check Google API quotas (may be hitting rate limits)
