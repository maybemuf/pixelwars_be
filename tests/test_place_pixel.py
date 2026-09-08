"""One check per exit of on_place_pixel: right ack, right result label."""

import asyncio

import pytest

from app.core import BOARD_KEY
from app.schemas.pixel import PixelPlacementError, PixelPlacementSuccess, PixelResultEnum
from app.sockets import boards as sut


class FakeNamespace(sut.BoardNamespace):
    def __init__(self, session):
        self._session = session
        self.emitted = []

    async def get_session(self, sid, namespace=None):
        return {"session": self._session}

    async def emit(
        self,
        event,
        data=None,
        to=None,
        room=None,
        skip_sid=None,
        namespace=None,
        callback=None,
        ignore_queue=False,
    ):
        self.emitted.append((event, data))


@pytest.fixture
def recorded(monkeypatch):
    """Capture what the counter/histogram/span were labelled with."""
    seen = {}
    monkeypatch.setattr(sut.place_pixel_attempt_counter, "add", lambda n, a: seen.setdefault("counter", a))
    monkeypatch.setattr(
        sut.place_pixel_attempt_duration_histogram, "record", lambda v, a: seen.update(duration=v, hist=a)
    )
    monkeypatch.setattr(sut.board_total_pixels, "set", lambda v, a: seen.update(total=v))
    return seen


def run(coro):
    return asyncio.run(coro)


VALID = {"offset": 5, "color": 3}


def test_unauthenticated(monkeypatch, recorded):
    monkeypatch.setattr(sut.users_service, "get_user", lambda s: _async(None))
    ack = run(FakeNamespace(None).on_place_pixel("sid", VALID))

    assert ack == {"error": "unauthenticated"}
    assert recorded["counter"]["result"] == PixelResultEnum.UNAUTHENTICATED
    assert recorded["hist"] == recorded["counter"]


def test_invalid_pixel(monkeypatch, recorded):
    monkeypatch.setattr(sut.users_service, "get_user", lambda s: _async(_user()))
    ack = run(FakeNamespace("s").on_place_pixel("sid", {"offset": -1, "color": 99}))

    assert ack == {"error": "invalid pixel"}
    assert recorded["counter"]["result"] == PixelResultEnum.INVALID


def test_cooldown_never_returns_negative_retry(monkeypatch, recorded):
    monkeypatch.setattr(sut.users_service, "get_user", lambda s: _async(_user()))
    monkeypatch.setattr(
        sut.boards_service,
        "place_pixel",
        lambda p, u: _async(PixelPlacementError(board_id="board", retry_in_ms=-2)),
    )
    ns = FakeNamespace("s")
    ack = run(ns.on_place_pixel("sid", VALID))

    assert ack == {"error": "cooldown", "retry_in_ms": 0}
    assert recorded["counter"]["result"] == PixelResultEnum.COOLDOWN
    assert ns.emitted == [], "a rejected pixel must not reach other clients"


def test_accepted(monkeypatch, recorded):
    monkeypatch.setattr(sut.users_service, "get_user", lambda s: _async(_user()))
    monkeypatch.setattr(
        sut.boards_service,
        "place_pixel",
        lambda p, u: _async(
            PixelPlacementSuccess(board_id="board", retry_in_ms=1000, entry_id="1-0", pixels_placed=42)
        ),
    )
    ns = FakeNamespace("s")
    ack = run(ns.on_place_pixel("sid", VALID))

    assert ack == {"retry_in_ms": 1000}
    assert ns.emitted == [("pixel", {"offset": 5, "color": 3, "id": "1-0"})]
    assert recorded["counter"]["result"] == PixelResultEnum.ACCEPTED
    assert recorded["total"] == 42
    assert recorded["duration"] >= 0


def test_span_attributes_are_dotted_and_drop_nones():
    dumped = sut.SetPixelSpanAttributes(pixel_result=PixelResultEnum.INVALID).model_dump(mode="json", exclude_none=True)
    # OTel rejects None values, and every key must be dotted, not snake_case.
    assert dumped == {"board.id": BOARD_KEY, "pixel.result": "invalid"}


async def _async(value):
    return value


class _user:
    """place_pixel only ever reads .id off the user."""

    id = "u1"


# The tests above stub users_service/boards_service out, so they never exercise the real
# session lookup or the real bitfield write. These go through both.


def test_no_session_cookie_is_unauthenticated(redis, recorded):
    ns = FakeNamespace(None)
    ack = run(ns.on_place_pixel("sid", VALID))

    assert ack == {"error": "unauthenticated"}
    assert recorded["counter"]["result"] == PixelResultEnum.UNAUTHENTICATED
    assert ns.emitted == [], "an unauthenticated attempt must not reach other clients"
    assert run(redis.keys("cooldown:*")) == [], "and must not burn a cooldown"


def test_expired_session_is_unauthenticated(redis, recorded):
    """Cookie present, but the session is gone from Redis — the other auth branch."""
    ns = FakeNamespace("stale-session-id")
    ack = run(ns.on_place_pixel("sid", VALID))

    assert ack == {"error": "unauthenticated"}
    assert recorded["counter"]["result"] == PixelResultEnum.UNAUTHENTICATED
    assert ns.emitted == []
    assert run(redis.keys("cooldown:*")) == []


def test_authenticated_place_pixel_reaches_the_bitfield(redis, session_cookie, recorded):
    ns = FakeNamespace(session_cookie)

    ack = run(ns.on_place_pixel("sid", VALID))

    assert ack == {"retry_in_ms": 60000}
    assert ns.emitted[0][0] == "pixel"
    assert ns.emitted[0][1]["offset"] == 5
    assert recorded["counter"]["result"] == PixelResultEnum.ACCEPTED
    # The pixel actually landed in the board, not just in an ack.
    assert run(redis.bitfield(BOARD_KEY).get("u4", "#5").execute()) == [3]


def test_second_pixel_is_cooled_down_and_changes_nothing(redis, session_cookie, recorded):
    ns = FakeNamespace(session_cookie)
    run(ns.on_place_pixel("sid", VALID))

    ack = run(ns.on_place_pixel("sid", {"offset": 5, "color": 9}))

    assert ack["error"] == "cooldown"
    # `counter` keeps the first call (setdefault); `hist` is overwritten, so it is the
    # one that reflects this second attempt.
    assert recorded["hist"]["result"] == PixelResultEnum.COOLDOWN
    assert run(redis.bitfield(BOARD_KEY).get("u4", "#5").execute()) == [3], "still the first colour"
