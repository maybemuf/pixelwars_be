from http.cookies import SimpleCookie

import socketio

from app.core import BOARD_KEY, BOARD_MAX_OFFSET, BOARD_USERS_KEY, settings
from app.deps.redis import get_redis
from app.schemas import User


def parse_pixel(data) -> tuple[int, int] | None:
    """Client JSON is untrusted: anything but an in-range pixel is rejected."""
    try:
        offset, color = int(data["offset"]), int(data["color"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= offset <= BOARD_MAX_OFFSET and 0 <= color <= 15):
        return None
    return offset, color


class BoardNamespace(socketio.AsyncNamespace):
    async def _broadcast_users(self):
        await self.emit("users", {"count": await get_redis().scard(BOARD_USERS_KEY)})

    async def on_connect(self, sid, environ):
        """Anyone may watch. We only remember who is allowed to paint."""
        cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        await self.save_session(sid, {"session": cookie["session"].value if "session" in cookie else None})

        await get_redis().sadd(BOARD_USERS_KEY, sid)
        await self._broadcast_users()

    async def on_disconnect(self, sid, reason=None):
        await get_redis().srem(BOARD_USERS_KEY, sid)
        await self._broadcast_users()

    async def on_place_pixel(self, sid, data):
        redis = get_redis()
        """The return value is the client's ack; None means accepted."""
        session = (await self.get_session(sid))["session"]
        raw = await redis.get(f"session:{session}")
        if not raw:
            return {"error": "Sign in to place pixels"}
        user = User.model_validate_json(raw, by_name=True)

        key = f"cooldown:{user.id}"
        ok, ttl_ms = await get_redis().pipeline().set(key, 1, ex=settings.COOLDOWN_SEC, nx=True).pttl(key).execute()
        if not ok:
            return {"error": "Cooldown", "retry_in_ms": max(ttl_ms, 0)}

        pixel = parse_pixel(data)
        if pixel is None:
            return {"error": "Invalid pixel"}
        offset, color = pixel

        await redis.bitfield(BOARD_KEY).set("u4", f"#{offset}", color).execute()

        await self.emit("pixel", {"offset": offset, "color": color})

        return {"retry_in_ms": settings.COOLDOWN_SEC * 1000}
