"""Demo web UI and streaming endpoints.

Provides a simple HTML page that renders Kafka pipeline output in-browser.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from app.config import get_settings
from app.services.mock_data import mock_data_service


router = APIRouter(tags=["demo"])


def _pick_account_by_token(access_token: str, accounts: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick a stable 'random' account from the list based on the token."""
    if not accounts:
        raise ValueError("No accounts loaded")
    token = access_token or ""
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:8], "big") % len(accounts)
    return accounts[idx]


@router.get("/demo", include_in_schema=False)
async def demo_page() -> HTMLResponse:
    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Review Fetcher Demo</title>
  <style>
    :root { color-scheme: light; }
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }
    h1 { margin: 0 0 8px; font-size: 20px; }
    h2 { margin: 0 0 8px; font-size: 16px; }
    .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin: 12px 0; }
    button { padding: 10px 14px; border-radius: 10px; border: 1px solid #ddd; background: #111827; color: white; cursor: pointer; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    input { padding: 10px 12px; border-radius: 10px; border: 1px solid #d1d5db; width: 520px; max-width: 100%; }
    .pill { padding: 6px 10px; border-radius: 999px; background: #f3f4f6; border: 1px solid #e5e7eb; font-size: 12px; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
    .card { border: 1px solid #e5e7eb; border-radius: 14px; padding: 14px; background: white; }
    pre { background: #0b1020; color: #d1d5db; padding: 12px; border-radius: 12px; overflow: auto; margin: 0; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace; font-size: 12px; }
    .muted { color: #6b7280; font-size: 12px; }
  </style>
</head>
<body>
  <h1>Demo Output Formats</h1>
  <div class=\"muted\">You asked for a final nested output: account → all locations for that account → all reviews for each location.</div>

  <div class=\"card\" style=\"margin-top: 12px;\">
    <h2>Final nested output (direct join)</h2>
    <div class=\"muted\">Picks a stable “random” account based on the token, then joins locations/reviews by IDs.</div>
    <div class=\"row\">
      <label for=\"token\"><b>Access token</b></label>
      <input id=\"token\" placeholder=\"paste any token (used only to pick a 'random' account deterministically)\" />
      <button id=\"btnNested\">Generate</button>
    </div>
    <pre><code id=\"nested\">(click Generate)</code></pre>
  </div>

  <div class=\"card\" style=\"margin-top: 12px;\">
    <h2>Kafka nested stream (SSE)</h2>
    <div class=\"muted\">Aggregates Kafka topics into one nested output by job_id.</div>

    <div class=\"row\">
      <button id=\"startBtn\">Start review fetch + stream</button>
      <span class=\"pill\">API: <code>/api/v1/review-fetch</code></span>
      <span class=\"pill\">Stream: <code>/api/v1/demo/stream/nested</code></span>
    </div>

    <div class=\"row\" style=\"justify-content: space-between;\">
      <div><strong>Job</strong> <span id=\"jobId\" class=\"muted\">(not started)</span></div>
      <div class=\"row\" style=\"gap: 10px;\">
        <div><strong>Accounts:</strong> <span id=\"countAccounts\">0</span></div>
        <div><strong>Locations:</strong> <span id=\"countLocations\">0</span></div>
        <div><strong>Reviews:</strong> <span id=\"countReviews\">0</span></div>
      </div>
    </div>

    <div class=\"muted\" style=\"margin-bottom: 6px;\">Nested output (stream)</div>
    <pre><code id=\"outputNested\">{}</code></pre>
  </div>

  <script>
    const pretty = (obj) => JSON.stringify(obj, null, 2);

    document.getElementById('btnNested').onclick = async () => {
      const access_token = document.getElementById('token').value || '';
      const resp = await fetch('/api/v1/demo/nested', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token })
      });
      const data = await resp.json();
      document.getElementById('nested').textContent = pretty(data);
    };

    const startBtn = document.getElementById('startBtn');
    const jobIdEl = document.getElementById('jobId');
    const countAccountsEl = document.getElementById('countAccounts');
    const countLocationsEl = document.getElementById('countLocations');
    const countReviewsEl = document.getElementById('countReviews');
    const outNested = document.getElementById('outputNested');

    let esNested = null;
    let latestNested = null;

    function render() {
      if (latestNested) {
        outNested.textContent = pretty(latestNested);
        const acc = latestNested.account ? 1 : 0;
        const locCount = Array.isArray(latestNested.locations) ? latestNested.locations.length : 0;
        let revCount = 0;
        if (Array.isArray(latestNested.locations)) {
          for (const l of latestNested.locations) {
            if (Array.isArray(l.reviews)) revCount += l.reviews.length;
          }
        }
        countAccountsEl.textContent = String(acc);
        countLocationsEl.textContent = String(locCount);
        countReviewsEl.textContent = String(revCount);
      } else {
        outNested.textContent = '{}';
        countAccountsEl.textContent = '0';
        countLocationsEl.textContent = '0';
        countReviewsEl.textContent = '0';
      }
    }

    function stopStreams() {
      if (esNested) { esNested.close(); esNested = null; }
    }

    async function start() {
      startBtn.disabled = true;
      stopStreams();
      latestNested = null;
      render();

      const resp = await fetch('/api/v1/review-fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: 'test_token_123456789' })
      });

      if (!resp.ok) {
        const text = await resp.text();
        jobIdEl.textContent = `error (${resp.status}): ${text}`;
        startBtn.disabled = false;
        return;
      }

      const data = await resp.json();
      const jobId = data.job_id || '(unknown)';
      jobIdEl.textContent = jobId;

      esNested = new EventSource(`/api/v1/demo/stream/nested?job_id=${encodeURIComponent(jobId)}&max_wait_sec=60&max_locations=200&max_reviews_per_location=200`);
      esNested.addEventListener('nested', (ev) => {
        try {
          latestNested = JSON.parse(ev.data);
          render();
        } catch (e) {
          console.error('bad nested payload', e, ev.data);
        }
      });
      esNested.addEventListener('done', () => {
        startBtn.disabled = false;
        stopStreams();
      });
      esNested.onerror = () => {
        startBtn.disabled = false;
      };
    }

    startBtn.addEventListener('click', () => start());
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@router.get("/api/v1/demo/accounts")
async def demo_accounts(limit: int = Query(25, ge=1, le=500)) -> list[dict[str, Any]]:
    """Return accounts in the requested schema (from jsom/accounts.json)."""
    return mock_data_service.accounts_data[:limit]


@router.get("/api/v1/demo/locations")
async def demo_locations(
    limit: int = Query(25, ge=1, le=500),
    google_account_id: Optional[int] = Query(None),
) -> list[dict[str, Any]]:
    """Return locations in the requested schema, optionally filtered by google_account_id."""
    if google_account_id is None:
        return mock_data_service.locations_data[:limit]
    filtered = [
        l
        for l in mock_data_service.locations_data
        if int(l.get("google_account_id", -1)) == int(google_account_id)
    ]
    return filtered[:limit]


@router.get("/api/v1/demo/reviews")
async def demo_reviews(
  limit: int = Query(25, ge=1, le=500),
  location_id: Optional[int] = Query(None),
) -> list[dict[str, Any]]:
  """Return reviews in the requested schema, optionally filtered by location_id."""
  if location_id is None:
    return mock_data_service.reviews_data[:limit]
  filtered = [
    r
    for r in mock_data_service.reviews_data
    if int(r.get("location_id", -1)) == int(location_id)
  ]
  return filtered[:limit]


@router.post("/api/v1/demo/nested")
async def demo_nested_output(
  payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
  """Return nested output: account → locations → reviews.

  Selection rule:
  - Pick one “random” account based on access_token (deterministic hash)

  Join rules:
  - locations.google_account_id == account.account_id
  - reviews.location_id == locations.location_id
  """

  access_token = str(payload.get("access_token") or "")
  max_locations = int(payload.get("max_locations", 500))
  max_reviews_per_location = int(payload.get("max_reviews_per_location", 500))

  accounts = list(mock_data_service.accounts_data)
  locations = list(mock_data_service.locations_data)
  reviews = list(mock_data_service.reviews_data)

  account = _pick_account_by_token(access_token, accounts)
  account_id = int(account.get("account_id", account.get("id")))

  account_locations = [
    l for l in locations if int(l.get("google_account_id", -1)) == account_id
  ][:max_locations]

  reviews_by_location_id: dict[int, list[dict[str, Any]]] = {}
  for review in reviews:
    try:
      loc_id = int(review.get("location_id", -1))
    except Exception:
      continue
    reviews_by_location_id.setdefault(loc_id, []).append(review)

  nested_locations: list[dict[str, Any]] = []
  for location in account_locations:
    loc_id = int(location.get("location_id", location.get("id")))
    loc_reviews = reviews_by_location_id.get(loc_id, [])[:max_reviews_per_location]
    location_with_reviews = dict(location)
    location_with_reviews["reviews"] = loc_reviews
    nested_locations.append(location_with_reviews)

  return {
    "account": account,
    "locations": nested_locations,
    "joins_ok": {
      "account.account_id == location.google_account_id": all(
        int(l.get("google_account_id", -999999)) == account_id
        for l in account_locations
      ),
      "location.location_id == review.location_id": all(
        int(r.get("location_id", -999999))
        == int(l.get("location_id", -999999))
        for l in nested_locations
        for r in (l.get("reviews") or [])
      ),
    },
  }


@router.get("/api/v1/demo/stream/accounts")
async def demo_stream_accounts(
  job_id: Optional[str] = Query(None),
  max_items: int = Query(25, ge=1, le=500),
  max_wait_sec: int = Query(60, ge=5, le=600),
) -> StreamingResponse:
    """Server-Sent Events stream of accounts emitted on `fetch-locations`.

    Emits SSE events:
    - event: account  (data: account schema JSON)
    - event: done     (when max_accounts reached or timeout)
    """

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    async def event_stream() -> AsyncIterator[bytes]:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            "fetch-locations",
            bootstrap_servers=bootstrap_servers,
        auto_offset_reset="earliest" if job_id else "latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"demo_web_accounts_{int(time.time())}",
            consumer_timeout_ms=1000,
        )

        seen_account_ids: set[str] = set()
        deadline = time.time() + max_wait_sec

        try:
            await consumer.start()
            if not job_id:
              await consumer.seek_to_end()

            while time.time() < deadline and len(seen_account_ids) < max_items:
                try:
                    msg = await consumer.getone()
                except Exception:
                    await asyncio.sleep(0.05)
                    continue

                payload = msg.value or {}
                if job_id and str(payload.get("job_id")) != str(job_id):
                    continue

                account_id = payload.get("account_id")
                account_key = str(account_id) if account_id is not None else ""
                if not account_key or account_key in seen_account_ids:
                    continue

                seen_account_ids.add(account_key)

                account_obj: dict[str, Any] = {
                    "id": payload.get("id", account_id),
                    "account_id": payload.get("account_id", account_id),
                    "client_id": payload.get("client_id", 1),
                    "google_account_name": payload.get("google_account_name"),
                    "account_display_name": payload.get("account_display_name")
                    or payload.get("account_name"),
                    "created_at": payload.get("created_at") or payload.get("timestamp"),
                    "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                }

                yield (
                    f"event: account\n"
                    f"data: {json.dumps(account_obj, ensure_ascii=False)}\n\n"
                ).encode("utf-8")

            yield b"event: done\ndata: {}\n\n"

        finally:
            await consumer.stop()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/v1/demo/stream/locations")
async def demo_stream_locations(
    job_id: Optional[str] = Query(None),
    max_items: int = Query(25, ge=1, le=500),
    max_wait_sec: int = Query(60, ge=5, le=600),
) -> StreamingResponse:
    """Server-Sent Events stream of locations emitted on `fetch-reviews`."""

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    async def event_stream() -> AsyncIterator[bytes]:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            "fetch-reviews",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="earliest" if job_id else "latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"demo_web_locations_{int(time.time())}",
            consumer_timeout_ms=1000,
        )

        seen_location_ids: set[str] = set()
        deadline = time.time() + max_wait_sec

        try:
            await consumer.start()
            if not job_id:
                await consumer.seek_to_end()

            while time.time() < deadline and len(seen_location_ids) < max_items:
                try:
                    msg = await consumer.getone()
                except Exception:
                    await asyncio.sleep(0.05)
                    continue

                payload = msg.value or {}
                if job_id and str(payload.get("job_id")) != str(job_id):
                    continue

                location_id = payload.get("location_id")
                location_key = str(location_id) if location_id is not None else ""
                if not location_key or location_key in seen_location_ids:
                    continue

                seen_location_ids.add(location_key)

                location_obj: dict[str, Any] = {
                    "id": payload.get("id"),
                    "location_id": payload.get("location_id"),
                    "client_id": payload.get("client_id"),
                    "google_account_id": payload.get("google_account_id")
                    or payload.get("account_id"),
                    "location_name": payload.get("location_name"),
                    "location_title": payload.get("location_title") or payload.get("location_name"),
                    "address": payload.get("address"),
                    "phone": payload.get("phone"),
                    "category": payload.get("category"),
                    "created_at": payload.get("created_at") or payload.get("timestamp"),
                    "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                }

                yield (
                    f"event: location\n"
                    f"data: {json.dumps(location_obj, ensure_ascii=False)}\n\n"
                ).encode("utf-8")

            yield b"event: done\ndata: {}\n\n"
        finally:
            await consumer.stop()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/v1/demo/stream/nested")
async def demo_stream_nested(
    job_id: str = Query(..., min_length=1),
    max_wait_sec: int = Query(60, ge=5, le=600),
    max_locations: int = Query(500, ge=1, le=5000),
    max_reviews_per_location: int = Query(500, ge=1, le=5000),
    emit_interval_ms: int = Query(250, ge=50, le=2000),
) -> StreamingResponse:
    """Kafka-backed nested stream: account → locations → reviews."""

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    async def event_stream() -> AsyncIterator[bytes]:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            "fetch-locations",
            "fetch-reviews",
            "reviews-raw",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"demo_web_nested_{int(time.time())}",
            consumer_timeout_ms=1000,
        )

        account_obj: Optional[dict[str, Any]] = None
        account_id: Optional[int] = None
        locations_by_id: dict[int, dict[str, Any]] = {}
        reviews_by_location_id: dict[int, list[dict[str, Any]]] = {}

        last_emit = 0.0
        deadline = time.time() + max_wait_sec
        dirty = False

        def build_nested() -> dict[str, Any]:
            locs: list[dict[str, Any]] = []
            for loc_id, loc in locations_by_id.items():
                loc_with_reviews = dict(loc)
                loc_reviews = reviews_by_location_id.get(loc_id, [])[:max_reviews_per_location]
                loc_with_reviews["reviews"] = loc_reviews
                locs.append(loc_with_reviews)
            locs.sort(key=lambda x: int(x.get("location_id", x.get("id", 0)) or 0))

            joins_ok_account = True
            if account_id is not None:
                for loc in locs:
                    try:
                        if int(loc.get("google_account_id", -999999)) != int(account_id):
                            joins_ok_account = False
                            break
                    except Exception:
                        joins_ok_account = False
                        break

            joins_ok_reviews = True
            for loc in locs:
                try:
                    loc_id_val = int(loc.get("location_id", -999999))
                except Exception:
                    joins_ok_reviews = False
                    break
                for rev in (loc.get("reviews") or []):
                    try:
                        if int(rev.get("location_id", -999999)) != loc_id_val:
                            joins_ok_reviews = False
                            break
                    except Exception:
                        joins_ok_reviews = False
                        break
                if not joins_ok_reviews:
                    break

            total_reviews = sum(len(v) for v in reviews_by_location_id.values())

            return {
                "account": account_obj,
                "locations": locs,
                "stats": {"locations": len(locs), "reviews": total_reviews},
                "joins_ok": {
                    "account.account_id == location.google_account_id": joins_ok_account,
                    "location.location_id == review.location_id": joins_ok_reviews,
                },
            }

        try:
            await consumer.start()

            while time.time() < deadline:
                try:
                    msg = await consumer.getone()
                except Exception:
                    await asyncio.sleep(0.05)
                    now = time.time()
                    if dirty and (now - last_emit) * 1000.0 >= emit_interval_ms:
                        payload = build_nested()
                        yield (
                            f"event: nested\n"
                            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        ).encode("utf-8")
                        last_emit = now
                        dirty = False
                    continue

                payload = msg.value or {}
                if str(payload.get("job_id")) != str(job_id):
                    continue

                if msg.topic == "fetch-locations":
                    acc_id = payload.get("account_id")
                    if acc_id is None:
                        continue
                    if account_obj is None:
                        try:
                            account_id = int(acc_id)
                        except Exception:
                            continue
                        account_obj = {
                            "id": payload.get("id", account_id),
                            "account_id": payload.get("account_id", account_id),
                            "client_id": payload.get("client_id", 1),
                            "google_account_name": payload.get("google_account_name"),
                            "account_display_name": payload.get("account_display_name")
                            or payload.get("account_name"),
                            "created_at": payload.get("created_at") or payload.get("timestamp"),
                            "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                        }
                        dirty = True

                elif msg.topic == "fetch-reviews":
                    if account_id is None:
                        continue
                    try:
                        gaid = int(payload.get("google_account_id", -1))
                    except Exception:
                        continue
                    if gaid != int(account_id):
                        continue
                    if len(locations_by_id) >= max_locations:
                        continue
                    try:
                        loc_id = int(payload.get("location_id", payload.get("id")))
                    except Exception:
                        continue
                    if loc_id in locations_by_id:
                        continue
                    locations_by_id[loc_id] = {
                        "id": payload.get("id", loc_id),
                        "location_id": payload.get("location_id", loc_id),
                        "client_id": payload.get("client_id", 1),
                        "google_account_id": payload.get("google_account_id"),
                        "location_name": payload.get("location_name"),
                        "location_title": payload.get("location_title") or payload.get("name"),
                        "address": payload.get("address"),
                        "phone": payload.get("phone"),
                        "category": payload.get("category"),
                        "created_at": payload.get("created_at") or payload.get("timestamp"),
                        "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                    }
                    dirty = True

                elif msg.topic == "reviews-raw":
                    try:
                        loc_id = int(payload.get("location_id", -1))
                    except Exception:
                        continue
                    if account_id is not None and loc_id not in locations_by_id:
                        continue
                    reviews_by_location_id.setdefault(loc_id, [])
                    if len(reviews_by_location_id[loc_id]) >= max_reviews_per_location:
                        continue
                    reviews_by_location_id[loc_id].append(
                        {
                            "id": payload.get("id"),
                            "client_id": payload.get("client_id"),
                            "location_id": payload.get("location_id"),
                            "google_review_id": payload.get("google_review_id"),
                            "rating": payload.get("rating"),
                            "comment": payload.get("comment") or payload.get("text"),
                            "reviewer_name": payload.get("reviewer_name"),
                            "reviewer_photo_url": payload.get("reviewer_photo_url"),
                            "review_created_time": payload.get("review_created_time"),
                            "reply_text": payload.get("reply_text"),
                            "reply_time": payload.get("reply_time"),
                            "created_at": payload.get("created_at") or payload.get("timestamp"),
                            "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                        }
                    )
                    dirty = True

                now = time.time()
                if dirty and (now - last_emit) * 1000.0 >= emit_interval_ms:
                    nested = build_nested()
                    yield (
                        f"event: nested\n"
                        f"data: {json.dumps(nested, ensure_ascii=False)}\n\n"
                    ).encode("utf-8")
                    last_emit = now
                    dirty = False

            nested = build_nested()
            yield (
                f"event: nested\n"
                f"data: {json.dumps(nested, ensure_ascii=False)}\n\n"
            ).encode("utf-8")
            yield b"event: done\ndata: {}\n\n"

        finally:
            await consumer.stop()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/v1/demo/stream/reviews")
async def demo_stream_reviews(
    job_id: Optional[str] = Query(None),
    max_items: int = Query(25, ge=1, le=500),
    max_wait_sec: int = Query(60, ge=5, le=600),
) -> StreamingResponse:
    """Server-Sent Events stream of reviews emitted on `reviews-raw`."""

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    async def event_stream() -> AsyncIterator[bytes]:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            "reviews-raw",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="earliest" if job_id else "latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"demo_web_reviews_{int(time.time())}",
            consumer_timeout_ms=1000,
        )

        seen_review_keys: set[str] = set()
        deadline = time.time() + max_wait_sec

        try:
            await consumer.start()
            if not job_id:
                await consumer.seek_to_end()

            while time.time() < deadline and len(seen_review_keys) < max_items:
                try:
                    msg = await consumer.getone()
                except Exception:
                    await asyncio.sleep(0.05)
                    continue

                payload = msg.value or {}
                if job_id and str(payload.get("job_id")) != str(job_id):
                    continue

                key = str(
                    payload.get("google_review_id")
                    or payload.get("id")
                    or payload.get("review_id")
                    or ""
                )
                if not key or key in seen_review_keys:
                    continue
                seen_review_keys.add(key)

                review_obj: dict[str, Any] = {
                    "id": payload.get("id") or payload.get("review_id"),
                    "client_id": payload.get("client_id"),
                    "location_id": payload.get("location_id"),
                    "google_review_id": payload.get("google_review_id"),
                    "rating": payload.get("rating"),
                    "comment": payload.get("comment") or payload.get("text"),
                    "reviewer_name": payload.get("reviewer_name"),
                    "reviewer_photo_url": payload.get("reviewer_photo_url"),
                    "review_created_time": payload.get("review_created_time"),
                    "reply_text": payload.get("reply_text"),
                    "reply_time": payload.get("reply_time"),
                    "created_at": payload.get("created_at") or payload.get("timestamp"),
                    "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                }

                yield (
                    f"event: review\n"
                    f"data: {json.dumps(review_obj, ensure_ascii=False)}\n\n"
                ).encode("utf-8")

            yield b"event: done\ndata: {}\n\n"
        finally:
            await consumer.stop()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
