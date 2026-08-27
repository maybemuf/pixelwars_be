from app.sockets.boards import MAX_OFFSET, parse_pixel


def test_parse_pixel():
    assert parse_pixel({"offset": 0, "color": 0}) == (0, 0)
    assert parse_pixel({"offset": MAX_OFFSET, "color": 15}) == (MAX_OFFSET, 15)
    assert parse_pixel({"offset": MAX_OFFSET + 1, "color": 1}) is None  # would grow the key
    assert parse_pixel({"offset": -1, "color": 1}) is None
    assert parse_pixel({"offset": 1, "color": 16}) is None
    assert parse_pixel({"offset": 1}) is None
    assert parse_pixel({"offset": "x", "color": 1}) is None
    assert parse_pixel("nope") is None
