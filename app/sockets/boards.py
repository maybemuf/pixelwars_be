from http.cookies import SimpleCookie

import socketio

from app.deps.redis import get_redis

BOARD_KEY = "board:1"
BOARD_USERS_KEY = "board:1:users"
MAX_OFFSET = 1024 * 1024 - 1  # 1M pixels, 4 bits each


def parse_pixel(data) -> tuple[int, int] | None:
    """Client JSON is untrusted: anything but an in-range pixel is rejected."""
    try:
        offset, color = int(data["offset"]), int(data["color"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= offset <= MAX_OFFSET and 0 <= color <= 15):
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
        """The return value is the client's ack; None means accepted."""
        session = (await self.get_session(sid))["session"]
        if not session or not await get_redis().exists(f"session:{session}"):
            return {"error": "Sign in to place pixels"}

        pixel = parse_pixel(data)
        if pixel is None:
            return {"error": "Invalid pixel"}
        offset, color = pixel

        await get_redis().bitfield(BOARD_KEY).set("u4", f"#{offset}", color).execute()

        await self.emit("pixel", {"offset": offset, "color": color})
