import asyncio

from fastapi import APIRouter, Response
from redis.exceptions import RedisError

from app.deps import RedisDep

# A readiness probe that can hang is worse than none: it turns a dead dependency
# into a stuck request instead of a fast 503.
REDIS_PING_TIMEOUT = 2

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("/live")
async def liveness():
    """Is the process up? Deliberately dependency-free — a failure here means restart me."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(redis: RedisDep, response: Response):
    """Can we actually serve? Redis holds the board, the sessions and the presence set."""
    try:
        async with asyncio.timeout(REDIS_PING_TIMEOUT):
            await redis.ping()
    except (RedisError, TimeoutError, OSError):
        response.status_code = 503
        return {"status": "unavailable", "redis": "down"}

    return {"status": "ok", "redis": "up"}
