import logging
import time
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from socketio import ASGIApp, AsyncRedisManager, AsyncServer
from starlette.middleware.sessions import SessionMiddleware

from app.core import BOARD_KEY, BOARD_MAX_OFFSET, BOARD_USERS_KEY, settings
from app.core.logging import setup_logging
from app.deps.redis import get_redis
from app.routers.auth import router as auth
from app.routers.boards import router as boards
from app.routers.health import router as health
from app.sockets.boards import BoardNamespace

ALLOWED_ORIGINS = [settings.FRONTEND_ORIGIN]

setup_logging(json_logs=settings.is_production())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    redis = get_redis()
    await redis.delete(BOARD_USERS_KEY)
    if not await redis.exists(BOARD_KEY):
        await redis.bitfield(BOARD_KEY).set("u4", f"#{BOARD_MAX_OFFSET}", 0).execute()
    yield


mgr = AsyncRedisManager(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
sio = AsyncServer(async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS, client_manager=mgr)
sio.register_namespace(BoardNamespace("/boards"))

app = FastAPI(title="PixelWars API", version=settings.API_VERSION, lifespan=lifespan)
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
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):

    start_time = time.perf_counter()
    response = await call_next(request)
    response_time = time.perf_counter() - start_time

    logger.info(f"request took {response_time}")

    return response


app.add_middleware(CorrelationIdMiddleware)
