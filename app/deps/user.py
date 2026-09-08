from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response

from app.core import SESSION_COOKIE, settings
from app.deps import RedisDep
from app.schemas import User


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

    response.set_cookie("session", session, max_age=settings.SESSION_TTL, **SESSION_COOKIE)

    return User.model_validate_json(data, by_name=True)


UserDep = Annotated[User, Depends(get_current_user)]
