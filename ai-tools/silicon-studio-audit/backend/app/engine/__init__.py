from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_engine_status():
    return {"module": "engine", "status": "active", "backend": "mlx"}
