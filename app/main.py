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
    logger.info("startup complete: env=%s version=%s", settings.ENVIROMENT, settings.API_VERSION)
    yield
    # Its absence is the signal — it tells a graceful stop apart from an OOM kill.
    logger.info("shutdown")

mgr = AsyncRedisManager(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
sio = AsyncServer(async_mode="asgi", cors_allowed_origins=settings.ALLOWED_ORIGINS, client_manager=mgr)
sio.register_namespace(BoardNamespace("/boards"))

app = FastAPI(title="PixelWars API", version=settings.API_VERSION, lifespan=lifespan)
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
