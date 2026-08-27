from fastapi import FastAPI
from socketio import ASGIApp, AsyncServer
from starlette.middleware.sessions import SessionMiddleware

from app.core import settings
from app.deps.redis import RedisDep
from app.routers.auth import router as auth
from app.routers.boards import router as boards
from app.sockets.boards import BoardNamespace

sio = AsyncServer(async_mode="asgi", cors_allowed_origins="*",)
sio.register_namespace(BoardNamespace("/boards"))

app = FastAPI(title="PixelWars API", version=settings.API_VERSION)
sio_asgi_app = ASGIApp(socketio_server=sio, other_asgi_app=app)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie="oauth_state",
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
