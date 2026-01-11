# Review Fetcher Microservice - Complete Technical Guide

**A high-performance, event-driven microservice for fetching Google Business Profile reviews with rate limiting, fault tolerance, and deduplication.**

> **Status**: ✅ Production-Ready | **Mode**: Real Google API Integration | **Deployment**: Docker Compose

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Tech Stack](#tech-stack)
4. [Data Structures & Algorithms](#data-structures--algorithms)
5. [Design Patterns](#design-patterns)
6. [OOP Principles](#oop-principles)
7. [Complete Flow](#complete-flow)
8. [API Reference](#api-reference)
9. [Configuration](#configuration)
10. [Deployment](#deployment)
11. [Monitoring](#monitoring)

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Google OAuth2 credentials with Business Profile API access
- Python 3.11+ (for local development)

### Start the Service

```bash
cd review-fetcher-service

# Start all services (Zookeeper, Kafka, Review Fetcher)
docker compose up -d

# Check status
docker compose ps

# View logs
docker logs review-fetcher-service -f
```

### Test the API

```bash
# Health check
curl http://localhost:8084/

# Submit a review fetch job
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.YOUR_GOOGLE_TOKEN"
  }'

# Response (202 Accepted)
{
  "job_id": "a11675be-be10-4f45-8f27-711104917523",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

### Interactive Documentation
- **Swagger UI**: http://localhost:8084/docs
- **ReDoc**: http://localhost:8084/redoc
- **Kafka UI**: http://localhost:8080

---

## Architecture Overview

### System Design - Fan-Out Hierarchical Pipeline

```
┌─────────────────┐
│  HTTP Request   │
│ (Job Submit)    │
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│ BoundedDequeBuffer       │  [FIFO Queue, Max 10,000 items]
│ (Burst Smoothing)        │  [Protects downstream]
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ KafkaEventPublisher      │  [Idempotent Producer]
│ (fetch-accounts topic)   │  [acks="all", Enable Idempotence]
└────────┬─────────────────┘
         │
         ▼
    ┌────────────────────────────┐
    │ STAGE 1: Account Fetching  │
    │                            │
    │ ┌──────────────────────┐  │
    │ │ AccountWorker        │  │
    │ │ ┌──────────────────┐ │  │
    │ │ │Rate Limiter      │ │  │ [Token Bucket]
    │ │ │100 tokens/10s    │ │  │ [300 QPM max]
    │ │ └──────────────────┘ │  │
    │ └──────────────────────┘  │
    │                            │
    │ Google API Call:           │ [Async httpx]
    │ → getGoogleAccounts()      │ [Tenacity retry]
    │                            │
    │ Publishes to:              │
    │ fetch-locations topic      │
    └────────┬───────────────────┘
             │
             ▼
    ┌────────────────────────────┐
    │ STAGE 2: Location Fetching │
    │                            │
    │ ┌──────────────────────┐  │
    │ │ LocationWorker       │  │
    │ │ ┌──────────────────┐ │  │
    │ │ │Rate Limiter      │ │  │ [Token Bucket]
    │ │ │100 tokens/10s    │ │  │ [Per-worker isolation]
    │ │ └──────────────────┘ │  │
    │ └──────────────────────┘  │
    │                            │
    │ Google API Call:           │ [Pagination support]
    │ → getGoogleLocations()     │ [For each account]
    │                            │
    │ Publishes to:              │
    │ fetch-reviews topic        │
    └────────┬───────────────────┘
             │
             ▼
    ┌────────────────────────────┐
    │ STAGE 3: Review Fetching   │
    │                            │
    │ ┌──────────────────────┐  │
    │ │ ReviewWorker         │  │
    │ │ ┌──────────────────┐ │  │
    │ │ │Rate Limiter      │ │  │ [Token Bucket]
    │ │ │100 tokens/10s    │ │  │ [Per-worker isolation]
    │ │ └──────────────────┘ │  │
    │ │ ┌──────────────────┐ │  │
    │ │ │Deduplication    │ │  │ [In-memory set]
    │ │ │(job_id basis)   │ │  │ [Prevents duplicates]
    │ │ └──────────────────┘ │  │
    │ └──────────────────────┘  │
    │                            │
    │ Google API Call:           │ [Async pagination]
    │ → getGoogleReviews()       │ [For each location]
    │                            │
    │ Publishes to:              │
    │ reviews-raw topic          │
    └────────┬───────────────────┘
             │
             ▼
    ┌────────────────────────────┐
    │ FINAL OUTPUT: reviews-raw  │
    │                            │
    │ [Kafka Topic]              │
    │ [Messages: Review Objects] │
    │ [Consumer: Separation Svc] │
    └────────────────────────────┘
```

### Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI App                         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ APIService                                       │  │
│  │ - Validates OAuth tokens                         │  │
│  │ - Creates jobs                                   │  │
│  │ - Enqueues to deque buffer                       │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │ BoundedDequeBuffer                               │  │
│  │ - FIFO queue (max 10k items)                     │  │
│  │ - Metrics: enqueued, dequeued, rejected          │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │ Producer Loop (Background Task)                  │  │
│  │ - Drains deque in batches (100 items)           │  │
│  │ - Publishes to fetch-accounts Kafka topic       │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
└─────────────────┼───────────────────────────────────────┘
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
       Kafka         Kafka UI
       Broker        Monitoring
          │
    ┌─────┴──────┬──────────┐
    │            │          │
    ▼            ▼          ▼
  Topic 1    Topic 2    Topic 3
  (fetch-)   (fetch-)   (fetch-)
  (accounts) (locations)(reviews)
    │            │          │
    ▼            ▼          ▼
  Worker 1   Worker 2   Worker 3
  (Account)  (Location) (Review)
    │            │          │
    └────┬───────┴─────┬────┘
         │             │
         ▼             ▼
    Retry Loop    Reviews-Raw
    (Reschedule   (Output Topic)
     Failed Jobs)
```

---

## Tech Stack

### Core Technologies

| Component | Technology | Purpose | Why Chosen |
|-----------|-----------|---------|-----------|
| **Framework** | FastAPI | REST API & Async Runtime | Fast, async-first, auto-docs (OpenAPI) |
| **Async Runtime** | asyncio | Concurrency Model | Built-in Python, efficient for I/O-heavy tasks |
| **HTTP Client** | httpx | Google API Requests | Async support, streaming, timeout handling |
| **Message Queue** | Apache Kafka | Event Streaming | Durable message log, partitioning, ordering guarantees |
| **Kafka Client** | aiokafka | Async Kafka Integration | Non-blocking, async/await compatible |
| **Data Validation** | Pydantic | Type-Safe Schemas | Runtime validation, OpenAPI integration |
| **Configuration** | pydantic-settings | Environment Variables | Automatic parsing, validation |
| **Retries** | tenacity | API Retry Logic | Backoff strategies, transient error handling |
| **Logging** | structlog | Structured Logs | JSON output, context propagation |
| **Containerization** | Docker Compose | Service Orchestration | Reproducible deployment, multi-service setup |

### Dependencies Graph

```
fastapi
  ├── starlette (async web framework)
  ├── pydantic (validation)
  │   └── pydantic-settings (env vars)
  └── uvicorn (ASGI server)

aiokafka
  ├── kafka-python (protocol)
  └── asyncio (async runtime)

httpx
  ├── httpcore (low-level HTTP)
  └── asyncio (async runtime)

tenacity (retry decorators)

structlog (structured logging)
```

---

## Data Structures & Algorithms

### 1. Bounded Deque (BoundedDequeBuffer)

**Purpose**: Burst smoothing and ingress flow control

**Data Structure**: `collections.deque` (doubly-linked list)

**Characteristics**:
- **Type**: FIFO (First-In-First-Out)
- **Max Size**: 10,000 items (configurable)
- **Operations**:
  - `enqueue(job)` → O(1) append
  - `dequeue_batch(batch_size)` → O(n) where n = batch_size (typically 100)
  - Full check → O(1) len() check

**Algorithm: Enqueue with Rejection**

```python
def enqueue(job):
    if len(queue) >= max_size:
        return False  # Reject - signal 429 to client
    queue.append(job)
    return True
```

**Benefits**:
- ✅ O(1) insertion/deletion at both ends
- ✅ Protects downstream workers from traffic spikes
- ✅ Clients get immediate feedback (429 response)
- ✅ Built-in len() for size checking

**Alternative Not Chosen**: Regular list would require O(n) for dequeue at index 0

---

### 2. Token Bucket Rate Limiter

**Purpose**: Rate limiting per worker (300 QPM Google quota)

**Data Structure**: 
- `capacity: float` (max tokens)
- `tokens: float` (current tokens)
- `last_refill: float` (monotonic timestamp)
- `refill_rate: float` (tokens per second)

**Algorithm: Monotonic Time-Based Refill**

```python
def acquire(tokens=1) -> bool:
    # Calculate elapsed time since last refill
    now = monotonic()
    elapsed = now - last_refill
    
    # Refill tokens based on elapsed time
    refilled_tokens = elapsed * refill_rate
    tokens = min(capacity, tokens + refilled_tokens)
    last_refill = now
    
    # Try to consume
    if tokens >= required_tokens:
        tokens -= required_tokens
        return True
    return False
```

**Complexity**:
- **Time**: O(1) per acquire call
- **Space**: O(1) per limiter instance

**Configuration** (Per Worker):
- `capacity`: 100 tokens
- `refill_rate`: 10.0 tokens/sec
- Allows 100 requests burst, then throttles to 10 req/sec

**Why This Approach**:
- ✅ O(1) performance (no heap/queue operations)
- ✅ No network calls needed (local state)
- ✅ Monotonic time prevents system clock issues
- ✅ Per-worker isolation prevents cascading failures

---

### 3. Exponential Backoff Retry Scheduler

**Purpose**: Intelligent retry scheduling for transient failures

**Data Structure**: `heapq` (binary min-heap)

**Queue Structure**:
```python
# Min-heap ordered by retry_at timestamp
heap = [
    (retry_at=1610000001.5, job_id="...", attempt=2, ...),
    (retry_at=1610000002.3, job_id="...", attempt=3, ...),
    (retry_at=1610000005.1, job_id="...", attempt=2, ...),
]
```

**Algorithm: Schedule Retry**

```python
def schedule_retry(job, error_code, attempt):
    # Distinguish error types
    if error_code in [429, 500, 502, 503]:  # Transient
        # Exponential backoff: 100ms * 2^attempt
        backoff_ms = initial_backoff_ms * (2 ** attempt)
        backoff_ms = min(backoff_ms, max_backoff_ms)  # Cap at 10s
        retry_at = now() + backoff_ms / 1000
        
        heapq.heappush(heap, (retry_at, job))
    else:  # Permanent error (401, 403, 404)
        send_to_dlq(job, error_code)
```

**Algorithm: Process Retries**

```python
def process_retries_loop():
    while True:
        if heap and heap[0].retry_at <= now():
            _, job = heapq.heappop(heap)
            # Republish job to Kafka for reprocessing
            await producer.publish(job)
        await sleep(1)  # Check every second
```

**Complexity**:
- **Push**: O(log n)
- **Pop**: O(log n)
- **Peek (check if due)**: O(1)

**Configuration**:
- `initial_backoff_ms`: 100ms
- `max_backoff_ms`: 10,000ms (10 seconds)
- `backoff_multiplier`: 2.0 (exponential)
- `max_retries`: 3 attempts total

**Backoff Schedule**:
- Attempt 1: 100ms
- Attempt 2: 200ms
- Attempt 3: 400ms
- Beyond: 10s cap

---

### 4. In-Memory Deduplication (ReviewWorker)

**Purpose**: Prevent duplicate reviews within a job

**Data Structure**: `set[str]` (hash set)

**Algorithm: Deduplication**

```python
# Per job_id
dedup_cache[job_id] = set()

def process_review(job_id, review):
    review_key = f"{review['account_id']}_{review['location_id']}_{review['review_id']}"
    
    if review_key in dedup_cache[job_id]:
        return False  # Already seen
    
    dedup_cache[job_id].add(review_key)
    return True  # New review
```

**Complexity**:
- **Add**: O(1) average case
- **Check**: O(1) average case
- **Memory**: O(n) where n = unique reviews per job

**Cleanup**:
```python
def cleanup_job_cache(job_id):
    # Run after job completes (all reviews published)
    del dedup_cache[job_id]  # O(1) deletion
```

**Limitations**:
- ✅ Works per-job (resets after job completion)
- ✅ Handles same job processed multiple times
- ⚠️ Doesn't prevent duplicates across jobs
- → (Use downstream database constraints for cross-job dedup)

---

## Design Patterns

### 1. Service Locator Pattern (AppState)

**Problem**: Multiple components need access to shared services without tight coupling

**Solution**: Centralized container for all singletons

```python
class AppState:
    """Central service registry"""
    deque_buffer: BoundedDequeBuffer
    event_publisher: KafkaEventPublisher
    rate_limiters: Dict[str, TokenBucketLimiter]
    retry_scheduler: RetryScheduler
    workers: Dict[str, Callable]

# Access anywhere
app_state = get_app_state()
app_state.event_publisher.publish(...)
```

**Benefits**:
- ✅ No global imports
- ✅ Easy to mock for testing
- ✅ Centralized initialization
- ✅ Cleaner dependency tracking

---

### 2. Factory Pattern (KafkaProducerFactory, WorkerFactory)

**Problem**: Creating complex objects with various configurations

**Solution**: Encapsulate creation logic

```python
class KafkaProducerFactory:
    @staticmethod
    def create(bootstrap_servers, settings):
        producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            acks="all",
            enable_idempotence=True,
            ...
        )
        return KafkaEventPublisher(producer)

# Usage
publisher = KafkaProducerFactory.create(
    bootstrap_servers="kafka:9092",
    settings=config
)
```

**Benefits**:
- ✅ Encapsulates Kafka config complexity
- ✅ Easy to swap implementations (mock/real)
- ✅ Centralized configuration logic

---

### 3. Strategy Pattern (Rate Limiters, Retry Policies)

**Problem**: Multiple ways to limit rate or retry; need flexibility

**Solution**: Pluggable strategies with common interface

```python
class RateLimiter(ABC):
    @abstractmethod
    async def acquire(self, tokens: int) -> bool:
        pass

class TokenBucketLimiter(RateLimiter):
    async def acquire(self, tokens=1):
        # Token bucket implementation
        pass

class NoOpLimiter(RateLimiter):
    async def acquire(self, tokens=1):
        return True  # No limiting

# Usage: Inject strategy
worker = ReviewWorker(..., rate_limiter=TokenBucketLimiter(...))
```

**Benefits**:
- ✅ Easy to swap implementations
- ✅ No conditional logic in workers
- ✅ Mock easily for testing

---

### 4. Template Method Pattern (KafkaConsumerBase)

**Problem**: Multiple consumers share common logic (connect, disconnect, error handling)

**Solution**: Abstract base class with template method

```python
class KafkaConsumerBase(ABC):
    async def start(self):
        """Template method - defines algorithm structure"""
        self.is_running = True
        await self.connect()  # Subclass implements
        while self.is_running:
            await self.consume()  # Subclass implements
    
    @abstractmethod
    async def connect(self):
        """Hook - implemented by subclass"""
        pass
    
    @abstractmethod
    async def consume(self):
        """Hook - implemented by subclass"""
        pass

class AccountWorker(KafkaConsumerBase):
    async def connect(self):
        await self.consumer.connect()
    
    async def consume(self):
        async for message in self.consumer:
            await self.process_message(message)
```

**Benefits**:
- ✅ Shared error handling, lifecycle
- ✅ Consistent behavior across workers
- ✅ Easy to add new workers

---

### 5. Adapter Pattern (BoundedDequeBuffer)

**Problem**: Need deque interface but with max size and metrics

**Solution**: Wrap deque with additional functionality

```python
class BoundedDequeBuffer(Adapter):
    def __init__(self, max_size: int):
        self._queue = deque()  # Wrapped deque
        self.max_size = max_size
        self.metrics = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0
        }
    
    def enqueue(self, job) -> bool:
        if len(self._queue) >= self.max_size:
            self.metrics["rejected"] += 1
            return False
        self._queue.append(job)
        self.metrics["enqueued"] += 1
        return True
```

**Benefits**:
- ✅ Extends deque without modifying it
- ✅ Adds metrics/monitoring
- ✅ Encapsulates complexity

---

### 6. Dependency Injection Pattern

**Problem**: Components need dependencies; want loose coupling

**Solution**: Pass dependencies as constructor arguments

```python
class ReviewWorker(KafkaConsumerBase):
    def __init__(
        self,
        topic: str,
        bootstrap_servers: list[str],
        rate_limiter: TokenBucketLimiter,  # Injected
        retry_scheduler: RetryScheduler,   # Injected
        event_publisher: KafkaEventPublisher,  # Injected
        google_api: GoogleAPIClient  # Injected
    ):
        self.rate_limiter = rate_limiter
        self.retry_scheduler = retry_scheduler
        # ...

# Usage
worker = ReviewWorker(
    topic="fetch-reviews",
    bootstrap_servers=["kafka:9092"],
    rate_limiter=state.review_rate_limiter,
    retry_scheduler=state.retry_scheduler,
    event_publisher=state.event_publisher,
    google_api=GoogleAPIClient(token)
)
```

**Benefits**:
- ✅ Easy to test (mock dependencies)
- ✅ Loose coupling
- ✅ Clear dependencies

---

### 7. Context Manager Pattern (FastAPI Lifespan)

**Problem**: Need initialization and cleanup on app startup/shutdown

**Solution**: Use async context manager

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    global _app_state
    _app_state = await initialize_components()
    
    yield  # App runs here
    
    # SHUTDOWN
    await cleanup_components(_app_state)

app = FastAPI(lifespan=lifespan)
```

**Benefits**:
- ✅ Guaranteed cleanup
- ✅ Clean startup/shutdown logic
- ✅ Exception handling built-in

---

## OOP Principles

### 1. Encapsulation

**Principle**: Hide internal details, expose only necessary interface

**Example**:

```python
class TokenBucketLimiter:
    """Encapsulates token bucket state"""
    
    def __init__(self, capacity: float, refill_rate: float):
        self._capacity = capacity  # Private
        self._tokens = capacity    # Private
        self._last_refill = monotonic()  # Private
        self._refill_rate = refill_rate  # Private
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Public interface - doesn't expose internals"""
        # Implementation hidden
        pass
```

**Benefits**:
- ✅ Users only interact with `acquire()`
- ✅ Internal state can change without affecting clients
- ✅ Prevents misuse of internal state

---

### 2. Inheritance & Polymorphism

**Principle**: Create hierarchy for shared behavior and interface

**Example**:

```python
# Abstract base class
class KafkaConsumerBase(ABC):
    @abstractmethod
    async def consume(self) -> None:
        pass

# Concrete implementations (polymorphic)
class AccountWorker(KafkaConsumerBase):
    async def consume(self):
        async for msg in self.consumer:
            await self.on_message(msg)

class LocationWorker(KafkaConsumerBase):
    async def consume(self):
        async for msg in self.consumer:
            await self.on_message(msg)

# Usage: Polymorphism
workers: list[KafkaConsumerBase] = [
    AccountWorker(...),
    LocationWorker(...),
    ReviewWorker(...)
]
for worker in workers:
    await worker.start()  # Each implements its own logic
```

**Benefits**:
- ✅ Code reuse (shared start/stop logic)
- ✅ Polymorphic calls (don't need to know concrete type)
- ✅ Easy to add new workers

---

### 3. Abstraction

**Principle**: Define contracts without implementation details

**Example**:

```python
class RateLimiter(ABC):
    """Abstract interface for any rate limiter"""
    
    @abstractmethod
    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Return True if successful."""
        pass

# Users program to abstraction, not concrete class
async def process_api_call(limiter: RateLimiter):
    if await limiter.acquire():
        return await google_api.call()
    else:
        raise TooManyRequestsError()
```

**Benefits**:
- ✅ Decouples from implementation
- ✅ Easy to swap strategies
- ✅ Testable with mock implementations

---

### 4. Composition over Inheritance

**Principle**: Favor object composition over class inheritance

**Example**:

```python
# Instead of: class ReviewWorkerWithLimiter(ReviewWorker)

# Use composition:
class ReviewWorker(KafkaConsumerBase):
    def __init__(
        self,
        topic: str,
        rate_limiter: TokenBucketLimiter,  # Composed
        retry_scheduler: RetryScheduler,   # Composed
        event_publisher: KafkaEventPublisher  # Composed
    ):
        self.rate_limiter = rate_limiter
        self.retry_scheduler = retry_scheduler
        self.event_publisher = event_publisher
    
    async def process_message(self, message):
        # Use composed objects
        if not await self.rate_limiter.acquire():
            await self.retry_scheduler.schedule_retry(message)
            return
        
        reviews = await self.google_api.fetch_reviews(...)
        await self.event_publisher.publish_reviews(reviews)
```

**Benefits**:
- ✅ More flexible than inheritance
- ✅ Easier to test (mock composed objects)
- ✅ Clearer responsibilities

---

### 5. Single Responsibility Principle (SRP)

**Principle**: Each class should have one reason to change

**Example**:

```python
# ✅ GOOD: Single responsibility
class TokenBucketLimiter:
    """Only responsible for rate limiting"""
    async def acquire(self, tokens: int = 1) -> bool:
        pass

class KafkaEventPublisher:
    """Only responsible for publishing events"""
    async def publish_fetch_accounts_event(self, job_id, token):
        pass

class GoogleAPIClient:
    """Only responsible for Google API calls"""
    async def get_accounts(self, token):
        pass

# ❌ WRONG: Multiple responsibilities
class ReviewWorkerMonster:
    async def rate_limit(self):
        pass
    async def publish_to_kafka(self):
        pass
    async def call_google_api(self):
        pass
    async def parse_response(self):
        pass
    async def log_metrics(self):
        pass
    # ... too many reasons to change!
```

**Benefits**:
- ✅ Classes are easier to understand
- ✅ Easier to test in isolation
- ✅ Changes to one concern don't affect others

---

### 6. Dependency Inversion Principle (DIP)

**Principle**: Depend on abstractions, not concretions

**Example**:

```python
# ❌ WRONG: High-level module depends on low-level
class ReviewWorker:
    def __init__(self):
        self.limiter = TokenBucketLimiter()  # Tightly coupled
        self.api = GoogleAPIClient()  # Tightly coupled

# ✅ GOOD: Both depend on abstractions
class ReviewWorker(KafkaConsumerBase):
    def __init__(
        self,
        rate_limiter: RateLimiter,  # Abstract type
        google_api: GoogleAPIClient  # Abstract interface
    ):
        self.rate_limiter = rate_limiter
        self.google_api = google_api
```

**Benefits**:
- ✅ Easy to inject mocks for testing
- ✅ Can swap implementations
- ✅ Loose coupling

---

## Complete Flow

### End-to-End Request Journey

```
1️⃣ CLIENT SUBMITS JOB
   ├─ POST /api/v1/review-fetch
   ├─ Body: {"access_token": "ya29.XXXXX"}
   └─ Response (202): {"job_id": "abc123", "status": "queued"}

2️⃣ API VALIDATION & QUEUEING
   ├─ APIService.validate_access_token()
   │  └─ Check token format (basic validation)
   ├─ Generate job_id (UUID4)
   ├─ Create job object
   │  {
   │    "job_id": "abc123",
   │    "access_token": "ya29.XXXXX",
   │    "created_at": 1609459200.0,
   │    "retries": 0
   │  }
   ├─ Try to enqueue in BoundedDequeBuffer
   │  ├─ Check: len(queue) < max_size (10000)?
   │  ├─ If NO → Return 429 (Too Many Requests)
   │  └─ If YES → Append job, return 202 (Accepted)
   └─ Response sent to client

3️⃣ PRODUCER LOOP (Background Task)
   ├─ Run: Every 100ms (burst_check_interval_sec)
   ├─ Step 1: Dequeue batch
   │  └─ Get up to 100 jobs from queue (in order)
   ├─ Step 2: For each job
   │  ├─ Publish to Kafka topic: fetch-accounts
   │  │  ├─ Message key: job_id (for ordering guarantee)
   │  │  └─ Compression: None (was snappy, now disabled)
   │  ├─ Commit locally
   │  └─ Log: "job_published_to_kafka job_id=abc123"
   ├─ Step 3: Wait 100ms
   └─ Repeat

4️⃣ ACCOUNT WORKER CONSUMES
   ├─ Kafka consumer group: account-worker
   ├─ Topic: fetch-accounts
   ├─ For each message (job):
   │  ├─ Extract: job_id, access_token
   │  │
   │  ├─ RATE LIMITING
   │  │  ├─ TokenBucketLimiter.acquire(tokens=1)
   │  │  ├─ Check: current_tokens >= 1?
   │  │  ├─ If NO:
   │  │  │  ├─ Schedule retry (exponential backoff)
   │  │  │  └─ Continue to next message
   │  │  └─ If YES:
   │  │     └─ Deduct token, proceed
   │  │
   │  ├─ GOOGLE API CALL (with tenacity retry)
   │  │  ├─ httpx.AsyncClient.get("https://...")
   │  │  ├─ Endpoint: /google_api/v2/accounts
   │  │  ├─ Header: Authorization: Bearer {token}
   │  │  ├─ Retry decorator: 3 attempts with backoff
   │  │  └─ Response: [{"accountId": "123", ...}, ...]
   │  │
   │  ├─ ERROR HANDLING
   │  │  ├─ If 401/403: Send to DLQ (permanent error)
   │  │  ├─ If 429/5xx: Schedule retry (transient)
   │  │  └─ If success: Continue
   │  │
   │  ├─ PROCESS RESPONSE
   │  │  └─ For each account:
   │  │     ├─ Create message:
   │  │     │  {
   │  │     │    "job_id": "abc123",
   │  │     │    "access_token": "ya29.XXXXX",
   │  │     │    "account_id": "123456"
   │  │     │  }
   │  │     └─ Publish to fetch-locations topic
   │  │
   │  ├─ COMMIT
   │  │  └─ Mark message as consumed
   │  │
   │  └─ LOGGING
   │     └─ Log: "accounts_fetched job_id=abc123 count=2"
   └─ Continue consuming

5️⃣ LOCATION WORKER CONSUMES
   ├─ Same pattern as Account Worker
   ├─ Topic: fetch-locations
   ├─ For each account:
   │  ├─ Rate limit
   │  ├─ Call: /google_api/v2/accounts/{id}/locations
   │  ├─ For each location:
   │  │  ├─ Publish to fetch-reviews topic
   │  │  └─ Message includes: job_id, account_id, location_id
   │  └─ Commit
   └─ Continue consuming

6️⃣ REVIEW WORKER CONSUMES
   ├─ Topic: fetch-reviews
   ├─ For each location:
   │  ├─ Rate limit
   │  ├─ Call: /google_api/v2/accounts/{id}/locations/{id}/reviews
   │  ├─ For each review:
   │  │  ├─ DEDUPLICATION CHECK
   │  │  │  ├─ Build key: f"{account}_{location}_{review_id}"
   │  │  │  ├─ Check: key in dedup_cache[job_id]?
   │  │  │  ├─ If YES: Skip (already published)
   │  │  │  └─ If NO:
   │  │  │     ├─ Add to cache
   │  │  │     └─ Continue
   │  │  │
   │  │  ├─ PUBLISH
   │  │  │  ├─ Topic: reviews-raw
   │  │  │  └─ Message: Full review object
   │  │  │
   │  │  └─ COMMIT
   │  │
   │  ├─ After location done:
   │  │  └─ Commit offset
   │  │
   │  └─ After job done:
   │     └─ Clear dedup cache (cleanup)
   │
   └─ Continue consuming

7️⃣ RETRY LOOP (Background Task)
   ├─ Run: Every 1 second
   ├─ Check: retry_scheduler.heap
   ├─ For each job with retry_at <= now():
   │  ├─ Pop from heap
   │  ├─ Republish to appropriate topic
   │  ├─ Increment retry count
   │  ├─ After 3 retries: Send to DLQ
   │  └─ Log: "job_retry job_id=abc123 attempt=2"
   └─ Repeat

8️⃣ FINAL OUTPUT
   ├─ Topic: reviews-raw
   ├─ Messages: Review objects
   │  {
   │    "reviewId": "review_123",
   │    "accountId": "acc_456",
   │    "locationId": "loc_789",
   │    "reviewer": "John Doe",
   │    "rating": 5,
   │    "text": "Great service!",
   │    "createTime": "2024-01-10T...",
   │    ...
   │  }
   └─ Consumer: Separation Service (sentiment analysis)
       or downstream system
```

---

## API Reference

### Health Check

```http
GET /
```

Response:
```json
{
  "service": "review-fetcher-service",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs"
}
```

---

### Submit Review Fetch Job

```http
POST /api/v1/review-fetch
Content-Type: application/json

{
  "access_token": "ya29.YOUR_GOOGLE_OAUTH_TOKEN"
}
```

**Parameters**:
- `access_token` (string, required): Google OAuth2 access token with Business Profile API access

**Response (202 Accepted)**:
```json
{
  "job_id": "a11675be-be10-4f45-8f27-711104917523",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

**Response (429 Too Many Requests)**:
```json
{
  "detail": "Deque buffer is full. Please retry later."
}
```

**Response (400 Bad Request)**:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "access_token"],
      "msg": "Invalid token format"
    }
  ]
}
```

---

### Interactive Documentation

- **Swagger UI**: `GET /docs`
- **ReDoc**: `GET /redoc`
- **OpenAPI JSON**: `GET /openapi.json`

---

## Configuration

### Environment Variables

Create a `.env` file or set in docker-compose.yml:

```env
# Service Configuration
LOG_LEVEL=INFO
ENVIRONMENT=production

# Feature Flags
MOCK_GOOGLE_API=false  # Set to "false" for real Google API

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_CONSUMER_GROUP=review-fetcher-service

# Rate Limiting (per worker)
RATELIMIT_TOKEN_BUCKET_CAPACITY=100
RATELIMIT_REFILL_RATE=10.0

# Retry Policy
RETRY_MAX_RETRIES=3
RETRY_INITIAL_BACKOFF_MS=100
RETRY_MAX_BACKOFF_MS=10000
RETRY_BACKOFF_MULTIPLIER=2.0

# Queue Configuration
DEQUE_MAX_SIZE=10000
DEQUE_BURST_CHECK_INTERVAL_SEC=0.1

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
```

### Configuration Classes

```python
# app/config.py

class RateLimitConfig(BaseSettings):
    token_bucket_capacity: int = 100  # Max tokens
    refill_rate: float = 10.0  # tokens per second

class RetryConfig(BaseSettings):
    max_retries: int = 3
    initial_backoff_ms: int = 100
    max_backoff_ms: int = 10000
    backoff_multiplier: float = 2.0

class KafkaConfig(BaseSettings):
    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "review-fetcher-service"
    
    def get_bootstrap_servers_list(self) -> list[str]:
        """Parse comma-separated string to list"""
        return [s.strip() for s in self.bootstrap_servers.split(",")]

class DequeConfig(BaseSettings):
    max_size: int = 10000
    burst_check_interval_sec: float = 0.1

class Settings(BaseSettings):
    log_level: str = "INFO"
    environment: str = "development"
    mock_google_api: bool = False
    
    kafka: KafkaConfig = KafkaConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    retry: RetryConfig = RetryConfig()
    deque: DequeConfig = DequeConfig()
```

---

## Deployment

### Docker Compose

```bash
cd review-fetcher-service

# Start all services
docker compose up -d

# View status
docker compose ps

# View logs
docker logs review-fetcher-service -f

# Stop services
docker compose down

# Clean up volumes
docker compose down -v
```

### Service Dependencies

```
review-fetcher-service
  ├─ depends_on: kafka (healthy)
  │  ├─ depends_on: zookeeper (healthy)
  │  └─ port: 9092
  ├─ port: 8084 (mapped from 8000)
  └─ network: review-network

kafka-ui
  ├─ depends_on: kafka (healthy)
  └─ port: 8080

separation-service (optional)
  ├─ depends_on: kafka (healthy)
  └─ port: 8085
```

### Port Mappings

| Service | Container Port | Host Port | Purpose |
|---------|---|---|---|
| review-fetcher | 8000 | 8084 | REST API |
| kafka | 9092 | 9092 | Message Broker |
| zookeeper | 2181 | 2181 | Coordination |
| kafka-ui | 8080 | 8080 | Monitoring |

---

## Monitoring

### Kafka UI Dashboard

Access at `http://localhost:8080`

**View**:
- Topics and partitions
- Consumer group lag
- Message content
- Broker health

### Service Logs

```bash
# Real-time logs
docker logs review-fetcher-service -f

# Last 100 lines
docker logs review-fetcher-service | tail -100

# Filter by worker
docker logs review-fetcher-service | grep "worker"

# Filter by job_id
docker logs review-fetcher-service | grep "a11675be-be10-4f45-8f27-711104917523"
```

### Metrics to Monitor

**Deque Buffer**:
```
enqueued_count: Total jobs enqueued
dequeued_count: Total jobs dequeued
rejected_count: Total jobs rejected (buffer full)
current_size: Current queue size
```

**Rate Limiter**:
```
acquire_requests: Total acquire attempts
acquire_success: Successful acquisitions
acquire_failure: Rejected (rate limited)
refills: Number of refill cycles
```

**Retry Scheduler**:
```
scheduled_retries: Jobs scheduled for retry
processed_retries: Retries processed
dead_letter_queue: Jobs permanently failed
```

**Kafka**:
```
published_messages: Messages sent to Kafka
publish_errors: Failed publishes
consumer_lag: Lag per consumer group
```

---

## Troubleshooting

### Service Won't Start

**Error**: `Unable to connect to kafka:9092`

**Cause**: Service not on same Docker network as Kafka

**Solution**: Check docker-compose.yml has:
```yaml
networks:
  - review-network
```

---

### High Memory Usage

**Cause**: Large deque buffer or review deduplication cache

**Solution**:
1. Reduce `DEQUE_MAX_SIZE`
2. Monitor `dedup_cache` cleanup
3. Increase worker throughput

---

### Slow Processing

**Cause**: Rate limiting throttling requests

**Check**:
```bash
# View logs for rate limit rejections
docker logs review-fetcher-service | grep "rate_limit"
```

**Solution**:
1. Increase `RATELIMIT_TOKEN_BUCKET_CAPACITY`
2. Increase `RATELIMIT_REFILL_RATE`
3. Verify Google API quota with credentials

---

## Files Overview

| File | Purpose |
|------|---------|
| `app/main.py` | Application orchestrator, lifespan, background tasks |
| `app/config.py` | Configuration management, environment variables |
| `app/api.py` | HTTP endpoints, job validation |
| `app/deque_buffer.py` | FIFO queue with metrics |
| `app/rate_limiter.py` | Token bucket rate limiting |
| `app/retry.py` | Exponential backoff retry scheduler |
| `app/kafka_producer.py` | Kafka producer with idempotence |
| `app/kafka_consumers/base.py` | Base consumer class, template method |
| `app/kafka_consumers/account_worker.py` | Fetch accounts from Google |
| `app/kafka_consumers/location_worker.py` | Fetch locations from Google |
| `app/kafka_consumers/review_worker.py` | Fetch reviews from Google |
| `app/services/google_api.py` | Google API client with async httpx |
| `app/models.py` | Pydantic schemas for requests/responses |
| `Dockerfile` | Container image definition |
| `docker-compose.yml` | Multi-service orchestration |

---

## Next Steps

1. **Obtain Google OAuth2 credentials** from Google Cloud Console
2. **Submit test jobs** with real tokens
3. **Monitor Kafka UI** at http://localhost:8080
4. **Check logs** for errors
5. **Scale workers** if needed by updating deployment config
6. **Set up downstream storage** for reviews-raw topic

---

**🚀 Ready to fetch reviews at scale!**

For detailed flow documentation, see [flow.md](flow.md)
