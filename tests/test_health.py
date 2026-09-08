"""Liveness and readiness. The fakes are real fakeredis clients now, except the
hanging one -- fakeredis has no latency injection, and the timeout is the point."""

import asyncio

from fakeredis.aioredis import FakeRedis

from app.deps.redis import get_redis
from app.main import app


class HangingRedis:
    """The one fake fakeredis cannot replace: it has no latency injection, and this
    test exists to prove asyncio.timeout cuts a stalled ping off."""

    async def ping(self):
        await asyncio.sleep(60)


def test_liveness_never_touches_redis(client):
    """Liveness answers even with no Redis at all: it decides whether to restart us."""
    app.dependency_overrides[get_redis] = lambda: FakeRedis(connected=False)
    assert client.get("/health/live").status_code == 200


def test_readiness_ok(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["redis"] == "up"


def test_readiness_503_when_redis_down(client):
    """The whole point: a dead dependency must not report 200."""
    app.dependency_overrides[get_redis] = lambda: FakeRedis(connected=False)
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["redis"] == "down"


def test_readiness_fails_fast_when_redis_hangs(client):
    """A probe that blocks forever is worse than none — it must time out into a 503."""
    app.dependency_overrides[get_redis] = HangingRedis
    r = client.get("/health/ready")
    assert r.status_code == 503


def test_liveness_reports_no_dependency(client):
    """It takes no dependencies, so it must not claim anything about redis."""
    assert client.get("/health/live").json() == {"status": "ok"}
