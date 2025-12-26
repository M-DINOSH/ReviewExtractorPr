from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.services.sync_service import SyncService
import structlog

logger = structlog.get_logger()


async def sync_reviews_task(access_token: str, client_id: str, sync_job_id: int):
    async with async_session() as db:
        service = SyncService(db)
        await service.sync_reviews(access_token, client_id, sync_job_id)