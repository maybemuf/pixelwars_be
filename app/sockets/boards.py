from http.cookies import SimpleCookie

import socketio

from app.deps.redis import get_redis

BOARD_KEY = "board:1"
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
    async def on_connect(self, sid, environ):
        """Anyone may watch. We only remember who is allowed to paint."""
        cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        await self.save_session(sid, {"session": cookie["session"].value if "session" in cookie else None})

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
        # No `to=` — every watcher including the author. The client does not
        # paint optimistically, so the author only sees it via this echo.
        await self.emit("pixel", {"offset": offset, "color": color})
