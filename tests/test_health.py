from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.deps.redis import get_redis
from app.main import app


class LiveRedis:
    async def ping(self):
        return True


class DeadRedis:
    async def ping(self):
        raise RedisConnectionError("connection refused")


class HangingRedis:
    async def ping(self):
        import asyncio

        await asyncio.sleep(60)  # must be cut off by REDIS_PING_TIMEOUT, not waited on


client = TestClient(app)


def test_liveness_never_touches_redis():
    """Liveness answers even with no Redis at all: it decides whether to restart us."""
    app.dependency_overrides[get_redis] = DeadRedis
    try:
        assert client.get("/health/live").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_readiness_ok():
    app.dependency_overrides[get_redis] = LiveRedis
    try:
        r = client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["redis"] == "up"
    finally:
        app.dependency_overrides.clear()


def test_readiness_503_when_redis_down():
    """The whole point: a dead dependency must not report 200."""
    app.dependency_overrides[get_redis] = DeadRedis
    try:
        r = client.get("/health/ready")
        assert r.status_code == 503
        assert r.json()["redis"] == "down"
    finally:
        app.dependency_overrides.clear()


def test_readiness_fails_fast_when_redis_hangs():
    """A probe that blocks forever is worse than none — it must time out into a 503."""
    app.dependency_overrides[get_redis] = HangingRedis
    try:
        r = client.get("/health/ready")
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()
