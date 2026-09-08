import asyncio

import pytest
from fastapi import HTTPException, Response

from app.core import settings
from app.deps.user import get_current_user

SESSION_JSON = '{"id":"sub-1","name":"Lesha","email":"a@b.co","avatar_url":"http://x/p.png"}'


class FakeRedis:
    """Records the read so the TTL renewal is observable."""

    def __init__(self, stored: str | None):
        self.stored = stored
        self.calls: list[tuple[str, int | None]] = []

    async def getex(self, key, ex=None):
        self.calls.append((key, ex))
        return self.stored


def test_session_ttl_slides_on_read():
    """The whole point of GETEX: an active user must not be logged out 14 days after
    login. Both redis and the cookie have to be renewed, or one outlives the other."""
    redis = FakeRedis(SESSION_JSON)
    response = Response()

    user = asyncio.run(get_current_user(redis, response, session="abc"))

    assert user.id == "sub-1"
    assert redis.calls == [("session:abc", settings.SESSION_TTL)]
    assert f"Max-Age={settings.SESSION_TTL}" in response.headers["set-cookie"]


def test_expired_session_is_401_and_sets_no_cookie():
    redis = FakeRedis(None)
    response = Response()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_user(redis, response, session="abc"))

    assert exc.value.status_code == 401
    assert "set-cookie" not in response.headers


def test_missing_cookie_never_hits_redis():
    redis = FakeRedis(SESSION_JSON)

    with pytest.raises(HTTPException):
        asyncio.run(get_current_user(redis, Response(), session=None))

    assert redis.calls == []
