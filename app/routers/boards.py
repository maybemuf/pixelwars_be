import base64

from fastapi import APIRouter

from app.deps import RedisDep

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)


@router.get("")
async def get_board(redis: RedisDep):
    raw = await redis.get("board:1")
    return base64.b64encode(raw).decode() if raw else None
