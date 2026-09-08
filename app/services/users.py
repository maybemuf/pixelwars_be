from app.core import settings
from app.deps.redis import redis
from app.schemas import User


async def get_user(session_id: str | None) -> User | None:
    raw = await redis.getex(f"session:{session_id}", ex=settings.SESSION_TTL)
    if not raw:
        return None

    return User.model_validate_json(raw, by_name=True)
