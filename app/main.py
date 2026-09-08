import logging
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from socketio import ASGIApp, AsyncRedisManager, AsyncServer
from starlette.middleware.sessions import SessionMiddleware

from app.core import settings
from app.core.logging import setup_logging
from app.core.telemetry import setup_telemetry, tracer
from app.routers.auth import router as auth
from app.routers.boards import router as boards
from app.routers.health import router as health
from app.services import boards_service
from app.sockets.boards import BoardNamespace

setup_logging(json_logs=settings.is_production())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with tracer.start_as_current_span("board.init") as span:
        created = await boards_service.init_board()
        span.set_attribute("board.created", created)

    # The anchor line when reading logs: which build, which env, and when it came up.
    logger.info("startup complete: env=%s version=%s", settings.ENVIRONMENT, settings.API_VERSION)
    yield
    # Its absence is the signal — it tells a graceful stop apart from an OOM kill.
    logger.info("shutdown")


mgr = AsyncRedisManager(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
sio = AsyncServer(async_mode="asgi", cors_allowed_origins=settings.ALLOWED_ORIGINS, client_manager=mgr)
sio.register_namespace(BoardNamespace("/boards"))

DESCRIPTION = """
A collaborative pixel canvas: a 1024x1024 shared board where every logged-in user may
paint one pixel per cooldown window.

The board is a **single Redis `u4` bitfield** -- one nibble per pixel, 16 colours, 512 KiB
for the whole canvas. `BITFIELD SET` is atomic, so concurrent painters need no locking.

### How a client uses this API

1. `GET /boards` once, to get the whole board as base64.
2. Connect to the `/boards` Socket.IO namespace for live updates.
3. `POST /auth/google` to log in -- watching is anonymous, painting is not.

### Socket.IO contract (namespace `/boards`, not covered by OpenAPI)

| Direction | Event | Payload |
|---|---|---|
| client -> server | `place_pixel` | `{"offset": int, "color": int}` |
| ack | *(return value)* | see below |
| server -> client | `pixel` | `{"offset": int, "color": int, "id": str}` |
| server -> client | `users` | `{"count": int}` |

`pixel` is broadcast on every accepted placement; `users` fires on each connect and
disconnect. The `place_pixel` ack is `{"retry_in_ms": int}` when the pixel was painted,
otherwise `{"error": ...}` where the error is one of `unauthenticated`, `invalid pixel`,
or `cooldown` -- the last also carries `retry_in_ms`.

`offset` is `y * 1024 + x` and must be `0..1048575`; `color` is a palette index `0..15`.
"""

TAGS = [
    {"name": "auth", "description": "Google OAuth login and the session cookie."},
    {"name": "boards", "description": "The pixel canvas itself."},
    {"name": "health", "description": "Liveness and readiness probes for the container."},
]

app = FastAPI(
    title="PixelWars API",
    version=settings.API_VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS,
    license_info={"name": "MIT", "identifier": "MIT"},
    lifespan=lifespan,
)
setup_telemetry(app)

sio_asgi_app = ASGIApp(socketio_server=sio, other_asgi_app=app)

app.include_router(auth)
app.include_router(boards)
app.include_router(health)

### Middleware setup

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie="oauth_state",
    https_only=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)
