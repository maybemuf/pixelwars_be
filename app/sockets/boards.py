from http.cookies import SimpleCookie

import socketio
from opentelemetry.trace import SpanKind, get_current_span

from app.core.telemetry import tracer
from app.schemas.pixel import PixelPlacement, PixelPlacementError, PixelResultEnum, SetPixelSpanAttributes
from app.services import boards_service, users_service


class BoardNamespace(socketio.AsyncNamespace):
    async def _broadcast_users(self):
        count = await boards_service.get_active_users()
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

    @tracer.start_as_current_span("sio.boards.disconnect", kind=SpanKind.SERVER)
    async def on_disconnect(self, sid, reason=None):
        await boards_service.remove_active_user(sid)
        await self._broadcast_users()

    @tracer.start_as_current_span("sio.boards.place_pixel", kind=SpanKind.SERVER)
    async def on_place_pixel(self, sid, data):
        """The return value is the client's ack."""
        span = get_current_span()

        session = (await self.get_session(sid))["session"]
        user = await users_service.get_user(session)
        if user is None:
            span.set_attributes(
                SetPixelSpanAttributes(result=PixelResultEnum.UNAUTHENTICATED).model_dump(exclude_unset=True)
            )
            return {"error": "unauthenticated"}

        pixel = PixelPlacement.model_validate(data)
        if pixel is None:
            span.set_attributes(SetPixelSpanAttributes(result=PixelResultEnum.INVALID).model_dump(exclude_unset=True))
            return {"error": "Invalid pixel"}
        offset, color = pixel

        result = await boards_service.place_pixel(pixel, user.id)
        if result.isinstance(PixelPlacementError):
            span.set_attributes(
                SetPixelSpanAttributes(
                    result=PixelResultEnum.COOLDOWN,
                    cooldown_retry_in_ms=result.retry_in_ms,
                    pixel_offset=offset,
                    pixel_color=color,
                    enduser_id=user.id,
                ).model_dump(exclude_unset=True)
            )
            return {
                "error": "cooldown",
                "retry_in_ms": max(result.retry_in_ms, 0),
            }

        await self.emit(
            "pixel",
            {"offset": offset, "color": color, "id": result.entry_id.decode()},
        )

        span.set_attributes(
            SetPixelSpanAttributes(
                result=PixelResultEnum.ACCEPTED,
                cooldown_retry_in_ms=result.retry_in_ms,
                pixel_offset=offset,
                pixel_color=color,
                enduser_id=user.id,
                steam_entry_id=(result.entry_id),
            ).model_dump(exclude_unset=True)
        )

        return {"retry_in_ms": max(result.retry_in_ms, 0)}
