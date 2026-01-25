from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_studio_status():
    return {"module": "studio", "status": "active"}
