# Review Fetcher Microservice

**Production-ready, event-driven microservice for fetching Google Business Profile reviews with intelligent rate limiting and retry mechanisms.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org)
[![Kafka](https://img.shields.io/badge/Kafka-Event--Driven-black.svg)](https://kafka.apache.org)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Development Modes](#development-modes)
- [Project Structure](#project-structure)
- [Design Patterns](#design-patterns)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

The Review Fetcher is an **async, event-driven microservice** that orchestrates the retrieval of Google Business Profile reviews through a multi-stage pipeline:

1. **Accepts fetch requests** via HTTP API (`POST /api/v1/review-fetch`)
2. **Queues jobs** in a bounded in-memory buffer (prevents overload)
3. **Publishes events** to Kafka topics at rate-limited intervals
4. **Processes events** through three worker stages (Accounts → Locations → Reviews)
5. **Applies intelligent rate limiting** to respect Google API quotas
6. **Retries failed requests** with exponential backoff
7. **Outputs clean reviews data** to `reviews-raw` Kafka topic

### Why This Service?

- **Async Processing**: Non-blocking architecture prevents API overload
- **Rate Limiting**: Token bucket algorithm respects Google API quotas (10 req/sec)
- **Fault Tolerance**: Exponential backoff retry with Dead Letter Queue (DLQ)
- **Scalability**: Kafka-based event streaming for horizontal scaling
- **Production-Ready**: Health checks, metrics, structured logging

---

## ✨ Features

### Core Capabilities

- ✅ **Google Business Profile API Integration**
  - Fetch accounts, locations, and reviews
  - OAuth 2.0 token validation
  - Automatic pagination handling

- ✅ **Event-Driven Architecture**
  - Kafka topics for async processing
  - Three-stage pipeline (Accounts → Locations → Reviews)
  - Event deduplication

- ✅ **Rate Limiting & Throttling**
  - Token bucket algorithm per worker
  - Configurable capacity and refill rates
  - Prevents API quota exhaustion

- ✅ **Fault Tolerance**
  - Exponential backoff retry (3 attempts)
  - Dead Letter Queue for failed messages
  - Graceful degradation

- ✅ **Operational Excellence**
  - Health check endpoint (`/api/v1/health`)
  - Metrics endpoint (`/api/v1/metrics`)
  - Structured JSON logging
  - CORS support

### Developer Experience

- 🔧 **Mock Mode**: Test without real Google API/Kafka
- 📊 **Auto-generated API Docs**: Interactive Swagger UI at `/docs`
- 🐳 **Docker Support**: Containerized deployment ready
- 🔄 **Hot Reload**: Auto-reload during development

---

## 🏗️ Architecture

### System Architecture

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
│ Worker  │  │ Worker   │  │ (Deduplicates) │
└────┬────┘  └────┬─────┘  └────────┬───────┘
     │            │                 │
     └────────────┴─────────────────┘
                  │
                  ▼
         [reviews-raw topic] → External consumers
```

### Data Flow

1. **Client Request** → API receives OAuth token
2. **Validation** → Token validated (mock or real Google API)
3. **Enqueue** → Job added to bounded deque (or 429 if full)
4. **Producer Loop** → Drains deque every 100ms, publishes to `fetch-accounts`
5. **Account Worker** → Fetches accounts, publishes to `fetch-locations`
6. **Location Worker** → Fetches locations, publishes to `fetch-reviews`
7. **Review Worker** → Fetches reviews (paginated), deduplicates, publishes to `reviews-raw`
8. **Retry Scheduler** → Failed messages retried with exponential backoff
9. **Dead Letter Queue** → Permanently failed messages sent to DLQ

### Kafka Topics

| Topic | Purpose | Producer | Consumer |
|-------|---------|----------|----------|
| `fetch-accounts` | Initiate account fetching | API Producer Loop | Account Worker |
| `fetch-locations` | Fetch locations for account | Account Worker | Location Worker |
| `fetch-reviews` | Fetch reviews for location | Location Worker | Review Worker |
| `reviews-raw` | Final output: clean reviews | Review Worker | External Services |
| `reviews-dlq` | Failed messages | All Workers | Monitoring/Alerts |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.13+ (Python 3.10+ compatible)
- pip (Python package manager)
- (Optional) Kafka 3.0+ for production mode
- (Optional) Docker for containerized deployment

### Quick Start (Mock Mode)

**1. Clone the repository**
```bash
git clone <repository-url>
cd review-fetcher-service
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Run the service**
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**4. Verify it's running**
```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "review-fetcher-service",
  "version": "1.0.0",
  "kafka_connected": true,
  "memory_used_percent": 0.0,
  "timestamp": "2026-01-09T13:10:49.197459"
}
```

**5. Test the API**
```bash
curl -X POST http://localhost:8000/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "ya29.test_token_12345678901234567890"}'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

**6. View fetched reviews (Mock Mode)**
```bash
curl http://localhost:8000/api/v1/reviews
```

---

## 📚 API Documentation

### Base URL
```
http://localhost:8000
```

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### 1. Create Fetch Job
```http
POST /api/v1/review-fetch
Content-Type: application/json

{
  "access_token": "ya29.your_google_oauth_token"
}
```

**Responses:**
- `202 Accepted`: Job queued successfully
- `401 Unauthorized`: Invalid access token
- `429 Too Many Requests`: Service at capacity (retry after delay)
- `422 Unprocessable Entity`: Invalid request body

**Success Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

#### 2. Check Job Status
```http
GET /api/v1/status/{job_id}
```

**Response:**
```json
{
  "status": "queued",
  "created_at": "2026-01-09T10:30:00.000000",
  "access_token": "ya29.***"
}
```

#### 3. Health Check
```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "review-fetcher-service",
  "version": "1.0.0",
  "kafka_connected": true,
  "memory_used_percent": 23.5,
  "timestamp": "2026-01-09T10:30:00.000000"
}
```

#### 4. Get Metrics
```http
GET /api/v1/metrics
```

**Response:**
```json
{
  "deque": {
    "current_size": 45,
    "max_size": 10000,
    "enqueued": 150,
    "dequeued": 105,
    "rejected": 0,
    "max_size_hit": 0,
    "load_percent": 0.45
  },
  "jobs_tracked": 15,
  "timestamp": "2026-01-09T10:30:00.000000"
}
```

#### 5. Get Reviews (Mock Mode Only)
```http
GET /api/v1/reviews
```

**Response:**
```json
{
  "topic": "reviews-raw",
  "total_reviews": 42,
  "reviews": [
    {
      "type": "review_raw",
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "review_id": "review_001",
      "location_id": "loc_123",
      "account_id": "acc_456",
      "rating": 5,
      "text": "Great service!",
      "reviewer_name": "John Doe",
      "timestamp": "2026-01-09T10:30:00.000000"
    }
  ],
  "timestamp": "2026-01-09T10:30:00.000000"
}
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Mode Configuration
MOCK_GOOGLE_API=false           # true = mock mode, false = real Google API
ENVIRONMENT=production          # development, staging, production
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP=review-fetcher-service

# Google API Rate Limiting
GOOGLE_REQUESTS_PER_SECOND=10   # Google API quota
GOOGLE_DAILY_QUOTA=1000

# Rate Limiting (Token Bucket)
RATELIMIT_TOKEN_BUCKET_CAPACITY=100
RATELIMIT_REFILL_RATE=10.0      # Tokens per second

# Retry Configuration
RETRY_MAX_RETRIES=3
RETRY_INITIAL_BACKOFF_MS=100
RETRY_MAX_BACKOFF_MS=10000
RETRY_BACKOFF_MULTIPLIER=2.0

# Deque Buffer Configuration
DEQUE_MAX_SIZE=10000
DEQUE_BURST_CHECK_INTERVAL_SEC=0.1
```

### Configuration Classes

The service uses Pydantic Settings for type-safe configuration:

- **KafkaConfig**: Kafka connection and consumer settings
- **GoogleAPIConfig**: Google API rate limits and quotas
- **RateLimitConfig**: Token bucket parameters
- **RetryConfig**: Exponential backoff settings
- **DequeConfig**: In-memory buffer settings

---

## 🔧 Development Modes

### Mock Mode (Development)

**Use Case**: Local development without Google API or Kafka

**Setup:**
```bash
export MOCK_GOOGLE_API=true
python3 -m uvicorn app.main:app --reload
```

**Features:**
- Generates fake accounts, locations, and reviews
- Uses in-memory mock Kafka (no broker needed)
- Instant response (no actual API calls)
- View results at `/api/v1/reviews`

### Google API Mode (Production)

**Use Case**: Fetch real data from Google Business Profile API

**Prerequisites:**
1. Google OAuth 2.0 access token with Business Profile API scope
2. Token must start with `ya29`

**Setup:**
```bash
export MOCK_GOOGLE_API=false
python3 -m uvicorn app.main:app --reload
```

**Required Scopes:**
```
https://www.googleapis.com/auth/business.manage
```

**Get OAuth Token:**
```bash
# Use Google OAuth 2.0 Playground or your own OAuth flow
# https://developers.google.com/oauthplayground/
```

**Test:**
```bash
curl -X POST http://localhost:8000/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "ya29.a0AfH6SMBxxxxxxxxx"}'
```

---

## 📁 Project Structure

```
review-fetcher-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifecycle management
│   ├── api.py                  # API routes and service logic
│   ├── config.py               # Configuration management
│   ├── models.py               # Pydantic data models
│   ├── deque_buffer.py         # Bounded deque for job queuing
│   ├── rate_limiter.py         # Token bucket rate limiter
│   ├── retry.py                # Retry scheduler with backoff
│   ├── kafka_producer.py       # Kafka producer abstraction
│   │
│   ├── kafka_consumers/        # Kafka consumer workers
│   │   ├── base.py             # Base consumer class
│   │   ├── account_worker.py   # Fetches Google accounts
│   │   ├── location_worker.py  # Fetches locations per account
│   │   └── review_worker.py    # Fetches reviews per location
│   │
│   ├── services/               # External service integrations
│   │   └── google_api.py       # Google Business Profile API client
│   │
│   └── observers/              # Observer pattern implementations
│       └── __init__.py
│
├── requirements.txt            # Python dependencies
├── .env                        # Environment configuration
├── .env.example                # Example environment file
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Multi-container setup
└── README.md                   # This file
```

---

## 🎨 Design Patterns

The service implements several **Software Design Patterns** for maintainability and scalability:

### 1. **Dependency Injection**
- `APIService` receives dependencies via constructor
- `get_api_service()` FastAPI dependency
- Enables easy testing and swapping implementations

### 2. **Factory Pattern**
- `KafkaProducerFactory.create()` - Creates mock or real producer
- `create_app()` - FastAPI application factory

### 3. **Strategy Pattern**
- `RateLimiter` abstract base class
- `TokenBucketLimiter` concrete implementation
- Easy to add new rate limiting algorithms

### 4. **Observer Pattern**
- Kafka consumers observe topic events
- Workers react to messages independently

### 5. **Service Locator**
- `AppState` container for global services
- `get_app_state()` accessor function

### 6. **Adapter Pattern**
- `BoundedDequeBuffer` wraps `collections.deque`
- Provides async interface and metrics

### 7. **Repository Pattern**
- `GoogleAPIClient` abstracts Google API calls
- Clean separation between business logic and external API

---

## 📊 Monitoring

### Health Checks

**Kubernetes Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

**Kubernetes Readiness Probe:**
```yaml
readinessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

### Metrics Collection

The `/api/v1/metrics` endpoint provides:
- Deque buffer statistics (size, throughput, rejections)
- Job tracking count
- Rate limiter status
- Timestamp for monitoring staleness

**Prometheus Integration Example:**
```python
# Future enhancement: Export Prometheus metrics
from prometheus_client import Counter, Gauge

jobs_enqueued = Counter('jobs_enqueued_total', 'Total jobs enqueued')
deque_size = Gauge('deque_current_size', 'Current deque size')
```

### Structured Logging

All logs are in structured JSON format for easy parsing:

```json
{
  "event": "job_created",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-09T10:30:00.000000",
  "level": "info"
}
```

**Log Levels:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages (e.g., rate limit hit)
- `ERROR`: Error messages (e.g., API call failed)

---

## 🔍 Troubleshooting

### Common Issues

#### 1. **Port Already in Use**
```bash
Error: [Errno 48] Address already in use
```
**Solution:**
```bash
lsof -ti:8000 | xargs kill -9
```

#### 2. **Module Not Found: 'app'**
```bash
ModuleNotFoundError: No module named 'app'
```
**Solution:**
```bash
# Ensure you're in the correct directory
cd review-fetcher-service
python3 -m uvicorn app.main:app
```

#### 3. **422 Unprocessable Entity**
```json
{"detail": [{"msg": "field required", "type": "value_error.missing"}]}
```
**Solution:**
Ensure your request body includes `access_token`:
```json
{"access_token": "ya29.your_token_here"}
```
Token must be at least 10 characters.

#### 4. **401 Unauthorized (Google API Mode)**
```json
{"detail": "Invalid access token"}
```
**Solution:**
- Verify token starts with `ya29`
- Check token has not expired
- Ensure token has Business Profile API scope

#### 5. **429 Too Many Requests**
```json
{"detail": "Service is at capacity. Please retry after a few seconds."}
```
**Solution:**
- Wait and retry (exponential backoff recommended)
- The deque buffer is full (10,000 jobs)
- Check `/api/v1/metrics` for buffer status

#### 6. **Kafka Connection Failed (Production Mode)**
```bash
ERROR: kafka_connection_failed
```
**Solution:**
```bash
# Verify Kafka is running
docker ps | grep kafka

# Check bootstrap servers in .env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

---

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t review-fetcher-service:latest .
```

### Run Container (Mock Mode)
```bash
docker run -p 8000:8000 \
  -e MOCK_GOOGLE_API=true \
  review-fetcher-service:latest
```

### Run with Docker Compose
```bash
docker-compose up -d
```

**docker-compose.yml** includes:
- Review Fetcher Service
- Kafka
- Zookeeper

---

## 🧪 Testing

### Manual Testing with cURL

**Create Job:**
```bash
curl -X POST http://localhost:8000/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "ya29.test_token_1234567890"}'
```

**Check Status:**
```bash
curl http://localhost:8000/api/v1/status/{job_id}
```

**View Reviews (Mock Mode):**
```bash
curl http://localhost:8000/api/v1/reviews
```

### Load Testing

```bash
# Install wrk
brew install wrk

# Run load test
wrk -t4 -c100 -d30s \
  -s post.lua \
  http://localhost:8000/api/v1/review-fetch
```

---

## 📝 License

[Your License Here]

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📧 Support

For issues and questions:
- Create an issue in the repository
- Contact: [your-email@example.com]

---

## 🔄 Version History

- **1.0.0** (2026-01-09)
  - Initial production release
  - Mock mode and Google API mode
  - Three-stage pipeline (Accounts → Locations → Reviews)
  - Rate limiting and retry logic
  - Health checks and metrics

---

**Built with ❤️ using FastAPI, Kafka, and Python**
