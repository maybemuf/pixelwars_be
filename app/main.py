from fastapi import FastAPI

from app.core import settings

app = FastAPI(
    title="TeacherBoard API",
    version=settings.API_VERSION
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}