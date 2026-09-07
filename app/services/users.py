from app.deps.redis import redis
from app.schemas import User


async def get_user(session_id: str | None) -> User | None:
    raw = await redis.get(f"session:{session_id}")
    if not raw:
        return None

    return User.model_validate_json(raw, by_name=True)