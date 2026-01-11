# Review Fetcher Service - Complete Explanation

## 🎯 **What is the Review Fetcher Service?**

The **Review Fetcher Service** is a sophisticated, production-ready **event-driven microservice** designed to fetch Google Business Profile reviews at scale using Kafka and OAuth authentication. It implements advanced software architecture patterns (SOLID principles, design patterns) with parallel processing, rate limiting, and comprehensive error handling.

**Core Purpose**: Fetch, validate, store, and stream Google Business Profile reviews with enterprise-grade reliability, scalability, and observability using event-driven architecture.

---

## 🏗️ **Architecture Overview**

### **High-Level Event-Driven Architecture**
```
                    ┌──────────────────────┐
                    │   Review Fetcher API │
                    │  (Initial Trigger)   │
                    └──────────┬───────────┘
                               │ POST /api/v1/review-fetch
                               ▼
                    ┌──────────────────────┐
                    │  Kafka Topic:        │
                    │ fetch-accounts       │
                    └──────────┬───────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │Account      │ │Location     │ │Review       │
        │Worker       │ │Worker       │ │Worker       │
        │(Kafka Cons) │ │(Kafka Cons) │ │(Kafka Cons) │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               ▼               ▼               ▼
        ┌──────────────────────────────────────┐
        │  PostgreSQL Database                 │
        │  (Accounts, Locations, Reviews)      │
        └──────────────────────────────────────┘
               │
               ▼
        ┌──────────────────────────────┐
        │  Kafka Topic:                │
        │ sentiment-reviews            │
        │ (for downstream services)    │
        └──────────────────────────────┘
```

### **Detailed Component Interaction**
```
┌─────────────────────────────────────────────────────────────┐
│           Review Fetcher Service (Event-Driven)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                           │
│  │ API Endpoint │ ──► POST /api/v1/review-fetch            │
│  │  (FastAPI)   │     Creates SyncJob + publishes to Kafka │
│  └──────┬───────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │       Kafka Consumer Workers (Async)                │  │
│  │  ┌────────────────┐  ┌────────────────┐ ┌─────────┐ │  │
│  │  │ AccountWorker  │  │ LocationWorker │ │ReviewWorker
│  │  │ • Validates    │  │ • Fetches locs │ │• Fetches  │ │  │
│  │  │   token        │  │ • Publishes    │ │  reviews  │ │  │
│  │  │ • Fetches accs │  │   fetch-revs   │ │• Publishes│ │  │
│  │  │ • Publishes    │  │                │ │  to topic │ │  │
│  │  │   fetch-locs   │  │                │ │           │ │  │
│  │  └────────────────┘  └────────────────┘ └─────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                    │                    │         │
│         ▼                    ▼                    ▼         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      PostgreSQL Database (Persistent Storage)       │  │
│  │  • SyncJob (tracks fetch operations)                │  │
│  │  • Account (Google business accounts)              │  │
│  │  • Location (business locations)                   │  │
│  │  • Review (customer reviews)                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    Infrastructure Components                        │  │
│  │  ┌────────────────┐  ┌────────────────┐ ┌─────────┐ │  │
│  │  │ Deque Buffer   │  │ Rate Limiter   │ │Kafka    │ │  │
│  │  │ (Queue Mgmt)   │  │ (Token Bucket) │ │Producer │ │  │
│  │  │ • Bounds burst │  │ • Rate control │ │         │ │  │
│  │  │ • Fair sched   │  │ • API quota    │ │         │ │  │
│  │  └────────────────┘  └────────────────┘ └─────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
│  │  • Account (Google business accounts)              │  │
│  │  • Location (business locations)                   │  │
│  │  • Review (customer reviews)                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    Infrastructure Components                        │  │
│  │  ┌────────────────┐  ┌────────────────┐ ┌─────────┐ │  │
│  │  │ Deque Buffer   │  │ Rate Limiter   │ │Kafka    │ │  │
│  │  │ (Queue Mgmt)   │  │ (Token Bucket) │ │Producer │ │  │
│  │  │ • Bounds burst │  │ • Rate control │ │         │ │  │
│  │  │ • Fair sched   │  │ • API quota    │ │         │ │  │
│  │  └────────────────┘  └────────────────┘ └─────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 **Complete Project Structure**

### **Root Directory**
```
ReviewExtractorPr/
├── review-fetcher-service/        # ⭐ Main event-driven microservice
├── separation-service/            # Separate service (not covered here)
├── ARCHITECTURE.md                # Detailed architecture documentation
├── README.md                      # Problem statement & overview
├── QUICKSTART.md                  # Getting started guide
├── explanation.md                 # This file - system explanation
└── REBUILD_SUMMARY.md             # Recent rebuild information
```

### **Application Directory Structure**
```
# Review Fetcher Service - Clear, Service-Only Explanation

## 🎯 Overview

The Review Fetcher Service is an event-driven FastAPI microservice that fetches Google Business Profile reviews at scale. It exposes a minimal API to enqueue fetch jobs and processes them asynchronously through Kafka consumer workers, with built-in burst handling, rate limiting, retries, and DLQ.

- Purpose: Fetch, validate, and stream Google reviews reliably and at scale.
- Style: Async, event-driven, SOLID-aligned components.
- Core outputs: Reviews published to Kafka (`reviews-raw`) and failure messages to `reviews-dlq`.

---

## 🏗️ Architecture

### High-Level Event Flow
```
Client → POST /api/v1/review-fetch → Deque buffer → Kafka: fetch-accounts
        → AccountWorker → Kafka: fetch-locations
                → LocationWorker → Kafka: fetch-reviews
                        → ReviewWorker → Kafka: reviews-raw (one per review)

Errors at any stage → Kafka: reviews-dlq
```

### Components (Where to Look)
- API: [review-fetcher-service/app/api.py](review-fetcher-service/app/api.py)
- App startup + wiring: [review-fetcher-service/app/main.py](review-fetcher-service/app/main.py)
- Models (Pydantic DTOs): [review-fetcher-service/app/models.py](review-fetcher-service/app/models.py)
- Kafka producer: [review-fetcher-service/app/kafka_producer.py](review-fetcher-service/app/kafka_producer.py)
- Kafka consumers:
    - Accounts: [review-fetcher-service/app/kafka_consumers/account_worker.py](review-fetcher-service/app/kafka_consumers/account_worker.py)
    - Locations: [review-fetcher-service/app/kafka_consumers/location_worker.py](review-fetcher-service/app/kafka_consumers/location_worker.py)
    - Reviews: [review-fetcher-service/app/kafka_consumers/review_worker.py](review-fetcher-service/app/kafka_consumers/review_worker.py)
- Burst handling: [review-fetcher-service/app/deque_buffer.py](review-fetcher-service/app/deque_buffer.py)
- Rate limiting: [review-fetcher-service/app/rate_limiter.py](review-fetcher-service/app/rate_limiter.py)
- Retries: [review-fetcher-service/app/retry.py](review-fetcher-service/app/retry.py)
- Config: [review-fetcher-service/app/config.py](review-fetcher-service/app/config.py)

---

## 🔄 End-to-End Flow

1) Client calls POST /api/v1/review-fetch with an OAuth access token.
- API validates token (mock in dev), enqueues a job in deque, returns `job_id`.
- Background producer drains the deque and publishes `fetch-accounts` with `job_id`.

2) AccountWorker consumes `fetch-accounts`.
- Rate limit check → calls Google accounts (mocked) → publishes `fetch-locations` per account.

3) LocationWorker consumes `fetch-locations`.
- Rate limit check → calls Google locations (mocked) → publishes `fetch-reviews` per location.

4) ReviewWorker consumes `fetch-reviews`.
- Rate limit check → paginated fetch (mocked) → deduplicate review IDs → publishes each to `reviews-raw`.

5) Failures anywhere → DLQ.
- Errors are published to `reviews-dlq` with original payload and error details.

---

## 📡 API Surface

- POST /api/v1/review-fetch
    - Body: `{ "access_token": "ya29..." }`
    - Returns: `{ "job_id": "uuid", "status": "queued", "message": "Job enqueued for processing" }`

- GET /api/v1/status/{job_id}
    - Returns in-memory job state: `queued | processing | completed | failed` and counters (if available).

- GET /api/v1/health
    - Returns health and basic load (deque utilization, version, service name).

---

## 🧵 Kafka Topics

- fetch-accounts: initial topic to fan-out accounts
- fetch-locations: per-account fan-out to locations
- fetch-reviews: per-location fan-out to reviews
- reviews-raw: one message per review (downstream consumers can subscribe)
- reviews-dlq: dead-letter queue for failures

---

## 🧩 Key Design Choices

- Deque buffer (bounded): absorbs bursts, prevents memory blow-up.
- Token bucket limiter: protects Google API quotas; smooths traffic.
- Exponential backoff retries: only for transient errors; DLQ for permanent.
- Idempotent publish: keys (`job_id`, `job_id_location`, `review_id`) used for partitioning/dedup hints.
- Worker-per-stage: each worker has a single responsibility and can scale independently.

---

## 🗃️ Data Models (DTOs)

Defined in [review-fetcher-service/app/models.py](review-fetcher-service/app/models.py):
- `ReviewFetchRequest` → POST body with `access_token` validation
- `ReviewFetchResponse` → `job_id`, `status`, `message`
- `FetchAccountsEvent`, `FetchLocationsEvent`, `FetchReviewsEvent` → internal Kafka event shapes
- `Review` → emitted to `reviews-raw` (job_id, review_id, location_id, account_id, rating, text, reviewer_name)
- `DLQMessage` → stored in `reviews-dlq` with original message + error
- `HealthCheckResponse` → API health payload

---

## ⚙️ Configuration

See [review-fetcher-service/app/config.py](review-fetcher-service/app/config.py). Key envs:

- Service:
    - `ENVIRONMENT` (default: development)
    - `LOG_LEVEL` (INFO | DEBUG | WARN)

- API:
    - `api_host` (default: 0.0.0.0)
    - `api_port` (default: 8000)

- Kafka (prefix KAFKA_):
    - `KAFKA_BOOTSTRAP_SERVERS` (comma-separated, default: localhost:9092)
    - `KAFKA_CONSUMER_GROUP` (default: review-fetcher-service)

- Rate limiting (prefix RATELIMIT_):
    - `RATELIMIT_TOKEN_BUCKET_CAPACITY` (default: 100)
    - `RATELIMIT_REFILL_RATE` tokens/sec (default: 10)

- Retry (prefix RETRY_):
    - `RETRY_MAX_RETRIES` (default: 3)
    - `RETRY_INITIAL_BACKOFF_MS` (default: 100)
    - `RETRY_MAX_BACKOFF_MS` (default: 10000)
    - `RETRY_BACKOFF_MULTIPLIER` (default: 2.0)

- Deque (prefix DEQUE_):
    - `DEQUE_MAX_SIZE` (default: 10000)
    - `DEQUE_BURST_CHECK_INTERVAL_SEC` (default: 0.1)

- Feature flags:
    - `MOCK_GOOGLE_API` (true/false, default: true for local)
    - `ENABLE_DLQ` (default: true)
    - `ENABLE_IDEMPOTENCY` (default: true)

---

## ▶️ Run Locally (Dev, Mock Mode)

From project root:

```bash
# 1) Create virtualenv and install
cd review-fetcher-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) Start API (uses MOCK_GOOGLE_API=true by default)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3) Test endpoints
curl -X POST http://localhost:8000/api/v1/review-fetch \
    -H "Content-Type: application/json" \
    -d '{"access_token": "ya29.test_token_12345"}'

curl http://localhost:8000/api/v1/health
```

---

## 🐳 Docker (With Kafka)

Minimal compose (service-only excerpt):

```yaml
version: '3.8'
services:
    review-fetcher:
        build: ./review-fetcher-service
        ports:
            - "8000:8000"
        environment:
            KAFKA_BOOTSTRAP_SERVERS: kafka:9092
            MOCK_GOOGLE_API: "true"
        depends_on:
            - kafka
            - zookeeper
    zookeeper:
        image: confluentinc/cp-zookeeper:7.5.0
        environment:
            ZOOKEEPER_CLIENT_PORT: 2181
    kafka:
        image: confluentinc/cp-kafka:7.5.0
        environment:
            KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
            KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
            KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

---

## 📈 Observability

- Structured logging with context (job_id, topic, attempt).
- Health endpoint exposes service status and deque load.
- Metrics hook points present for deque size, rate limiter, and retries (extend as needed).

---

## 🧪 Troubleshooting

- 429 Too Many Requests on POST /review-fetch → Deque full. Reduce rate or increase `DEQUE_MAX_SIZE`.
- No Kafka seen in logs → Ensure `KAFKA_BOOTSTRAP_SERVERS` and broker availability; set `MOCK_GOOGLE_API=true` for offline dev.
- Stuck jobs → Check worker logs; verify rate limiter and retry scheduler activity.
- Duplicate reviews → ReviewWorker uses per-job dedup set; ensure `review_id` is stable.

---

## ✅ Key Takeaways

- Clean event flow with bounded buffering, rate limiting, and retries.
- Independent workers for accounts, locations, and reviews.
- Reviews emitted to `reviews-raw`; failures to `reviews-dlq`.
- Simple API surface to trigger and observe jobs.

Event: fetch-reviews
    ↓
ReviewWorker consumes event
    ├─ Calls Google API: list_reviews(location_id)
    ├─ Stores reviews in PostgreSQL
    ├─ Publishes "sentiment-reviews" events to Kafka
    └─ Marks review fetch complete
```

**Responsibility**: ONLY handles review fetching and publishing review data to downstream services

### **Why This Architecture?**

| Aspect | Benefit |
|--------|---------|
| **Decoupling** | Services don't call each other; they communicate via events |
| **Scalability** | Each worker scales independently based on queue depth |
| **Reliability** | Failed events go to Dead Letter Queue (DLQ), not lost |
| **Observability** | Every event is logged and traceable with correlation IDs |
| **Resilience** | One worker crashing doesn't affect others |
| **Rate Limiting** | Token bucket in `rate_limiter.py` prevents API quota exhaustion |
| **Burst Handling** | Deque buffer in `deque_buffer.py` smooths traffic spikes |

---

## 🔑 **Key Components Deep Dive**

### **1. Main Entry Point (`main.py`)**
```python
# Starts FastAPI application
# Sets up Kafka producer for publishing events
# Initializes workers that subscribe to Kafka topics
# Exposes health check endpoint
# Starts background tasks for worker management
```

### **2. API Handler (`api.py`)**
```python
# POST /api/v1/review-fetch
#   ├─ Accepts access_token and client_id
#   ├─ Creates SyncJob record in database
#   ├─ Publishes fetch-accounts event
#   └─ Returns job_id for status checking

# GET /api/v1/health
#   └─ Returns service health status

# GET /api/v1/metrics
#   └─ Returns operational metrics
```

### **3. Bounded Deque Buffer (`deque_buffer.py`)**

**Problem it solves**: API rate limits and burst handling

**Implementation**:
```python
class BoundedDequeBuffer:
    """
    Thread-safe queue with max_size limit
    - Prevents memory exhaustion from excessive requests
    - Fair scheduling: FIFO ordering
    - Configurable limits for different scenarios
    """
    
    def __init__(self, max_size=1000):
        self.max_size = max_size
        self.queue = deque(maxlen=max_size)
    
    def enqueue(self, item):
        # Oldest items automatically dropped if queue is full
        self.queue.append(item)
    
    def dequeue(self):
        return self.queue.popleft()
```

**SOLID Principle**: Single Responsibility - only manages bounded queue

### **4. Token Bucket Rate Limiter (`rate_limiter.py`)**

**Problem it solves**: Google API quota limits (e.g., 1000 requests/hour)

**Implementation**:
```python
class TokenBucketLimiter:
    """
    Smooth rate limiting without dropping requests
    - Tokens refill at fixed rate (e.g., 10/second)
    - Request gets token from bucket
    - Empty bucket = request waits (not dropped)
    """
    
    def __init__(self, rate=10, capacity=100):
        self.rate = rate          # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
    
    async def acquire(self, count=1):
        # Refill tokens based on elapsed time
        # Wait if not enough tokens
        # Deduct tokens from bucket
```

**SOLID Principle**: Single Responsibility - only handles rate limiting

### **5. Retry Mechanism (`retry.py`)**

**Pattern**: Exponential backoff with Tenacity library

```python
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(APIError)
)
async def fetch_from_google_api():
    # Attempt 1: immediate
    # Attempt 2: wait 2 seconds
    # Attempt 3: wait 4 seconds
    # Attempt 4: wait 8 seconds
    # Attempt 5: wait 10 seconds
    # Then fail
```

### **6. Google API Client (`services/google_api.py`)**

```python
class GoogleAPIClient:
    """
    HTTP client for Google Business Profile API
    Methods:
    - validate_access_token(token: str) -> bool
    - list_accounts(token: str) -> List[Account]
    - list_locations(account_id: str, token: str) -> List[Location]
    - list_reviews(location_id: str, token: str) -> List[Review]
    """
```

### **7. Kafka Producer (`kafka_producer.py`)**

```python
class KafkaEventPublisher:
    """
    Publishes domain events to Kafka
    Events published:
    - fetch-accounts: Trigger account worker
    - fetch-locations: Trigger location worker
    - fetch-reviews: Trigger review worker
    - sentiment-reviews: Published for downstream processing
    """
    
    async def publish(self, topic: str, event: dict):
        # Adds timestamp and correlation_id
        # Serializes to JSON
        # Sends to Kafka with retry
```

### **8. Database Models (`models.py`)**

```python
class SyncJob(Base):
    """Tracks overall fetch operation status"""
    id: int
    client_id: str
    status: str  # pending → running → completed/failed
    started_at: datetime
    completed_at: datetime
    error_message: Optional[str]

class Account(Base):
    """Google Business account"""
    google_account_id: str
    display_name: str
    sync_job_id: int  # Foreign key

class Location(Base):
    """Business location"""
    google_location_id: str
    display_name: str
    address: str
    account_id: int  # Foreign key

class Review(Base):
    """Customer review"""
    google_review_id: str
    location_id: int  # Foreign key
    rating: int
    comment: str
    reviewer_name: str
    sentiment_score: Optional[float]  # For downstream processing
```

### **9. Configuration (`config.py`)**

```python
class Settings(BaseSettings):
    # Database
    database_url: str  # PostgreSQL connection
    
    # Kafka
    kafka_bootstrap_servers: str  # Kafka broker addresses
    
    # Google API
    google_api_key: str
    
    # Rate limiting
    rate_limit_per_second: int = 10
    rate_limit_capacity: int = 100
    
    # Queue management
    deque_max_size: int = 1000
    
    # Logging
    log_level: str = "INFO"
```

---

## 📊 **How Data Flows Through the System**

### **Complete End-to-End Flow**

```
1. USER INITIATES
   POST /api/v1/review-fetch
   {"access_token": "ya29.xxx", "client_id": "client123"}
   
2. API CREATES JOB
   ├─ INSERT INTO sync_job (status='pending')
   ├─ Returns job_id = 42
   └─ Publishes event: {
        "event_type": "fetch-accounts",
        "job_id": 42,
        "access_token": "ya29.xxx",
        "client_id": "client123",
        "timestamp": "2025-01-15T10:30:00Z",
        "correlation_id": "uuid-xxx"
      }

3. ACCOUNT WORKER CONSUMES
   ├─ Receives fetch-accounts event
   ├─ Rate limiter: checks token bucket (has tokens? yes → proceed)
   ├─ Calls Google API: /v1/accounts:list
   ├─ Response: [Account1, Account2, Account3]
   ├─ FOR EACH account:
   │   ├─ INSERT INTO account (google_account_id, display_name, job_id)
   │   └─ Publishes: {
   │        "event_type": "fetch-locations",
   │        "account_id": "accounts/1000",
   │        "job_id": 42,
   │        "correlation_id": "uuid-xxx"
   │      }
   └─ Updates sync_job: status='running', current_step='accounts_fetched'

4. LOCATION WORKERS CONSUME (parallel)
   ├─ Receive fetch-locations event (one per account)
   ├─ Call Google API: /v1/{accountId}/locations:list
   ├─ Response: [Location1, Location2, ...]
   ├─ FOR EACH location:
   │   ├─ INSERT INTO location (google_location_id, address, account_id, job_id)
   │   └─ Publishes: {
   │        "event_type": "fetch-reviews",
   │        "location_id": "locations/5000",
   │        "job_id": 42,
   │        "correlation_id": "uuid-xxx"
   │      }
   └─ Updates progress tracking

5. REVIEW WORKERS CONSUME (parallel)
   ├─ Receive fetch-reviews event (one per location)
   ├─ Call Google API: /v1/{locationId}/reviews:list
   ├─ Response: [Review1, Review2, ...]
   ├─ FOR EACH review:
   │   ├─ INSERT INTO review (google_review_id, rating, comment, location_id, job_id)
   │   └─ Publishes: {
   │        "event_type": "sentiment-reviews",
   │        "review_id": "review/7000",
   │        "comment": "Great service!",
   │        "rating": 5,
   │        "location_id": "locations/5000",
   │        "job_id": 42,
   │        "correlation_id": "uuid-xxx"
   │      }
   └─ Updates sync_job: status='running', current_step='reviews_fetched'

7. FINAL STATUS
   ├─ All review workers complete
   ├─ Updates sync_job: status='completed', completed_at=now()
   └─ Sentiment-reviews events published for downstream consumption

8. USER CHECKS STATUS
   GET /api/v1/job/42
   Response: {
     "job_id": 42,
     "status": "completed",
     "started_at": "2025-01-15T10:30:00Z",
     "completed_at": "2025-01-15T10:35:45Z",
     "accounts_count": 3,
     "locations_count": 15,
     "reviews_count": 342
   }
```

---

## 🏛️ **Architecture Principles Applied**

### **SOLID Principles**

| Principle | Implementation |
|-----------|-----------------|
| **S**ingle Responsibility | Each worker handles ONE task (AccountWorker → accounts only) |
| **O**pen/Closed | New data sources extend GoogleAPIClient, don't modify existing code |
| **L**iskov Substitution | All workers implement BaseWorker interface |
| **I**nterface Segregation | Workers only depend on interfaces they use |
| **D**ependency Inversion | Depend on abstractions (interfaces), not concrete classes |

### **Design Patterns**

| Pattern | Usage |
|---------|-------|
| **Event Sourcing** | All state changes published as events (Kafka) |
| **CQRS** | Command: API endpoint; Query: Database reads |
| **Saga Pattern** | Distributed transaction across workers with compensation |
| **Circuit Breaker** | Retry mechanism detects failed APIs, stops hammering |
| **Bulkhead** | Rate limiter isolates API quota exhaustion effects |
| **Dead Letter Queue** | Failed events sent to DLQ, not lost |

### **Data Structures**

| Structure | Purpose |
|-----------|---------|
| **Deque** | FIFO queue with bounded size |
| **Token Bucket** | Smooth rate limiting algorithm |
| **Heap** | Retry scheduling with exponential backoff |
| **Set** | De-duplication of processed reviews |
| **Dict** | In-memory tracking of job progress |

---

## 🚀 **Deployment & Configuration**

### **Environment Setup**

```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/reviews

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Google API
GOOGLE_API_KEY=your_service_account_json
GOOGLE_API_ENDPOINT=https://businessprofiles.googleapis.com/v1

# Rate Limiting
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_CAPACITY=100

# Application
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Queue
DEQUE_MAX_SIZE=1000
```

### **Docker Deployment**

```yaml
version: '3.8'
services:
  review-fetcher:
    build: ./review-fetcher-service
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - kafka
    environment:
      DATABASE_URL: postgresql+asyncpg://user:pass@postgres:5432/reviews
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: reviews
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    # ... kafka config ...
```

### **Health Checks**

```bash
# Service health
curl http://localhost:8000/api/v1/health

# Metrics
curl http://localhost:8000/api/v1/metrics
```

---

## 📚 **Understanding Kafka Consumer Workers**

### **Worker Pattern**

Each worker is an **independent async process** that:
1. **Subscribes** to a Kafka topic
2. **Consumes** messages from that topic
3. **Processes** the message (e.g., API call, database insert)
4. **Publishes** output events to new topics
5. **Handles errors** gracefully (retry, DLQ, logging)

### **AccountWorker Lifecycle**

```python
# File: app/kafka_consumers/account_worker.py
class AccountWorker(BaseWorker):
    def __init__(self, kafka_consumer, db_session, google_api_client):
        self.kafka_consumer = kafka_consumer
        self.db_session = db_session
        self.google_api_client = google_api_client
        self.rate_limiter = TokenBucketLimiter(rate=10)
    
    async def start(self):
        """Main event loop - runs forever"""
        async for message in self.kafka_consumer.subscribe("fetch-accounts"):
            try:
                await self.process_fetch_accounts_event(message)
            except Exception as e:
                # Publish to DLQ for manual inspection
                await self.publish_to_dlq(message, error=str(e))
    
    async def process_fetch_accounts_event(self, event):
        # 1. Extract data from event
        access_token = event.get("access_token")
        job_id = event.get("job_id")
        
        # 2. Rate limiting: ensure we don't exceed API quota
        await self.rate_limiter.acquire()
        
        # 3. Call Google API with retry
        @retry(stop=stop_after_attempt(5), wait=wait_exponential())
        async def fetch_accounts():
            return await self.google_api_client.list_accounts(access_token)
        
        accounts = await fetch_accounts()
        
        # 4. Store in PostgreSQL
        for account in accounts:
            db_account = Account(
                google_account_id=account.id,
                display_name=account.displayName,
                job_id=job_id
            )
            self.db_session.add(db_account)
        
        await self.db_session.commit()
        
        # 5. Publish fetch-locations events (one per account)
        for account in accounts:
            await self.kafka_producer.publish("fetch-locations", {
                "event_type": "fetch-locations",
                "account_id": account.id,
                "job_id": job_id,
                "access_token": access_token,
                "correlation_id": event.get("correlation_id")
            })
        
        # 6. Update job status
        sync_job = await self.db_session.get(SyncJob, job_id)
        sync_job.status = "running"
        sync_job.current_step = "fetching_locations"
        await self.db_session.commit()
```

### **Parallel Processing**

When AccountWorker publishes multiple "fetch-locations" events, LocationWorkers consume them **in parallel**:

```
AccountWorker publishes:
  fetch-locations for account 1
  fetch-locations for account 2
  fetch-locations for account 3

↓

Kafka distributes to available LocationWorkers:
  Worker 1 processes account 1 (in parallel)
  Worker 2 processes account 2 (in parallel)
  Worker 3 processes account 3 (in parallel)

↓

Each publishes fetch-reviews events for its locations (more parallelism)
```

This creates an **explosion of parallelism** as the data structure expands (1 account → N locations → M reviews).

---

## 🛡️ **Error Handling & Resilience**

### **Failure Scenarios**

| Scenario | Handling |
|----------|----------|
| **API rate limit exceeded** | TokenBucketLimiter waits, doesn't drop request |
| **API temporary error (500)** | Exponential backoff retry (2s → 4s → 8s) |
| **API permanent error (401)** | Send to DLQ, alert operator |
| **Database connection lost** | Connection pool reconnects automatically |
| **Kafka unavailable** | Event stays in offset, retry when Kafka recovers |
| **Worker crashes** | Kubernetes/Docker restarts container |
| **Deque buffer full** | Oldest unprocessed request dropped (bounded queue) |

### **Dead Letter Queue (DLQ)**

```python
# Failed events stored for manual inspection
async def publish_to_dlq(message, error):
    dlq_event = {
        "original_message": message,
        "error": error,
        "timestamp": datetime.now(),
        "worker_type": "AccountWorker"
    }
    await self.kafka_producer.publish("dlq-events", dlq_event)
    
    # Operator can:
    # 1. Fix the underlying issue
    # 2. Manually replay the DLQ message
    # 3. Skip and continue
```

---

## 🔍 **Observability & Monitoring**

### **Structured Logging**

Every significant operation logs with **correlation_id** for tracing:

```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "INFO",
  "message": "Published fetch-locations events",
  "worker": "AccountWorker",
  "job_id": 42,
  "correlation_id": "uuid-xxx",
  "account_count": 3,
  "location_count": 15,
  "duration_ms": 1245
}
```

### **Metrics Collection**

```python
# Prometheus-style metrics
metrics = {
    "worker_messages_processed_total": 5432,
    "worker_messages_failed_total": 23,
    "worker_api_call_duration_seconds": 1.45,
    "deque_buffer_size_current": 156,
    "deque_buffer_size_max": 1000,
    "rate_limiter_tokens_available": 89,
    "database_connections_active": 12,
}
```

---

## 🎓 **Learning Path**

To understand this system, study in this order:

1. **Start with `main.py`**: Understand FastAPI setup and startup sequence
2. **Read `api.py`**: See how POST /api/v1/review-fetch triggers the flow
3. **Study `deque_buffer.py`**: Learn bounded queue pattern
4. **Study `rate_limiter.py`**: Learn token bucket algorithm
5. **Read `config.py`**: Understand configuration management
6. **Read `models.py`**: See database schema (SyncJob, Account, Location, Review)
7. **Read `kafka_consumers/base.py`**: Understand base worker class
8. **Read `kafka_consumers/account_worker.py`**: Full worker implementation
9. **Study `kafka_producer.py`**: Event publishing mechanism
10. **Read `services/google_api.py`**: Google API integration
11. **Study `ARCHITECTURE.md`**: Deep dive into design patterns

---

## 🎯 **Key Takeaways**

### **What This System Does**
- **Fetches Google Business Profile reviews** using OAuth authentication
- **Stores data** in PostgreSQL with relationships (Account → Location → Review)
- **Processes asynchronously** using Kafka event streaming
- **Scales horizontally** by running multiple worker instances
- **Monitors extensively** with structured logging and metrics

### **Why This Architecture**
- **Decoupled**: Services communicate via events, not direct calls
- **Resilient**: Failed messages go to DLQ, not lost
- **Scalable**: Each worker scales independently
- **Testable**: Mock data provides test environment
- **Observable**: Full traceability with correlation IDs
- **Rate-limited**: Token bucket prevents API quota exhaustion
- **Burst-handling**: Deque buffer smooths traffic spikes

### **When to Scale**
- **Horizontal**: Add more worker containers
- **Vertical**: Increase rate limits and deque size
- **API quota**: Adjust rate limiter and deque buffer config

---

## 📞 **Quick Reference**

### **API Endpoints**
```
POST /api/v1/review-fetch          # Trigger fetch job
GET /api/v1/job/{job_id}          # Check job status
GET /api/v1/health                 # Service health
GET /api/v1/metrics               # Operational metrics
```

### **Kafka Topics**
```
fetch-accounts        → AccountWorker consumes
fetch-locations       → LocationWorker consumes
fetch-reviews         → ReviewWorker consumes
sentiment-reviews     → Published for downstream consumers
dlq-events           → Failed events
```

### **Database Tables**
```
sync_job   # Fetch operation tracking
account    # Google Business accounts
location   # Business locations
review     # Customer reviews
```

### **Configuration Files**
```
config.py           # Environment variables
models.py          # Database schema
api.py             # REST endpoints
kafka_producer.py  # Event publishing
rate_limiter.py   # Rate limiting
deque_buffer.py   # Queue management
```

---

**This microservice represents a sophisticated, production-ready implementation of modern software architecture principles: event-driven architecture, SOLID principles, design patterns, and distributed systems best practices applied to the real-world problem of fetching Google Business Profile reviews at scale.**</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/explanation.md