"""GET /boards -- the whole board in one response."""

import asyncio
import base64

from app.core import BOARD_DIM, BOARD_KEY
from app.schemas.pixel import PixelPlacement
from app.services import boards_service

# u4 means one nibble per pixel, so the entire 1024x1024 board is 512 KiB.
BOARD_BYTES = BOARD_DIM * BOARD_DIM // 2


def test_get_board_returns_the_whole_bitfield(client):
    r = client.get("/boards")

    assert r.status_code == 200
    assert len(base64.b64decode(r.json()["data"])) == BOARD_BYTES
    assert r.json()["dim"] == BOARD_DIM
    assert r.json()["bits_per_pixel"] == 4


def test_get_board_reflects_a_placed_pixel(client, redis):
    asyncio.run(boards_service.place_pixel(PixelPlacement(offset=1, color=7), "u1"))

    raw = base64.b64decode(client.get("/boards").json()["data"])

    # offset 1 is the low nibble of byte 0; offset 0 is the high nibble.
    assert raw[0] & 0x0F == 7


def test_get_board_missing_key_is_not_a_500(client, redis):
    """b64encode(None) used to raise TypeError. An un-seeded board is empty, not broken."""
    asyncio.run(redis.delete(BOARD_KEY))

    r = client.get("/boards")

    assert r.status_code == 200
    assert r.json()["data"] == ""
