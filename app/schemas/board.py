from pydantic import BaseModel, Field

from app.core import BOARD_DIM


class BoardState(BaseModel):
    """The whole board in one shot.

    Wrapped in an object rather than returned as a bare JSON string so the dimensions
    travel with the data and new fields can be added without breaking clients.
    """

    data: str = Field(
        description="Base64 of the raw u4 bitfield: one nibble per pixel, row-major. "
        f"Empty when the board has not been seeded yet. {BOARD_DIM * BOARD_DIM // 2} bytes decoded.",
        examples=["AAAAAAAAAAA="],
    )
    dim: int = Field(description="Board edge length in pixels; the board is square.", examples=[BOARD_DIM])
    bits_per_pixel: int = Field(description="Bits per pixel, hence the palette size (2^n).", examples=[4])
