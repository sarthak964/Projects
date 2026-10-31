from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.core.config import SCHEDULER_ENABLED, SCHEDULER_INTERVAL_SECONDS
from app.models.user import User, UserRole
from app.services.scheduler import run_sweep, state

router = APIRouter(prefix="/admin/scheduler", tags=["admin"])


@router.get("/status")
def scheduler_status(
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    return {
        "enabled": SCHEDULER_ENABLED,
        "interval_seconds": SCHEDULER_INTERVAL_SECONDS,
        **state,
    }


@router.post("/run")
def run_scheduler_now(
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    """Runs one sweep immediately and reports what it did. Useful for testing."""
    return run_sweep()
