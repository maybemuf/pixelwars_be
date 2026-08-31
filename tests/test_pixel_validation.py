from app.core import BOARD_MAX_OFFSET
from app.sockets.boards import parse_pixel


def test_parse_pixel():
    assert parse_pixel({"offset": 0, "color": 0}) == (0, 0)
    assert parse_pixel({"offset": BOARD_MAX_OFFSET, "color": 15}) == (BOARD_MAX_OFFSET, 15)
    assert parse_pixel({"offset": BOARD_MAX_OFFSET + 1, "color": 1}) is None  # would grow the key
    assert parse_pixel({"offset": -1, "color": 1}) is None
    assert parse_pixel({"offset": 1, "color": 16}) is None
    assert parse_pixel({"offset": 1}) is None
    assert parse_pixel({"offset": "x", "color": 1}) is None
    assert parse_pixel("nope") is None
