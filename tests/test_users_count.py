"""Presence counting through the namespace handlers. The logic moved to
boards_service, which reads the module-global redis -- hence the `redis` fixture
rather than the old patch of a get_redis that no longer exists here."""

import asyncio

from app.core import BOARD_USERS_KEY
from app.sockets.boards import BoardNamespace


def test_users_count(redis, monkeypatch):
    asyncio.run(_run(redis, monkeypatch))


async def _run(redis, monkeypatch):
    emitted = []

    async def emit(event, data):
        emitted.append((event, data))

    async def save_session(sid, data):
        pass

    ns = BoardNamespace("/boards")
    monkeypatch.setattr(ns, "emit", emit)
    monkeypatch.setattr(ns, "save_session", save_session)

    await ns.on_connect("a", {})
    await ns.on_connect("b", {})
    await ns.on_connect("a", {})  # reconnect must not double-count
    await ns.on_disconnect("b")
    await ns.on_disconnect("b")  # duplicate disconnect must not go negative

    assert [d["count"] for _, d in emitted] == [1, 2, 2, 1, 1]
    assert await redis.smembers(BOARD_USERS_KEY) == {b"a"}
