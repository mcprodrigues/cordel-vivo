"""Liveness probe: the only public route (AGENTS.md, principle 10)."""

from fastapi import APIRouter

from app.schemas.health import Health

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> Health:
    """Liveness only: the process is up and serving. It does not check dependencies."""
    return Health(status="ok")
