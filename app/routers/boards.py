import base64

from fastapi import APIRouter

from app.core import BOARD_KEY
from app.deps import RedisDep

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)


@router.get("")
async def get_main_board(redis: RedisDep):
    return base64.b64encode(await redis.get(BOARD_KEY)).decode()
