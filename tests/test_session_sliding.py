"""Sliding session TTL, and what happens when the stored session is unusable.

The recording fake stays: these three assert on the *call shape* (that GETEX was
handed ex=SESSION_TTL), which a real store cannot show us. The last test uses
fakeredis, because there the stored bytes are the thing under test.
"""

import asyncio

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import HTTPException, Response

from app.core import settings
from app.deps.user import get_current_user

SESSION_JSON = '{"id":"sub-1","name":"Lesha","email":"a@b.co","avatar_url":"http://x/p.png"}'


class RecordingRedis(FakeRedis):
    """A real client that also records how getex was called -- the TTL renewal only
    shows up in the arguments, which a plain store cannot reveal."""

    def __init__(self, stored: str | None):
        super().__init__()
        self.stored = stored
        self.calls: list[tuple[str, int | None]] = []

    async def getex(self, name, ex=None, px=None, exat=None, pxat=None, persist=False):
        self.calls.append((name, ex))
        return self.stored


def test_session_ttl_slides_on_read():
    """The whole point of GETEX: an active user must not be logged out 14 days after
    login. Both redis and the cookie have to be renewed, or one outlives the other."""
    redis = RecordingRedis(SESSION_JSON)
    response = Response()

    user = asyncio.run(get_current_user(redis, response, session="abc"))

    assert user.id == "sub-1"
    assert redis.calls == [("session:abc", settings.SESSION_TTL)]
    assert f"Max-Age={settings.SESSION_TTL}" in response.headers["set-cookie"]


def test_expired_session_is_401_and_sets_no_cookie():
    redis = RecordingRedis(None)
    response = Response()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_user(redis, response, session="abc"))

    assert exc.value.status_code == 401
    assert "set-cookie" not in response.headers


def test_missing_cookie_never_hits_redis():
    redis = RecordingRedis(SESSION_JSON)

    with pytest.raises(HTTPException):
        asyncio.run(get_current_user(redis, Response(), session=None))

    assert redis.calls == []


def test_malformed_session_json_is_401_not_500(redis):
    """A corrupt session is an invalid session. This used to let pydantic's
    ValidationError escape, turning every authenticated request into a 500."""

    async def run():
        await redis.set("session:abc", b"not json")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(redis, Response(), session="abc")
        assert exc.value.status_code == 401

    asyncio.run(run())
