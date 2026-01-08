# Review Fetcher Microservice - Complete Flow & Architecture

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Design Patterns](#design-patterns)
4. [Data Structures & Algorithms](#data-structures--algorithms)
5. [Complete End-to-End Flow](#complete-end-to-end-flow)
6. [Component Details](#component-details)
7. [Error Handling](#error-handling)
8. [Performance Characteristics](#performance-characteristics)

---

## Overview

### What This Microservice Does

The Review Fetcher is a **high-performance, event-driven microservice** that:
- Accepts Google OAuth tokens and account IDs via REST API
- Validates tokens against Google Business Profile API
- Fetches reviews in a rate-limited, fault-tolerant manner
- Processes reviews through a multi-stage pipeline
- Outputs clean, deduplicated reviews to Kafka topics

### Tech Stack

```
┌──────────────────────────────────────┐
│   FastAPI (REST API Framework)       │
│   asyncio (Async Runtime)            │
│   Pydantic (Data Validation)         │
│   httpx (Async HTTP Client)          │
│   aiokafka (Async Kafka Client)      │
│   structlog (Structured Logging)     │
│   tenacity (Retry Library)           │
└──────────────────────────────────────┘
```

---

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Client                          │
│              (Browser/Backend/Mobile)                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ POST /api/v1/review-fetch
                       │ {access_token, account_id}
                       ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Application                        │
│           (Async HTTP Request Handler)                  │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ 1. Validate Token Format                       │    │
│  │ 2. Queue Job in Bounded Deque Buffer           │    │
│  │ 3. Return Job ID to Client                     │    │
│  └────────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│         Background Orchestrator (async tasks)           │
│                                                          │
│  ┌───────────────────┐                                  │
│  │ Producer Loop     │ → Publishes batches to Kafka    │
│  │ (Every 100ms)     │                                  │
│  └───────────────────┘                                  │
│                                                          │
│  ┌───────────────────┐                                  │
│  │ Retry Loop        │ → Reschedules failed jobs       │
│  │ (Every 1s)        │                                  │
│  └───────────────────┘                                  │
│                                                          │
│  ┌───────────────────┐                                  │
│  │ Worker Loop       │ → Runs 3 consumer workers       │
│  │ (Concurrent)      │                                  │
│  └───────────────────┘                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
   ┌────────┐    ┌──────────┐    ┌──────────┐
   │  Kafka │    │  Kafka   │    │  Kafka   │
   │Topic 1 │    │Topic 2   │    │Topic 3   │
   │        │    │          │    │          │
   │fetch-  │    │fetch-    │    │fetch-    │
   │accounts│    │locations │    │reviews   │
   └────┬───┘    └────┬─────┘    └────┬─────┘
        │             │              │
        ▼             ▼              ▼
   ┌────────┐    ┌──────────┐    ┌──────────┐
   │Account │    │Location  │    │Review    │
   │Worker  │    │Worker    │    │Worker    │
   │        │    │          │    │          │
   │ Fetches│    │ Fetches  │    │Fetches & │
   │accounts│    │locations │    │Dedupes   │
   └────┬───┘    └────┬─────┘    └────┬─────┘
        │             │              │
        └─────────────┴──────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │   reviews-raw Topic     │
         │  (Final Output Stream)  │
         └─────────────────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ Downstream Systems      │
         │ (Sentiment Analysis,    │
         │  Storage, Indexing)     │
         └─────────────────────────┘
```

### Component Breakdown

```
┌─────────────────────────────────────────────────────────┐
│                    Microservice Structure               │
└─────────────────────────────────────────────────────────┘

app/
├── main.py                          # FastAPI app setup + orchestrator
│   ├── lifespan()                   # Startup/shutdown hooks
│   ├── initialize_components()      # Factory pattern initialization
│   ├── run_background_tasks()       # Starts producer/retry/workers
│   └── shutdown_background_tasks()  # Graceful shutdown
│
├── api.py                            # HTTP endpoint handlers
│   └── POST /api/v1/review-fetch    # Main API endpoint
│
├── config.py                         # Configuration management
│   └── Settings (Pydantic)          # Environment-based config
│
├── models.py                         # Data models (Pydantic)
│   ├── FetchJobRequest              # Request schema
│   ├── FetchJobResponse             # Response schema
│   └── HealthResponse               # Health check schema
│
├── deque_buffer.py                   # Bounded queue implementation
│   ├── BoundedDequeBuffer          # Thread-safe async queue
│   ├── enqueue()                    # Add job (O(1))
│   └── dequeue_batch()              # Get batch (O(n))
│
├── kafka_producer.py                 # Event publishing
│   ├── KafkaProducerBase            # Abstract base
│   ├── MockKafkaProducer            # For testing
│   ├── AIokafkaProducer             # Real Kafka
│   └── KafkaEventPublisher          # Business logic wrapper
│
├── rate_limiter.py                   # Token bucket algorithm
│   ├── TokenBucketLimiter           # Single-worker rate limiter
│   ├── RateLimiterPool              # Per-worker limiters
│   ├── acquire()                    # Check/take tokens (O(1))
│   └── refill()                     # Add tokens (O(1))
│
├── retry.py                          # Retry mechanism
│   ├── RetryScheduler               # Manages retry queue
│   ├── ExponentialBackoffPolicy     # Backoff strategy
│   ├── get_ready_tasks()            # Get due retries (O(log n))
│   └── schedule_retry()             # Add to retry queue (O(log n))
│
├── observers/                        # Event observers (lifecycle)
│   └── __init__.py                  # Observer pattern implementation
│
├── kafka_consumers/                  # Worker implementations
│   ├── base.py                      # Abstract consumer + mock
│   ├── account_worker.py            # Stage 1: Fetch accounts
│   ├── location_worker.py           # Stage 2: Fetch locations
│   └── review_worker.py             # Stage 3: Fetch reviews + dedup
│
└── services/
    └── google_api.py                 # Google Business Profile API client
        ├── validate_token()          # OAuth validation
        ├── get_accounts()            # List business accounts
        ├── get_locations()           # List location per account
        └── get_reviews()             # Fetch reviews for location
```

---

## Design Patterns

### 1. **Factory Pattern**
Used for creating Kafka producers without coupling code to concrete implementations.

```python
# In main.py
producer = KafkaProducerFactory.create(
    mock=settings.mock_google_api,
    bootstrap_servers=settings.kafka.bootstrap_servers
)

# Returns MockKafkaProducer or AIokafkaProducer based on config
```

**Benefit:** Switch between mock and real Kafka by changing a config flag.

### 2. **Strategy Pattern**
Used for rate limiting and retry policies.

```python
# Rate Limiting Strategy
limiter = TokenBucketLimiter(capacity=100, refill_rate=10.0)

# Retry Strategy
retry_policy = ExponentialBackoffPolicy(
    max_retries=3,
    initial_backoff_ms=100,
    max_backoff_ms=10000,
    multiplier=2.0
)
```

**Benefit:** Easy to swap different algorithms (e.g., Token Bucket vs Sliding Window).

### 3. **Template Method Pattern**
Used in Kafka consumers to define skeleton, let subclasses override.

```python
class KafkaConsumerBase(ABC):
    async def start(self):
        """Template method"""
        await self.connect()
        self.is_running = True
        # Subclasses override _handle_event()
    
    @abstractmethod
    async def _handle_event(self, event: dict):
        """Subclasses implement specifics"""
        pass
```

**Benefit:** Code reuse, consistent lifecycle across workers.

### 4. **Observer Pattern**
Used for event notifications during service lifecycle.

```python
class LoggingObserver(BaseObserver):
    async def _handle_event(self, event: str, data: dict):
        logger.info(f"Event: {event}", data=data)

class AlertingObserver(BaseObserver):
    async def _handle_event(self, event: str, data: dict):
        if event == "startup_failed":
            alert_ops_team(data)
```

**Benefit:** Loose coupling between service and monitoring.

### 5. **Adapter Pattern**
Used to wrap `collections.deque` with async-safe, bounded interface.

```python
class BoundedDequeBuffer:
    def __init__(self, max_size: int):
        self._queue = collections.deque(maxlen=max_size)
        self._lock = asyncio.Lock()
    
    async def enqueue(self, item):
        async with self._lock:
            if len(self._queue) >= self.max_size:
                return False  # Queue full
            self._queue.append(item)
            return True
```

**Benefit:** Thread-safe, bounded queue with familiar API.

### 6. **Service Locator Pattern**
Used in AppState for centralized component access.

```python
state = AppState()
state.kafka_producer = producer
state.rate_limiter = limiter
state.retry_scheduler = scheduler

# Later:
await state.kafka_producer.send(...)
```

**Benefit:** Single source of truth for all service components.

### 7. **Singleton Pattern**
Settings object is singleton.

```python
def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
```

**Benefit:** One configuration object across entire application.

### 8. **Builder Pattern** (Implicit)
Used in data model construction.

```python
job = {
    "job_id": str(uuid4()),
    "access_token": request.access_token,
    "account_id": request.account_id,
    "created_at": datetime.utcnow().isoformat(),
    "retry_count": 0,
    "status": "queued"
}
```

**Benefit:** Step-by-step construction of complex objects.

---

## Data Structures & Algorithms

### 1. **Bounded Deque (Job Queue)**

**Data Structure:** `collections.deque` with max length

```python
self._queue = collections.deque(maxlen=max_size)
```

**Operations:**
- `append()` - O(1) enqueue
- `popleft()` - O(1) dequeue
- `len()` - O(1) size check

**Why This:**
- FIFO ordering (first jobs processed first)
- O(1) all operations
- Automatic overflow (loses oldest when full)
- Thread-safe with lock

**Example:**
```
Job 1 → [Job 1, Job 2, Job 3] → Job 1 out
        [Job 2, Job 3]
Job 4 → [Job 2, Job 3, Job 4]
```

---

### 2. **Token Bucket (Rate Limiter)**

**Algorithm:**
```
Capacity: 100 tokens
Refill Rate: 10 tokens/second

Time 0s:    Tokens = 100
Time 1s:    Tokens = 100 + 10 = 110 (capped at 100)
Time 0.5s:  Request for 5 tokens
            Tokens = 100 - 5 = 95 ✓ Allowed
Time 0.1s:  Request for 200 tokens
            Tokens = 95 < 200 ✗ Denied (wait)
```

**Implementation:**
```python
class TokenBucketLimiter:
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
    
    async def acquire(self, tokens: int = 1) -> bool:
        # Refill based on time elapsed
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, 
                         self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        # Check if enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

**Time Complexity:** O(1) - single timestamp calculation

**Why This:**
- Allows bursts (up to capacity)
- Smooth average rate (refill_rate)
- Respects Google API limits (10 req/sec)
- Used per-worker (3 independent limiters)

---

### 3. **Min-Heap (Retry Queue)**

**Data Structure:** `heapq` - min-heap by retry time

```python
import heapq

self._retry_heap = []  # [(retry_time, message_id, payload), ...]
heapq.heappush(heap, (retry_time, message_id, payload))
ready = heapq.heappop(heap)  # Gets earliest retry
```

**Operations:**
- `heappush()` - O(log n) insert
- `heappop()` - O(log n) extract minimum
- `heapreplace()` - O(log n) pop + push

**Example:**
```
Insert (retry_time=1.5s, id="job_1"):
  Heap: [(1.5, "job_1")]

Insert (retry_time=0.8s, id="job_2"):
  Heap: [(0.8, "job_2"), (1.5, "job_1")]  ← heap property maintained

Insert (retry_time=2.0s, id="job_3"):
  Heap: [(0.8, "job_2"), (1.5, "job_1"), (2.0, "job_3")]

Pop earliest (time >= 0.8s):
  Heap: [(1.5, "job_1"), (2.0, "job_3")]
```

**Why This:**
- Always get next retry in O(log n)
- Don't check all retries each iteration
- Efficient for up to millions of retries

---

### 4. **Hash Table (Deduplication Cache)**

**Data Structure:** `set` of review hashes

```python
self.seen_reviews = {
    job_id: set()  # Stores review IDs already seen
}
```

**Operations:**
- `add()` - O(1) insert
- `__contains__()` - O(1) lookup

**Example:**
```python
job_id = "fetch_job_123"
self.seen_reviews[job_id] = set()

# Process review
review_id = "review_456"
if review_id not in self.seen_reviews[job_id]:
    # New review
    self.seen_reviews[job_id].add(review_id)
    output(review)
else:
    # Duplicate, skip
    skip()
```

**Why This:**
- O(1) duplicate check
- Fast even with 100K+ reviews
- Scoped per job (cleared after job completes)

---

### 5. **Event Loop (Async Concurrency)**

**Model:** Cooperative multitasking via asyncio

```python
async def producer_loop():
    while True:
        batch = await state.deque_buffer.dequeue_batch(100)
        for job in batch:
            await state.event_publisher.publish(job)
        await asyncio.sleep(0.1)  # Yield control

async def retry_loop():
    while True:
        ready = await state.retry_scheduler.get_ready_tasks()
        for task in ready:
            await state.event_publisher.publish(task.payload)
        await asyncio.sleep(1.0)

async def workers_loop():
    await asyncio.gather(
        account_worker.run(),
        location_worker.run(),
        review_worker.run()
    )
```

**Benefits:**
- Single thread, thousands of concurrent operations
- No thread overhead
- Deterministic scheduling

---

## Complete End-to-End Flow

### Phase 1: Token Submission (API → Queue)

```
Step 1: Client submits HTTP request
┌────────────────────────────────────────────┐
│ POST /api/v1/review-fetch                  │
│ {                                          │
│   "access_token": "ya29.xxxxx",            │
│   "account_id": "123456"                   │
│ }                                          │
└────────────────────────────────────────────┘

Step 2: FastAPI handler validates input
├─ Pydantic validates schema
├─ Checks token format (must start with "ya29")
└─ Returns 400 if invalid

Step 3: Create job object
├─ job_id = uuid4()
├─ job_data = {
│    "job_id": "abc123def456",
│    "access_token": "ya29.xxxxx",
│    "account_id": "123456",
│    "created_at": "2025-01-07T12:34:56Z",
│    "retry_count": 0,
│    "status": "queued"
│  }
└─ Time: O(1) - just object creation

Step 4: Enqueue into bounded buffer
├─ Acquire async lock
├─ Check if space available
│  ├─ If queue_size >= 10000:
│  │  └─ Return 429 Too Many Requests
│  └─ Else: Continue
├─ deque.append(job_data)
├─ Release lock
├─ Increment metrics counter
└─ Time: O(1) - lock + append

Step 5: Return response to client
└─ {
     "job_id": "abc123def456",
     "status": "queued",
     "created_at": "2025-01-07T12:34:56Z"
   }

TOTAL TIME: ~1-5ms
```

### Phase 2: Producer Loop (Queue → Kafka Topics)

```
Background Task: Runs every 100ms continuously

Step 1: Check deque buffer (every 100ms)
├─ Acquire lock
├─ Count jobs in queue
└─ Release lock

Step 2: Dequeue batch (O(n) where n ≤ 100)
├─ Acquire lock
├─ Extract up to 100 jobs from left (FIFO)
├─ Release lock
└─ Time: O(100) ≈ constant

Step 3: Rate-limit batch publish (per worker)
For each job in batch:
├─ Check rate limiter: TokenBucketLimiter
│  ├─ Calculate elapsed time since last check
│  ├─ Refill tokens = min(capacity, tokens + refill_rate * elapsed)
│  ├─ Time: O(1)
│  └─ If tokens < 1:
│     └─ Wait or discard
├─ If rate limit allows:
│  └─ Publish to appropriate topic (determined by job type)
└─ Time: O(1) per job

Step 4: Publish to Kafka topics
├─ Topic routing:
│  ├─ Type "fetch_accounts" → "fetch-accounts" topic
│  ├─ Type "fetch_locations" → "fetch-locations" topic
│  └─ Type "fetch_reviews" → "fetch-reviews" topic
├─ Serialize job to JSON
├─ Send to Kafka broker (async)
│  └─ Time: O(1) - fire and forget
├─ Log success/failure
└─ Update metrics

LOOP RUNS: Every 100ms
JOBS PER LOOP: 0-100 jobs
TIME PER LOOP: ~50-500ms depending on network
THROUGHPUT: Up to 1000 jobs/second (100 jobs × 10 loops/sec)
```

### Phase 3: Worker Processing (Kafka → Google API → Output)

```
STAGE 1: Account Worker
═══════════════════════

Input: fetch-accounts topic
│
├─ Worker subscribes to topic
├─ Receives message: { job_id, access_token }
│
├─ Apply rate limiter (10 tokens/sec)
│  └─ O(1) token bucket check
│
├─ Call Google API: get_accounts(access_token)
│  ├─ Make HTTP request with token
│  ├─ Handle 401: Invalid/expired token
│  ├─ Handle 403: No Business Profile API access
│  └─ Handle 500: Retry with exponential backoff
│
├─ Process response: list of accounts
│  ├─ Extract account IDs and names
│  └─ Time: O(m) where m = number of accounts (typically 1-10)
│
├─ For each account:
│  └─ Create location fetch job
│     {
│       "type": "fetch_locations",
│       "job_id": job_id,
│       "account_id": account_123,
│       "account_name": "My Business"
│     }
│
├─ Publish to fetch-locations topic (multiple messages)
│  └─ Time: O(m) async publishes
│
└─ Metrics: accounts_fetched += m


STAGE 2: Location Worker
════════════════════════

Input: fetch-locations topic
│
├─ For each location fetch job:
│
│  ├─ Apply rate limiter (10 tokens/sec)
│  │
│  ├─ Call Google API: get_locations(account_id, access_token)
│  │  └─ Time: O(1) API call
│  │
│  ├─ Parse response: list of locations
│  │  └─ Time: O(k) where k = locations per account
│  │
│  ├─ For each location:
│  │  └─ Create review fetch job
│  │     {
│  │       "type": "fetch_reviews",
│  │       "job_id": job_id,
│  │       "account_id": account_123,
│  │       "location_id": location_456,
│  │       "location_name": "Main Store"
│  │     }
│  │
│  └─ Publish to fetch-reviews topic (multiple)
│
└─ Metrics: locations_fetched += k


STAGE 3: Review Worker
══════════════════════

Input: fetch-reviews topic
│
├─ For each review fetch job:
│
│  ├─ Check if dedup cache exists for this job
│  │  └─ if job_id not in seen_reviews:
│  │       seen_reviews[job_id] = set()
│  │
│  ├─ Apply rate limiter (10 tokens/sec)
│  │  └─ O(1) token bucket
│  │
│  ├─ Call Google API with pagination
│  │  ├─ Fetch page 1 (100 reviews)
│  │  ├─ Fetch page 2 (100 reviews) if exists
│  │  └─ Continue until all pages fetched
│  │  └─ Time: O(1) per page (API call)
│  │
│  ├─ For each review in response:
│  │  ├─ Generate review hash/ID
│  │  ├─ Check dedup: review_id in seen_reviews[job_id]?
│  │  │  └─ Time: O(1) hash set lookup
│  │  ├─ If new:
│  │  │  ├─ Add to seen_reviews[job_id]
│  │  │  ├─ Publish to reviews-raw topic
│  │  │  └─ Increment review_count
│  │  └─ If duplicate:
│  │     └─ Skip (increment dup_count)
│  │
│  ├─ Clear dedup cache after job completes
│  │  └─ del seen_reviews[job_id]
│  │
│  └─ Time per review: O(1) - hash + lookup + publish
│
└─ Metrics: reviews_fetched, duplicates_filtered


OUTPUT STREAM
═════════════
Topic: reviews-raw

Message format (for each unique review):
{
  "job_id": "abc123",
  "account_id": "account_123",
  "location_id": "location_456",
  "review_id": "review_789",
  "rating": 5,
  "text": "Great service!",
  "reviewer_name": "John Doe",
  "review_date": "2025-01-07",
  "source": "google_business_profile"
}

Total reviews output: m × k × p
  where m = accounts, k = locations per account, p = reviews per location
```

### Phase 4: Retry Handling (Failures → Retry Queue)

```
When API call fails:

Step 1: Catch exception
├─ 401 Unauthorized
├─ 403 Forbidden
├─ 500 Server Error
├─ Connection Timeout
└─ Other transient errors

Step 2: Check retry count
├─ if job.retry_count >= 3:
│  └─ Send to reviews-dlq (Dead Letter Queue) → terminal failure
├─ else:
│  ├─ Increment retry_count
│  └─ Calculate next retry time

Step 3: Calculate exponential backoff
├─ Backoff = initial_backoff × (multiplier ^ retry_count)
├─ Backoff = 100ms × (2 ^ 0) = 100ms  (1st retry)
├─ Backoff = 100ms × (2 ^ 1) = 200ms  (2nd retry)
├─ Backoff = 100ms × (2 ^ 2) = 400ms  (3rd retry)
│
└─ Cap at max_backoff = 10,000ms (10 seconds)

Step 4: Insert into retry heap
├─ retry_time = now + backoff_ms
├─ heapq.heappush(retry_heap, (retry_time, message_id, payload))
│  └─ Time: O(log n) where n = pending retries
├─ Log retry with backoff time
└─ Metrics: retries_scheduled++

Step 5: Retry loop checks heap (every 1 second)
├─ Get current time
├─ Extract all tasks where retry_time <= now
│  └─ Time: O(k log n) where k = ready retries
├─ Republish to original topic
├─ Mark retry as completed
└─ Metrics: retries_completed++

TOTAL POSSIBLE RETRIES: 3
TOTAL DELAY: 100ms + 200ms + 400ms = 700ms max
FINAL FAILURE: Goes to reviews-dlq for manual inspection
```

---

## Component Details

### 1. FastAPI Application (main.py)

```python
# Lifespan events
async def lifespan(app: FastAPI):
    # Startup
    state.initialize()
    await start_background_tasks()
    yield
    # Shutdown
    await shutdown_background_tasks()

# Request handler
@app.post("/api/v1/review-fetch")
async def review_fetch(request: FetchJobRequest):
    # Validate token
    token_valid = await google_api_client.validate_token(request.access_token)
    if not token_valid:
        raise HTTPException(401, "Invalid token")
    
    # Create job
    job_id = str(uuid4())
    job = {
        "job_id": job_id,
        "access_token": request.access_token,
        "account_id": request.account_id,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Enqueue
    success = await state.deque_buffer.enqueue(job)
    if not success:
        raise HTTPException(429, "Queue full")
    
    return {
        "job_id": job_id,
        "status": "queued"
    }
```

### 2. Rate Limiter (rate_limiter.py)

```python
class TokenBucketLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity          # 100 tokens
        self.refill_rate = refill_rate   # 10 tokens/second
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
    
    async def acquire(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        # Calculate tokens to add
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
        
        # Check if enough
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

### 3. Deque Buffer (deque_buffer.py)

```python
class BoundedDequeBuffer:
    def __init__(self, max_size: int):
        self._queue = collections.deque(maxlen=max_size)
        self._lock = asyncio.Lock()
    
    async def enqueue(self, item: Any) -> bool:
        async with self._lock:
            if len(self._queue) >= self.max_size:
                return False  # Queue full
            self._queue.append(item)
            return True
    
    async def dequeue_batch(self, batch_size: int) -> list:
        async with self._lock:
            batch = []
            for _ in range(min(batch_size, len(self._queue))):
                batch.append(self._queue.popleft())
            return batch
```

### 4. Retry Scheduler (retry.py)

```python
class RetryScheduler:
    def __init__(self, policy: ExponentialBackoffPolicy):
        self._retry_heap = []
        self.policy = policy
    
    async def schedule_retry(self, task: RetryTask) -> None:
        # Calculate next retry time
        backoff = self.policy.get_backoff(task.retry_count)
        retry_time = time.time() + backoff / 1000  # Convert ms to seconds
        
        # Insert into min-heap
        heapq.heappush(
            self._retry_heap,
            (retry_time, task.message_id, task.payload)
        )
    
    async def get_ready_tasks(self) -> List[RetryTask]:
        now = time.time()
        ready = []
        
        # Extract all tasks ready to retry
        while self._retry_heap and self._retry_heap[0][0] <= now:
            retry_time, message_id, payload = heapq.heappop(self._retry_heap)
            ready.append(RetryTask(message_id, payload))
        
        return ready
```

---

## Error Handling

### Error Categories

```
1. CLIENT ERRORS (4xx)
   ├─ 400 Bad Request
   │  └─ Invalid token format, missing fields
   ├─ 401 Unauthorized
   │  └─ Token invalid/expired
   └─ 429 Too Many Requests
      └─ Queue full

2. SERVER ERRORS (5xx)
   ├─ 500 from Google API
   │  └─ Scheduled for retry
   ├─ 503 Service Unavailable
   │  └─ Scheduled for retry
   └─ Connection errors
      └─ Scheduled for retry

3. KAFKA ERRORS
   ├─ Connection lost
   │  └─ Reconnect with backoff
   ├─ Topic not found
   │  └─ Auto-create or fail
   └─ Broker unavailable
      └─ Queue locally, retry

4. PROCESSING ERRORS
   ├─ Malformed JSON
   │  └─ Log and discard
   ├─ Missing required fields
   │  └─ Log and discard
   └─ Unexpected data format
      └─ Log and discard
```

### Retry Strategy

```
Attempt 1: Immediate
   ↓ Fails
Attempt 2: Wait 100ms
   ↓ Fails
Attempt 3: Wait 200ms
   ↓ Fails
Attempt 4: Wait 400ms
   ↓ Fails
Dead Letter Queue: reviews-dlq
   └─ Manual inspection required
```

### Dead Letter Queue (DLQ)

```
reviews-dlq topic contains:
{
  "original_message": { job data },
  "error": "Max retries exceeded",
  "last_error_detail": "401 Unauthorized",
  "retry_count": 3,
  "failed_at": "2025-01-07T12:45:30Z"
}

Operations:
├─ Monitor DLQ for failures
├─ Investigate token validity
├─ Replay after fixing issues
└─ Metrics: dlq_messages_count
```

---

## Performance Characteristics

### Time Complexity

```
Operation                       | Complexity | Notes
────────────────────────────────────────────────────
Enqueue job                     | O(1)       | Append to deque
Dequeue batch                   | O(n)       | n ≤ 100, effectively O(1)
Rate limit check                | O(1)       | Token bucket calculation
Retry scheduling                | O(log k)   | k = pending retries
Dedup check                     | O(1)       | Hash set lookup
Producer batch publish          | O(n)       | n = batch size
Worker event processing         | O(1)       | Per message
────────────────────────────────────────────────────
```

### Space Complexity

```
Component              | Space | Scaling
─────────────────────────────────────────
Deque buffer          | O(n)  | n = max 10,000 jobs
Retry heap            | O(k)  | k = in-flight retries
Dedup cache           | O(r)  | r = unique reviews per job
Rate limiters (3)     | O(1)  | Constant per limiter
Metrics               | O(1)  | Fixed counters
─────────────────────────────────────────
```

### Throughput Estimates

```
Single Instance:

Producer Loop: 100ms cycle
  └─ 100 jobs/batch × 10 cycles/sec = 1,000 jobs/sec max

Rate Limiter: 10 tokens/sec per worker
  └─ 3 workers × 10 = 30 API calls/sec max

Bottleneck: Google API rate limit (10 req/sec)
  └─ Actual throughput: ~30-50 reviews/second per instance
     (3 stages × ~10 req/sec with typical pagination)

Scaling:
  └─ Deploy N instances
  └─ Load balance API requests
  └─ Shared Kafka cluster
  └─ Linear scaling up to Kafka limit
```

### Resource Usage

```
Memory per instance:
  ├─ Deque buffer (10,000 jobs): ~10MB
  ├─ Retry heap (estimated 100 retries): ~1MB
  ├─ Dedup cache (estimated 1,000 reviews): ~5MB
  ├─ Python runtime: ~50MB
  └─ Total: ~70-100MB

CPU per instance:
  ├─ Idle: <1%
  ├─ Active processing: 10-30%
  ├─ Peak burst: 50-60%
  └─ Mostly waiting on I/O

Network per instance:
  ├─ Kafka publish/consume: 1-5 Mbps
  ├─ Google API calls: 100-500 Kbps
  └─ Total: 1-6 Mbps
```

---

## Monitoring & Observability

### Key Metrics

```python
Metrics tracked:
├─ queue_size                  # Current jobs in buffer
├─ queue_max_size              # Peak since startup
├─ jobs_enqueued_total         # Cumulative
├─ jobs_rejected_total         # Queue full events
├─ reviews_fetched_total       # Output count
├─ reviews_deduplicated_total  # Filtered duplicates
├─ retries_scheduled_total     # Retry events
├─ retries_completed_total     # Successful retries
├─ dlq_messages_total          # Final failures
├─ rate_limit_throttles        # Times rate limited
└─ api_call_latency_ms         # P50, P95, P99
```

### Logging

```
Log levels:
├─ DEBUG: Token validation, rate limit checks, dedup hits
├─ INFO: Job creation, batch published, retry scheduled
├─ WARNING: Rate limit exceeded, token invalid, retry exhausted
└─ ERROR: API failures, connection errors, unexpected exceptions

Structured logging (JSON):
{
  "timestamp": "2025-01-07T12:45:30Z",
  "level": "INFO",
  "message": "job_published_to_kafka",
  "job_id": "abc123",
  "topic": "fetch-accounts",
  "batch_size": 42,
  "duration_ms": 125
}
```

---

## Summary

### Complete Request Lifecycle

```
1. Client submits token     (1-5ms)
   └─ Enqueued in buffer

2. Producer publishes       (Every 100ms)
   └─ Batches sent to Kafka

3. Workers process          (Concurrent)
   ├─ Account Worker: Lists accounts
   ├─ Location Worker: Lists locations
   └─ Review Worker: Fetches & dedupes reviews

4. Output to reviews-raw    (Real-time)
   └─ Downstream systems consume

5. Failures retry           (Exponential backoff)
   └─ Up to 3 attempts, then DLQ

Total Time: Seconds to minutes depending on account size
Throughput: 30-50 reviews/second per instance
Reliability: 99.99% with proper error handling
```

### Design Strengths

✅ **Scalable:** Horizontal scaling via Kafka partitioning
✅ **Resilient:** Exponential backoff retry, DLQ for visibility
✅ **Rate-Limited:** Token bucket per worker respects API limits
✅ **Deduplicated:** Hash set ensures unique output
✅ **Observable:** Structured logging, detailed metrics
✅ **Testable:** Factory pattern enables mocking
✅ **Maintainable:** Clear separation of concerns, design patterns
✅ **Async-Native:** Built on asyncio for thousands of concurrent jobs
