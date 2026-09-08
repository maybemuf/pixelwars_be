import logging

from pydantic import ValidationError

from app.core import settings
from app.deps.redis import redis
from app.schemas import User

logger = logging.getLogger(__name__)


async def get_user(session_id: str | None) -> User | None:
    if session_id is None:
        # Otherwise we'd look up the literal key "session:None" on every anonymous
        # placement attempt -- a pointless round-trip, and a key someone could plant.
        return None

    raw = await redis.getex(f"session:{session_id}", ex=settings.SESSION_TTL)
    if not raw:
        return None

    try:
        return User.model_validate_json(raw, by_name=True)
    except ValidationError:
        logger.warning("discarding unreadable session payload")
        return None
