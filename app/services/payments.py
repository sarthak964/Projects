from fastapi import HTTPException

from app.models.job import JobStatus
from app.models.payment import Payment, PaymentStatus
from app.services.money import to_paise


def require_payment(job, db, expected):
    payment = db.query(Payment).filter(Payment.job_id == job.id).first()
    if payment is None or payment.status != expected:
        raise HTTPException(
            status_code=409,
            detail="Payment state does not match this action. Contact support.",
        )
    try:
        valid = (
            job.reviewer_id is not None
            and to_paise(payment.amount) > 0
            and to_paise(payment.amount) == to_paise(job.price)
        )
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=409, detail="Job and payment amounts are inconsistent.")
    return payment


def release_job_payment(job, db):
    payment = require_payment(job, db, PaymentStatus.held)
    payment.status = PaymentStatus.released
    job.status = JobStatus.paid
