import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError
from socketio import ASGIApp, AsyncRedisManager, AsyncServer
from starlette.middleware.sessions import SessionMiddleware

from app.core import BOARD_KEY, BOARD_MAX_OFFSET, BOARD_USERS_KEY, settings
from app.deps.redis import RedisDep, get_redis
from app.routers.auth import router as auth
from app.routers.boards import router as boards
from app.sockets.boards import BoardNamespace

ALLOWED_ORIGINS = [settings.FRONTEND_ORIGIN]

# A readiness probe that can hang is worse than none: it turns a dead dependency
# into a stuck request instead of a fast 503.
REDIS_PING_TIMEOUT = 2


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

app.include_router(auth)
app.include_router(boards)


@app.get("/health/live", tags=["health"])
async def liveness():
    """Is the process up? Deliberately dependency-free — a failure here means restart me."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness(redis: RedisDep, response: Response):
    """Can we actually serve? Redis holds the board, the sessions and the presence set."""
    try:
        async with asyncio.timeout(REDIS_PING_TIMEOUT):
            await redis.ping()
    except (RedisError, TimeoutError, OSError):
        response.status_code = 503
        return {"status": "unavailable", "redis": "down"}

    return {"status": "ok", "redis": "up"}
