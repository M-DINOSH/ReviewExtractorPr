"""
FastAPI application for Sentiment Analysis Service
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

from sentiment_service.core.config import settings
from sentiment_service.core.logging import setup_logging
from sentiment_service.api.routes import api_router, health_router

# Setup logging
setup_logging()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    start_time = time.time()
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")

    startup_time = time.time() - start_time
    print(f"✅ Service started in {startup_time:.2f}s")
    yield

    print("🛑 Shutting down Sentiment Analysis Service")


def create_application() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="A scalable sentiment analysis service for classifying reviews as positive, negative, or neutral",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security middleware (only in production)
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Configure properly in production
        )

    # Rate limiting middleware
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # Include routers
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(api_router, prefix="/api/v1", tags=["sentiment-analysis"])

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with service information"""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "description": "Sentiment analysis service for classifying reviews",
            "docs": "/docs" if settings.debug else "Disabled in production",
            "health": "/api/v1/health",
            "analyze": "/api/v1/analyze"
        }

    # Metrics endpoint (if enabled)
    if settings.metrics_enabled:
        try:
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            from fastapi.responses import Response

            @app.get("/metrics")
            async def metrics():
                """Prometheus metrics endpoint"""
                return Response(
                    generate_latest(),
                    media_type=CONTENT_TYPE_LATEST
                )
        except ImportError:
            pass  # Prometheus not installed

    # Add exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        from sentiment_service.models.schemas import ErrorResponse
        from fastapi.responses import JSONResponse
        import time

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error="HTTP_EXCEPTION",
                message=exc.detail,
                timestamp=time.time()
            ).dict()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions"""
        from sentiment_service.core.logging import get_logger
        from sentiment_service.models.schemas import ErrorResponse
        from fastapi.responses import JSONResponse
        from fastapi import status
        import time

        logger = get_logger(__name__)
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                timestamp=time.time()
            ).dict()
        )

    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )