from fastapi import APIRouter
from app.connectors.registry import connector_registry
from app.core.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health")
async def get_health():
    """Liveness probe meeting Integration Standard 8."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "simulation_mode": settings.SIMULATION_MODE
    }

@router.get("/ready")
async def get_ready():
    """Readiness probe meeting Integration Standard 8."""
    connectors = connector_registry.list_all()
    return {
        "status": "ready",
        "connectors_loaded": len(connectors),
        "connectors": [c.get("key") for c in connectors],
        "storage": settings.STORAGE_TYPE
    }
