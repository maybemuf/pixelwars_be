from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from socketio import ASGIApp, AsyncServer
from starlette.middleware.sessions import SessionMiddleware

from app.core import BOARD_KEY, BOARD_MAX_OFFSET, BOARD_USERS_KEY, settings
from app.deps.redis import RedisDep, get_redis
from app.routers.auth import router as auth
from app.routers.boards import router as boards
from app.sockets.boards import BoardNamespace

ALLOWED_ORIGINS = [settings.FRONTEND_ORIGIN]


@asynccontextmanager
async def lifespan(_: FastAPI):
    redis = get_redis()
    await redis.delete(BOARD_USERS_KEY)
    if not await redis.exists(BOARD_KEY):
        await redis.bitfield(BOARD_KEY).set("u4", f"#{BOARD_MAX_OFFSET}", 0).execute()
    yield


sio = AsyncServer(async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS)
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


@app.get("/health", tags=["health"])
async def health(redis: RedisDep):
    result = await redis.ping()

    return {
        "status": "ok",
        "redis": "alive" if result else "dead",
    }
