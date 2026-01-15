# work.md — How it works internally

This document explains the internal flow of the **review-fetcher-service**, how **mock mode** vs **real Google API mode** works, and how the **demo UI/endpoints** relate to the production pipeline.

## 1) High-level architecture

There is one core path:

1. **Production pipeline (Kafka workers)**
  - Frontend sends an `access_token`.
  - The service creates a `job_id` and pushes work into Kafka.
  - Three Kafka workers process the job:
    - AccountWorker → LocationWorker → ReviewWorker
  - Output reviews are published to `reviews-raw`.

The demo endpoints are just *different views/aggregations* over this same Kafka pipeline (one-shot JSON vs SSE stream).

## 2) Key configuration flags (mock vs real)

There are two separate concepts:

### A) `MOCK_GOOGLE_API` (data source)

- **Where it is used:** in the `GoogleAPIClient` implementation.
- **Purpose:** chooses whether workers fetch data from:
  - **Mock JSON** in `jsom/` (when `MOCK_GOOGLE_API=true`), or
  - **Real Google Business Profile APIs** (when `MOCK_GOOGLE_API=false`).

This is the flag you will use when you go “live” later.

### B) `MOCK_KAFKA` (Kafka connectivity)

- **Where it is used:** the Kafka producer/consumers factory.
- **Purpose:** chooses whether to:
  - connect to real Kafka (default), or
  - use an in-memory mock Kafka implementation.

In docker-compose we run **real Kafka**, even in mock data mode.

## 3) Production flow (API → Kafka → workers)

### Step 1: Frontend calls API

Endpoint:
- `POST /api/v1/review-fetch`

Input:
- `{ "access_token": "..." }`

Output:
- `{ "job_id": "...", "message": "..." }`

Internally:
- The API generates `job_id`.
- The job is placed in an internal deque buffer.
- A background loop drains the deque and publishes the first Kafka event.

### Step 2: Kafka topics and event chain

Topics:
- `fetch-accounts` — start of a job
- `fetch-locations` — one message per account
- `fetch-reviews` — one message per location
- `reviews-raw` — final output (one message per review)

The chain:

1. Producer publishes to `fetch-accounts`:
   - `{ job_id, access_token }`

2. **AccountWorker** consumes `fetch-accounts`, fetches accounts, and publishes many `fetch-locations`:
   - `{ job_id, account_id, access_token, ... }`

3. **LocationWorker** consumes `fetch-locations`, fetches locations, and publishes many `fetch-reviews`:
   - `{ job_id, account_id, google_account_id, location_id, access_token, ... }`

4. **ReviewWorker** consumes `fetch-reviews`, fetches reviews, and publishes to `reviews-raw`:
   - `{ job_id, account_id, location_id, rating, comment/text, reviewer_name, ... }`

### Step 3: Join rules (the “strict correctness” rules)

All nested outputs and validators assume the strict joins:

- `accounts.account_id == locations.google_account_id`
- `locations.location_id == reviews.location_id`

In mock mode, these joins are enforced by the IDs in the JSON files.

In real Google mode, Google returns resource names like:
- `accounts/123...`
- `accounts/123.../locations/456...`

Internally we normalize these so joins remain consistent.

## 4) Mock mode vs real Google mode internals

### Mock mode (`MOCK_GOOGLE_API=true`)

Data source:
- `jsom/accounts.json`
- `jsom/locations.json`
- `jsom/Reviews.json`

Implementation:
- The workers call `GoogleAPIClient`, but the client reads from `mock_data_service`.
- Token validation is “soft” in mock mode:
  - any non-empty token is accepted
  - token is still passed through Kafka so the frontend contract stays identical

Important note:
- Some locations may legitimately have **0 reviews** in `Reviews.json`.
  - In that case the ReviewWorker will publish nothing for that location.

### Real mode (`MOCK_GOOGLE_API=false`)

Data source:
- Google Business Profile APIs via HTTP.

Implementation:
- The same workers call the same `GoogleAPIClient` methods.
- The client calls Google endpoints (accounts/locations/reviews).
- Token validity is determined by real API responses.

This keeps the frontend integration stable:
- Frontend always sends `access_token`
- Backend decides mock vs real behavior via configuration

## 5) Demo endpoints: what is demo, what is production

The demo code lives in `app/demo_web.py`.

### A) Demo UI page

- `GET /demo`

This is just an HTML page that calls the endpoints below.

### B) One-shot nested demo (Kafka pipeline)

- `POST /api/v1/demo/nested`

What it does:
- Creates a job via the same API service used by production.
- Aggregates Kafka topics (`fetch-locations`, `fetch-reviews`, `reviews-raw`) into a single nested payload.

Important:
- This endpoint uses the **same Kafka + worker pipeline** as production.
- Mock vs real behavior is controlled only by `MOCK_GOOGLE_API`:
  - `true` → reads from `jsom/`
  - `false` → calls real Google APIs

### C) Kafka nested stream demo (SSE) (USES Kafka pipeline)

- Create a new job and stream it: `GET /api/v1/demo/stream/nested?access_token=...`
- Or stream an existing job: `GET /api/v1/demo/stream/nested?job_id=...`

What it does:
- Consumes Kafka topics (`fetch-locations`, `fetch-reviews`, `reviews-raw`) and aggregates them into a single nested payload.
- Streams progressive updates as SSE events.

In `access_token=...` mode, the endpoint emits:
- `event: job` with the newly created `job_id`, then
- `event: nested` updates, then
- `event: done`.

Important:
- This endpoint reflects the **real production pipeline output**.
- In mock mode (`MOCK_GOOGLE_API=true`) it shows the mocked data flowing through Kafka.
- In real mode (`MOCK_GOOGLE_API=false`) it will show real Google data flowing through Kafka.

Also important:
- Kafka topics do not guarantee cross-topic ordering.
- The aggregator buffers reviews so they aren’t lost if `reviews-raw` arrives before `fetch-reviews`.

## 6) Separation service (sentiment)

The `separation-service` (optional) consumes:
- Input: `reviews-raw`

…and can publish:
- Output: `reviews-sentiment`

This is separate from fetching and does not affect the join correctness; it only enriches downstream.

## 7) Practical notes for production integration

- Frontend contract should remain:
  - send `{ access_token }` to `POST /api/v1/review-fetch`
  - use `job_id` to track/stream results
- Switch mock ↔ real using environment:
  - `MOCK_GOOGLE_API=true` (now)
  - `MOCK_GOOGLE_API=false` (later)
- Expect some locations to have no reviews (both in mock and real life).

