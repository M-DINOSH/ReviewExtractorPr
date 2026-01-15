"""Demo web UI and streaming endpoints.

Provides a simple HTML page that renders Kafka pipeline output in-browser.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Body, Query, Depends
from fastapi.responses import HTMLResponse, StreamingResponse

from app.config import get_settings
from app.api import APIService, get_api_service
from app.models import ReviewFetchRequest
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
        <h2>Final nested output (Kafka pipeline)</h2>
        <div class=\"muted\">Aggregates Kafka topics into one nested output by job_id. Uses the same access token from above.</div>\
    <div class=\"row\">
      <label for=\"token\"><b>Access token</b></label>
            <input id=\"token\" placeholder=\"paste token (mock mode accepts any non-empty token)\" />
      <button id=\"btnNested\">Generate</button>
    </div>
    <pre><code id=\"nested\">(click Generate)</code></pre>
  </div>

  <div class=\"card\" style=\"margin-top: 12px;\">
    <h2>Kafka nested stream (SSE)</h2>
        <div class=\"muted\">Production-safe streaming (token in POST body → session_id, then SSE).</div>

    <div class=\"row\">
      <button id=\"startBtn\">Start review fetch + stream</button>
            <span class=\"pill\">API: <code>/api/v1/stream-session</code></span>
            <span class=\"pill\">Stream: <code>/api/v1/stream/nested</code></span>
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

        function computeCountsFromPayload(p) {
            if (!p || typeof p !== 'object') return { accounts: 0, locations: 0, reviews: 0 };
            if (p.stats && typeof p.stats === 'object') {
                return {
                    accounts: Number(p.stats.accounts || 0),
                    locations: Number(p.stats.locations || 0),
                    reviews: Number(p.stats.reviews || 0),
                };
            }

            // Fallback (shouldn't be needed): count from accounts/locations/reviews.
            let accounts = 0;
            let locations = 0;
            let reviews = 0;
            if (Array.isArray(p.accounts)) {
                accounts = p.accounts.length;
                for (const a of p.accounts) {
                    if (Array.isArray(a.locations)) {
                        locations += a.locations.length;
                        for (const l of a.locations) {
                            if (Array.isArray(l.reviews)) reviews += l.reviews.length;
                        }
                    }
                }
            }
            return { accounts, locations, reviews };
        }

    function render() {
      if (latestNested) {
        outNested.textContent = pretty(latestNested);
                const c = computeCountsFromPayload(latestNested);
                countAccountsEl.textContent = String(c.accounts);
                countLocationsEl.textContent = String(c.locations);
                countReviewsEl.textContent = String(c.reviews);
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

            const access_token = document.getElementById('token').value || '';
            if (!access_token.trim()) {
                startBtn.disabled = false;
                alert('Please paste an access token first. In mock mode any non-empty value works.');
                return;
            }

                        // 1) Create short-lived session_id (keeps token out of the URL).
                        const sessResp = await fetch('/api/v1/stream-session', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ access_token })
                        });
                        if (!sessResp.ok) {
                            startBtn.disabled = false;
                            const txt = await sessResp.text();
                            alert(`Failed to create stream session (${sessResp.status}): ${txt}`);
                            return;
                        }
                        const sess = await sessResp.json();
                        const session_id = sess.session_id;
                        if (!session_id) {
                            startBtn.disabled = false;
                            alert('Stream session response missing session_id');
                            return;
                        }

                        // 2) Start SSE stream; server will attach, then create a new job and emit event: job.
                        esNested = new EventSource(`/api/v1/stream/nested?session_id=${encodeURIComponent(session_id)}&max_wait_sec=60&max_accounts=50&max_locations_total=200&max_reviews_per_location=200`);
            esNested.addEventListener('job', (ev) => {
                try {
                    const info = JSON.parse(ev.data);
                    jobIdEl.textContent = info.job_id || '(unknown)';
                } catch (e) {
                    console.error('bad job payload', e, ev.data);
                }
            });
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
  api_service: APIService = Depends(get_api_service),
) -> dict[str, Any]:
    """Return nested output: account → locations → reviews (Kafka pipeline).

    This endpoint runs the SAME pipeline as production:
    - Enqueue job via the same API service
    - Workers publish to Kafka topics
    - This endpoint consumes Kafka topics and aggregates them by job_id

    Mock vs real behavior:
    - Controlled by `MOCK_GOOGLE_API`
    - Mock mode reads from `jsom/`
    - Real mode calls Google APIs
    """

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token is required")

    max_wait_sec = max(5, int(payload.get("max_wait_sec", 30)))
    max_locations = max(0, int(payload.get("max_locations", 500)))
    max_reviews_per_location = max(0, int(payload.get("max_reviews_per_location", 500)))

    # IMPORTANT: this endpoint must NOT start consuming from "earliest".
    # These topics can be large; starting from earliest would require scanning
    # historical traffic before reaching this job's events.
    # We instead seek to the end first, then trigger a new job.
    from aiokafka import AIOKafkaConsumer

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    def _as_int_id(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            s = str(value)
            if "/" in s:
                s = s.split("/")[-1]
            return int(s)
        except Exception:
            return None

    consumer = AIOKafkaConsumer(
        "fetch-locations",
        "fetch-reviews",
        "reviews-raw",
        bootstrap_servers=bootstrap_servers,
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id=f"demo_web_nested_one_shot_{int(time.time())}",
        consumer_timeout_ms=1000,
    )

    accounts_by_id: dict[int, dict[str, Any]] = {}
    pending_locations_by_account: dict[int, dict[int, dict[str, Any]]] = {}
    locations_by_id: dict[int, dict[str, Any]] = {}
    reviews_by_location_id: dict[int, list[dict[str, Any]]] = {}

    selected_account: Optional[dict[str, Any]] = None
    selected_account_id: Optional[int] = None
    job_id: Optional[str] = None
    start = time.time()
    deadline = start + max_wait_sec

    def _maybe_select_account() -> None:
        nonlocal selected_account, selected_account_id
        if selected_account_id is not None:
            return
        if not accounts_by_id:
            return
        candidates = [accounts_by_id[k] for k in sorted(accounts_by_id.keys())]
        selected_account = _pick_account_by_token(access_token, candidates)
        selected_account_id = _as_int_id(selected_account.get("account_id") or selected_account.get("id"))
        if selected_account_id is None:
            selected_account = None
            return
        locations_by_id.update(pending_locations_by_account.get(selected_account_id, {}))

    try:
        await consumer.start()
        # Force partition assignment before seeking.
        await consumer.getmany(timeout_ms=0)
        await consumer.seek_to_end()

        # Create a new job via the same codepath as production.
        job = await api_service.create_fetch_job(ReviewFetchRequest(access_token=access_token))
        job_id = job.job_id

        while time.time() < deadline:
            try:
                msg = await consumer.getone()
            except Exception:
                await asyncio.sleep(0.05)
                _maybe_select_account()
                continue

            payload_msg = msg.value or {}
            if not job_id or str(payload_msg.get("job_id")) != str(job_id):
                continue

            if msg.topic == "fetch-locations":
                acc_id = _as_int_id(payload_msg.get("account_id"))
                if acc_id is None:
                    continue
                accounts_by_id.setdefault(
                    acc_id,
                    {
                        "id": payload_msg.get("id", acc_id),
                        "account_id": payload_msg.get("account_id", acc_id),
                        "client_id": payload_msg.get("client_id", 1),
                        "google_account_name": payload_msg.get("google_account_name"),
                        "account_display_name": payload_msg.get("account_display_name") or payload_msg.get("account_name"),
                        "created_at": payload_msg.get("created_at") or payload_msg.get("timestamp"),
                        "updated_at": payload_msg.get("updated_at") or payload_msg.get("timestamp"),
                    },
                )
                if (time.time() - start) >= 1.0 or len(accounts_by_id) >= 10:
                    _maybe_select_account()

            elif msg.topic == "fetch-reviews":
                gaid = _as_int_id(payload_msg.get("google_account_id"))
                loc_id = _as_int_id(payload_msg.get("location_id") or payload_msg.get("id"))
                if gaid is None or loc_id is None:
                    continue

                loc_obj = {
                    "id": payload_msg.get("id", loc_id),
                    "location_id": payload_msg.get("location_id", loc_id),
                    "client_id": payload_msg.get("client_id", 1),
                    "google_account_id": payload_msg.get("google_account_id"),
                    "location_name": payload_msg.get("location_name"),
                    "location_title": payload_msg.get("location_title") or payload_msg.get("name"),
                    "address": payload_msg.get("address"),
                    "phone": payload_msg.get("phone"),
                    "category": payload_msg.get("category"),
                    "created_at": payload_msg.get("created_at") or payload_msg.get("timestamp"),
                    "updated_at": payload_msg.get("updated_at") or payload_msg.get("timestamp"),
                }

                pending_locations_by_account.setdefault(gaid, {})
                pending_locations_by_account[gaid].setdefault(loc_id, loc_obj)

                _maybe_select_account()
                if selected_account_id is not None and gaid == int(selected_account_id):
                    if len(locations_by_id) < max_locations:
                        locations_by_id.setdefault(loc_id, loc_obj)

            elif msg.topic == "reviews-raw":
                loc_id = _as_int_id(payload_msg.get("location_id"))
                if loc_id is None:
                    continue

                review_account_id = _as_int_id(payload_msg.get("account_id"))
                if selected_account_id is not None and review_account_id is not None:
                    if review_account_id != int(selected_account_id):
                        continue

                reviews_by_location_id.setdefault(loc_id, [])
                if len(reviews_by_location_id[loc_id]) >= max_reviews_per_location:
                    continue
                reviews_by_location_id[loc_id].append(
                    {
                        "id": payload_msg.get("id"),
                        "client_id": payload_msg.get("client_id"),
                        "account_id": payload_msg.get("account_id"),
                        "location_id": payload_msg.get("location_id"),
                        "google_review_id": payload_msg.get("google_review_id"),
                        "rating": payload_msg.get("rating"),
                        "comment": payload_msg.get("comment") or payload_msg.get("text"),
                        "reviewer_name": payload_msg.get("reviewer_name"),
                        "reviewer_photo_url": payload_msg.get("reviewer_photo_url"),
                        "review_created_time": payload_msg.get("review_created_time"),
                        "reply_text": payload_msg.get("reply_text"),
                        "reply_time": payload_msg.get("reply_time"),
                        "created_at": payload_msg.get("created_at") or payload_msg.get("timestamp"),
                        "updated_at": payload_msg.get("updated_at") or payload_msg.get("timestamp"),
                    }
                )

        _maybe_select_account()

    finally:
        await consumer.stop()

    # Build final nested output
    if selected_account_id is None and accounts_by_id:
        selected_account_id = sorted(accounts_by_id.keys())[0]
        selected_account = accounts_by_id[selected_account_id]
        locations_by_id.update(pending_locations_by_account.get(selected_account_id, {}))

    locations_out: list[dict[str, Any]] = []
    for loc_id in sorted(locations_by_id.keys()):
        loc = dict(locations_by_id[loc_id])
        loc_reviews = list(reviews_by_location_id.get(loc_id, []))
        if selected_account_id is not None:
            loc_reviews = [r for r in loc_reviews if _as_int_id(r.get("account_id")) == int(selected_account_id)]
        loc["reviews"] = loc_reviews[:max_reviews_per_location]
        locations_out.append(loc)

    joins_ok_account = True
    if selected_account_id is not None:
        for loc in locations_out:
            if _as_int_id(loc.get("google_account_id")) != int(selected_account_id):
                joins_ok_account = False
                break

    joins_ok_reviews = True
    for loc in locations_out:
        lid = _as_int_id(loc.get("location_id"))
        if lid is None:
            joins_ok_reviews = False
            break
        for rev in (loc.get("reviews") or []):
            if _as_int_id(rev.get("location_id")) != lid:
                joins_ok_reviews = False
                break
        if not joins_ok_reviews:
            break

    return {
        "job_id": job_id,
        "account": selected_account,
        "locations": locations_out,
        "stats": {"locations": len(locations_out), "reviews": sum(len(l.get("reviews") or []) for l in locations_out)},
        "joins_ok": {
            "account.account_id == location.google_account_id": joins_ok_account,
            "location.location_id == review.location_id": joins_ok_reviews,
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
    job_id: Optional[str] = Query(None, min_length=1),
    access_token: Optional[str] = Query(None, min_length=1),
    max_wait_sec: int = Query(60, ge=5, le=600),
    max_locations: int = Query(500, ge=1, le=5000),
    max_reviews_per_location: int = Query(500, ge=1, le=5000),
    emit_interval_ms: int = Query(250, ge=50, le=2000),
    api_service: APIService = Depends(get_api_service),
) -> StreamingResponse:
    """Kafka-backed nested stream: account → locations → reviews."""

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    async def event_stream() -> AsyncIterator[bytes]:
        from aiokafka import AIOKafkaConsumer

        token = (access_token or "").strip()
        create_job_mode = job_id is None
        if create_job_mode and not token:
            raise HTTPException(status_code=400, detail="Provide either job_id or access_token")

        consumer = AIOKafkaConsumer(
            "fetch-locations",
            "fetch-reviews",
            "reviews-raw",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="latest" if create_job_mode else "earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"demo_web_nested_{int(time.time())}",
            consumer_timeout_ms=1000,
        )

        account_obj: Optional[dict[str, Any]] = None
        account_id: Optional[int] = None
        accounts_by_id: dict[int, dict[str, Any]] = {}
        pending_locations_by_account: dict[int, dict[int, dict[str, Any]]] = {}
        locations_by_id: dict[int, dict[str, Any]] = {}
        reviews_by_location_id: dict[int, list[dict[str, Any]]] = {}

        last_emit = 0.0
        deadline = time.time() + max_wait_sec
        dirty = False

        def _as_int_id(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                s = str(value)
                if "/" in s:
                    s = s.split("/")[-1]
                return int(s)
            except Exception:
                return None

        def build_nested() -> dict[str, Any]:
            locs: list[dict[str, Any]] = []
            for loc_id, loc in locations_by_id.items():
                loc_with_reviews = dict(loc)
                all_reviews = reviews_by_location_id.get(loc_id, [])
                if account_id is not None:
                    all_reviews = [
                        r for r in all_reviews
                        if _as_int_id(r.get("account_id")) == int(account_id)
                    ]
                loc_reviews = all_reviews[:max_reviews_per_location]
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

            total_reviews = sum(len(loc.get("reviews") or []) for loc in locs)

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

            if create_job_mode:
                # Ensure we only stream data for a new job created after we attach.
                await consumer.getmany(timeout_ms=0)
                await consumer.seek_to_end()
                job = await api_service.create_fetch_job(
                    ReviewFetchRequest(access_token=token)
                )
                resolved_job_id = job.job_id
                yield (
                    f"event: job\n"
                    f"data: {json.dumps({'job_id': resolved_job_id})}\n\n"
                ).encode("utf-8")
            else:
                resolved_job_id = str(job_id)

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
                if str(payload.get("job_id")) != str(resolved_job_id):
                    continue

                if msg.topic == "fetch-locations":
                    acc_id = payload.get("account_id")
                    if acc_id is None:
                        continue
                    acc_id_int = _as_int_id(acc_id)
                    if acc_id_int is None:
                        continue

                    accounts_by_id.setdefault(
                        acc_id_int,
                        {
                            "id": payload.get("id", acc_id_int),
                            "account_id": payload.get("account_id", acc_id_int),
                            "client_id": payload.get("client_id", 1),
                            "google_account_name": payload.get("google_account_name"),
                            "account_display_name": payload.get("account_display_name")
                            or payload.get("account_name"),
                            "created_at": payload.get("created_at") or payload.get("timestamp"),
                            "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                        },
                    )

                    if account_obj is None:
                        account_id = acc_id_int
                        account_obj = accounts_by_id[acc_id_int]

                        # If locations arrived before accounts, merge them now.
                        for loc_id, loc_obj in pending_locations_by_account.get(acc_id_int, {}).items():
                            if len(locations_by_id) >= max_locations:
                                break
                            locations_by_id.setdefault(loc_id, loc_obj)

                        dirty = True

                elif msg.topic == "fetch-reviews":
                    gaid = _as_int_id(payload.get("google_account_id"))
                    if gaid is None:
                        continue
                    try:
                        loc_id = int(payload.get("location_id", payload.get("id")))
                    except Exception:
                        continue

                    loc_obj = {
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

                    pending_locations_by_account.setdefault(gaid, {})
                    pending_locations_by_account[gaid].setdefault(loc_id, loc_obj)

                    # If we already know which account to display, project only those locations.
                    if account_id is not None and gaid == int(account_id):
                        if len(locations_by_id) < max_locations:
                            locations_by_id.setdefault(loc_id, loc_obj)
                            dirty = True

                elif msg.topic == "reviews-raw":
                    loc_id = _as_int_id(payload.get("location_id"))
                    if loc_id is None:
                        continue

                    review_account_id = _as_int_id(payload.get("account_id"))
                    if account_id is not None and review_account_id is not None and review_account_id != int(account_id):
                        continue

                    reviews_by_location_id.setdefault(loc_id, [])
                    if len(reviews_by_location_id[loc_id]) >= max_reviews_per_location:
                        continue
                    reviews_by_location_id[loc_id].append(
                        {
                            "id": payload.get("id"),
                            "client_id": payload.get("client_id"),
                            "account_id": payload.get("account_id"),
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
