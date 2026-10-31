from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.job import Job
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.payment import PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/{payment_id}/release",
    response_model=PaymentOut,
    deprecated=True,
)
def release_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter, UserRole.admin)),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    job = db.query(Job).filter(Job.id == payment.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    if current_user.role != UserRole.admin and job.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="This is not your payment")

    if payment.status != PaymentStatus.held:
        raise HTTPException(
            status_code=400,
            detail=f"Payment cannot be released from status '{payment.status.value}'",
        )

    # Payouts must follow the photo-review workflow, including its deadlines,
    # human decisions and appeals. This legacy route must not bypass it.
    raise HTTPException(
        status_code=409,
        detail=(
            "Direct payment release is disabled. "
            f"Use GET /jobs/{job.id}/photo-review to check the current stage. "
            "Renters must use the appropriate photo-review action; "
            "admins must use the human-review or appeal decision endpoint."
        ),
    )
