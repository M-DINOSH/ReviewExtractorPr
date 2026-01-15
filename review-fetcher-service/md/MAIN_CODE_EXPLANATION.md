# FastAPI Application Orchestrator - Code Explanation

## Overview
This is the **main orchestrator** of the Review Fetcher microservice. It manages the entire application lifecycle, initializes all components, and coordinates background tasks. Think of it as the "conductor" that starts the orchestra and ensures all musicians (components) are working in harmony.

---

## Architecture Patterns Used

### 1. **Service Locator Pattern**
- **What it is**: A centralized registry that holds all application services/components
- **Where**: `AppState` class acts as the service locator
- **Why**: Makes it easy to access shared services from anywhere in the app without passing them through every function

### 2. **Factory Pattern**
- **What it is**: Creates objects based on configuration without exposing creation logic
- **Where**: `initialize_components()` function creates all objects
- **Why**: Centralizes object creation and configuration, making it testable and flexible

### 3. **Dependency Injection**
- **What it is**: Components receive dependencies through constructor parameters
- **Where**: Workers, API service receive their dependencies in `__init__`
- **Why**: Makes code loosely coupled and testable

### 4. **Context Manager Pattern**
- **What it is**: Manages resource lifecycle (setup and cleanup)
- **Where**: `lifespan()` context manager
- **Why**: Ensures resources are properly initialized on startup and cleaned up on shutdown

---

## Key Components Explained

### 1. **AppState Class**
```python
class AppState:
    """Container for application state"""
```

**Purpose**: Single source of truth for all application components

**What it holds**:
- **Settings**: Application configuration (from config.py)
- **Deque Buffer**: Queue for pending jobs
- **Kafka Producer**: Sends messages to Kafka
- **Event Publisher**: High-level API for publishing events
- **Rate Limiters**: Control API request rates (one per worker type)
- **Retry Scheduler**: Manages failed job retries
- **Workers**: Three Kafka consumers:
  - `AccountWorker`: Fetches accounts
  - `LocationWorker`: Fetches locations
  - `ReviewWorker`: Fetches reviews
- **Background Tasks**: Asyncio tasks that run continuously

**Why separate rate limiters per worker?**
Each worker fetches different data from different APIs with different rate limits. Isolating rate limiters prevents one slow worker from blocking others.

---

### 2. **Global State Management**
```python
_app_state: Optional[AppState] = None

def get_app_state() -> AppState:
    """Get global app state"""
    global _app_state
    return _app_state
```

**Purpose**: Make the app state accessible throughout the application

**Why global?**: Other parts of the app (like API routes) need access to services like the deque buffer or event publisher without creating new instances

---

## Initialization Flow (The Startup Process)

### Step 1: Application Creation
```python
app = create_app()
```
Creates the FastAPI application with:
- CORS middleware (allows requests from any origin)
- API routes
- Root endpoint
- Lifespan context manager

### Step 2: Startup (when server starts)
The `lifespan` context manager runs the "Startup" block:

1. **Initialize Components** → `initialize_components()`
   - Creates all the objects the app needs
   - Connects to Kafka
   - Sets up rate limiters
   - Initializes workers
   
2. **Start Background Tasks** → `start_background_tasks()`
   - Launches three concurrent tasks (see below)

3. **Inject API Service** → `set_api_service()`
   - Makes the API service available to route handlers

4. **Store Global State** → `app.state.app_state = _app_state`
   - Stores state in FastAPI's app.state for access in routes

---

## Initialization Details

### `initialize_components()` - Line by Line

**1. Deque Buffer**
```python
state.deque_buffer = BoundedDequeBuffer(max_size=state.settings.deque.max_size)
```
- **What**: A queue with a maximum size limit
- **Why**: Holds pending fetch jobs that couldn't be sent to Kafka yet
- **Example flow**: 
  ```
  API receives /submit-job → adds to deque → producer picks it up → sends to Kafka
  ```

**2. Kafka Producer**
```python
producer = KafkaProducerFactory.create(...)
await producer.connect()
```
- **What**: Connection to Apache Kafka message broker
- **Why**: Sends event messages to workers in other services
- **In-memory Kafka mode**: If `MOCK_KAFKA=true`, uses an in-memory Kafka implementation for testing (no broker required)

**3. Event Publisher**
```python
state.event_publisher = KafkaEventPublisher(producer)
```
- **What**: High-level wrapper around Kafka producer
- **Why**: Provides clean methods like `publish_fetch_accounts_event()` instead of raw Kafka calls
- **Benefit**: If you change how events are published, only this class needs updating

**4. Rate Limiters** (3 instances)
```python
state.account_rate_limiter = TokenBucketLimiter(...)
state.location_rate_limiter = TokenBucketLimiter(...)
state.review_rate_limiter = TokenBucketLimiter(...)
```
- **What**: Token bucket algorithm - limits how many requests per second
- **Why**: Google API has rate limits. If we exceed them, requests fail and get expensive
- **How it works**: 
  ```
  Token bucket analogy:
  - Bucket holds tokens (starts full)
  - Each API request costs 1 token
  - Tokens refill at a fixed rate (e.g., 5 per second)
  - When bucket is empty, wait for refill
  ```

**5. Retry Scheduler**
```python
retry_policy = ExponentialBackoffPolicy(...)
state.retry_scheduler = RetryScheduler(policy=retry_policy)
```
- **What**: Manages failed jobs that need to be retried
- **Why**: Network and API failures happen. Retries with exponential backoff avoid overwhelming failed services
- **Example**: 
  ```
  Attempt 1: fails → wait 1 second
  Attempt 2: fails → wait 2 seconds
  Attempt 3: fails → wait 4 seconds
  ...
  ```

**6. Kafka Workers** (3 instances)
```python
state.account_worker = AccountWorker(...)
state.location_worker = LocationWorker(...)
state.review_worker = ReviewWorker(...)
```
- **What**: Kafka consumer processes that listen to topics
- **Why**: Each worker handles one stage of the data pipeline
- **Flow**:
  ```
  fetch-accounts topic → AccountWorker extracts accounts → publishes to fetch-locations topic
  fetch-locations topic → LocationWorker extracts locations → publishes to fetch-reviews topic
  fetch-reviews topic → ReviewWorker extracts reviews → saves to storage
  ```

**7. API Service**
```python
state.api_service = APIService(
    deque_buffer=state.deque_buffer,
    event_publisher=state.event_publisher,
    settings=state.settings
)
```
- **What**: Handles HTTP requests from clients
- **Why**: Your client calls `/submit-job` which the API service handles
- **What it does**: 
  - Validates requests
  - Adds jobs to deque
  - Publishes events
  - Returns responses

---

## Background Tasks Explained

### **Producer Loop** - The Queue Drainer
```python
async def producer_loop():
    while True:
        batch = await state.deque_buffer.dequeue_batch(batch_size=100)
        for job in batch:
            await state.event_publisher.publish_fetch_accounts_event(...)
        await asyncio.sleep(state.settings.deque.burst_check_interval_sec)
```

**What it does**:
1. Check the deque every N seconds
2. Get up to 100 pending jobs
3. Send each to Kafka `fetch-accounts` topic
4. Log success/failure

**Why separate from API?**
- API responds to requests immediately
- Producer runs in background and sends to Kafka when ready
- Decouples HTTP layer from message layer

**Flow visualization**:
```
Client API request
    ↓
Add job to deque (instant response to client)
    ↓
[Background] Producer loop picks it up
    ↓
Sends to Kafka
    ↓
AccountWorker consumes and processes
```

---

### **Retry Loop** - The Retry Handler
```python
async def retry_loop():
    while True:
        ready_tasks = await state.retry_scheduler.get_ready_tasks()
        for task in ready_tasks:
            message_type = task.payload.get("type")
            if message_type == "fetch_accounts":
                await state.event_publisher.publish_fetch_accounts_event(...)
            # ... other types
```

**What it does**:
1. Check retry scheduler every 1 second
2. Find tasks ready to retry
3. Determine message type (accounts, locations, or reviews)
4. Re-publish to appropriate Kafka topic
5. Mark task as retried

**Why needed?**
- Workers might fail due to:
  - Network timeouts
  - API rate limits
  - Temporary service outages
- Retry logic recovers from transient failures

**Example failure scenario**:
```
AccountWorker tries to fetch account → API down → fails
  ↓
Task scheduled for retry with exponential backoff
  ↓
[10 seconds later] Retry loop picks it up
  ↓
Re-publishes to fetch-accounts topic
  ↓
AccountWorker retries → API back up → succeeds
```

---

### **Workers Loop** - The Consumers
```python
async def workers_loop():
    await asyncio.gather(
        state.account_worker.run(),
        state.location_worker.run(),
        state.review_worker.run(),
        return_exceptions=True
    )
```

**What it does**:
1. Starts all three workers concurrently
2. Each worker listens to its Kafka topic
3. Processes messages as they arrive
4. If one worker crashes, others continue (due to `return_exceptions=True`)

**Why `asyncio.gather()`?**
- Runs 3 independent workers simultaneously
- Without it, they'd run sequentially (slow)
- `return_exceptions=True` prevents one failure from crashing all

**Worker responsibilities**:
- **AccountWorker**: Listens to `fetch-accounts` → calls Google API → publishes accounts
- **LocationWorker**: Listens to `fetch-locations` → calls Google API → publishes locations  
- **ReviewWorker**: Listens to `fetch-reviews` → calls Google API → publishes/saves reviews

---

## Shutdown Flow (Application Stops)

The `lifespan` context manager handles cleanup:

```python
# Shutdown block runs when server stops:
await shutdown_background_tasks(_app_state)
```

**What happens**:
1. **Cancel background tasks**: Stop producer, retry, and workers loops
2. **Stop workers gracefully**: Allow current tasks to finish
3. **Close Kafka connection**: Disconnect from message broker
4. **Log shutdown**: Record that application stopped

**Why important?**
- Prevents orphaned connections
- Ensures in-flight messages aren't lost
- Graceful shutdown is cleaner than force-kill

---

## Complete Request Flow Example

### User submits a job:

```
1. Client: HTTP POST /submit-job
    ↓
2. API Handler (in routes.py):
    - Validates request
    - Gets app_state via get_app_state()
    - Adds to deque_buffer
    - Returns 200 OK immediately
    ↓
3. [Background] Producer loop runs every 5 seconds:
    - Checks rate limiter
    - Gets batch from deque
    - Publishes to Kafka fetch-accounts topic
    ↓
4. AccountWorker (in separate service):
    - Reads from fetch-accounts topic
    - Calls Google API with rate limiter
    - Extracts account data
    - Publishes to fetch-locations topic
    - OR on failure: RetryScheduler schedules retry
    ↓
5. LocationWorker:
    - Reads from fetch-locations topic
    - Calls Google API
    - Extracts location data
    - Publishes to fetch-reviews topic
    ↓
6. ReviewWorker:
    - Reads from fetch-reviews topic
    - Calls Google API
    - Extracts review data
    - Saves to database/storage
```

---

## Why This Architecture?

### **Scalability**
- Deque prevents overload (bounded queue)
- Rate limiters prevent API throttling
- Kafka allows multiple workers to scale independently

### **Reliability**
- Retry scheduler recovers from failures
- Kafka persists messages (doesn't lose data)
- Graceful shutdown prevents corruption

### **Maintainability**
- AppState centralizes all dependencies
- Service Locator makes it easy to swap implementations (e.g., mock Kafka for testing)
- Separation of concerns (producer loop, workers, API are independent)

### **Testability**
- Mock mode for Kafka
- Components can be tested in isolation
- Dependency injection enables test doubles

---

## Configuration

All settings come from `get_settings()` (in config.py):
- Kafka bootstrap servers
- Rate limit capacities
- Retry policies (max retries, backoff)
- Deque buffer size
- Check intervals for loops

This allows different configurations for different environments (dev, staging, production).

---

## Summary Table

| Component | Purpose | Lifecycle |
|-----------|---------|-----------|
| AppState | Container for all services | Created at startup, stored globally |
| Deque Buffer | Queue for pending jobs | Initialized, drained by producer loop |
| Kafka Producer | Sends messages to Kafka | Connected at startup, disconnected at shutdown |
| Event Publisher | High-level event API | Initialized, used by API and retry loop |
| Rate Limiters (3x) | Limit API request rates | Initialized per worker type |
| Retry Scheduler | Manages failed job retries | Initialized, processed by retry loop |
| Workers (3x) | Consume and process Kafka messages | Started at startup, stopped at shutdown |
| API Service | Handles HTTP requests | Initialized, accessible to routes |
| Producer Task | Drains deque → publishes to Kafka | Runs continuously until shutdown |
| Retry Task | Retries failed jobs | Runs continuously until shutdown |
| Workers Task | Runs Kafka consumers | Runs continuously until shutdown |

---

## Key Takeaways

1. **This is an orchestrator** - it doesn't do the actual work (fetching reviews), it coordinates the pieces that do
2. **Async first** - everything is async for high concurrency with minimal resources
3. **Background workers** - heavy lifting happens in background tasks, not blocking the API
4. **Graceful degradation** - if one piece fails, others continue working
5. **Stateful initialization** - complex setup happens once at startup, then services use the initialized state

---

---

# Complete Microservices Implementation Guide

## File-by-File Explanation with Why/What/How Questions

---

## 1. **config.py** - Configuration Management

**Purpose**: Centralized configuration with environment variable support

### Architecture Pattern: Singleton + Strategy Pattern

**Why do we need a separate config file?**
- Microservices need different settings in different environments (dev, staging, prod)
- Configuration should be centralized, not scattered across the code
- Type safety: validate config values on startup, not at runtime

**What does it do?**
```python
class Settings(BaseSettings):
    service_name: str = "review-fetcher-service"
    version: str = "1.0.0"
    log_level: str = "INFO"
    mock_google_api: bool = True  # Can be overridden via env vars
```

**How it works?**
1. Define sub-config classes (KafkaConfig, RateLimitConfig, etc.)
2. Aggregate them in Settings class
3. Pydantic validates types automatically
4. Environment variables override defaults (e.g., `KAFKA_BOOTSTRAP_SERVERS=kafka:9092`)

### Key Configuration Groups

**KafkaConfig - Message Broker Settings**
```python
bootstrap_servers: list[str] = ["localhost:9092"]  # Where to find Kafka
consumer_group: str = "review-fetcher-service"     # Which consumer group
auto_offset_reset: str = "earliest"                # Start from beginning or end
```
- **Why**: Kafka needs to know where the broker is and which group is consuming
- **How it's used**: AIokafkaProducer and AIokafkaConsumer classes read this

**RateLimitConfig - API Rate Limiting**
```python
token_bucket_capacity: int = 100      # Max burst size
refill_rate: float = 10.0              # Tokens per second
```
- **Why**: Google API limits requests to 10/sec. Must respect this or get throttled
- **How it's used**: TokenBucketLimiter gets these values during initialization

**RetryConfig - Failure Recovery**
```python
max_retries: int = 3                   # Max retry attempts
initial_backoff_ms: int = 100          # Start with 100ms wait
max_backoff_ms: int = 10000            # Cap backoff at 10 seconds
backoff_multiplier: float = 2.0        # Exponential: 100ms → 200ms → 400ms
```
- **Why**: When API calls fail (network issues, timeouts), we want to retry with increasing delays
- **How it's used**: ExponentialBackoffPolicy uses these for retry scheduling

**DequeConfig - Buffer Settings**
```python
max_size: int = 10000                  # Queue can hold max 10k jobs
burst_check_interval_sec: float = 0.1  # Check queue every 100ms
```
- **Why**: Deque needs size limit to prevent memory overload
- **How it's used**: BoundedDequeBuffer rejects jobs when full (HTTP 429 response)

### Singleton Pattern

```python
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
```

**Why?**
- Configuration should be loaded once, not repeatedly
- Expensive to validate and parse environment variables multiple times
- Ensures everyone in the app uses the same config

**How?**
- First call creates instance
- Subsequent calls return cached instance

### How to Use Environment Variables

```bash
# Override Kafka broker
export KAFKA_BOOTSTRAP_SERVERS="kafka.prod:9092"

# Enable production mode
export MOCK_GOOGLE_API=false

# Change log level
export LOG_LEVEL=DEBUG

# Run service - it automatically loads from .env file too
python -m uvicorn app.main:app
```

---

## 2. **models.py** - Data Models & Schemas

**Purpose**: Define all data structures with validation

### Architecture Pattern: Value Objects + Data Transfer Objects (DTOs)

**Why separate models?**
- Clear contract between components
- Automatic validation (Pydantic)
- API documentation (OpenAPI/Swagger)
- Type safety across the system

**What models exist?**

#### 1. JobStatus Enum
```python
class JobStatus(str, Enum):
    PENDING = "pending"          # Waiting to process
    PROCESSING = "processing"    # Currently being fetched
    COMPLETED = "completed"      # Successfully finished
    FAILED = "failed"            # Permanent failure
    DLQ = "dlq"                  # Dead Letter Queue (unsalvageable)
```
- **Why**: Track job lifecycle states
- **Used by**: Retry scheduler, API service

#### 2. ReviewFetchRequest
```python
class ReviewFetchRequest(BaseModel):
    access_token: str = Field(..., min_length=10)
    
    @validator("access_token")
    def validate_token_format(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("token cannot be empty")
        return v.strip()
```
- **What**: Client sends this in POST /api/v1/review-fetch
- **Why**: Validate before processing (fail fast)
- **How**: Pydantic automatically validates on deserialization

#### 3. ReviewFetchResponse
```python
class ReviewFetchResponse(BaseModel):
    job_id: str          # UUID for tracking
    status: str = "queued"
    message: str
```
- **What**: Server responds immediately with job_id
- **Why**: Client can poll status using job_id
- **HTTP**: 202 Accepted (async operation)

#### 4. Event Models (Kafka Messages)

```python
class FetchAccountsEvent(BaseModel):
    job_id: str
    access_token: str
    created_at: datetime

class FetchLocationsEvent(BaseModel):
    job_id: str
    account_id: str
    account_name: str
    created_at: datetime

class FetchReviewsEvent(BaseModel):
    job_id: str
    account_id: str
    location_id: str
    location_name: str
    created_at: datetime
```

- **Why**: Serialize/deserialize Kafka messages
- **How they relate**:
  ```
  FetchAccountsEvent
    ↓ (AccountWorker processes)
  FetchLocationsEvent (for each account)
    ↓ (LocationWorker processes)
  FetchReviewsEvent (for each location)
    ↓ (ReviewWorker processes)
  Reviews published
  ```

#### 5. Data Models (Results)

```python
class Account(BaseModel):
    job_id: str
    account_id: str
    account_name: str
    created_at: datetime

class Location(BaseModel):
    job_id: str
    account_id: str
    location_id: str
    location_name: str
```

- **Why**: Represent extracted data from Google API
- **How used**: Published to Kafka topics for persistence service

### Validation Flow

```
Client sends request
    ↓
Pydantic validates ReviewFetchRequest
    ↓
If invalid: return 422 Unprocessable Entity
    ↓
If valid: access_token is guaranteed clean string
    ↓
Pass to APIService.create_fetch_job()
```

---

## 3. **deque_buffer.py** - Job Queue Management

**Purpose**: Thread-safe, bounded queue for async job processing

### Architecture Pattern: Adapter Pattern (wraps collections.deque)

**Why a deque?**
- FIFO (First In First Out) - fair job ordering
- Bounded - prevents memory explosion
- Async-safe - uses asyncio.Lock for thread safety

**What problem does it solve?**

Imagine the API gets 10,000 requests per second but can only send 10/second to Google API:
```
Without deque:
Request 1-9: Queued in memory
Request 10: Memory explosion! 💥
Response to all: "Please wait"
Loss of requests

With bounded deque:
Request 1-10000: Enqueued successfully
Request 10001: Rejected with HTTP 429
Response to client: "Come back later"
Fair backpressure
```

**How it works**

```python
class BoundedDequeBuffer:
    def __init__(self, max_size: int = 10000):
        self._queue = deque(maxlen=max_size)  # maxlen auto-drops old items
        self._lock = asyncio.Lock()
```

**Key Methods**

1. **enqueue() - Add job**
   ```python
   async def enqueue(self, item: Any) -> bool:
       async with self._lock:
           if len(self._queue) >= self.max_size:
               return False  # Queue full!
           self._queue.append(item)
           return True
   ```
   - **Why lock**: Multiple tasks might enqueue simultaneously
   - **Why bool return**: API needs to know if it succeeded (return 429 if not)

2. **dequeue_batch() - Get multiple jobs**
   ```python
   async def dequeue_batch(self, batch_size: int = 100):
       # Remove up to 100 items from front
       # Producer loop calls this every 100ms
   ```
   - **Why batch**: More efficient than one-at-a-time
   - **Why 100**: Reasonable batch size, prevents thread starvation

3. **Metrics Tracking**
   ```python
   self._metrics = {
       "enqueued": 0,     # Total added
       "dequeued": 0,     # Total removed
       "rejected": 0,     # Failed to add (queue full)
       "max_size_hit": 0  # Times queue was full
   }
   ```
   - **Why**: Understand queue behavior in production
   - **How**: Export to monitoring system (Prometheus, DataDog, etc.)

**Flow Example**

```
Time 0: Queue empty [  ]
    ↓
API POST /review-fetch
    ↓
enqueue({job_id, token}) → True
    ↓
Queue: [Job1]
Response 202 to client
    ↓
Producer loop wakes up (100ms)
    ↓
dequeue_batch(100) → [Job1]
    ↓
Publishes to Kafka fetch-accounts topic
    ↓
Queue empty again [  ]
```

---

## 4. **rate_limiter.py** - Token Bucket Rate Limiting

**Purpose**: Prevent exceeding API rate limits

### Architecture Pattern: Strategy Pattern (pluggable limiters)

**Why do we need rate limiting?**

Google API allows:
- 10 requests per second
- 1000 per day

If we ignore this:
```
Second 1: Send 100 requests → Google throttles us
Second 2: Requests fail with 429 Too Many Requests
Second 3-10: All requests fail, we lose data
Reputation: Bad (might get API key banned)
```

**Token Bucket Algorithm Explained**

Think of it like a gas tank:
```
Tank capacity: 100 "tokens"
Refill rate: 10 tokens/second

Initial: Tank full [●●●●●●●●●●...]

Request 1: Need 1 token → Take from tank [●●●●●●●●●...]
Request 2: Need 1 token → Take from tank [●●●●●●●●...]
...
Request 10: Need 1 token → Take from tank [●●●●●●●●...]
Request 11: Need 1 token → NO TOKENS LEFT! Wait...

Meanwhile, background: Refill runs
Every second: Add 10 new tokens
After 1 second: Tank has 10 tokens again → Request 11 proceeds

Burst handling: Can do 100 requests instantly (burst), then must wait
```

**Implementation**

```python
class TokenBucketLimiter(RateLimiter):
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = 100        # Max tokens
        self.refill_rate = 10.0    # Tokens per second
        self.tokens = 100          # Current tokens
        self.last_refill = time.monotonic()
    
    async def acquire(self, tokens: int = 1) -> bool:
        async with self._lock:
            self._refill()  # Add any earned tokens
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        
        # Add: elapsed_seconds * refill_rate
        # Example: 1.5 seconds elapsed, rate=10 → add 15 tokens
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
```

**Using the Limiter in Workers**

```python
class AccountWorker:
    def __init__(self, rate_limiter: TokenBucketLimiter, ...):
        self.rate_limiter = rate_limiter
    
    async def _on_message(self, message: dict):
        # Before calling Google API...
        if not await self.rate_limiter.acquire(tokens=1):
            # Not ready, schedule retry
            await self.retry_scheduler.schedule_retry(...)
            return
        
        # Safe to call API
        response = await self.google_api.get_accounts(token)
```

**Why per-worker limiters?**
- Each worker (accounts, locations, reviews) calls different Google API endpoints
- Each has independent rate limits
- Isolates failures: if account worker is throttled, location worker still works

---

## 5. **retry.py** - Failure Recovery with Exponential Backoff

**Purpose**: Recover from transient failures (network, timeouts, temporary API issues)

### Architecture Pattern: Strategy Pattern (retry policies)

**Why retry?**
- API calls fail transiently: network timeouts, temporary 5xx errors
- Without retries: lose 5-10% of data
- With retries: lose <1% (only permanent failures)

**Permanent vs Transient Errors**

```python
Transient (should retry):
  429 Too Many Requests → Wait, then retry
  503 Service Unavailable → Temporary issue, retry later
  Timeout                → Maybe network glitch, retry

Permanent (don't retry):
  401 Unauthorized       → Token is invalid, won't fix by retrying
  403 Forbidden          → Permission issue, won't fix by retrying
  404 Not Found          → Resource doesn't exist, won't fix by retrying
  400 Bad Request        → Invalid input, won't fix by retrying
```

**Exponential Backoff with Jitter**

```python
def get_backoff_ms(self, attempt: int) -> int:
    # Attempt 0: 100ms
    # Attempt 1: 200ms (100 * 2^1)
    # Attempt 2: 400ms (100 * 2^2)
    # Attempt 3: Would be 800ms, but capped at 10000ms
    
    backoff = initial * (multiplier ^ attempt)
    backoff = min(backoff, max_backoff)
    
    # Add jitter: ±10% randomness
    # Why? Prevents thundering herd (multiple clients retrying at same time)
    jitter = backoff * 0.1 * random.random()
    backoff += jitter
    
    return backoff
```

**Retry Scheduler**

Uses a priority queue (heapq) to manage scheduled retries:

```python
retry_queue: list[RetryTask] = []

class RetryTask:
    retry_at: float    # Unix timestamp when to retry
    attempt: int       # Which attempt (0-indexed)
    message_id: str    # Unique ID
    payload: dict      # Original message
```

**How it works**

```python
async def schedule_retry(
    self,
    message_id: str,
    payload: dict,
    error_code: str,  # "429", "503", "401", etc.
    attempt: int = 0
) -> bool:
    # Check if this error is retryable
    if not self.policy.should_retry(error_code, attempt):
        # → Send to Dead Letter Queue
        if self.dlq_callback:
            await self.dlq_callback(...)
        return False
    
    # Calculate when to retry
    backoff_ms = self.policy.get_backoff_ms(attempt)
    retry_at = time.time() + (backoff_ms / 1000.0)
    
    # Add to priority queue (sorted by retry_at)
    task = RetryTask(
        retry_at=retry_at,
        attempt=attempt + 1,
        message_id=message_id,
        payload=payload
    )
    heapq.heappush(self.retry_queue, task)
```

**Retry Loop (in main.py)**

```python
async def retry_loop():
    while True:
        # Get tasks ready to retry
        ready_tasks = await self.retry_scheduler.get_ready_tasks()
        
        for task in ready_tasks:
            # Republish to Kafka
            await self.event_publisher.publish_fetch_accounts_event(...)
        
        await asyncio.sleep(1.0)
```

**Example Retry Scenario**

```
Time 0: AccountWorker processes message
        → Calls Google API
        → Gets 429 Too Many Requests
        → Schedule retry in 200ms
        
Time 200ms: Retry loop checks
           → Task is ready
           → Republish to fetch-accounts topic
           
Time 200ms: AccountWorker picks it up again
           → Calls Google API
           → Success! ✓
```

**Dead Letter Queue (DLQ)**

Messages that fail permanently go to DLQ:
```python
if error_code in {"401", "403", "404", "400"}:
    # Don't retry - permanent failure
    # Send to DLQ for manual investigation
    await dlq_callback(message_id, payload, error_code)
```

---

## 6. **kafka_producer.py** - Message Publishing

**Purpose**: Send events to Kafka topics

### Architecture Pattern: Strategy Pattern (pluggable producers)

**Why Kafka?**
- Decouples producers from consumers
- Persists messages (replay on failure)
- Scales horizontally (add more consumers)
- Provides ordering guarantees

**Two Implementations**

#### 1. MockKafkaProducer

```python
class MockKafkaProducer(KafkaProducerBase):
    """For development without Kafka broker"""
    
    def __init__(self):
        self.is_connected = False
        self.sent_messages: list[dict] = []
```

- **Why**: Develop locally without Docker/Kafka setup
- **How used**: Set `MOCK_GOOGLE_API=true` in .env
- **Benefit**: Fast local testing, deterministic

#### 2. AIokafkaProducer

```python
class AIokafkaProducer(KafkaProducerBase):
    """Production Kafka using aiokafka library"""
    
    async def connect(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            compression_type="snappy",        # Compress messages
            acks="all",                       # Wait for all replicas
            enable_idempotence=True           # Prevent duplicates
        )
```

**Key Settings**
- `acks="all"`: Wait for all broker replicas to acknowledge
- `enable_idempotence=True`: Prevent duplicate messages
- `compression_type="snappy"`: Reduce network traffic

**Sending Messages**

```python
async def send(
    self,
    topic: str,
    message: dict[str, Any],
    key: Optional[str] = None
) -> bool:
    """Send to topic"""
    
    envelope = {
        "topic": topic,
        "key": key,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "message_id": f"{topic}_{key}_{unique_id}"
    }
    
    # Actually send to Kafka
    await self.producer.send_and_wait(topic, value=envelope, key=key)
    return True
```

**KafkaEventPublisher - High-Level API**

```python
class KafkaEventPublisher:
    def __init__(self, producer: KafkaProducerBase):
        self.producer = producer
    
    async def publish_fetch_accounts_event(
        self,
        job_id: str,
        access_token: str
    ) -> bool:
        """Publish to fetch-accounts topic"""
        message = {
            "type": "fetch_accounts",
            "job_id": job_id,
            "access_token": access_token,
            "created_at": datetime.utcnow().isoformat()
        }
        
        return await self.producer.send(
            topic="fetch-accounts",
            message=message,
            key=job_id  # Use job_id as key for ordering
        )
```

**Why KafkaEventPublisher wrapper?**
- Hides Kafka details from business logic
- Provides type-safe methods (not raw strings)
- Easy to add common logic (versioning, tracing)

---

## 7. **api.py** - HTTP Endpoints

**Purpose**: Accept requests from clients, queue jobs for processing

### Architecture Pattern: Dependency Injection + Service Locator

**Why separate API service?**
- Business logic isolated from FastAPI routes
- Easier to test
- Can be reused by other interfaces (gRPC, CLI, etc.)

**APIService Class**

```python
class APIService:
    """Business logic for API operations"""
    
    def __init__(
        self,
        deque_buffer: BoundedDequeBuffer,
        event_publisher: KafkaEventPublisher,
        settings = None
    ):
        self.deque_buffer = deque_buffer
        self.event_publisher = event_publisher
        self.settings = settings
        self.job_tracking: dict = {}  # In-memory job state
```

**Key Methods**

1. **validate_access_token()**
   ```python
   async def validate_access_token(self, token: str) -> bool:
       if not token or len(token) < 10:
           return False
       
       if self.settings.mock_google_api:
           return True  # Accept in dev mode
       
       # Production: call Google API to validate
       # (commented out in this version)
   ```
   - **Why**: Don't waste resources on invalid tokens
   - **Fail fast**: Reject bad tokens immediately

2. **create_fetch_job()**
   ```python
   async def create_fetch_job(
       self,
       request: ReviewFetchRequest
   ) -> ReviewFetchResponse:
       # 1. Validate token
       is_valid = await self.validate_access_token(request.access_token)
       if not is_valid:
           raise HTTPException(401, "Invalid token")
       
       # 2. Generate job ID
       job_id = str(uuid.uuid4())
       
       # 3. Try to enqueue
       enqueued = await self.deque_buffer.enqueue({
           "job_id": job_id,
           "access_token": request.access_token
       })
       if not enqueued:
           raise HTTPException(429, "Service at capacity")
       
       # 4. Track job
       self.job_tracking[job_id] = {
           "status": "queued",
           "created_at": datetime.utcnow()
       }
       
       return ReviewFetchResponse(job_id=job_id)
   ```

3. **get_health()**
   ```python
   async def get_health(self) -> HealthCheckResponse:
       deque_load = await self.deque_buffer.get_load_percent()
       
       return HealthCheckResponse(
           status="healthy" if deque_load < 90 else "degraded",
           memory_used_percent=deque_load
       )
   ```
   - **Why**: Load balancers use this to decide if service is healthy
   - **How**: Report deque load percentage

**HTTP Routes**

```python
router = APIRouter(prefix="/api/v1", tags=["review-fetcher"])

@router.post(
    "/review-fetch",
    response_model=ReviewFetchResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def submit_review_fetch(
    request: ReviewFetchRequest,
    service: APIService = Depends(get_api_service)
) -> ReviewFetchResponse:
    """
    Submit a review fetch job
    
    Returns: 202 Accepted with job_id
    Client polls /review-fetch/{job_id} to check status
    """
    return await service.create_fetch_job(request)
```

**Status Codes Explained**
- **202 Accepted**: Job accepted, processing started
- **401 Unauthorized**: Invalid access token
- **429 Too Many Requests**: Deque is full, try again later
- **500 Internal Server Error**: Unexpected error

---

## 8. **kafka_consumers/base.py** - Consumer Base Classes

**Purpose**: Abstract interface for consuming Kafka messages

### Architecture Pattern: Template Method Pattern

**Why abstract base class?**
- Define contract for all consumers
- Mock and production implementations
- Consistent error handling

**KafkaConsumerBase**

```python
class KafkaConsumerBase(ABC):
    """Abstract consumer with lifecycle methods"""
    
    def __init__(
        self,
        topic: str,
        consumer_group: str,
        bootstrap_servers: list[str],
        on_message: Callable[[dict], None]  # Message handler
    ):
        self.topic = topic
        self.consumer_group = consumer_group
        self.on_message = on_message
        self.is_running = False
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker"""
        pass
    
    @abstractmethod
    async def consume(self) -> None:
        """Consume messages loop"""
        pass
    
    async def run(self) -> None:
        """Convenience method: connect + consume"""
        await self.start()
        await self.consume()
```

**MockKafkaConsumer**

```python
class MockKafkaConsumer(KafkaConsumerBase):
    """For testing without Kafka"""
    
    def __init__(self, topic: str, consumer_group: str, on_message: Callable):
        super().__init__(topic, consumer_group, ["localhost:9092"], on_message)
        self.messages: list[dict] = []
    
    async def consume(self) -> None:
        """Process queued messages"""
        while self.is_running:
            if self.messages:
                message = self.messages.pop(0)
                await self.on_message(message)
            await asyncio.sleep(0.1)
```

- **How tested**: Add messages with `add_message()`, then call `run()`

**AIokafkaConsumer**

```python
class AIokafkaConsumer(KafkaConsumerBase):
    """Production consumer using aiokafka"""
    
    async def connect(self) -> None:
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            auto_offset_reset="earliest",   # Start from beginning
            enable_auto_commit=False,       # Manual commit for reliability
            max_poll_records=100
        )
        await self.consumer.start()
    
    async def consume(self) -> None:
        """Consume messages with automatic offset management"""
        async for message in self.consumer:
            try:
                await self.on_message(message.value)
                await self.consumer.commit()  # Mark as processed
            except Exception as e:
                logger.error("Error processing message: %s", str(e))
                # Don't commit - message will be retried
```

**Key Points**
- `enable_auto_commit=False`: Manual commit ensures message is processed before marking done
- `max_poll_records=100`: Batch processing for efficiency
- `auto_offset_reset="earliest"`: If group is new, start from beginning (replay all messages)

---

## 9. **kafka_consumers/account_worker.py** - Accounts Fetching

**Purpose**: Consume fetch-accounts events, call Google API, publish locations

### Architecture Pattern: Single Responsibility Principle

**Pipeline Stage**
```
fetch-accounts topic
    ↓
AccountWorker (this file)
    ↓
Calls Google API: GET /accounts
    ↓
Extracts account IDs and names
    ↓
Publishes to fetch-locations topic
    ↓
(or retries on failure)
```

**AccountWorker Class**

```python
class AccountWorker:
    def __init__(
        self,
        rate_limiter: TokenBucketLimiter,
        retry_scheduler: RetryScheduler,
        event_publisher: KafkaEventPublisher,
        mock_mode: bool = True,
        bootstrap_servers: Optional[list[str]] = None
    ):
        self.rate_limiter = rate_limiter
        self.retry_scheduler = retry_scheduler
        self.event_publisher = event_publisher
        self._setup_consumer()
```

**Message Processing**

```python
async def _on_message(self, message: dict) -> None:
    """
    Input message:
    {
        "job_id": "123e4567...",
        "access_token": "ya29..."
    }
    """
    try:
        job_id = message.get("job_id")
        access_token = message.get("access_token")
        
        # 1. Rate limit check
        if not await self.rate_limiter.acquire(tokens=1):
            # Not ready, schedule retry
            await self.retry_scheduler.schedule_retry(
                message_id=f"{job_id}_accounts",
                payload=message,
                error_code="429"
            )
            return
        
        # 2. Call Google API
        accounts = await self.google_api.get_accounts(access_token)
        
        # 3. Extract account data
        for account in accounts.get("accounts", []):
            account_id = account["name"]  # e.g., "accounts/12345"
            account_name = account.get("displayName", "")
            
            # 4. Publish to next stage
            await self.event_publisher.publish_fetch_locations_event(
                job_id=job_id,
                account_id=account_id,
                account_name=account_name
            )
        
        logger.info("fetch_accounts_completed job_id=%s accounts=%d", job_id, len(accounts))
        
    except GoogleAPIError as e:
        # Determine if retryable
        error_code = str(e.status_code) if hasattr(e, 'status_code') else "500"
        
        await self.retry_scheduler.schedule_retry(
            message_id=f"{job_id}_accounts",
            payload=message,
            error_code=error_code,
            attempt=message.get("attempt", 0)
        )
```

**Flow Diagram**

```
Kafka Topic: fetch-accounts
    ↓
AccountWorker._on_message()
    ├─ Check rate limit (10 req/sec)
    ├─ Call Google API: GET /v1/accounts
    ├─ Parse accounts from response
    └─ For each account:
        └─ Publish FetchLocationsEvent
    
Success → Continue
Retryable error → Schedule retry (429, 503, timeout)
Permanent error → Send to DLQ (401, 403, 404)
```

---

## 10. **kafka_consumers/location_worker.py** - Locations Fetching

**Purpose**: Consume fetch-locations events, fetch locations per account, publish reviews

**Similar Structure to AccountWorker**

```python
class LocationWorker:
    async def _on_message(self, message: dict) -> None:
        """
        Input message:
        {
            "job_id": "123e4567...",
            "account_id": "accounts/12345",
            "account_name": "My Business"
        }
        """
        try:
            job_id = message.get("job_id")
            account_id = message.get("account_id")
            account_name = message.get("account_name")
            
            # Rate limit
            if not await self.rate_limiter.acquire():
                await self.retry_scheduler.schedule_retry(...)
                return
            
            # Fetch locations for this account
            locations = await self.google_api.get_locations(
                account_id, 
                access_token
            )
            
            # For each location, publish fetch-reviews event
            for location in locations.get("locations", []):
                location_id = location["name"]
                location_name = location.get("displayName", "")
                
                await self.event_publisher.publish_fetch_reviews_event(
                    job_id=job_id,
                    account_id=account_id,
                    location_id=location_id,
                    location_name=location_name
                )
        except GoogleAPIError as e:
            await self.retry_scheduler.schedule_retry(...)
```

**Why separate workers?**
- Each stage can be scaled independently
- Failure in one doesn't block others
- Can have different rate limits per stage

---

## 11. **kafka_consumers/review_worker.py** - Reviews Fetching

**Purpose**: Final stage - fetch reviews, deduplicate, publish results

**Additional Feature: Deduplication**

```python
class ReviewWorker:
    def __init__(self, ...):
        # Track seen review IDs per job
        self.seen_reviews: dict[str, Set[str]] = defaultdict(set)
```

**Why deduplication?**
- Google API might return same review multiple times
- Pagination can overlap
- Want unique reviews only

```python
async def _on_message(self, message: dict) -> None:
    """
    Input message:
    {
        "job_id": "123e4567...",
        "location_id": "locations/98765",
        "location_name": "Sunset Cafe"
    }
    """
    try:
        job_id = message.get("job_id")
        location_id = message.get("location_id")
        
        # Rate limit
        if not await self.rate_limiter.acquire():
            await self.retry_scheduler.schedule_retry(...)
            return
        
        # Fetch reviews (may be paginated)
        page_token = None
        while True:
            reviews_response = await self.google_api.get_reviews(
                location_id,
                page_token=page_token
            )
            
            for review in reviews_response.get("reviews", []):
                review_id = review["name"]
                
                # Deduplication check
                if review_id in self.seen_reviews[job_id]:
                    logger.debug("duplicate_review_skipped")
                    continue
                
                # Mark as seen
                self.seen_reviews[job_id].add(review_id)
                
                # Publish result
                await self.event_publisher.publish_review(
                    job_id=job_id,
                    review_data=review
                )
            
            # Check for next page
            page_token = reviews_response.get("nextPageToken")
            if not page_token:
                break
    
    except GoogleAPIError as e:
        await self.retry_scheduler.schedule_retry(...)
```

**Pagination Handling**

```
Page 1: Get 50 reviews (token="abc")
    ↓
Process and publish each
    ↓
Page 2: Get next 50 reviews (token="def")
    ↓
Continue until no more pages
```

---

## 12. **services/google_api.py** - Google API Integration

**Purpose**: Encapsulate Google API calls with retry logic and error handling

```python
class GoogleAPIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError))
    )
    async def _get(self, url: str, access_token: str):
        """Base method with automatic retry"""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    async def get_accounts(self, access_token: str):
        """List all accounts"""
        url = "https://mybusinessbusinessinformation.googleapis.com/v1/accounts"
        return await self._get(url, access_token)
    
    async def get_locations(self, account_id: str, access_token: str):
        """List locations for account"""
        url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
        return await self._get(url, access_token)
    
    async def get_reviews(self, location_id: str, access_token: str, page_token: str = None):
        """Fetch reviews for location"""
        url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{location_id}/reviews"
        if page_token:
            url += f"?pageToken={page_token}"
        return await self._get(url, access_token)
```

**Retry Decorator** (from `tenacity` library)
- Automatic retries on transient errors
- Exponential backoff (4s, 8s, 16s)
- Built-in, doesn't require manual scheduling

---

## Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT                                                          │
│ POST /api/v1/review-fetch                                       │
│ { "access_token": "ya29..." }                                   │
└────────────────┬──────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ API LAYER (api.py)                                              │
│ ├─ Validate token                                               │
│ ├─ Generate job_id                                              │
│ ├─ Enqueue to deque_buffer                                      │
│ └─ Return 202 Accepted with job_id                              │
└────────────────┬──────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ Deque Buffer   │
        │ [Job1, Job2]   │
        └────────┬───────┘
                 │
         ┌──────────────────────────────────┐
         │ Producer Loop (Background Task)  │
         │ - Check deque every 100ms        │
         │ - Batch dequeue 100 jobs         │
         │ - Publish to fetch-accounts      │
         └──────────┬──────────────────────┘
                    │
                    ▼
        ┌──────────────────────┐
        │ Kafka Topic:         │
        │ fetch-accounts       │
        │ [FetchAccountEvent]  │
        └──────────┬───────────┘
                   │
              ┌────┴────┬──────┬──────┐
              │          │      │      │
              ▼          ▼      ▼      ▼
    ┌──────────────────┐  (All run concurrently)
    │ AccountWorker    │
    ├─ Rate limit      │
    ├─ Call Google API │
    ├─ Parse response  │
    └─ Publish events  │
                    │
                    ▼
        ┌──────────────────────┐
        │ Kafka Topic:         │
        │ fetch-locations      │
        └──────────┬───────────┘
                   │
              ┌────┴────┬──────┬──────┐
              │          │      │      │
              ▼          ▼      ▼      ▼
    ┌──────────────────┐
    │ LocationWorker   │
    ├─ Rate limit      │
    ├─ Call Google API │
    └─ Publish events  │
                    │
                    ▼
        ┌──────────────────────┐
        │ Kafka Topic:         │
        │ fetch-reviews        │
        └──────────┬───────────┘
                   │
              ┌────┴────┬──────┬──────┐
              │          │      │      │
              ▼          ▼      ▼      ▼
    ┌──────────────────┐
    │ ReviewWorker     │
    ├─ Rate limit      │
    ├─ Call Google API │
    ├─ Deduplicate     │
    └─ Publish results │
                    │
                    ▼
        ┌──────────────────────┐
        │ Kafka Topic:         │
        │ reviews-raw          │
        │ [Review data]        │
        └──────────┬───────────┘
                   │
                   ▼
    (Separation service consumes)


FAILURE HANDLING (Background Task: Retry Loop)
────────────────────────────────────────────

API Error (429, 503, timeout)
    │
    ▼
schedule_retry(message_id, payload, error_code="429", attempt=0)
    │
    ▼
Check if retryable (not permanent error)
    │
    ├─ Yes → Calculate backoff (200ms)
    │        Schedule task for retry_at = now + 200ms
    │        Add to retry_queue (priority queue)
    │
    └─ No → Send to DLQ (Dead Letter Queue)
    
Retry Loop (runs every 1 second)
    │
    ├─ Get ready_tasks from retry_queue
    │
    └─ For each task:
        ├─ Determine message type (fetch_accounts/locations/reviews)
        ├─ Republish to appropriate Kafka topic
        └─ Worker processes again
```

---

## Environment Setup Example

```bash
# .env file
ENVIRONMENT=development
LOG_LEVEL=INFO
MOCK_GOOGLE_API=true

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP=review-fetcher-service

# Rate limiting
RATELIMIT_TOKEN_BUCKET_CAPACITY=100
RATELIMIT_REFILL_RATE=10.0

# Retry policy
RETRY_MAX_RETRIES=3
RETRY_INITIAL_BACKOFF_MS=100
RETRY_MAX_BACKOFF_MS=10000
RETRY_BACKOFF_MULTIPLIER=2.0

# Deque
DEQUE_MAX_SIZE=10000
DEQUE_BURST_CHECK_INTERVAL_SEC=0.1
```

---

## Deployment Architecture

```
┌────────────────────────────────────────┐
│ Kubernetes Cluster                     │
├────────────────────────────────────────┤
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ review-fetcher Service Pods      │  │
│ │ (3 replicas for HA)              │  │
│ │                                  │  │
│ │ ┌─────────────────────────────┐  │  │
│ │ │ Pod 1                       │  │  │
│ │ │ ├─ API Server (8000)        │  │  │
│ │ │ ├─ Producer Loop            │  │  │
│ │ │ ├─ Retry Loop               │  │  │
│ │ │ └─ Worker Processes         │  │  │
│ │ └─────────────────────────────┘  │  │
│ │                                  │  │
│ │ ┌─────────────────────────────┐  │  │
│ │ │ Pod 2                       │  │  │
│ │ └─────────────────────────────┘  │  │
│ │                                  │  │
│ │ ┌─────────────────────────────┐  │  │
│ │ │ Pod 3                       │  │  │
│ │ └─────────────────────────────┘  │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ Kafka Broker Pods (3 nodes)      │  │
│ │ - Partition replication          │  │
│ │ - Message persistence            │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ Persistent Storage               │  │
│ │ - Kafka data volumes             │  │
│ │ - Results database               │  │
│ └──────────────────────────────────┘  │
│                                        │
└────────────────────────────────────────┘
     │
     ├─ Load Balancer (Ingress)
     │
     └─ Monitoring (Prometheus/Grafana)
```

---

## Testing Strategy

```python
# Unit Tests
- RateLimiter: Verify token consumption and refill
- RetryScheduler: Verify backoff calculation
- BoundedDequeBuffer: Verify enqueue/dequeue with limits

# Integration Tests
- AccountWorker: Mock Kafka, verify publishes to fetch-locations
- LocationWorker: Mock Kafka, verify publishes to fetch-reviews
- ReviewWorker: Mock Kafka, verify deduplication

# End-to-End Tests
- Full flow: POST /review-fetch → workers process → results in Kafka
- Retry flow: Simulate API failure → verify retry scheduling → verify retry success
- Load test: Burst of requests → verify queueing and rate limiting
```

---

## Key Learnings

### 1. **Microservices Pattern**
- Each worker handles one business capability (accounts/locations/reviews)
- Can scale independently
- Can be deployed separately

### 2. **Async/Await Architecture**
- Non-blocking I/O enables high concurrency
- Multiple events processed simultaneously
- Efficient resource usage

### 3. **Event-Driven Design**
- Kafka decouples producers from consumers
- Easy to add new consumers (e.g., for analytics)
- Message replay for recovery

### 4. **Resilience Patterns**
- Rate limiting prevents overwhelming downstream APIs
- Exponential backoff prevents thundering herd
- Dead Letter Queue captures unsalvageable failures
- Retry scheduling enables eventual consistency

### 5. **Configuration Management**
- Centralized config with environment overrides
- Different settings per environment
- Type-safe (Pydantic validation)

### 6. **Graceful Degradation**
- Deque backpressure (HTTP 429) signals overload
- Workers continue even if one fails
- Health endpoint enables load balancer decisions
