from http.cookies import SimpleCookie
from time import perf_counter

import socketio
from opentelemetry.trace import SpanKind, get_current_span
from pydantic import ValidationError

from app.core import BOARD_KEY
from app.core.telemetry import (
    board_active_user_gauge,
    board_total_pixels,
    place_pixel_attempt_counter,
    place_pixel_attempt_duration_histogram,
    socket_connect_counter,
    socket_disconnect_counter,
    tracer,
)
from app.schemas.pixel import (
    PixelPlacement,
    PixelPlacementSuccess,
    PixelResultEnum,
    SetPixelSpanAttributes,
)
from app.services import boards_service, users_service


class BoardNamespace(socketio.AsyncNamespace):
    async def _broadcast_users(self):
        count = await boards_service.get_active_users()
        board_active_user_gauge.set(count)
        await self.emit("users", {"count": count})

    @tracer.start_as_current_span("sio.boards.connect", kind=SpanKind.SERVER)
    async def on_connect(self, sid, environ):
        """Anyone may watch. We only remember who is allowed to paint."""
        span = get_current_span()

        cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        session_cookie = cookie["session"].value if "session" in cookie else None
        await self.save_session(sid, {"session": session_cookie})

        await boards_service.add_active_user(sid)
        await self._broadcast_users()

        span.set_attributes({"sio.sid": sid, "sio.has_session_cookie": session_cookie is not None})
        socket_connect_counter.add(
            1,
            {"board.id": BOARD_KEY, "is_authenticated": session_cookie is not None},
        )

    @tracer.start_as_current_span("sio.boards.disconnect", kind=SpanKind.SERVER)
    async def on_disconnect(self, sid, reason=None):
        await boards_service.remove_active_user(sid)
        await self._broadcast_users()
        socket_disconnect_counter.add(1, {"board.id": BOARD_KEY, "reason": reason})

    @tracer.start_as_current_span("sio.boards.place_pixel", kind=SpanKind.SERVER)
    async def on_place_pixel(self, sid, data):
        """The return value is the client's ack."""
        span = get_current_span()
        started = perf_counter()
        attrs = {}

        def ack(result: PixelResultEnum, response: dict) -> dict:
            """Every exit records the same three signals — only the result label differs."""
            span.set_attributes(
                SetPixelSpanAttributes(pixel_result=result, **attrs).model_dump(mode="json", exclude_none=True)
            )
            metric_attrs = {"board.id": BOARD_KEY, "result": result.value}
            place_pixel_attempt_counter.add(1, metric_attrs)
            place_pixel_attempt_duration_histogram.record(perf_counter() - started, metric_attrs)
            return response

        session = (await self.get_session(sid))["session"]
        user = await users_service.get_user(session)
        if user is None:
            return ack(PixelResultEnum.UNAUTHENTICATED, {"error": "unauthenticated"})
        attrs["enduser_id"] = user.id

        try:
            pixel = PixelPlacement.model_validate(data)
        except ValidationError:
            return ack(PixelResultEnum.INVALID, {"error": "invalid pixel"})
        attrs |= {"pixel_offset": pixel.offset, "pixel_color": pixel.color}

        result = await boards_service.place_pixel(pixel, user.id)
        attrs["cooldown_retry_in_ms"] = result.retry_in_ms
        retry_in_ms = max(result.retry_in_ms, 0)

        if not isinstance(result, PixelPlacementSuccess):
            return ack(PixelResultEnum.COOLDOWN, {"error": "cooldown", "retry_in_ms": retry_in_ms})

        attrs["stream_entry_id"] = result.entry_id
        await self.emit("pixel", {"offset": pixel.offset, "color": pixel.color, "id": result.entry_id})
        board_total_pixels.set(result.pixels_placed, {"board.id": BOARD_KEY})
        return ack(PixelResultEnum.ACCEPTED, {"retry_in_ms": retry_in_ms})
