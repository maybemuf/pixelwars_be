from fastapi import APIRouter, Request

router = APIRouter(
    prefix="/boards",
    tags=["boards"]
)

@router.get("/")
async def get_boards(request: Request):
    return "Hello! Theses are our boards 🛹"