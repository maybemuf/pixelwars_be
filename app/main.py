from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.core import settings
from app.routers.auth import router as auth
from app.routers.boards import router as boards

app = FastAPI(title="PixelWars APIII", version=settings.API_VERSION)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    max_age=60 * 60 * 24 * 14, # 14 days
)

app.include_router(auth)
app.include_router(boards)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
