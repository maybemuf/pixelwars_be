import asyncio

from app.sockets import boards
from app.sockets.boards import BOARD_USERS_KEY, BoardNamespace


class FakeRedis:
    """Only the three set ops the counter uses."""

    def __init__(self):
        self.sets = {}

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    async def srem(self, key, member):
        self.sets.get(key, set()).discard(member)

    async def scard(self, key):
        return len(self.sets.get(key, ()))


def test_users_count(monkeypatch):
    asyncio.run(_run(monkeypatch))


async def _run(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(boards, "get_redis", lambda: redis)

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
    assert redis.sets[BOARD_USERS_KEY] == {"a"}
