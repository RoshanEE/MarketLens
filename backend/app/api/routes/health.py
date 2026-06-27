"""Health check endpoints — used by load balancers and Docker health checks."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    # Could add DB connectivity check here in future
    return {"status": "ready"}
