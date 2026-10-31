from app.core.time import utcnow
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.config import STRIKES_BEFORE_SUSPENSION
from app.core.database import get_db
from app.services.payments import require_payment
from app.models.job import Job, JobStatus
from app.models.payment import Payment, PaymentStatus
from app.models.photo_review import PhotoReview, PhotoReviewStatus, FeeStatus
from app.models.reviewer_profile import ReviewerProfile
from app.models.user import User, UserRole
from app.routers.admin_review import _detail
from app.schemas.appeal import (
    AppealDecisionRequest,
    AppealDetail,
    AppealQueueItem,
    SuspendedReviewer,
    UnsuspendRequest,
)

# Shown in the uvicorn console. There is no audit table yet.
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/admin", tags=["admin"])


def _load(job_id: int, db: Session) -> tuple[Job, PhotoReview]:
    job = db.query(Job).filter(Job.id == job_id).first()
    review = db.query(PhotoReview).filter(PhotoReview.job_id == job_id).first()
    if not job or not review:
        raise HTTPException(status_code=404, detail="No photo review found for this job")
    return job, review


def _appeal_detail(job: Job, review: PhotoReview, db: Session) -> AppealDetail:
    base = _detail(job, review, db)
    return AppealDetail(
        **base.model_dump(),
        appeal_by=review.appeal_by,
        appeal_reason=review.appeal_reason,
        appealed_at=review.appealed_at,
        appeal_status=review.appeal_status,
        appeal_decided_by=review.appeal_decided_by,
        appeal_notes=review.appeal_notes,
        appeal_decided_at=review.appeal_decided_at,
    )


def _overturn(job: Job, review: PhotoReview, db: Session) -> None:
    """Flips a human decision: money, fees, strike and suspension all move back."""
    expected_job_status = {
        PhotoReviewStatus.resolved_genuine: JobStatus.paid,
        PhotoReviewStatus.resolved_not_genuine: JobStatus.refunded,
    }
    if review.status not in expected_job_status or job.status != expected_job_status[review.status]:
        raise HTTPException(
            status_code=400,
            detail=f"This case can no longer be reversed (review is '{review.status.value}', job is '{job.status.value}')",
        )

    expected_payment = (
        PaymentStatus.released
        if review.status == PhotoReviewStatus.resolved_genuine
        else PaymentStatus.refunded
    )
    payment = require_payment(job, db, expected_payment)
    profile = (
        db.query(ReviewerProfile)
        .filter(ReviewerProfile.user_id == job.reviewer_id)
        .first()
    )
    human_fee_paid = (review.human_fee_amount or 0) > 0

    if review.status == PhotoReviewStatus.resolved_genuine:
        # Was "genuine", now "not genuine": the renter gets everything back,
        # the reviewer loses the pay and receives a strike.
        if payment and payment.status == PaymentStatus.released:
            payment.status = PaymentStatus.refunded
        job.status = JobStatus.refunded
        review.status = PhotoReviewStatus.resolved_not_genuine
        review.fee_status = FeeStatus.refunded
        if human_fee_paid:
            review.human_fee_status = FeeStatus.refunded
        review.human_decision = "not_genuine"
        if profile:
            profile.strikes = (profile.strikes or 0) + 1
            if profile.strikes >= STRIKES_BEFORE_SUSPENSION:
                profile.suspended = True
    else:
        # Was "not genuine", now "genuine": the reviewer is paid, the renter loses
        # the fees again, and the reviewer's strike is taken back.
        if payment and payment.status == PaymentStatus.refunded:
            payment.status = PaymentStatus.released
        job.status = JobStatus.paid
        review.status = PhotoReviewStatus.resolved_genuine
        review.fee_status = FeeStatus.kept
        if human_fee_paid:
            review.human_fee_status = FeeStatus.kept
        review.human_decision = "genuine"
        if profile:
            profile.strikes = max(0, (profile.strikes or 0) - 1)
            if profile.strikes < STRIKES_BEFORE_SUSPENSION:
                profile.suspended = False


@router.get("/appeals", response_model=list[AppealQueueItem])
def list_appeals(
    status: Literal["pending", "upheld", "overturned"] = "pending",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    """Appeals waiting for an admin, oldest first."""
    reviews = (
        db.query(PhotoReview)
        .filter(PhotoReview.appeal_status == status)
        .order_by(PhotoReview.appealed_at)
        .all()
    )
    return [
        AppealQueueItem(
            job_id=r.job_id,
            appeal_by=r.appeal_by,
            appeal_reason=r.appeal_reason,
            appealed_at=r.appealed_at,
            human_decision=r.human_decision,
            decision_notes=r.decision_notes,
        )
        for r in reviews
    ]


@router.get("/appeals/{job_id}", response_model=AppealDetail)
def get_appeal_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    job, review = _load(job_id, db)
    return _appeal_detail(job, review, db)


@router.post("/appeals/{job_id}/decide", response_model=AppealDetail)
def decide_appeal(
    job_id: int,
    body: AppealDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    job, review = _load(job_id, db)

    if review.appeal_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"This case has no pending appeal (appeal status: {review.appeal_status})",
        )

    if body.decision == "overturn":
        _overturn(job, review, db)
        review.appeal_status = "overturned"
    else:
        review.appeal_status = "upheld"

    review.appeal_decided_by = current_user.id
    review.appeal_notes = body.notes
    review.appeal_decided_at = utcnow()

    db.commit()
    db.refresh(review)
    db.refresh(job)
    return _appeal_detail(job, review, db)


@router.get("/reviewers/suspended", response_model=list[SuspendedReviewer])
def list_suspended_reviewers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    rows = (
        db.query(ReviewerProfile, User)
        .join(User, User.id == ReviewerProfile.user_id)
        .filter(ReviewerProfile.suspended.is_(True))
        .order_by(ReviewerProfile.user_id)
        .all()
    )
    return [
        SuspendedReviewer(
            user_id=user.id,
            name=user.name,
            phone=user.phone,
            strikes=profile.strikes or 0,
            suspended=True,
        )
        for profile, user in rows
    ]


@router.post("/reviewers/{user_id}/unsuspend", response_model=SuspendedReviewer)
def unsuspend_reviewer(
    user_id: int,
    body: UnsuspendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    profile = db.query(ReviewerProfile).filter(ReviewerProfile.user_id == user_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not profile or not user:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    if not profile.suspended:
        raise HTTPException(status_code=400, detail="This reviewer is not suspended")

    # Back on probation: one more strike suspends them again.
    profile.suspended = False
    profile.strikes = min(profile.strikes or 0, STRIKES_BEFORE_SUSPENSION - 1)
    db.commit()
    db.refresh(profile)

    logger.info(
        "Admin %s lifted the suspension of reviewer %s: %s",
        current_user.id,
        user_id,
        body.notes,
    )

    return SuspendedReviewer(
        user_id=user.id,
        name=user.name,
        phone=user.phone,
        strikes=profile.strikes or 0,
        suspended=False,
    )
