import redis.asyncio as redis
from app.config import settings

redis_client = redis.from_url(settings.redis_url)


async def cache_get(key: str):
    try:
        data = await redis_client.get(key)
        if data:
            import json
            return json.loads(data)
    except Exception:
        pass
    return None


async def cache_set(key: str, value, ttl: int = 3600):
    try:
        import json
        await redis_client.setex(key, ttl, json.dumps(value))
    except Exception:
        pass