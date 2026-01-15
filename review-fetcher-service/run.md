# Run Guide — Review Fetcher + Kafka (Docker)

This service is designed to run as a small stack:

- **review-fetcher** (FastAPI) — exposes API + demo UI
- **Kafka + Zookeeper** — event pipeline
- **Kafka UI** — to inspect topics
- (Optional) **separation-service** — included in docker compose, not required for the demo output

This guide shows exactly how to start everything and how to view the final **nested output**:

```
account {
  ...
  locations: [
    {
      ...
      reviews: [ ... ]
    }
  ]
}
```

---

## 1) Prerequisites

- Docker Desktop installed and running
- `docker compose` available

Optional (only if you want to run scripts on your host machine):

- Python 3.10+

---

## 2) Start the full stack (recommended)

From this folder:

```bash
cd review-fetcher-service
```

Start everything:

```bash
docker compose up -d
```

Check container status:

```bash
docker compose ps
```

Wait until the API is healthy:

```bash
curl -s http://localhost:8084/api/v1/health | python3 -m json.tool
```

Expected output includes `kafka_connected: true`.

---

## 3) URLs / Ports

- **Review Fetcher API**: `http://localhost:8084`
- **Health**: `http://localhost:8084/api/v1/health`
- **Demo UI**: `http://localhost:8084/demo`
- **Kafka UI**: `http://localhost:8080`
- **Kafka (host bootstrap)**: `localhost:9094`

---

## 4) Run the nested output (Kafka-streamed)

### Option A — Web UI (easiest)

Open in browser:

- `http://localhost:8084/demo`

On that page you can:

- Trigger `/api/v1/review-fetch`
- Watch the nested Kafka stream output via `/api/v1/demo/stream/nested`

### Option B — CLI demo (prints final nested JSON)

From `review-fetcher-service/`:

```bash
python3 kafka_stream_demo.py
```

What it does:

1. Checks Kafka connectivity (`localhost:9094`)
2. Calls the API `POST http://localhost:8084/api/v1/review-fetch`
3. Consumes Kafka topics and prints one final nested JSON structure:
   - account
   - locations[]
   - reviews[] per location

Environment overrides if needed:

```bash
API_BASE_URL=http://localhost:8084 KAFKA_BOOTSTRAP=localhost:9094 python3 kafka_stream_demo.py
```

---

## 5) (Optional) Get a nested output directly (no Kafka)

There is also a **direct join** endpoint (loads from `jsom/*.json` and joins in-memory):

```bash
curl -s http://localhost:8084/api/v1/demo/nested \
  -H 'Content-Type: application/json' \
  -d '{"access_token":"any-token"}' | python3 -m json.tool
```

Notes:

- The token is only used to pick a deterministic “random” account.
- This path does **not** consume Kafka.

---

## 6) Switch to REAL Google API (future / production)

Right now the service runs in **mock mode** by default (it reads from `jsom/*.json`).

When you want real-time data from Google, you do **not** need to change the code — the service already has a “real mode”. You only switch the flag and provide a valid Google OAuth access token.

### A) Enable real mode

In the `review-fetcher` container, set:

- `MOCK_GOOGLE_API=false`

With the current docker compose setup, you can do:

```bash
cd review-fetcher-service
MOCK_GOOGLE_API=false docker compose up -d --build
```

### B) Provide a real Google OAuth token

In real mode, `POST /api/v1/review-fetch` expects a real Google OAuth **access token** (the code checks it looks like a Google token, e.g. starts with `ya29`).

Example:

```bash
curl -s http://localhost:8084/api/v1/review-fetch \
  -H 'Content-Type: application/json' \
  -d '{"access_token":"ya29.REAL_TOKEN_HERE"}' | python3 -m json.tool
```

### C) Where you see the output in real mode

Use the Kafka-backed nested stream (same as mock mode):

- Web UI: `http://localhost:8084/demo`
- Nested SSE: `/api/v1/demo/stream/nested?job_id=...`

Important note:

- The **direct join** endpoint `/api/v1/demo/nested` is mock-only (it joins `jsom/*.json`). For real Google data, you use `/api/v1/review-fetch` + Kafka stream.

### D) Google API access requirements

To make real mode work, your OAuth token must have access to Google Business Profile APIs for the account(s) you’re requesting:

- Business Information API (accounts + locations)
- Reviews endpoint (used by the service)

If permissions are missing, you will see `401` (token invalid/expired) or `403` (no permission / API not enabled).

---

## 7) Troubleshooting

### A) API health is failing (`health=000`)

Check container state:

```bash
docker compose ps
```

If `review-fetcher` exited, check logs:

```bash
docker logs --tail 200 review-fetcher-service
```

Restart just the API container:

```bash
docker compose restart review-fetcher
```

### B) Kafka won’t start (Zookeeper broker id already exists)

This happens when Zookeeper still has an old broker registration.

Reset the stack:

```bash
docker compose down --remove-orphans
docker compose up -d
```

If it still persists and you don’t need persisted volumes:

```bash
docker compose down -v
docker compose up -d
```

### C) Kafka UI shows topics but demo prints nothing

Make sure you are triggering the job:

```bash
curl -s http://localhost:8084/api/v1/review-fetch \
  -H 'Content-Type: application/json' \
  -d '{"access_token":"test_token_123456789"}' | python3 -m json.tool
```

Then watch the nested stream:

```bash
JOB_ID=<paste_job_id_here>
curl -s -N "http://localhost:8084/api/v1/demo/stream/nested?job_id=$JOB_ID&max_wait_sec=30" | head -n 80
```

---

## 8) Stop everything

```bash
docker compose down
```

Stop + delete volumes (full reset):

```bash
docker compose down -v
```
