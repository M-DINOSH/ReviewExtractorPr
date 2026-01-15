# End-to-End Workflow (Review Fetcher + Kafka + Sentiment)

## 1) What this covers
- How a request enters the system, moves through Kafka, hits Google APIs (real mode), and is streamed back.
- Where to plug in the sentiment (separation-service) enrichment step.

## 2) How to run the stack (mock by default)
- From `review-fetcher-service/`: `docker compose up -d`
- Health: `curl http://localhost:8084/api/v1/health`
- UIs: Reviews Viewer `http://localhost:8084/api/v1/reviews-viewer`, Demo `http://localhost:8084/demo`, Swagger `http://localhost:8084/docs`, Kafka UI `http://localhost:8080`

## 3) End-to-end data flow
1) Client submits a job
   - Endpoint: `POST /api/v1/review-fetch` with `{ "access_token": "..." }`
   - API validates token (real mode hits Google accounts endpoint once). Response: `job_id`, status `queued`.
2) Ingress buffer
   - Bounded deque (max 10k) smooths bursts; returns 429 if full.
3) Producer loop -> Kafka
   - Background task drains deque in batches and publishes to topic `fetch-accounts` (keyed by `job_id`).
4) Account worker
   - Consumes `fetch-accounts`; rate-limited; fetches accounts via `GoogleAPIClient.get_accounts`.
   - Emits one message per account to `fetch-locations`.
5) Location worker
   - Consumes `fetch-locations`; rate-limited; fetches locations via `get_locations`.
   - Emits one message per location to `fetch-reviews`.
6) Review worker
   - Consumes `fetch-reviews`; rate-limited; fetches reviews via `get_reviews`.
   - Deduplicates per `job_id`; publishes each review to `reviews-raw` (keyed by `job_id`).
7) Aggregation / streaming to clients
   - SSE production-safe flow:
     1. `POST /api/v1/stream-session` with `{ "access_token": "..." }` -> `session_id`
     2. `GET /api/v1/stream/nested?session_id=...` -> events `job`, `nested` (accounts/locations/reviews + stats), `done`
   - Demo-only shortcut (token in URL): `GET /api/v1/demo/stream/nested?access_token=...`
   - One-shot nested JSON (no streaming UI): `POST /api/v1/demo/nested`
8) Downstream options
   - Frontend: consume SSE nested stream (used by Reviews Viewer) keyed by `job_id`.
   - Backend/analytics: consume Kafka topic `reviews-raw` directly for per-review processing.
   - Sentiment (separation-service): POST batch `{id,text}` to `http://localhost:8000/api/v1/analyze`, then join scores back on `review_id`.

## 4) Real vs mock Google mode
- Default: mock data from `jsom/` (`MOCK_GOOGLE_API=true`).
- Real mode: set `MOCK_GOOGLE_API=false` (env or docker compose) and provide a valid Google Business Profile OAuth access token.
- Real endpoints called:
  - Accounts: `https://mybusinessbusinessinformation.googleapis.com/v1/accounts`
  - Locations: `.../v1/accounts/{account}/locations`
  - Reviews: `https://mybusiness.googleapis.com/v4/accounts/{account}/locations/{location}/reviews`

## 5) Operational guardrails
- Rate limiting: token bucket per worker (capacity 100, refill 10/sec by default). Exceeded -> retry scheduler.
- Retries: exponential backoff for transient errors (429/5xx). 401/403 go to DLQ.
- Dedup: in-memory per `job_id` to avoid duplicate publishes to `reviews-raw`.
- Buffer protection: 429 when deque > max to prevent overload.

## 6) Quick demo script (happy-path)
1. `docker compose up -d`
2. `curl http://localhost:8084/api/v1/health`
3. In browser open `http://localhost:8084/api/v1/reviews-viewer`, submit token, watch live stream.
4. (Optional) Start sentiment service in `separation-service`: `make install && make run`; send a small batch from streamed reviews to `/api/v1/analyze`.

## 7) Where Google API vs mock is called (reference code)

### GoogleAPIClient (switches on MOCK_GOOGLE_API)
- Real-mode calls are in [app/services/google_api.py](../app/services/google_api.py):
  - `get_accounts` → GET https://mybusinessbusinessinformation.googleapis.com/v1/accounts
  - `get_locations` → GET https://mybusinessbusinessinformation.googleapis.com/v1/accounts/{account}/locations
  - `get_reviews` → GET https://mybusiness.googleapis.com/v4/accounts/{account}/locations/{location}/reviews
- Mock-mode paths return fixtures from `jsom/` via `mock_data_service`.

Snippet (real vs mock selection):

```python
class GoogleAPIClient:
   def __init__(self, use_mock: bool = None):
      self.use_mock = use_mock if use_mock is not None else settings.mock_google_api

   async def get_accounts(self, access_token: str):
      if self.use_mock:
         return await mock_data_service.get_accounts()  # mock data
      return await self._get("https://mybusinessbusinessinformation.googleapis.com/v1/accounts", access_token)

   async def get_locations(self, account_id: str, access_token: str):
      if self.use_mock:
         return await mock_data_service.get_locations(account_id)
      url = f"https://mybusinessbusinessinformation.googleapis.com/v1/accounts/{account_id}/locations"
      return await self._get(url, access_token)

   async def get_reviews(self, account_id: str, location_id: str, access_token: str):
      if self.use_mock:
         return await mock_data_service.get_reviews(int(str(location_id).split("/")[-1]))
      url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews"
      return await self._get(url, access_token)
```

### Where workers call the client
- Account worker: [app/kafka_consumers/account_worker.py](../app/kafka_consumers/account_worker.py) → `accounts = await google_api_client.get_accounts(access_token)`
- Location worker: [app/kafka_consumers/location_worker.py](../app/kafka_consumers/location_worker.py) → `locations = await google_api_client.get_locations(...)`
- Review worker: [app/kafka_consumers/review_worker.py](../app/kafka_consumers/review_worker.py) → `reviews = await google_api_client.get_reviews(...)`
