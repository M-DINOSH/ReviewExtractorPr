"""
FastAPI routes for Review Fetcher service
Implements Clean Architecture with dependency injection
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import StreamingResponse
from typing import Annotated
import logging
import uuid
from datetime import datetime, timezone
import time
import json
from typing import Any, AsyncIterator, Optional
import asyncio

from app.models import (
    ReviewFetchRequest, ReviewFetchResponse, HealthCheckResponse, StreamSessionRequest, StreamSessionResponse
)
from app.deque_buffer import BoundedDequeBuffer
from app.kafka_producer import KafkaEventPublisher
from app.config import get_settings
from app.services.google_api import GoogleAPIClient, GoogleAPIError

logger = logging.getLogger(__name__)

# Create router (will be added to FastAPI app in main.py)
router = APIRouter(prefix="/api/v1", tags=["review-fetcher"])


class APIService:
    """
    Service class for API business logic
    Implements Dependency Injection pattern
    """
    
    def __init__(
        self,
        deque_buffer: BoundedDequeBuffer,
        event_publisher: KafkaEventPublisher,
        settings = None
    ):
        self.deque_buffer = deque_buffer
        self.event_publisher = event_publisher
        self.settings = settings or get_settings()
        self.job_tracking: dict = {}  # In-memory job state
        self.stream_sessions: dict[str, dict[str, Any]] = {}  # {session_id: {access_token, expires_at}}
        self.google_api_client = GoogleAPIClient()  # Initialize Google API client

    def create_stream_session(self, access_token: str, ttl_sec: int = 120) -> StreamSessionResponse:
        """Create a short-lived stream session.

        This keeps the access token out of the URL while still allowing SSE consumption.
        Note: in multi-replica deployments this must be backed by shared storage (e.g. Redis).
        """

        session_id = str(uuid.uuid4())
        expires_at = time.time() + max(10, int(ttl_sec))
        self.stream_sessions[session_id] = {
            "access_token": access_token,
            "expires_at": expires_at,
            "created_at": datetime.utcnow().isoformat(),
        }
        return StreamSessionResponse(session_id=session_id, expires_in_sec=max(10, int(ttl_sec)))

    def pop_stream_session(self, session_id: str) -> Optional[str]:
        rec = self.stream_sessions.pop(session_id, None)
        if not rec:
            return None
        if float(rec.get("expires_at") or 0) < time.time():
            return None
        return str(rec.get("access_token") or "")
    
    async def validate_access_token(self, token: str) -> bool:
        """
        Validate Google OAuth access token
        Uses GoogleAPIClient which handles both mock and real API
        """
        if not token or len(token.strip()) == 0:
            return False
        
        try:
            result = await self.google_api_client.validate_token(token)
            logger.info(f"token_validation_result: {result}")
            return result.get("valid", False)
        except Exception as e:
            logger.error(f"token_validation_error: {str(e)} ({type(e).__name__})")
            return False
    
    async def create_fetch_job(self, request: ReviewFetchRequest) -> ReviewFetchResponse:
        """
        Create a new review fetch job
        
        Returns: ReviewFetchResponse with job_id
        Raises: HTTPException on error
        """
        # Validate token
        is_valid = await self.validate_access_token(request.access_token)
        if not is_valid:
            logger.warning("invalid_access_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Try to enqueue job into deque
        enqueued = await self.deque_buffer.enqueue({
            "job_id": job_id,
            "access_token": request.access_token,
            "created_at": datetime.utcnow().isoformat()
        })
        
        if not enqueued:
            logger.warning("job_enqueue_failed_deque_full job_id=%s", job_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service is at capacity. Please retry after a few seconds."
            )
        
        # Track job
        self.job_tracking[job_id] = {
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "access_token": request.access_token
        }
        
        logger.info("job_created job_id=%s", job_id)
        
        return ReviewFetchResponse(job_id=job_id)
    
    def get_job_status(self, job_id: str) -> dict:
        """Get current job status"""
        if job_id not in self.job_tracking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        return self.job_tracking.get(job_id, {})
    
    async def get_health(self) -> HealthCheckResponse:
        """Get service health status"""
        deque_load = await self.deque_buffer.get_load_percent()
        
        return HealthCheckResponse(
            status="healthy" if deque_load < 90 else "degraded",
            service=self.settings.service_name,
            version=self.settings.version,
            kafka_connected=True,  # Placeholder
            memory_used_percent=deque_load
        )


# Global API service instance
_api_service: APIService = None


def get_api_service() -> APIService:
    """Dependency injection for API service"""
    global _api_service
    return _api_service


def set_api_service(service: APIService) -> None:
    """Set the global API service instance (called from main.py)"""
    global _api_service
    _api_service = service


@router.post(
    "/review-fetch",
    response_model=ReviewFetchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate review fetch job",
    description="Submit a Google OAuth token to start fetching reviews"
)
async def fetch_reviews(
    request: ReviewFetchRequest,
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> ReviewFetchResponse:
    """
    POST /api/v1/review-fetch
    
    Accepts a Google OAuth access token and creates an async job
    to fetch reviews from Google Business Profile API.
    
    Returns immediately with job_id (async processing).
    Client can poll /api/v1/status/{job_id} for progress.
    
    Responses:
    - 202: Job queued successfully
    - 400: Invalid request
    - 401: Invalid token
    - 429: Service at capacity
    - 500: Internal error
    """
    return await api_service.create_fetch_job(request)


@router.get(
    "/status/{job_id}",
    response_model=dict,
    summary="Get job status",
    description="Check the status of a review fetch job"
)
async def get_status(
    job_id: str,
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> dict:
    """
    GET /api/v1/status/{job_id}
    
    Get current status of a job.
    
    Status values: queued, processing, completed, failed
    """
    return api_service.get_job_status(job_id)


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check service health"
)
async def health_check(
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> HealthCheckResponse:
    """
    GET /api/v1/health
    
    Returns service health status.
    
    Used by Kubernetes liveness/readiness probes.
    """
    return await api_service.get_health()


@router.get(
    "/metrics",
    summary="Get service metrics",
    description="Get operational metrics"
)
async def get_metrics(
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> dict:
    """
    GET /api/v1/metrics
    
    Returns service metrics for monitoring.
    """
    deque_metrics = api_service.deque_buffer.get_metrics()
    
    return {
        "deque": deque_metrics,
        "jobs_tracked": len(api_service.job_tracking),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get(
    "/reviews",
    summary="Get published reviews",
    description="Get all reviews published to reviews-raw topic (mock mode only)"
)
async def get_reviews(
    api_service: Annotated[APIService, Depends(get_api_service)],
    topic: str = "reviews-raw"
) -> dict:
    """
    GET /api/v1/reviews
    
    Returns all reviews that have been published to the reviews-raw Kafka topic.
    Only works in mock mode.
    """
    messages = api_service.event_publisher.producer.get_messages(topic=topic)
    reviews = [msg["message"] for msg in messages if msg.get("topic") == topic]
    
    return {
        "topic": topic,
        "total_reviews": len(reviews),
        "reviews": reviews,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post(
    "/stream-session",
    response_model=StreamSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create stream session",
    description="Creates a short-lived session so you can open an SSE stream without putting the access token in the URL."
)
async def create_stream_session(
    request: StreamSessionRequest,
    api_service: Annotated[APIService, Depends(get_api_service)],
) -> StreamSessionResponse:
    # Validate token using the same rules as job creation.
    is_valid = await api_service.validate_access_token(request.access_token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return api_service.create_stream_session(request.access_token, ttl_sec=120)


@router.get(
    "/stream/nested",
    summary="Stream nested reviews (Kafka-backed)",
    description="Streams accounts → locations → reviews aggregated from Kafka for a job. Use session_id for production-safe create-and-stream."
)
async def stream_nested(
    job_id: Optional[str] = Query(None, min_length=1, description="Existing job id to stream"),
    session_id: Optional[str] = Query(None, min_length=1, description="Stream session id from POST /api/v1/stream-session"),
    max_wait_sec: int = Query(60, ge=5, le=600),
    max_accounts: int = Query(50, ge=1, le=500),
    max_locations_total: int = Query(2000, ge=1, le=10000),
    max_reviews_per_location: int = Query(200, ge=1, le=5000),
    emit_interval_ms: int = Query(250, ge=50, le=2000),
    api_service: Annotated[APIService, Depends(get_api_service)] = None,
) -> StreamingResponse:
    """Production SSE endpoint.

    Modes:
    - session_id: safest for browsers (token is sent via POST, then GET uses session_id). Server attaches to Kafka, seeks to end, then creates a new job.
    - job_id: stream an already-created job. Attempts to seek near job creation time (if known) to avoid scanning old Kafka history.
    """

    if (job_id is None and session_id is None) or (job_id is not None and session_id is not None):
        raise HTTPException(status_code=400, detail="Provide exactly one of job_id or session_id")

    settings = get_settings()
    bootstrap_servers = settings.kafka.get_bootstrap_servers_list()

    async def event_stream() -> AsyncIterator[bytes]:
        from aiokafka import AIOKafkaConsumer

        create_job_mode = session_id is not None
        resolved_job_id: str

        consumer = AIOKafkaConsumer(
            "fetch-locations",
            "fetch-reviews",
            "reviews-raw",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="latest" if create_job_mode else "earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"prod_stream_nested_{int(time.time())}",
            consumer_timeout_ms=1000,
        )

        # Aggregation state
        accounts_by_id: dict[int, dict[str, Any]] = {}
        locations_by_id: dict[int, dict[str, Any]] = {}
        locations_by_account_id: dict[int, set[int]] = {}
        reviews_by_location_id: dict[int, list[dict[str, Any]]] = {}

        last_emit = 0.0
        dirty = False
        deadline = time.time() + max_wait_sec

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

        def build_nested_all() -> dict[str, Any]:
            # Build accounts → locations → reviews (all accounts).
            out_accounts: list[dict[str, Any]] = []
            out_locations_total = 0
            out_reviews_total = 0

            for acc_id in sorted(accounts_by_id.keys()):
                acc = accounts_by_id[acc_id]
                loc_ids = sorted(list(locations_by_account_id.get(acc_id, set())))
                locs: list[dict[str, Any]] = []
                for loc_id in loc_ids:
                    if out_locations_total >= max_locations_total:
                        break
                    loc = locations_by_id.get(loc_id)
                    if not loc:
                        continue
                    loc_out = dict(loc)
                    revs = list(reviews_by_location_id.get(loc_id, []))[:max_reviews_per_location]
                    loc_out["reviews"] = revs
                    locs.append(loc_out)
                    out_locations_total += 1
                    out_reviews_total += len(revs)

                out_accounts.append({
                    "account": acc,
                    "locations": locs,
                    "stats": {"locations": len(locs), "reviews": sum(len(l.get("reviews") or []) for l in locs)},
                })
                if len(out_accounts) >= max_accounts:
                    break

            # Joins checks (best-effort)
            joins_ok_account = True
            joins_ok_reviews = True
            for acc_block in out_accounts:
                acc = acc_block.get("account") or {}
                acc_id = _as_int_id(acc.get("account_id"))
                for loc in acc_block.get("locations") or []:
                    if acc_id is not None and _as_int_id(loc.get("google_account_id")) != acc_id:
                        joins_ok_account = False
                        break
                    loc_id = _as_int_id(loc.get("location_id"))
                    for rev in loc.get("reviews") or []:
                        if loc_id is not None and _as_int_id(rev.get("location_id")) != loc_id:
                            joins_ok_reviews = False
                            break
                    if not joins_ok_reviews:
                        break
                if not joins_ok_account and not joins_ok_reviews:
                    break

            return {
                "job_id": resolved_job_id,
                "accounts": out_accounts,
                "stats": {"accounts": len(out_accounts), "locations": out_locations_total, "reviews": out_reviews_total},
                "joins_ok": {
                    "account.account_id == location.google_account_id": joins_ok_account,
                    "location.location_id == review.location_id": joins_ok_reviews,
                },
            }

        async def _seek_near_job_created(consumer: AIOKafkaConsumer, created_at_iso: str) -> None:
            # Seek by Kafka record timestamps (approx) to avoid scanning old history.
            try:
                dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
            except Exception:
                return
            if dt.tzinfo is None:
                # Treat naive timestamps as UTC
                dt = dt.replace(tzinfo=timezone.utc)
                created_ms = int(dt.timestamp() * 1000)
            else:
                created_ms = int(dt.timestamp() * 1000)

            # Ensure assignment exists
            await consumer.getmany(timeout_ms=0)
            tps = consumer.assignment()
            if not tps:
                return
            offsets = await consumer.offsets_for_times({tp: created_ms for tp in tps})
            for tp, oat in offsets.items():
                if oat is None:
                    continue
                try:
                    consumer.seek(tp, oat.offset)
                except Exception:
                    continue

        try:
            await consumer.start()

            if create_job_mode:
                token = api_service.pop_stream_session(str(session_id))
                if not token:
                    raise HTTPException(status_code=404, detail="Invalid or expired session_id")

                # Attach first, then create job.
                await consumer.getmany(timeout_ms=0)
                await consumer.seek_to_end()

                job = await api_service.create_fetch_job(ReviewFetchRequest(access_token=token))
                resolved_job_id = job.job_id
                yield (f"event: job\n" f"data: {json.dumps({'job_id': resolved_job_id})}\n\n").encode("utf-8")
            else:
                resolved_job_id = str(job_id)
                job_info = api_service.job_tracking.get(resolved_job_id)
                if isinstance(job_info, dict) and job_info.get("created_at"):
                    await _seek_near_job_created(consumer, str(job_info["created_at"]))

            while time.time() < deadline:
                try:
                    msg = await consumer.getone()
                except Exception:
                    await asyncio.sleep(0.05)
                    now = time.time()
                    if dirty and (now - last_emit) * 1000.0 >= emit_interval_ms:
                        payload = build_nested_all()
                        yield (f"event: nested\n" f"data: {json.dumps(payload, ensure_ascii=False)}\n\n").encode("utf-8")
                        last_emit = now
                        dirty = False
                    continue

                payload = msg.value or {}
                if str(payload.get("job_id")) != str(resolved_job_id):
                    continue

                if msg.topic == "fetch-locations":
                    acc_id = _as_int_id(payload.get("account_id"))
                    if acc_id is None:
                        continue
                    accounts_by_id.setdefault(
                        acc_id,
                        {
                            "id": payload.get("id", acc_id),
                            "account_id": payload.get("account_id", acc_id),
                            "client_id": payload.get("client_id", 1),
                            "google_account_name": payload.get("google_account_name"),
                            "account_display_name": payload.get("account_display_name") or payload.get("account_name"),
                            "created_at": payload.get("created_at") or payload.get("timestamp"),
                            "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                        },
                    )
                    dirty = True

                elif msg.topic == "fetch-reviews":
                    gaid = _as_int_id(payload.get("google_account_id"))
                    if gaid is None:
                        # Some messages might only carry account_id
                        gaid = _as_int_id(payload.get("account_id"))
                    if gaid is None:
                        continue
                    loc_id = _as_int_id(payload.get("location_id", payload.get("id")))
                    if loc_id is None:
                        continue

                    locations_by_account_id.setdefault(gaid, set()).add(loc_id)
                    locations_by_id.setdefault(
                        loc_id,
                        {
                            "id": payload.get("id", loc_id),
                            "location_id": payload.get("location_id", loc_id),
                            "client_id": payload.get("client_id", 1),
                            "google_account_id": payload.get("google_account_id") or gaid,
                            "location_name": payload.get("location_name"),
                            "location_title": payload.get("location_title") or payload.get("name"),
                            "address": payload.get("address"),
                            "phone": payload.get("phone"),
                            "category": payload.get("category"),
                            "created_at": payload.get("created_at") or payload.get("timestamp"),
                            "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                        },
                    )
                    dirty = True

                elif msg.topic == "reviews-raw":
                    loc_id = _as_int_id(payload.get("location_id"))
                    if loc_id is None:
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
                    nested = build_nested_all()
                    yield (f"event: nested\n" f"data: {json.dumps(nested, ensure_ascii=False)}\n\n").encode("utf-8")
                    last_emit = now
                    dirty = False

            nested = build_nested_all()
            yield (f"event: nested\n" f"data: {json.dumps(nested, ensure_ascii=False)}\n\n").encode("utf-8")
            yield b"event: done\ndata: {}\n\n"

        finally:
            await consumer.stop()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
