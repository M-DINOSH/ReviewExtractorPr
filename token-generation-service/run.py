"""
Main entry point for running the application
"""
import uvicorn
from src.token_service.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.token_service.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
