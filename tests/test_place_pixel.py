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

    async def get_session(self, sid):
        return {"session": self._session}

    async def emit(self, event, data=None, **kw):
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
