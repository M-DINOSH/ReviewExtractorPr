#!/usr/bin/env python3
"""
Run script for Sentiment Analysis Service
"""
import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# Import and run the application
from sentiment_service.api.main import app

if __name__ == "__main__":
    import uvicorn
    from sentiment_service.core.config import settings

    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📍 Environment: {settings.environment}")
    print(f"🌐 Host: {settings.host}:{settings.port}")

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )