"""Test environment and the shared Redis fake.

The env block MUST run before any `app.*` import: `app/core/settings.py` builds its
`Settings()` at import time from ten required variables. pydantic-settings ranks
`os.environ` above `env_file`, so assigning here both supplies the values in CI (which
has no `.env`) and neutralises whatever happens to sit in a developer's real one --
otherwise the suite is only reproducible on machines whose `.env` happens to match.
"""

import os

os.environ.update(
    ENVIRONMENT="test",
    API_VERSION="0.0.0-test",
    GOOGLE_OAUTH_CLIENT_ID="test-client-id",
    GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret",
    SESSION_SECRET="test-session-secret",
    REDIS_HOST="localhost",
    REDIS_PORT="6379",
    COOLDOWN_SEC="60",
    # Load-bearing: keeps setup_telemetry on its early-return path. With telemetry on,
    # the suite tries to reach otel-lgtm:4318, retries with backoff, and the console
    # metric exporter throws "I/O operation on closed file" at interpreter teardown.
    OTEL_ENABLED="false",
    OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318",
    FRONTEND_URL="http://frontend.test/",
)

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fakeredis.aioredis import FakeRedis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.services.boards  # noqa: E402
import app.services.users  # noqa: E402
from app.deps.redis import get_redis  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.schemas import User  # noqa: E402

USER_JSON = '{"id":"g-123","name":"Lesha","email":"a@b.co","avatar_url":"http://x/p.png"}'


@pytest.fixture
def redis(monkeypatch):
    """One fake behind both Redis access paths.

    `get_redis` covers the injected routes, but app/services/{boards,users}.py each did
    `from app.deps.redis import redis`, which binds its own module-level name -- patching
    `app.deps.redis.redis` would not reach them. Miss one and those tests quietly talk to
    a real Redis. decode_responses stays False: get_board's b64encode and entry_id.decode
    both need bytes.
    """
    fake = FakeRedis()
    monkeypatch.setattr(app.services.boards, "redis", fake)
    monkeypatch.setattr(app.services.users, "redis", fake)
    fastapi_app.dependency_overrides[get_redis] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(redis):
    """https so the Secure/SameSite=none session cookie behaves as it does in production."""
    with TestClient(fastapi_app, base_url="https://testserver") as c:
        yield c


@pytest.fixture
def user():
    return User.model_validate_json(USER_JSON, by_name=True)


@pytest.fixture
def session_cookie(redis):
    """Seeds a live session and returns its id, as the OAuth callback would have."""
    sid = "test-session-id"
    asyncio.run(redis.set(f"session:{sid}", USER_JSON))
    return sid
