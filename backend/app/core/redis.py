import logging
import redis.asyncio as aioredis
from .config import settings

logger = logging.getLogger(__name__)
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.ping()
            _redis = client
        except Exception:
            if settings.environment == "development":
                logger.warning("Redis unavailable — falling back to fakeredis for local dev")
                import fakeredis.aioredis as fakeredis
                _redis = fakeredis.FakeRedis(decode_responses=True)
            else:
                raise
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
