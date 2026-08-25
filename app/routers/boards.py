from fastapi import APIRouter

from app.deps import UserDep

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("/")
async def get_boards(user: UserDep):

    return f"Hello {user.name}! Theses are our boards 🛹"
