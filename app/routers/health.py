import asyncio
import logging

from fastapi import APIRouter, Response
from redis.exceptions import RedisError

from app.deps import RedisDep
from app.schemas import HealthStatus

# A readiness probe that can hang is worse than none: it turns a dead dependency
# into a stuck request instead of a fast 503.
REDIS_PING_TIMEOUT = 2

logger = logging.getLogger(__name__)

# Probes hit this every few seconds, so logging every failed ping would bury the rest of
# the log inside a single outage. Only the up<->down transitions are news.
# ponytail: per-process flag, so N workers each report the transition once.
_redis_reachable = True

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get(
    "/live",
    response_model=HealthStatus,
    response_model_exclude_none=True,
    summary="Liveness probe",
    responses={200: {"description": "The process is running."}},
)
async def liveness() -> HealthStatus:
    """Is the process up? Deliberately dependency-free — a failure here means restart me."""
    return HealthStatus(status="ok")


@router.get(
    "/ready",
    response_model=HealthStatus,
    summary="Readiness probe",
    responses={
        200: {"description": "Redis reachable; safe to route traffic here."},
        503: {
            "model": HealthStatus,
            "description": "Redis unreachable or too slow. Board, sessions and presence all live there.",
        },
    },
)
async def readiness(redis: RedisDep, response: Response) -> HealthStatus:
    """Can we actually serve? Redis holds the board, the sessions and the presence set."""
    global _redis_reachable

    try:
        async with asyncio.timeout(REDIS_PING_TIMEOUT):
            await redis.ping()
    except (RedisError, TimeoutError, OSError) as exc:
        if _redis_reachable:
            logger.error("readiness failing: redis unreachable (%s)", exc)
            _redis_reachable = False
        response.status_code = 503
        return HealthStatus(status="unavailable", redis="down")

    if not _redis_reachable:
        logger.info("readiness recovered: redis reachable again")
        _redis_reachable = True

    return HealthStatus(status="ok", redis="up")
