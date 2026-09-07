import base64
import logging

from app.core import (
    BOARD_KEY,
    BOARD_LEADERBOARD_KEY,
    BOARD_LOG_MAXLEN,
    BOARD_LOGS_KEY,
    BOARD_MAX_OFFSET,
    BOARD_TOTAL_KEY,
    BOARD_USERS_KEY,
    settings,
)
from app.deps.redis import redis
from app.schemas.pixel import PixelPlacement, PixelPlacementError, PixelPlacementSuccess

logger = logging.getLogger("service.boards")

async def init_board() -> bool:
    """Returns True when the board was missing and had to be seeded."""
    await redis.delete(BOARD_USERS_KEY)
    seeded = not await redis.exists(BOARD_KEY)
    if seeded:
        await redis.bitfield(BOARD_KEY).set("u4", f"#{BOARD_MAX_OFFSET}", 0).execute()

    # Once per process, and a fresh seed means the previous board is gone — worth knowing.
    logger.info("board initialized: seeded=%s", seeded)
    return seeded


async def get_board() -> bytes:
    return base64.b64encode(await redis.get(BOARD_KEY)).decode()


async def place_pixel(pixel: PixelPlacement, user_id: str) -> PixelPlacementSuccess | PixelPlacementError:
    cooldown_key = f"cooldown:{user_id}"
    p = redis.pipeline()

    p.set(cooldown_key, 1, ex=settings.COOLDOWN_SEC, nx=True)
    p.pttl(cooldown_key)
    ok, ttl_ms = await p.execute()

    if not ok:
        return PixelPlacementError(ttl_ms)

    p.execute_command("BITFIELD", BOARD_KEY, "SET", "u4", f"#{pixel.offset}", pixel.color)
    p.xadd(
        BOARD_LOGS_KEY,
        {"offset": pixel.offset, "color": pixel.color, "user_id": user_id},
        maxlen=BOARD_LOG_MAXLEN,
        approximate=True,
    )
    p.zincrby(BOARD_LEADERBOARD_KEY, 1, user_id)
    p.incr(BOARD_TOTAL_KEY)
    _, entry_id, _, _ = await p.execute()

    return PixelPlacementSuccess(entry_id, ttl_ms)


async def get_active_users() -> int:
    return await redis.scard(BOARD_USERS_KEY)


async def add_active_user(id: str) -> None:
    await redis.sadd(BOARD_USERS_KEY, id)


async def remove_active_user(id: str) -> None:
    await redis.srem(BOARD_USERS_KEY, id)
