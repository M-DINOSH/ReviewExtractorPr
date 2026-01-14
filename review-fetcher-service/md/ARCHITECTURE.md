# Review Fetcher Microservice - Architecture & Design Document

## Executive Summary

The rebuilt **Review Fetcher Microservice** is a production-ready, event-driven microservice following **SOLID principles** and **OOP design patterns**. It demonstrates enterprise-grade architecture with:

- ✅ **100% Async/Await** - Non-blocking, concurrent processing
- ✅ **SOLID Principles** - Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- ✅ **Design Patterns** - Factory, Strategy, Template Method, Observer, Singleton, Adapter, Bulkhead, Circuit Breaker
- ✅ **Data Structures** - deque (burst), Token Bucket (rate limit), heapq (retry), set (dedup), dict (tracking)
- ✅ **Error Handling** - Exponential backoff, DLQ, circuit breaker, selective retry
- ✅ **Scalability** - Horizontal scaling, stateless API, bounded deque, configurable limits
- ✅ **Observability** - Structured logging, health checks, metrics endpoint

---

## 1. SOLID Principles Breakdown

### Single Responsibility Principle (SRP)

Each class has ONE reason to change:

| Class | Responsibility | Reason to Change |
|-------|---|---|
| `BoundedDequeBuffer` | Manage in-memory queue | Changes to queue behavior |
| `TokenBucketLimiter` | Rate limiting | Algorithm changes |
| `RetryScheduler` | Retry coordination | Retry policy changes |
| `AccountWorker` | Fetch Google accounts | Google API contract changes |
| `LocationWorker` | Fetch business locations | Google API contract changes |
| `ReviewWorker` | Fetch reviews | Google API contract changes |
| `APIService` | HTTP request handling | API endpoint changes |
| `KafkaEventPublisher` | Event publishing | Kafka protocol changes |

**Example: AccountWorker**
```python
class AccountWorker:
    """ONLY responsible for consuming fetch-accounts and publishing fetch-locations"""
    async def _on_message(self, message):
        # Fetch accounts via Google API
        # Publish fetch-locations events
        # Handle errors -> DLQ
```

### Open/Closed Principle (OCP)

**Open for extension, closed for modification:**

```python
# ❌ Bad: Would need to modify class to add new rate limiter
class Worker:
    def rate_limit(self):
        if algo == "token_bucket":
            # ...

# ✅ Good: Use strategy pattern
class RateLimiter(ABC):  # Abstract base
    @abstractmethod
    async def acquire(self, tokens: int) -> bool: pass

class TokenBucketLimiter(RateLimiter):  # Extends without modifying
    async def acquire(self, tokens: int) -> bool: ...

class LeakyBucketLimiter(RateLimiter):  # New implementation
    async def acquire(self, tokens: int) -> bool: ...
```

### Liskov Substitution Principle (LSP)

All implementations are substitutable:

```python
# Workers can be substituted without changing behavior
worker: KafkaConsumerBase = mock_consumer  # or real AIokafkaConsumer
await worker.start()
await worker.consume()

# Producers can be substituted
producer: KafkaProducerBase = MockKafkaProducer()  # or AIokafkaProducer()
await producer.send(topic, message)
```

### Interface Segregation Principle (ISP)

Clients depend only on methods they use:

```python
# ✅ Good: Specific interfaces
class RateLimiter(ABC):
    async def acquire(self, tokens: int) -> bool: pass

class RetryPolicy(ABC):
    def should_retry(self, error_code: str, attempt: int) -> bool: pass

# Instead of one "Worker" interface with everything
```

### Dependency Inversion Principle (DIP)

Depend on abstractions, not concrete implementations:

```python
# ✅ Good: Inject abstractions
class AccountWorker:
    def __init__(
        self,
        rate_limiter: TokenBucketLimiter,        # Abstraction
        retry_scheduler: RetryScheduler,         # Abstraction
        event_publisher: KafkaEventPublisher     # Abstraction
    ):
        self.rate_limiter = rate_limiter

# Instead of creating internal dependencies
class AccountWorker:
    def __init__(self):
        self.rate_limiter = TokenBucketLimiter()  # Hard dependency
```

---

## 2. Design Patterns Implemented

### 1. Factory Pattern

**Location:** `KafkaProducerFactory`, `Settings`

**Purpose:** Create objects without revealing their concrete classes

```python
class KafkaProducerFactory:
    @staticmethod
    def create(mock: bool, bootstrap_servers: list) -> KafkaProducerBase:
        if mock:
            return MockKafkaProducer()
        return AIokafkaProducer(bootstrap_servers)

# Usage
producer = KafkaProducerFactory.create(
    mock=settings.mock_google_api,
    bootstrap_servers=settings.kafka.bootstrap_servers
)
```

### 2. Strategy Pattern

**Location:** `RateLimiter`, `RetryPolicy`

**Purpose:** Define family of algorithms, encapsulate each one

```python
class RateLimiter(ABC):
    @abstractmethod
    async def acquire(self, tokens: int) -> bool: pass

class TokenBucketLimiter(RateLimiter):
    async def acquire(self, tokens: int) -> bool:
        # Token bucket algorithm
        ...

# Usage
limiter = TokenBucketLimiter(capacity=100, refill_rate=10)
if await limiter.acquire(1):
    # Process
```

### 3. Template Method Pattern

**Location:** `KafkaConsumerBase`

**Purpose:** Define skeleton in base class, subclasses fill in details

```python
class KafkaConsumerBase(ABC):
    async def start(self):
        self.is_running = True
        await self.connect()
        logger.info(f"{self.__class__.__name__}_started")
    
    @abstractmethod
    async def connect(self): pass
    
    @abstractmethod
    async def consume(self): pass

class AIokafkaConsumer(KafkaConsumerBase):
    async def connect(self):
        # Real Kafka connection
        ...
    
    async def consume(self):
        # Real message consumption
        ...
```

### 4. Observer Pattern

**Location:** `KafkaEventPublisher`

**Purpose:** Define one-to-many relationship between objects

```python
class KafkaEventPublisher:
    async def publish_fetch_accounts_event(self, job_id, access_token):
        message = {"type": "fetch_accounts", "job_id": job_id, ...}
        return await self.producer.send("fetch-accounts", message)
        # Observers (workers) react asynchronously
```

### 5. Singleton Pattern

**Location:** `Settings`, `AppState`

**Purpose:** Ensure only one instance of critical objects

```python
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance

# Usage
settings = get_settings()  # Always same instance
```

### 6. Adapter Pattern

**Location:** `BoundedDequeBuffer`

**Purpose:** Convert interface of class into another clients expect

```python
class BoundedDequeBuffer:
    """Adapts collections.deque to be thread-safe, bounded"""
    
    def __init__(self, max_size: int):
        self._queue: deque = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
    
    async def enqueue(self, item) -> bool:
        async with self._lock:
            if len(self._queue) >= self.max_size:
                return False
            self._queue.append(item)
            return True
```

### 7. Bulkhead Pattern

**Location:** `RetryScheduler`

**Purpose:** Isolate failures in one area from affecting others

```python
class RetryScheduler:
    """Isolates retry logic - if one message fails, others still retry"""
    
    async def schedule_retry(self, message_id, payload, error_code, attempt):
        # One message's retry doesn't block others
        task = RetryTask(...)
        heapq.heappush(self.retry_queue, task)
```

### 8. Circuit Breaker Pattern

**Location:** `CircuitBreaker` in `retry.py`

**Purpose:** Prevent cascading failures

```python
class CircuitBreaker:
    """States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN"""
    
    def can_execute(self) -> bool:
        if self.state == "OPEN":
            if timeout_elapsed():
                self.state = "HALF_OPEN"  # Try again
                return True
            return False  # Don't try, fail fast
        return True
```

---

## 3. Data Structures & Algorithms

### 1. collections.deque (Burst Handling)

**Why:** FIFO queue, bounded size, O(1) append/pop

```python
class BoundedDequeBuffer:
    self._queue: deque = deque(maxlen=10000)
    
    # O(1) operations
    self._queue.append(job)           # Add
    job = self._queue.popleft()       # Remove
    size = len(self._queue)           # Size
```

**Problem Solved:** API gets burst of requests, deque smooths them out for Kafka producer

### 2. Token Bucket (Rate Limiting)

**Why:** Smooth traffic, allow burst, prevent overwhelming API

```python
class TokenBucketLimiter:
    # Refill: tokens += (elapsed_time * refill_rate)
    # Acquire: if tokens >= requested, give them, else wait
    
    async def acquire(self, tokens: int) -> bool:
        self._refill()  # Add tokens based on time passed
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

**Algorithm:**
```
Initially: tokens = capacity = 100
Rate: 10 tokens/sec
Acquire 20 → tokens = 80 (success)
Wait 1 sec → tokens = 90 (refilled)
Acquire 20 → tokens = 70 (success)
Acquire 50 → tokens = 70 (NOT enough, fail, wait)
```

### 3. heapq (Retry Scheduling)

**Why:** Priority queue, O(log n) operations, automatic sorting by time

```python
class RetryScheduler:
    self.retry_queue: list[RetryTask] = []
    
    # Schedule for later
    task = RetryTask(retry_at=now+2.5, message_id="123", ...)
    heapq.heappush(self.retry_queue, task)  # O(log n)
    
    # Get all ready tasks
    while self.retry_queue[0].retry_at <= now:
        task = heapq.heappop(self.retry_queue)  # O(log n)
        await retry_message(task)
```

**Algorithm:**
```
Message fails at t=0:
→ schedule retry at t=0.1 (100ms backoff)
→ heappush(task, retry_at=0.1)

Message fails at t=0:
→ schedule retry at t=0.2 (200ms backoff, exponential)
→ heappush(task, retry_at=0.2)

At t=0.15:
→ heappop() returns task with retry_at=0.1
→ re-publish message
```

### 4. set (Deduplication)

**Why:** O(1) lookup, ignore duplicates

```python
class ReviewWorker:
    self.seen_reviews: dict[job_id, Set[review_id]] = {}
    
    # O(1) duplicate check
    if review_id in self.seen_reviews[job_id]:
        # Skip duplicate
        continue
    
    # O(1) add to set
    self.seen_reviews[job_id].add(review_id)
```

**Purpose:** If same review fetched twice, don't publish twice

### 5. dict (Job Tracking)

**Why:** O(1) key lookup, in-memory tracking

```python
class APIService:
    self.job_tracking: dict = {}
    
    # O(1) store
    self.job_tracking[job_id] = {"status": "queued", ...}
    
    # O(1) retrieve
    return self.job_tracking.get(job_id)
```

### 6. Pagination (Sliding Window)

**Why:** Stateless, memory-efficient, easy to parallelize

```python
async def _fetch_reviews_from_google(..., page: int, page_size: int):
    # Sliding window: [page*page_size, (page+1)*page_size)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    
    return reviews[start_idx:end_idx]
```

---

## 4. Component Architecture

### 4.1 API Layer (FastAPI)

```
POST /api/v1/review-fetch
├── Validate token (Pydantic)
├── Check deque not full (429 if full)
├── Generate job_id (UUID4)
├── Enqueue to deque
├── Track job in dict
└── Return 202 Accepted
```

**SOLID:** APIService handles business logic separately from HTTP routing

### 4.2 Burst Buffer (Deque)

```
Jobs from API
    ↓
BoundedDequeBuffer (max 10K)
    ├─ Enqueue O(1)
    ├─ Check full O(1)
    └─ Metrics
    
Returns 429 if full → Client backs off
```

**SOLID:** Adapter pattern wraps deque safely

### 4.3 Producer Loop

```
While running:
    ├─ Drain deque (batch 100)
    ├─ Rate limit (Token Bucket)
    ├─ Publish to fetch-accounts Kafka topic
    └─ Sleep 100ms
```

**SOLID:** Strategy pattern for rate limiting, dependency injection

### 4.4 Account Worker

```
Consume from fetch-accounts
├─ Rate limit (Token Bucket)
├─ Validate message
├─ Call Google API (mocked)
├─ For each account:
│   └─ Publish to fetch-locations
├─ Log success
└─ On error:
   ├─ Retry logic (heapq scheduler)
   ├─ DLQ if unrecoverable
   └─ Do NOT commit Kafka offset
```

**SOLID:** Template Method for consumer base, Strategy for rate limiting

### 4.5 Location Worker

```
Consume from fetch-locations
├─ Rate limit (Token Bucket)
├─ Call Google API
├─ For each location:
│   └─ Publish to fetch-reviews
├─ Retry on 429/5xx
└─ DLQ on 401/403/error
```

### 4.6 Review Worker

```
Consume from fetch-reviews
├─ Rate limit (Token Bucket)
├─ For each page:
│   ├─ Call Google API (paginated)
│   ├─ For each review:
│   │   ├─ Check dedup set (O(1))
│   │   ├─ Publish to reviews-raw
│   │   └─ Add to seen set
│   └─ Next page
├─ Commit Kafka offset (success)
└─ DLQ on error
```

**SOLID:** Set for deduplication (high cohesion), Template Method pattern

---

## 5. Error Handling Flow

### 5.1 Transient Errors (429, 5xx)

```
Error occurs
    ↓
Check: should_retry(error_code, attempt)?
    ├─ Yes → ExponentialBackoffPolicy.get_backoff_ms()
    ├─ Schedule retry via heapq
    ├─ Don't commit Kafka offset
    └─ Message will be reprocessed
    
    └─ No (3+ retries) → Send to DLQ
```

### 5.2 Permanent Errors (401, 403, 404)

```
Error occurs
    ↓
Check: should_retry("401", attempt)?
    ├─ No (auth errors never retry)
    └─ Send to DLQ immediately
```

### 5.3 Circuit Breaker

```
Failure count >= threshold (5 consecutive)
    ├─ State: CLOSED → OPEN
    ├─ Reject all requests (fail fast)
    └─ After timeout (60s), try HALF_OPEN
        ├─ Allow 1 request
        ├─ If success → CLOSED
        └─ If fails → OPEN (restart timer)
```

---

## 6. Concurrency Model

```
asyncio Event Loop
│
├─ FastAPI HTTP Server
│   ├─ POST /api/v1/review-fetch (async)
│   ├─ GET /api/v1/status (async)
│   └─ GET /api/v1/health (async)
│
├─ Producer Loop (asyncio.Task)
│   ├─ Drain deque
│   ├─ Rate limit (Token Bucket)
│   └─ Publish to Kafka
│
├─ Retry Loop (asyncio.Task)
│   ├─ Check retry queue (heapq)
│   ├─ Re-publish ready tasks
│   └─ Clear completed tasks
│
└─ Workers Loop (3 concurrent asyncio.Tasks)
    ├─ AccountWorker.consume()
    ├─ LocationWorker.consume()
    └─ ReviewWorker.consume()

All tasks:
✅ Non-blocking
✅ Cooperative multitasking
✅ Share CPU fairly
✅ No GIL contention
```

---

## 7. Configuration Management (Singleton + Nested)

```python
@dataclass
Settings:
    ├─ Service: name, version, env
    ├─ API: host, port, workers
    ├─ KafkaConfig: brokers, group, timeouts
    ├─ RateLimitConfig: capacity, refill_rate
    ├─ RetryConfig: max_retries, backoff
    └─ DequeConfig: max_size, check_interval

# Singleton access
settings = get_settings()  # Always same instance
```

---

## 8. Logging & Observability

```python
# Structured logging with context
logger.info(
    "job_created",
    job_id=job_id,
    deque_size=await buffer.size(),
    timestamp=datetime.utcnow()
)

# JSON output
{
    "event": "job_created",
    "job_id": "550e8400...",
    "deque_size": 42,
    "timestamp": "2024-01-07T10:30:00Z"
}

# Health endpoint
GET /api/v1/health
{
    "status": "healthy",
    "kafka_connected": true,
    "memory_used_percent": 45.2
}

# Metrics endpoint
GET /api/v1/metrics
{
    "deque": {"enqueued": 150, "dequeued": 140, ...},
    "jobs_tracked": 25
}
```

---

## 9. Testing Strategy

### Unit Tests
- Test each class in isolation
- Mock dependencies
- Test error paths

### Integration Tests
```python
# Local, no Docker needed
async def test_full_workflow():
    # 1. Create job
    # 2. Process through workers
    # 3. Verify output
```

### Load Tests
```
Simulate 1000+ concurrent requests
Measure:
  - API latency
  - Deque fullness
  - Worker throughput
  - Memory usage
```

---

## 10. Production Deployment

### Kubernetes
```yaml
kind: Deployment
spec:
  replicas: 3  # Horizontal scaling
  containers:
    - image: review-fetcher:1.0.0
      resources:
        requests: {cpu: 100m, memory: 256Mi}
        limits: {cpu: 500m, memory: 512Mi}
      livenessProbe:
        httpGet: {path: /api/v1/health, port: 8000}
        initialDelaySeconds: 10
      readinessProbe:
        httpGet: {path: /api/v1/health, port: 8000}
        initialDelaySeconds: 5
```

### Monitoring
- Prometheus metrics
- ELK stack for logging
- Jaeger for distributed tracing
- PagerDuty for alerting

---

## Summary: SOLID + OOP in Action

| Principle | Implementation | Benefit |
|-----------|---|---|
| SRP | Each worker has one job | Easy to test, maintain |
| OCP | Strategies for rate limit/retry | Add new algorithms without change |
| LSP | Interface-based workers | Swap mock/real easily |
| ISP | Separate interfaces | Clean, focused contracts |
| DIP | Dependency injection | Testable, loosely coupled |
| Factory | `KafkaProducerFactory` | No tight coupling to concrete types |
| Strategy | `RateLimiter`, `RetryPolicy` | Pluggable behaviors |
| Template Method | `KafkaConsumerBase` | Standardized flow, override details |
| Observer | Event publishing | Loose coupling, extensible |
| Singleton | `Settings` | Single source of truth |
| Adapter | `BoundedDequeBuffer` | Safe wrapping of deque |

**Result:** Production-ready, testable, maintainable, scalable microservice! 🎯
