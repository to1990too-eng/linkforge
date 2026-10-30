from redis.asyncio import Redis

from app.config import settings

redis_client: Redis | None = None


async def init_redis() -> Redis:
    global redis_client
    redis_client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()  # type: ignore[attr-defined]
        redis_client = None


def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return redis_client