from fastapi import APIRouter

from app.deps import RedisDep

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)

@router.get("/")
async def get_board(redis: RedisDep):
    bytes = await redis.get("board:1")
    return bytes
