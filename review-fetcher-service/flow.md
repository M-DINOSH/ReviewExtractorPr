# Review Fetcher Microservice - Complete Flow Documentation

## Table of Contents
1. [Quick Reference](#quick-reference)
2. [End-to-End Message Flow](#end-to-end-message-flow)
3. [Component Responsibilities](#component-responsibilities)
4. [Worker Pipeline](#worker-pipeline)
5. [Error Recovery](#error-recovery)
6. [Performance Characteristics](#performance-characteristics)
7. [Sequence Diagrams](#sequence-diagrams)

---

## Quick Reference

### What This Service Does
- ✅ Accepts Google OAuth tokens via REST API
- ✅ Fetches accounts, locations, and reviews from Google Business Profile API
- ✅ Implements rate limiting (config-driven; defaults are 10 req/sec with burst capacity 100)
- ✅ Handles transient errors with exponential backoff retry
- ✅ Deduplicates reviews per job
- ✅ Outputs clean reviews to Kafka for downstream processing

### Key Constraints
- **Google API Rate**: Config-driven (see `GOOGLE_REQUESTS_PER_SECOND`, `RATELIMIT_*`)
- **Distributed Rate Limiting**: Per-worker limiter (defaults: capacity=100, refill=10 tokens/sec)
- **Job Deduplication**: Per job_id (resets after job completion)
- **Retry Strategy**: 3 attempts with 100ms-10s exponential backoff
- **Buffer Size**: 10,000 items (returns 429 when full)

### Demo Output (Nested)

- **Web UI**: `GET /demo`
- **One-shot nested output (runs Kafka pipeline)**: `POST /api/v1/demo/nested`
- **Kafka aggregated nested stream (SSE)**:
  - Create a new job: `GET /api/v1/demo/stream/nested?access_token=...`
  - Or stream an existing job: `GET /api/v1/demo/stream/nested?job_id=...`

The nested output format is: account → all locations for that account → all reviews for each location.

---

## End-to-End Message Flow

### Phase 1: Job Submission & Queueing

```
┌─────────────────────────────────────────────────────┐
│ 1. CLIENT REQUEST                                   │
│                                                      │
│ POST /api/v1/review-fetch                          │
│ Content-Type: application/json                      │
│                                                      │
│ {                                                    │
│   "access_token": "ya29.XXXXXXXXXXXXX"             │
│ }                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 2. API VALIDATION (APIService)                      │
│                                                      │
│ ✓ Token format check (string, not empty)            │
│ ✓ Generate UUID4 job_id                             │
│ ✓ Create job object                                 │
│                                                      │
│ Job Structure:                                       │
│ {                                                    │
│   "job_id": "abc123",                               │
│   "access_token": "ya29.XXXXX",                    │
│   "created_at": 1609459200.0,                      │
│   "retries": 0                                      │
│ }                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 3. BUFFER ENQUEUE (BoundedDequeBuffer)              │
│                                                      │
│ Check: Is buffer full?                              │
│                                                      │
│ ┌─ YES → len(queue) >= 10000                        │
│ │        Return 429 (Too Many Requests)            │
│ │        Client should retry later                  │
│ │                                                   │
│ └─ NO → Append to queue                             │
│         Return 202 (Accepted)                       │
│         Include job_id in response                  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 4. RESPONSE TO CLIENT (202 ACCEPTED)                │
│                                                      │
│ {                                                    │
│   "job_id": "abc123",                               │
│   "status": "queued",                               │
│   "message": "Job enqueued for processing"          │
│ }                                                    │
│                                                      │
│ Job now in queue, waiting for producer              │
└─────────────────────────────────────────────────────┘
```

### Phase 2: Background Producer Task

```
┌─────────────────────────────────────────────────────┐
│ PRODUCER LOOP (Every 100ms)                         │
│                                                      │
│ while True:                                          │
│   batch = dequeue_batch(max_items=100)              │
│   for job in batch:                                 │
│     publish_to_kafka(topic="fetch-accounts")        │
│   sleep(100ms)                                      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ DEQUEUE OPERATION (O(n))                            │
│                                                      │
│ Step 1: Check if queue empty                        │
│         ├─ Empty → Return [], continue              │
│         └─ Not empty → Get up to 100 items         │
│                                                      │
│ Step 2: Remove items from queue front               │
│         (FIFO order maintained)                     │
│                                                      │
│ Step 3: Update metrics                              │
│         dequeued_count += batch_size                │
│         current_size -= batch_size                  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ KAFKA PUBLISH (Idempotent Producer)                 │
│                                                      │
│ For each job in batch:                              │
│   ├─ Topic: fetch-accounts                          │
│   ├─ Key: job_id (ensures ordering)                 │
│   ├─ Value: {access_token, ...}                    │
│   ├─ Acks: all (broker writes to all replicas)     │
│   ├─ Idempotent: true (no duplicates)              │
│   │                                                  │
│   └─ Wait for broker acknowledgment                 │
│      (request_timeout: 30s)                         │
│                                                      │
│ On Success: Log "job_published_to_kafka"            │
│ On Failure: Log error, try next cycle              │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
          Message in Kafka Topic
             (fetch-accounts)
```

### Phase 3: Account Worker Consumption

```
┌─────────────────────────────────────────────────────┐
│ ACCOUNT WORKER CONSUMER                             │
│                                                      │
│ Group: account-worker                               │
│ Topic: fetch-accounts                               │
│ Partition: 0 (auto-partitioned)                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ MESSAGE CONSUMED                                    │
│                                                      │
│ Message: {                                           │
│   "job_id": "abc123",                               │
│   "access_token": "ya29.XXXXX"                     │
│ }                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
    YES: Rate Limit    NO: Skip Message
    Acquired?          (Wait for refill)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ GOOGLE API CALL                                     │
│                                                      │
│ Endpoint (REAL mode): GET https://mybusinessbusinessinformation.googleapis.com/v1/accounts │
│ Endpoint (MOCK mode): served from jsom/accounts.json │
│ Header: Authorization: Bearer {token}               │
│ Retry: tenacity (3 attempts)                        │
│                                                      │
│ Response:                                            │
│ [                                                    │
│   {                                                  │
│     "accountId": "123456",                          │
│     "accountName": "My Business",                   │
│     ...                                              │
│   },                                                 │
│   ...                                                │
│ ]                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴────────────────────────┐
        │                                   │
    SUCCESS                             ERROR
        │                                   │
        ▼                                   ▼
  Process Accounts            ┌─────────────────────────┐
        │                     │ ERROR HANDLING          │
        │                     │                         │
        │                     │ 401/403: Permanent     │
        │                     │ → Send to DLQ           │
        │                     │                         │
        │                     │ 429/5xx: Transient     │
        │                     │ → Schedule retry        │
        │                     │ → Continue next msg    │
        │                     └────────┬────────────────┘
        │                              │
        ▼                              ▼
  For each account:           Retry Scheduler
  {                           (Exponential Backoff)
    "job_id": "abc123",
    "account_id": "123456"
  }
  ├─ Publish to: fetch-locations topic
  ├─ Partition: by job_id key
  └─ Wait for ack
        │
        ▼
  Message in fetch-locations topic
```

### Phase 4: Location Worker Consumption

```
Same pattern as Account Worker:

Consumer Group: location-worker
Input Topic: fetch-locations
Output Topic: fetch-reviews

For each account in message:
  ├─ Rate limit check (defaults: capacity=100, refill=10 tokens/sec)
  ├─ Google API (REAL mode): GET https://mybusinessbusinessinformation.googleapis.com/v1/accounts/{accountId}/locations
  ├─ Google API (MOCK mode): served from jsom/locations.json
  ├─ Error handling (transient vs permanent)
  └─ For each location:
     ├─ Create message:
     │  {
     │    "job_id": "abc123",
     │    "account_id": "123456",
     │    "location_id": "789"
     │  }
     └─ Publish to fetch-reviews topic
```

### Phase 5: Review Worker Consumption & Deduplication

```
┌─────────────────────────────────────────────────────┐
│ REVIEW WORKER CONSUMER                              │
│                                                      │
│ Group: review-worker                                │
│ Topic: fetch-reviews                                │
│ Partition: 0                                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ MESSAGE CONSUMED                                    │
│                                                      │
│ Message: {                                           │
│   "job_id": "abc123",                               │
│   "account_id": "123456",                           │
│   "location_id": "789"                              │
│ }                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ INITIALIZE JOB CACHE (if needed)                    │
│                                                      │
│ if job_id not in dedup_cache:                       │
│   dedup_cache[job_id] = set()                       │
│                                                      │
│ dedup_cache = {                                     │
│   "abc123": set(),  # Empty at start                │
│   ...                                                │
│ }                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ GOOGLE API CALL                                     │
│                                                      │
│ Endpoint (REAL mode): GET https://mybusiness.googleapis.com/v4/accounts/{accountId}/locations/{locationId}/reviews │
│ Endpoint (MOCK mode): served from jsom/Reviews.json  │
│ Pagination: All reviews for location                │
│                                                      │
│ Response:                                            │
│ [                                                    │
│   {                                                  │
│     "reviewId": "review_123",                       │
│     "reviewer": "John Doe",                         │
│     "rating": 5,                                    │
│     "text": "Great service!",                       │
│     ...                                              │
│   },                                                 │
│   ...                                                │
│ ]                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ FOR EACH REVIEW: DEDUPLICATION CHECK                │
│                                                      │
│ review_key = f"{account_id}_{location_id}_{id}"     │
│ review_key = "123456_789_review_123"                │
│                                                      │
│ if review_key in dedup_cache[job_id]:               │
│   ├─ Review already published                       │
│   ├─ Skip it                                         │
│   └─ Continue to next review                        │
│ else:                                                │
│   ├─ Add to cache                                   │
│   │  dedup_cache[job_id].add(review_key)            │
│   ├─ Publish to reviews-raw topic                  │
│   └─ Continue                                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ KAFKA PUBLISH (reviews-raw topic)                   │
│                                                      │
│ Topic: reviews-raw                                  │
│ Key: job_id (for ordering)                          │
│ Value: Full review object                           │
│                                                      │
│ {                                                    │
│   "reviewId": "review_123",                         │
│   "reviewer": "John Doe",                           │
│   "rating": 5,                                      │
│   "text": "Great service!",                         │
│   "createTime": "2024-01-10T...",                  │
│   ...                                                │
│ }                                                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ COMMIT OFFSET                                       │
│                                                      │
│ After publishing review:                            │
│   ├─ Mark message as consumed                       │
│   ├─ Commit offset to Kafka                         │
│   └─ Update consumer group lag                      │
│                                                      │
│ After processing all locations:                     │
│   ├─ Check if job_id processing complete           │
│   ├─ Clear dedup_cache[job_id]                     │
│   └─ Free memory                                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
         Final Output: reviews-raw topic
                 (Ready for downstream)
```

### Phase 6: Error Recovery (Retry Loop)

```
┌─────────────────────────────────────────────────────┐
│ RETRY LOOP (Every 1 second)                         │
│                                                      │
│ while True:                                          │
│   for each job in retry_heap:                       │
│     if job.retry_at <= now():                       │
│       pop from heap                                  │
│       republish to appropriate topic                │
│   sleep(1s)                                          │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ EXPONENTIAL BACKOFF CALCULATION                     │
│                                                      │
│ backoff_ms = min(                                    │
│   initial_ms * (multiplier ^ attempt),              │
│   max_backoff_ms                                    │
│ )                                                    │
│                                                      │
│ Attempt 0: 100ms                                    │
│ Attempt 1: 200ms                                    │
│ Attempt 2: 400ms                                    │
│ Attempt 3+: 10000ms (capped)                        │
│ Max attempts: 3                                      │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴─────────┐
        │                    │
    Attempt < 3         Attempt >= 3
        │                    │
        ▼                    ▼
  Schedule Retry       Send to DLQ
  (Republish job)      (Permanent failure)
```

---

## Component Responsibilities

### APIService
- **Input**: HTTP requests with access tokens
- **Validation**: Check token format, generate job_id
- **Output**: Enqueue to buffer or return error
- **Response**: 202 (accepted), 429 (full), 400 (invalid)

### BoundedDequeBuffer
- **Input**: Job objects from API
- **Storage**: FIFO queue (max 10k items)
- **Output**: Batch dequeue (up to 100 items)
- **Metrics**: Track enqueued, dequeued, rejected

### KafkaEventPublisher
- **Input**: Job batches from producer loop
- **Publishing**: To Kafka topics with idempotence
- **Output**: Message published acknowledgment
- **Config**: acks=all, enable_idempotence=true

### AccountWorker
- **Input**: Messages from fetch-accounts topic
- **Processing**: Google API call to get accounts
- **Output**: Messages to fetch-locations topic
- **Rate Limiting**: Token bucket per worker (defaults: capacity=100, refill=10 tokens/sec)

### LocationWorker
- **Input**: Messages from fetch-locations topic
- **Processing**: Google API call to get locations per account
- **Output**: Messages to fetch-reviews topic
- **Rate Limiting**: Token bucket per worker (defaults: capacity=100, refill=10 tokens/sec)

### ReviewWorker
- **Input**: Messages from fetch-reviews topic
- **Processing**: Google API call to get reviews per location
- **Deduplication**: Per-job-id in-memory set
- **Output**: Messages to reviews-raw topic
- **Cleanup**: Clear dedup cache after job completes

### RetryScheduler
- **Input**: Failed jobs from workers
- **Storage**: Min-heap ordered by retry timestamp
- **Logic**: Exponential backoff (100ms → 400ms → 10s)
- **Output**: Republish to appropriate topic after delay
- **DLQ**: Permanent errors after max retries

---

## Worker Pipeline

The three workers form a fan-out hierarchy:

```
                Job (access_token)
                       │
                       ▼
        ┌──────────────────────────┐
        │  AccountWorker           │
        │  Fetch 1-10 accounts     │
        └──────────┬───────────────┘
                   │
       ┌───────────┴──────────┬────────────┐
       │                      │            │
       ▼                      ▼            ▼
    Account 1            Account 2    Account 3
       │                  │               │
       │ each account     │               │
       ▼                  ▼               ▼
┌────────────┐      ┌────────────┐  ┌────────────┐
│Location    │      │Location    │  │Location    │
│  Worker    │      │  Worker    │  │  Worker    │
│ Per Acct   │      │ Per Acct   │  │ Per Acct   │
└──────┬─────┘      └──────┬─────┘  └──────┬─────┘
       │                   │               │
   Loc1 Loc2          Loc1 Loc2       Loc1 Loc2
       │                   │               │
       ▼                   ▼               ▼
    ReviewWorker processes all locations, fetches reviews
       │
       │ (deduplicated per job_id)
       │
       ▼
   reviews-raw topic (output)
```

**Key Insight**: 
- One job can generate multiple accounts
- One account can have multiple locations
- One location can have multiple reviews
- All work is asynchronous and non-blocking

---

## Error Recovery

### Error Classification

```
Google API Response
       │
   ┌───┴────┐
   │        │
ERROR    SUCCESS
   │        │
   ├─401    └─ Process response
   │        (continue normally)
   ├─403
   ├─404      Permanent Errors
   │          (auth/not found)
   │
   ├─429
   ├─500      Transient Errors
   ├─502      (rate limit/server)
   └─503
```

### Recovery Strategy

**Transient Errors (429, 5xx)**:
```
1. Extract job from message
2. Calculate: backoff = init_ms * (2 ^ attempt)
3. Set retry_at = now + backoff
4. Push to retry_scheduler heap
5. Continue to next message
6. Retry loop will republish after delay
```

**Permanent Errors (401, 403, 404)**:
```
1. Extract job from message
2. Log error with full context
3. Send to Dead Letter Queue (DLQ)
4. Continue to next message
5. Manual intervention required for DLQ
```

---

## Performance Characteristics

### Throughput

| Component | Throughput | Bottleneck |
|-----------|-----------|-----------|
| API Endpoint | ~1000 req/s (FastAPI) | Network I/O |
| Deque Buffer | ~10k items/s enqueue | Memory (10k cap) |
| Producer Loop | ~100 items/100ms | Kafka broker |
| Account Worker | 100 items/10s (rate limit) | Google API quota |
| Location Worker | 100 items/10s (rate limit) | Google API quota |
| Review Worker | 100 items/10s (rate limit) | Google API quota |

### Latency

```
Total Job Latency = API latency + Queue wait + Worker latency

Queue Wait:
  - If empty: 0ms
  - If 5000 items: (5000 / 100) * 100ms = 5 seconds

Worker Latency (per job):
  - Account fetch: ~200ms (Google API)
  - Location fetch: ~500ms (accounts * locations API calls)
  - Review fetch: ~1000ms (locations * reviews API calls)
  
Total: ~1-2 seconds per job (best case)
       + queue wait time + retry delays
```

### Memory Usage

```
BoundedDequeBuffer:
  - 10k jobs * 100 bytes = ~1MB

TokenBucketLimiter (x3 workers):
  - Negligible (~1KB each)

RetryScheduler:
  - Depends on failure rate
  - Max backoff 10s, typically < 100 items
  - ~10KB estimate

ReviewWorker Dedup Cache:
  - Per job_id, cleared after completion
  - Estimate: 50KB per active job
  - With 100 concurrent jobs: 5MB
```

---

## Sequence Diagrams

### Normal Flow (Success Path)

```
Client    API      Deque    Kafka    AccountWorker
  │        │        │        │           │
  │──POST──>│        │        │           │
  │  token  │        │        │           │
  │        │─enqueue>│        │           │
  │        │        │        │           │
  │        │<─202───│        │           │
  │        │ job_id │        │           │
  │<────────│        │        │           │
  │        │        │        │           │
  │        │        │─batch──>│          │
  │        │        │publish  │          │
  │        │        │        │           │
  │        │        │        │<─consume─│
  │        │        │        │           │
  │        │        │        │    Google API call
  │        │        │        │      (get accounts)
  │        │        │        │           │
  │        │        │        │           ✓ Success
  │        │        │        │           │
  │        │        │        │    Publish to fetch-locations
```

### Error Recovery (Transient Error)

```
AccountWorker    Google API    Retry Scheduler
     │                │              │
     │────GET───────>│              │
     │ /accounts      │              │
     │                │              │
     │<─429──────────│              │
     │ Rate Limit     │              │
     │                │              │
     │ Backoff = 200ms
     │                │              │
     │─schedule_retry(job, 200ms)───>│
     │                │              │
     │ Continue next  │              │
     │ message        │              │
     │                │              │
     │                │    wait 200ms
     │                │              │
     │<─republish job─────<──────────│
     │                │              │
     │ Retry attempt  │              │
     │                │              │
     │────GET───────>│              │
     │ /accounts      │              │
     │                │              │
     │<─200 OK───────│              │
     │ Success!       │              │
```

---

## Summary

The Review Fetcher implements a **production-ready event-driven pipeline** with:

✅ **Ingress Control**: Bounded buffer prevents overload
✅ **Asynchronous Processing**: Non-blocking I/O throughout
✅ **Fault Tolerance**: Exponential backoff retries with DLQ
✅ **Rate Limiting**: Per-worker token bucket (defaults: capacity=100, refill=10 tokens/sec)
✅ **Deduplication**: Per-job-id in-memory set
✅ **Scalability**: Kafka topics enable horizontal scaling
✅ **Observability**: Structured logging, metrics tracking
✅ **Resilience**: Graceful degradation on errors

For comprehensive technical details, see [README.md](README.md)
