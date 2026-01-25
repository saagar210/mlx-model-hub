from fastapi import APIRouter
from app.monitor.system import SystemMonitor

router = APIRouter()

@router.get("/stats")
async def get_system_stats():
    """
    Get real-time system statistics (RAM, CPU, Disk).
    Used for the 'Memory Tetris' visualization.
    """
    return SystemMonitor.get_system_stats()
