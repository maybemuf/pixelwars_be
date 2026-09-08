import logging
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response
from pydantic import ValidationError

from app.core import SESSION_COOKIE, settings
from app.deps import RedisDep
from app.schemas import User

logger = logging.getLogger(__name__)


async def get_current_user(
    redis: RedisDep,
    response: Response,
    session: str | None = Cookie(default=None),
) -> User:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = await redis.getex(f"session:{session}", ex=settings.SESSION_TTL)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        user = User.model_validate_json(data, by_name=True)
    except ValidationError as exc:
        # A corrupt payload is an invalid session, not a server fault. Letting the
        # ValidationError escape turned every authenticated request into a 500.
        logger.warning("discarding unreadable session payload")
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc

    response.set_cookie("session", session, max_age=settings.SESSION_TTL, **SESSION_COOKIE)

    return user


UserDep = Annotated[User, Depends(get_current_user)]
