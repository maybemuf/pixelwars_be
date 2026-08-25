from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.core import settings

r = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

def get_redis() -> Redis:
    return r

RedisDep = Annotated[Redis, Depends(get_redis)]