from fastapi import APIRouter

from app.services import boards_service

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)


@router.get("")
async def get_main_board():
    return await boards_service.get_board()
