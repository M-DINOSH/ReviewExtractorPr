from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Configure connection pooling for scalability
engine = create_async_engine(
    settings.database_url,
    pool_size=20,          # Number of connections to keep in pool
    max_overflow=30,       # Max connections beyond pool_size
    pool_timeout=30,       # Timeout for getting connection from pool
    pool_recycle=1800,     # Recycle connections after 30 minutes
    echo=False
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session