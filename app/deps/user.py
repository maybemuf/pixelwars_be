from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from app.deps import RedisDep
from app.schemas import User


async def get_current_user(redis: RedisDep, session: str | None = Cookie(default=None)) -> User:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = await redis.get(f"session:{session}")
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return User.model_validate_json(data, by_name=True)


UserDep = Annotated[User, Depends(get_current_user)]
