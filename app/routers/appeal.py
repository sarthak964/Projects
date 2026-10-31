from app.core.time import utcnow
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.config import APPEAL_WINDOW_HOURS
from app.core.database import get_db
from app.models.job import Job
from app.models.photo_review import PhotoReview, PhotoReviewStatus
from app.models.user import User, UserRole
from app.schemas.appeal import AppealRequest, AppealStatusOut

router = APIRouter(tags=["appeals"])

_DECIDED = (PhotoReviewStatus.resolved_genuine, PhotoReviewStatus.resolved_not_genuine)


def _load(job_id: int, db: Session) -> tuple[Job, PhotoReview]:
    job = db.query(Job).filter(Job.id == job_id).first()
    review = db.query(PhotoReview).filter(PhotoReview.job_id == job_id).first()
    if not job or not review:
        raise HTTPException(status_code=404, detail="No photo review found for this job")
    return job, review


def _loser_id(job: Job, review: PhotoReview) -> int | None:
    """The side that lost the human decision: the renter if the photos were ruled
    genuine, the reviewer if they were ruled not genuine."""
    if review.human_decision == "genuine":
        return job.renter_id
    if review.human_decision == "not_genuine":
        return job.reviewer_id
    return None


def _appeal_deadline(review: PhotoReview) -> datetime | None:
    if review.status in _DECIDED and review.decided_at:
        return review.decided_at + timedelta(hours=APPEAL_WINDOW_HOURS)
    return None


def _can_appeal(user: User, job: Job, review: PhotoReview, now: datetime) -> bool:
    deadline = _appeal_deadline(review)
    return (
        review.status in _DECIDED
        and review.appeal_status is None
        and _loser_id(job, review) == user.id
        and deadline is not None
        and now <= deadline
    )


def _out(user: User, job: Job, review: PhotoReview) -> AppealStatusOut:
    return AppealStatusOut(
        job_id=job.id,
        review_status=review.status.value,
        human_decision=review.human_decision,
        decision_notes=review.decision_notes,
        decided_at=review.decided_at,
        appeal_deadline=_appeal_deadline(review),
        can_appeal=_can_appeal(user, job, review, utcnow()),
        appeal_by=review.appeal_by,
        appeal_reason=review.appeal_reason,
        appealed_at=review.appealed_at,
        appeal_status=review.appeal_status,
        appeal_notes=review.appeal_notes,
        appeal_decided_at=review.appeal_decided_at,
    )


@router.get("/jobs/{job_id}/appeal", response_model=AppealStatusOut)
def get_appeal_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job, review = _load(job_id, db)
    if current_user.role != UserRole.admin and current_user.id not in (
        job.renter_id,
        job.reviewer_id,
    ):
        raise HTTPException(status_code=403, detail="You do not have access to this job")
    return _out(current_user, job, review)


@router.post("/jobs/{job_id}/appeal", response_model=AppealStatusOut)
def file_appeal(
    job_id: int,
    body: AppealRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter, UserRole.reviewer)),
):
    job, review = _load(job_id, db)

    if current_user.id not in (job.renter_id, job.reviewer_id):
        raise HTTPException(status_code=403, detail="This is not your job")

    if review.status not in _DECIDED:
        raise HTTPException(
            status_code=400,
            detail="There is no human decision on this job to appeal",
        )

    if review.appeal_status is not None:
        raise HTTPException(status_code=400, detail="This decision has already been appealed")

    if _loser_id(job, review) != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the side that lost the decision can appeal it",
        )

    now = utcnow()
    deadline = _appeal_deadline(review)
    if deadline is None or now > deadline:
        raise HTTPException(
            status_code=400,
            detail=f"The {APPEAL_WINDOW_HOURS}-hour appeal window for this decision has passed",
        )

    review.appeal_by = current_user.id
    review.appeal_reason = body.reason
    review.appealed_at = now
    review.appeal_status = "pending"

    db.commit()
    db.refresh(review)
    return _out(current_user, job, review)
