from fastapi import APIRouter

from app.core import BOARD_DIM
from app.schemas import BoardState
from app.services import boards_service

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)


@router.get(
    "",
    response_model=BoardState,
    summary="Fetch the whole board",
    responses={200: {"description": "The current board. `data` is empty if it has not been seeded yet."}},
)
async def get_main_board() -> BoardState:
    """Returns the entire board as one base64 blob.

    The board lives in a single Redis key as a `u4` bitfield, so this is a flat
    512 KiB read with no per-pixel work. Clients decode it once on load and then track
    changes through the `pixel` Socket.IO event rather than polling here.
    """
    return BoardState(data=await boards_service.get_board(), dim=BOARD_DIM, bits_per_pixel=4)
