from app.core.time import utcnow
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.config import STRIKES_BEFORE_SUSPENSION
from app.core.database import get_db
from app.services.payments import require_payment
from app.models.job import Job, JobStatus
from app.models.payment import Payment, PaymentStatus
from app.models.photo import Photo
from app.models.photo_review import PhotoReview, PhotoReviewStatus, FeeStatus
from app.models.report import Report
from app.models.reviewer_profile import ReviewerProfile
from app.models.user import User, UserRole
from app.schemas.admin_review import (
    AdminReviewDetail,
    HumanDecisionRequest,
    QueueItem,
    ReviewPhoto,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _load(job_id: int, db: Session) -> tuple[Job, PhotoReview]:
    job = db.query(Job).filter(Job.id == job_id).first()
    review = db.query(PhotoReview).filter(PhotoReview.job_id == job_id).first()
    if not job or not review:
        raise HTTPException(status_code=404, detail="No photo review found for this job")
    return job, review


def _human_fee_status(review: PhotoReview) -> FeeStatus:
    return review.human_fee_status or FeeStatus.none


def _detail(job: Job, review: PhotoReview, db: Session) -> AdminReviewDetail:
    report = db.query(Report).filter(Report.job_id == job.id).first()
    payment = db.query(Payment).filter(Payment.job_id == job.id).first()
    photos = db.query(Photo).filter(Photo.job_id == job.id).order_by(Photo.id).all()
    rejected = review.rejected_items or []

    profile = None
    if job.reviewer_id:
        profile = (
            db.query(ReviewerProfile)
            .filter(ReviewerProfile.user_id == job.reviewer_id)
            .first()
        )

    return AdminReviewDetail(
        job_id=job.id,
        address=job.address,
        checklist=job.checklist_json or [],
        renter_id=job.renter_id,
        reviewer_id=job.reviewer_id,
        job_status=job.status.value,
        job_price=job.price,
        payment_status=payment.status.value if payment else None,
        report_notes=report.notes if report else None,
        review_status=review.status.value,
        rejected_items=rejected,
        renter_reason=review.renter_reason,
        escalation_reason=review.escalation_reason,
        fee_amount=review.fee_amount or 0.0,
        fee_status=review.fee_status.value,
        human_fee_amount=review.human_fee_amount or 0.0,
        human_fee_status=_human_fee_status(review).value,
        ai_verdict=review.ai_verdict,
        photos=[
            ReviewPhoto(
                id=p.id,
                checklist_item=p.checklist_item,
                url=f"/photos/{p.id}",
                created_at=p.created_at,
                round="reupload" if p.photo_review_id == review.id else "original",
                is_rejected_item=p.checklist_item in rejected,
            )
            for p in photos
        ],
        human_decision=review.human_decision,
        decision_notes=review.decision_notes,
        decided_by=review.decided_by,
        decided_at=review.decided_at,
        reviewer_strikes=(profile.strikes or 0) if profile else None,
        reviewer_suspended=bool(profile.suspended) if profile else None,
    )


@router.get("/photo-reviews", response_model=list[QueueItem])
def list_photo_reviews(
    status: PhotoReviewStatus = PhotoReviewStatus.awaiting_human,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    """The queue of cases waiting for a human decision, oldest first."""
    rows = (
        db.query(PhotoReview, Job)
        .join(Job, Job.id == PhotoReview.job_id)
        .filter(PhotoReview.status == status)
        .order_by(PhotoReview.created_at)
        .all()
    )
    return [
        QueueItem(
            job_id=job.id,
            renter_id=job.renter_id,
            reviewer_id=job.reviewer_id,
            rejected_items=review.rejected_items or [],
            escalation_reason=review.escalation_reason,
            fee_amount=review.fee_amount or 0.0,
            fee_status=review.fee_status.value,
            human_fee_amount=review.human_fee_amount or 0.0,
            human_fee_status=_human_fee_status(review).value,
            review_created_at=review.created_at,
        )
        for review, job in rows
    ]


@router.get("/photo-reviews/{job_id}", response_model=AdminReviewDetail)
def get_photo_review_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    job, review = _load(job_id, db)
    return _detail(job, review, db)


@router.post("/photo-reviews/{job_id}/decide", response_model=AdminReviewDetail)
def decide_photo_review(
    job_id: int,
    body: HumanDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    job, review = _load(job_id, db)

    if review.status != PhotoReviewStatus.awaiting_human or job.status != JobStatus.verified:
        raise HTTPException(
            status_code=400,
            detail=f"This case is not waiting for a human decision (review is '{review.status.value}', job is '{job.status.value}')",
        )

    payment = require_payment(job, db, PaymentStatus.held)
    now = utcnow()
    human_fee_paid = _human_fee_status(review) == FeeStatus.held

    if body.decision == "genuine":
        # The photos are fine: the reviewer is paid and the renter loses every fee
        # they paid (the check fee and, if they asked for a human, the human fee).
        if payment and payment.status == PaymentStatus.held:
            payment.status = PaymentStatus.released
        job.status = JobStatus.paid
        review.status = PhotoReviewStatus.resolved_genuine
        review.fee_status = FeeStatus.kept
        if human_fee_paid:
            review.human_fee_status = FeeStatus.kept
    else:
        # The photos are not genuine: the renter gets the job price and every fee back,
        # the reviewer is not paid and receives a strike.
        if payment and payment.status == PaymentStatus.held:
            payment.status = PaymentStatus.refunded
        job.status = JobStatus.refunded
        review.status = PhotoReviewStatus.resolved_not_genuine
        review.fee_status = FeeStatus.refunded
        if human_fee_paid:
            review.human_fee_status = FeeStatus.refunded

        profile = (
            db.query(ReviewerProfile)
            .filter(ReviewerProfile.user_id == job.reviewer_id)
            .first()
        )
        if profile:
            profile.strikes = (profile.strikes or 0) + 1
            if profile.strikes >= STRIKES_BEFORE_SUSPENSION:
                profile.suspended = True

    review.human_decision = body.decision
    review.decision_notes = body.notes
    review.decided_by = current_user.id
    review.decided_at = now

    db.commit()
    db.refresh(review)
    db.refresh(job)
    return _detail(job, review, db)
