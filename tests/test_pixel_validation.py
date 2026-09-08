"""Bounds on an incoming pixel. Was parse_pixel(); the checks now live in the
PixelPlacement model, which raises instead of returning None."""

import pytest
from pydantic import ValidationError

from app.core import BOARD_MAX_OFFSET
from app.schemas.pixel import PixelPlacement


def test_accepts_the_corners():
    assert PixelPlacement.model_validate({"offset": 0, "color": 0}).offset == 0
    p = PixelPlacement.model_validate({"offset": BOARD_MAX_OFFSET, "color": 15})
    assert (p.offset, p.color) == (BOARD_MAX_OFFSET, 15)


@pytest.mark.parametrize(
    "data",
    [
        {"offset": BOARD_MAX_OFFSET + 1, "color": 1},  # would grow the key
        {"offset": -1, "color": 1},
        {"offset": 1, "color": 16},
        {"offset": 1},  # missing colour
        {"offset": "x", "color": 1},
        "nope",  # not a mapping at all
    ],
)
def test_rejects(data):
    with pytest.raises(ValidationError):
        PixelPlacement.model_validate(data)
