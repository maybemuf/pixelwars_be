import base64

from fastapi import APIRouter, Body

from app.deps import RedisDep

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)


@router.get("")
async def get_board(redis: RedisDep):
    raw = await redis.get("board:1")
    return base64.b64encode(raw).decode() if raw else None


@router.post("")
async def place_pixel(
    redis: RedisDep,
    color: int = Body(ge=0, le=15, embed=True),
    offset: int = Body(ge=0, le=1048575, embed=True),
):
    await redis.bitfield("board:1").set("u4", f"#{offset}", color).execute()
    return 'ok'
