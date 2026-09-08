from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.core import settings

redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)


def get_redis() -> Redis:
    """Indirection exists so tests can override it via app.dependency_overrides."""
    return redis


RedisDep = Annotated[Redis, Depends(get_redis)]
