# Review Fetcher Microservice – Architecture Overview

## Purpose & Scope
- Accept client jobs to fetch Google Business Profile reviews.
- Decouple HTTP ingress from downstream API calls via Kafka and background workers.
- Provide resilience (rate limiting, retries, backpressure) and observability hooks.

## Core Design Choices (DSA, Patterns, OOP)
- **Data Structures & Algorithms (DSA)**
	- **Bounded deque** (FIFO, capped): smooths bursts and enforces backpressure; `collections.deque` with maxlen.
	- **Priority queue (heap)**: retry scheduler orders tasks by next retry time; `heapq` ensures O(log n) inserts.
	- **Token bucket**: lightweight rate limiting; O(1) checks/refills using monotonic time.
	- **Sets for dedup**: O(1) membership to avoid duplicate reviews in ReviewWorker.
- **Tech Stack Rationale**
	- **FastAPI**: async-first, OpenAPI docs, lightweight for IO-bound microservices.
	- **Kafka (aiokafka/mock)**: durable, replayable event bus; mock path for local/dev speed.
	- **Pydantic/Settings**: type-safe validation for requests and configuration.
	- **httpx + tenacity**: async HTTP client with battle-tested retry decorators for Google APIs.
	- **asyncio**: cooperative concurrency for background loops (producer/retry/workers) without threads.
- **Design Patterns**
	- **Service Locator**: `AppState` holds shared services for easy access in routes/workers.
	- **Factory/Abstract Factory**: Kafka producers/consumers instantiated per mode (mock vs prod).
	- **Strategy**: interchangeable rate limiters, retry policies, producer/consumer implementations.
	- **Template Method**: base consumer defines lifecycle; concrete consumers provide `consume`/`on_message`.
	- **Adapter**: `BoundedDequeBuffer` wraps `deque` with async locks and metrics.
	- **Dependency Injection**: APIService and workers receive dependencies in constructors.
	- **Context Manager**: FastAPI `lifespan` manages startup/shutdown.
- **OOP Principles**
	- **SRP**: each worker handles one stage (accounts/locations/reviews); producer/retry loops are distinct.
	- **Open/Closed**: extend by adding new topics/workers or swapping strategies without changing callers.
	- **Liskov/Substitution**: Mock vs real Kafka producer/consumer share base interfaces.
	- **Composition over Inheritance**: services composed from injected collaborators (rate limiter, retry, publisher).

## High-Level Flow
1) Client POST `/api/v1/review-fetch` with access token.  
2) Job is validated → enqueued in bounded deque (backpressure).  
3) Producer loop batches deque items → publishes `fetch-accounts` events to Kafka.  
4) AccountWorker consumes → calls Google API → emits `fetch-locations`.  
5) LocationWorker consumes → calls Google API → emits `fetch-reviews`.  
6) ReviewWorker consumes → paginates, deduplicates, emits reviews to downstream topic (`reviews-raw`).  
7) Retry loop republishes failed messages with exponential backoff; DLQ optional.

## Core Components
- FastAPI app (`app/main.py`): lifecycle, dependency wiring, background task orchestration.
- API layer (`app/api.py`): request validation, job creation, health endpoint.
- Buffer (`app/deque_buffer.py`): bounded async deque for burst smoothing; returns 429 when full.
- Messaging (`app/kafka_producer.py`, `app/kafka_consumers/*`): mock + aiokafka strategies; topics per stage.
- Rate limiting (`app/rate_limiter.py`): token bucket per worker type to respect Google quotas.
- Retry (`app/retry.py`): heap-based scheduler with exponential backoff + DLQ hook.
- Domain models (`app/models.py`): Pydantic DTOs for API + Kafka payloads.
- Google API client (`app/services/google_api.py`): httpx + tenacity retries (prod); mock mode supported.

## Topics (default names)
- `fetch-accounts` → input to AccountWorker.
- `fetch-locations` → input to LocationWorker.
- `fetch-reviews` → input to ReviewWorker.
- `reviews-raw` (or downstream persistence topic) → output of ReviewWorker.

## Why Kafka?
- **Decoupling**: API produces events; workers consume asynchronously without blocking client responses.
- **Durability & Replay**: Messages persisted; consumers can rewind on bugs or outages.
- **Scalability**: Partitioned topics let us scale workers horizontally per stage.
- **Backpressure Compatibility**: Producer can buffer via deque; Kafka smooths downstream spikes.
- **Ordering by Key**: Using `job_id` as key keeps per-job events ordered across partitions.
- **Fault Tolerance**: With replication and `acks=all`, we avoid data loss on broker failure.

## Without Kafka (What Would Break)
- **Tight coupling**: API would call workers or Google APIs directly, blocking request latency and tying deployments together.
- **No durable buffering**: A process crash or restart would drop in-flight jobs; no replay or catch-up.
- **Limited scaling**: Harder to fan out processing by stage; would need custom work queues or cron-style batching.
- **Weaker backpressure**: Deque alone cannot absorb long outages; Kafka provides persisted backlog to drain later.
- **Harder ordering and idempotency**: Without keyed partitions, per-job ordering would require custom routing/state.
- **Recovery gaps**: No offset tracking means partial processing would need bespoke checkpointing logic.

## Resilience & Backpressure
- Bounded deque prevents OOM; 429 tells clients to back off.
- Per-stage token buckets avoid Google API throttling.
- Exponential backoff retries for transient errors; permanent errors → DLQ.
- Manual Kafka offset commit in production consumers to avoid message loss on failure.
- Graceful shutdown cancels background tasks and disconnects Kafka.

## Configuration (env-driven via Pydantic Settings)
- Kafka: `KAFKA_BOOTSTRAP_SERVERS`, consumer group, offsets.
- Rate limit: `RATELIMIT_TOKEN_BUCKET_CAPACITY`, `RATELIMIT_REFILL_RATE`.
- Retry: `RETRY_MAX_RETRIES`, `RETRY_INITIAL_BACKOFF_MS`, `RETRY_MAX_BACKOFF_MS`, `RETRY_BACKOFF_MULTIPLIER`.
- Deque: `DEQUE_MAX_SIZE`, `DEQUE_BURST_CHECK_INTERVAL_SEC`.
- Flags: `MOCK_GOOGLE_API` (mock mode), `LOG_LEVEL`.

## Request/Worker Sequence (success path)
- HTTP: validate token → enqueue job → 202 Accepted with `job_id`.
- Producer loop: dequeue batch → publish `fetch-accounts` (keyed by `job_id`).
- AccountWorker: rate-limit → Google accounts → publish `fetch-locations` per account.
- LocationWorker: rate-limit → Google locations → publish `fetch-reviews` per location.
- ReviewWorker: rate-limit → Google reviews (paginated) → dedup → publish to `reviews-raw`.

## Failure Handling
- Token bucket empty → schedule retry (error code 429) instead of dropping.
- HTTP 429 when buffer full to signal client backoff.
- Retry scheduler distinguishes retryable vs permanent (401/403/404/400 non-retryable).
- DLQ callback hook for observability / manual intervention.

## Security Considerations
- Access tokens handled in-memory; ensure TLS termination in ingress.
- Consider stripping tokens from logs; current mock mode skips external validation.
- Add authN/Z at gateway or per-route if exposed beyond trusted network.

## Observability Hooks (to implement/verify)
- Emit metrics: deque depth, enqueue rejects, rate-limiter denials, retry counts, DLQ counts, per-topic publish/consume rates.
- Structured logging with correlation IDs (`job_id` as key) across stages.
- Health endpoint uses deque load; extend to Kafka connectivity checks.

## Deployment Notes
- Stateless pods; scale horizontally by adding replicas (workers are async).  
- Kafka required in non-mock mode; ensure brokers and topics exist.  
- Configure readiness/liveness probes on API and consider a lightweight Kafka connectivity check for readiness.

## Architecture Diagram (Text)
```
Client
  ↓ HTTP POST /api/v1/review-fetch
FastAPI API (api.py)
  - validate token
  - enqueue job → BoundedDequeBuffer
  - 202 Accepted (job_id)
	↓
Background Producer Loop
  - dequeue batch
  - publish fetch-accounts (Kafka)
	↓
Kafka Topic: fetch-accounts
	↓
AccountWorker (rate-limited)
  - Google API: accounts
  - publish fetch-locations
	↓
Kafka Topic: fetch-locations
	↓
LocationWorker (rate-limited)
  - Google API: locations
  - publish fetch-reviews
	↓
Kafka Topic: fetch-reviews
	↓
ReviewWorker (rate-limited + dedup)
  - Google API: reviews (paginated)
  - publish reviews-raw
	↓
Kafka Topic: reviews-raw (downstream persistence/analytics)

Retry Loop (side path)
  - priority queue (heap)
  - exponential backoff
  - re-publish to appropriate topic
  - DLQ on permanent errors
```

## Quick Validation Checklist
- [ ] `.env` set for environment (mock vs prod) and Kafka endpoints.
- [ ] Topics created with intended partition count and retention.
- [ ] Rate limit and retry settings match Google API quotas.
- [ ] Monitoring dashboards for queue depth, retries, DLQ, publish/consume lag.
- [ ] Load test shows 429 on saturation and successful recovery after backoff.

---

# Technical Design Document (TDD) — Google Business Profile Review Fetcher

## 1. Executive Summary
- **Business value**: Automates retrieval of Google Business Profile reviews at scale, enabling timely reputation insights and downstream analytics. Reduces manual effort, accelerates response to customer feedback, and supplies clean, ordered data to downstream services.
- **System goals**: High-throughput, stateless, event-driven ingestion with strict adherence to Google API quotas (300 QPM), durable delivery via Kafka, and clear observability and compliance boundaries (30-day TTL, attribution).
- **Principles**: Stateless workers, immutable event contracts, backpressure-first ingress, and graceful degradation under downstream stress.

## 2. Architecture Diagram Description (API Gateway → Kafka → Workers → Output)
1) **API Gateway → FastAPI**: Receives POST `/api/v1/review-fetch`, validates OAuth2 token, and enqueues job into a bounded `collections.deque` buffer to protect against ingress floods (HTTP 429 when full).
2) **Burst Smoothing → Producer Loop**: Background producer drains the deque in batches and publishes `fetch-accounts` events to Kafka (keyed by `job_id` for ordering).
3) **Kafka Fan-Out (Hierarchical Fetching)**:
	 - `fetch-accounts` → **AccountWorker** fan-outs accounts → publishes `fetch-locations`.
	 - `fetch-locations` → **LocationWorker** fan-outs locations → publishes `fetch-reviews`.
	 - `fetch-reviews` → **ReviewWorker** fetches paginated reviews → publishes `reviews-raw` for downstream consumers.
4) **Rate Limiting (Distributed)**: Each worker uses a Redis-backed token bucket (300 QPM cap) to honor Google quotas; tokens are shared across instances.
5) **Resilience**: Non-blocking retry scheduler (heapq priority queue) resubmits to Kafka with exponential backoff + jitter; Kafka pause/resume can be used to temporarily stop consumption during incident handling.
6) **Output**: Final reviews land on `reviews-raw` topic for persistence/analytics. Data expires after 30 days per retention policy if cached.

## 3. Data Flow & Contract (Event Schemas)
- **fetch-accounts**
	- `job_id: string` (UUID), `access_token: string`, `type: "fetch_accounts"`, `created_at: ISO-8601`.
- **fetch-locations**
	- `job_id: string`, `account_id: string`, `account_name: string`, `type: "fetch_locations"`, `created_at: ISO-8601`.
- **fetch-reviews**
	- `job_id: string`, `account_id: string`, `location_id: string`, `location_name: string`, `type: "fetch_reviews"`, `created_at: ISO-8601`.
- **Contracts**: Pydantic models enforce shape and types; messages are versioned implicitly via topic and `type` field. Keys use `job_id` to preserve per-job ordering across partitions.

## 4. Scalability & Performance
- **Instances**: 9+ stateless pods; all share Redis for distributed rate limits and Kafka for coordination.
- **Kafka partitions**: Each stage topic partitioned to match or exceed worker parallelism (e.g., 6–12 partitions). Worker groups scale horizontally; Kafka balances partitions across instances.
- **Burst handling**: Ingress deque (bounded) returns 429 when saturated; producer loop batches dequeues to smooth load.
- **Throughput**: Async FastAPI + aiokafka prevents thread blocking; backpressure (429 + bounded deque) protects downstream and avoids cascading failures.

## 5. Reliability & Error Handling
- **Retry**: Heap-based priority queue drives exponential backoff with jitter; retries are republished to Kafka. Transient errors (429/5xx/timeouts) are retried; permanent (401/403/404/400) go to DLQ.
- **DLQ**: Dead-letter topic for non-retryable or exhausted attempts, enabling investigation and replay.
- **Kafka pause/resume**: Operators can pause consumption on a topic during incidents while preserving offsets, then resume without data loss.
- **Idempotency**: Kafka idempotent producer (acks=all, enable_idempotence) plus `job_id` keys reduce duplicates; ReviewWorker dedupes review IDs.

## 6. Security & Compliance
- **OAuth2 tokens**: Passed in Authorization header; validated server-side. Tokens are not persisted; kept in-memory only for the call path. Logs must redact tokens.
- **Data retention**: Any cached review data or intermediate storage must enforce **30-day TTL**; Kafka topic retention aligned to policy. Downstream consumers must honor the same TTL.
- **Google attribution**: Responses and any surfaced data must include required Google attribution per API terms; no token sharing or cross-project reuse.
- **Transport**: TLS termination at gateway; internal traffic secured via mTLS or trusted network policies.

## 7. Alternatives Considered
- **Kafka vs Celery/Task Queue**:
	- **Why Kafka**: Durable, replayable log; strong ordering per key; partition-based horizontal scaling; ecosystem support for backpressure and DLQ patterns.
	- **Why not Celery-only**: Broker/task-queue semantics fit RPC-style jobs but offer weaker replay semantics, less transparent ordering guarantees, and more operational overhead for high-volume fan-out pipelines.

## 8. Key Decisions (Why)
- **collections.deque (bounded)** for ingress: O(1) ops, simple backpressure, predictable memory; returns HTTP 429 when full.
- **Redis Token Bucket**: Centralized, distributed rate limiting to enforce 300 QPM across all instances consistently.
- **Heap-based Retry Scheduler**: Deterministic ordering of retries with non-blocking scheduling; avoids tight loops and aligns with backoff math.
- **Hierarchical Fan-Out (Account → Location → Review)**: Mirrors external API hierarchy, isolates concerns, and lets each stage scale and rate-limit independently.

