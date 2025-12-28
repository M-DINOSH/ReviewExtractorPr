from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.services.sync_service import SyncService
import structlog

logger = structlog.get_logger()


from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.services.sync_service import SyncService
import structlog

logger = structlog.get_logger()


async def sync_reviews_task(access_token: str, client_id: str, sync_job_id: int):
    """Execute the continuous sync flow automatically"""
    async with async_session() as db:
        service = SyncService(db)
        # Use the new continuous flow method
        await service.start_sync_flow(access_token, client_id, sync_job_id)