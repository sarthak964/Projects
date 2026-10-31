from app.core.time import utcnow
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.config import (
    HUMAN_REVIEW_FEE,
    PHOTO_REVIEW_WINDOW_HOURS,
    RECHECK_WINDOW_HOURS,
    REUPLOAD_WINDOW_HOURS,
    UPLOAD_DIR,
)
from app.core.database import get_db
from app.services.payments import release_job_payment, require_payment
from app.models.job import Job, JobStatus
from app.models.payment import Payment, PaymentStatus
from app.models.photo import Photo
from app.models.photo_review import PhotoReview, PhotoReviewStatus, FeeStatus
from app.models.report import Report
from app.models.user import User, UserRole
from app.schemas.photo_review import (
    DisputeAIResultRequest,
    FeeQuoteOut,
    PhotoReviewOut,
    ReasonRequest,
    RejectRequest,
)
from app.services.job_lifecycle import check_and_expire_job
from app.services.photo_fees import calculate_review_fee
from app.services.money import same_amount
from app.services.photo_review_ai import check_photos

router = APIRouter(tags=["photo-review"])


def _load_job(job_id: int, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _renter_job(job_id: int, db: Session, user: User) -> Job:
    job = _load_job(job_id, db)
    if job.renter_id != user.id:
        raise HTTPException(status_code=403, detail="You did not create this job")
    return check_and_expire_job(job, db)


def _get_review(job: Job, db: Session) -> PhotoReview | None:
    return db.query(PhotoReview).filter(PhotoReview.job_id == job.id).first()


def _deadline(job: Job) -> datetime | None:
    if job.verified_at is None:
        return None
    return job.verified_at + timedelta(hours=PHOTO_REVIEW_WINDOW_HOURS)


def _require_reviewable(job: Job, db: Session) -> None:
    if job.status != JobStatus.verified:
        raise HTTPException(
            status_code=400,
            detail=f"Photos can only be reviewed while the job is 'verified' (it is '{job.status.value}')",
        )
    existing = _get_review(job, db)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"These photos were already reviewed (status '{existing.status.value}')",
        )


def _validated_items(job: Job, items: list[str]) -> list[str]:
    items = list(dict.fromkeys(items))
    if not items:
        raise HTTPException(status_code=400, detail="Select at least one checklist item")
    checklist = job.checklist_json or []
    unknown = [i for i in items if i not in checklist]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"These are not checklist items of this job: {unknown}",
        )
    return items


def _release_payment(job: Job, db: Session) -> None:
    release_job_payment(job, db)


def _require_status(job: Job, review: PhotoReview | None, expected: PhotoReviewStatus, message: str) -> PhotoReview:
    if review is None or review.status != expected or job.status != JobStatus.verified:
        raise HTTPException(status_code=400, detail=message)
    return review


def _out(job: Job, review: PhotoReview | None) -> PhotoReviewOut:
    if review is None:
        status = "pending" if job.status == JobStatus.verified else "not_available"
        return PhotoReviewOut(job_id=job.id, status=status, review_deadline=_deadline(job))
    return PhotoReviewOut(
        job_id=job.id,
        status=review.status.value,
        review_deadline=_deadline(job),
        rejected_items=review.rejected_items or [],
        renter_reason=review.renter_reason,
        fee_amount=review.fee_amount or 0.0,
        fee_status=review.fee_status.value,
        human_fee_amount=review.human_fee_amount or 0.0,
        human_fee_status=(review.human_fee_status or FeeStatus.none).value,
        ai_verdict=review.ai_verdict,
        ai_result_deadline=review.ai_result_deadline,
        reupload_deadline=review.reupload_deadline,
        recheck_deadline=review.recheck_deadline,
        escalation_reason=review.escalation_reason,
        decided_at=review.decided_at,
    )


@router.get("/jobs/{job_id}/photo-review", response_model=PhotoReviewOut)
def get_photo_review(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _load_job(job_id, db)
    if current_user.role != UserRole.admin and current_user.id not in (
        job.renter_id,
        job.reviewer_id,
    ):
        raise HTTPException(status_code=403, detail="You do not have access to this job")

    job = check_and_expire_job(job, db)
    return _out(job, _get_review(job, db))


@router.get("/jobs/{job_id}/photo-review/fee-quote", response_model=FeeQuoteOut)
def fee_quote(
    job_id: int,
    items: list[str] = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    _require_reviewable(job, db)
    items = _validated_items(job, items)

    count = (
        db.query(Photo)
        .filter(Photo.job_id == job.id, Photo.checklist_item.in_(items))
        .count()
    )
    return FeeQuoteOut(items=items, photo_count=count, fee=calculate_review_fee(count))


@router.post("/jobs/{job_id}/photo-review/approve", response_model=PhotoReviewOut)
def approve_photos(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    _require_reviewable(job, db)

    _release_payment(job, db)
    review = PhotoReview(
        job_id=job.id,
        status=PhotoReviewStatus.approved,
        rejected_items=[],
        fee_amount=0.0,
        fee_status=FeeStatus.none,
        decided_at=utcnow(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    db.refresh(job)
    return _out(job, review)


@router.post("/jobs/{job_id}/photo-review/reject", response_model=PhotoReviewOut)
def reject_photos(
    job_id: int,
    body: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    _require_reviewable(job, db)
    items = _validated_items(job, body.items)

    photo_rows = (
        db.query(Photo)
        .filter(Photo.job_id == job.id, Photo.checklist_item.in_(items))
        .order_by(Photo.id)
        .all()
    )
    fee = calculate_review_fee(len(photo_rows))
    if not same_amount(body.confirm_fee, fee):
        raise HTTPException(
            status_code=400,
            detail=f"The fee for this review is {fee}. Resend with confirm_fee={fee} to agree to it.",
        )

    report = db.query(Report).filter(Report.job_id == job.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this job")

    photos = []
    for p in photo_rows:
        path = UPLOAD_DIR / p.stored_name
        if not path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"A stored photo (id {p.id}) is missing on the server, cannot check",
            )
        photos.append(
            {
                "checklist_item": p.checklist_item,
                "path": str(path),
                "content_type": p.content_type,
            }
        )

    require_payment(job, db, PaymentStatus.held)

    # Run the AI first: if it fails, nothing has been held or recorded.
    try:
        verdict = check_photos(items, report.notes or "", photos)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="The AI photo check failed, so nothing was charged. Please try again.",
        )

    now = utcnow()
    if verdict["all_genuine"]:
        status = PhotoReviewStatus.ai_checked_genuine
        # The renter has the same 24 hours as the re-check window to accept or dispute.
        ai_result_deadline = now + timedelta(hours=RECHECK_WINDOW_HOURS)
        reupload_deadline = None
    else:
        status = PhotoReviewStatus.awaiting_reupload
        ai_result_deadline = None
        reupload_deadline = now + timedelta(hours=REUPLOAD_WINDOW_HOURS)

    review = PhotoReview(
        job_id=job.id,
        status=status,
        rejected_items=items,
        renter_reason=body.reason,
        fee_amount=fee,
        fee_status=FeeStatus.held,
        ai_verdict=verdict,
        ai_result_deadline=ai_result_deadline,
        reupload_deadline=reupload_deadline,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _out(job, review)


@router.post("/jobs/{job_id}/photo-review/accept-ai-result", response_model=PhotoReviewOut)
def accept_ai_result(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    review = _require_status(
        job,
        _get_review(job, db),
        PhotoReviewStatus.ai_checked_genuine,
        "There is no AI result waiting for you to accept on this job",
    )

    review.status = PhotoReviewStatus.accepted_ai_result
    review.fee_status = FeeStatus.kept
    review.decided_at = utcnow()
    _release_payment(job, db)

    db.commit()
    db.refresh(review)
    db.refresh(job)
    return _out(job, review)


@router.post("/jobs/{job_id}/photo-review/dispute-ai-result", response_model=PhotoReviewOut)
def dispute_ai_result(
    job_id: int,
    body: DisputeAIResultRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    review = _require_status(
        job,
        _get_review(job, db),
        PhotoReviewStatus.ai_checked_genuine,
        "There is no AI result waiting for you to dispute on this job",
    )

    if not same_amount(body.confirm_fee, HUMAN_REVIEW_FEE):
        raise HTTPException(
            status_code=400,
            detail=f"The fee for a human review is {float(HUMAN_REVIEW_FEE)}. Resend with confirm_fee={float(HUMAN_REVIEW_FEE)} to agree to it.",
        )

    # The job price and both fees stay held until a human decides.
    reason = "Renter disputes the AI's 'genuine' verdict"
    if body.reason:
        reason = f"{reason}: {body.reason}"

    review.human_fee_amount = float(HUMAN_REVIEW_FEE)
    review.human_fee_status = FeeStatus.held
    review.status = PhotoReviewStatus.awaiting_human
    review.escalation_reason = reason

    db.commit()
    db.refresh(review)
    return _out(job, review)


@router.post("/jobs/{job_id}/photo-review/reupload-complete", response_model=PhotoReviewOut)
def reupload_complete(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    job = _load_job(job_id, db)
    if job.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the reviewer for this job")
    job = check_and_expire_job(job, db)

    review = _require_status(
        job,
        _get_review(job, db),
        PhotoReviewStatus.awaiting_reupload,
        "Nothing is waiting for a re-upload on this job",
    )

    items = review.rejected_items or []
    new_photos = (
        db.query(Photo)
        .filter(Photo.job_id == job.id, Photo.photo_review_id == review.id)
        .all()
    )
    missing = [i for i in items if not any(p.checklist_item == i for p in new_photos)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Upload at least one new photo for each rejected item. Missing: {missing}",
        )

    now = utcnow()
    review.status = PhotoReviewStatus.awaiting_renter_recheck
    review.reuploaded_at = now
    review.recheck_deadline = now + timedelta(hours=RECHECK_WINDOW_HOURS)

    db.commit()
    db.refresh(review)
    return _out(job, review)


@router.post("/jobs/{job_id}/photo-review/recheck/approve", response_model=PhotoReviewOut)
def recheck_approve(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    review = _require_status(
        job,
        _get_review(job, db),
        PhotoReviewStatus.awaiting_renter_recheck,
        "There are no re-uploaded photos waiting for your review on this job",
    )

    # The AI doubted the original photos, so the renter's rejection was fair:
    # the fee is refunded and the reviewer is paid.
    review.status = PhotoReviewStatus.approved_after_reupload
    review.fee_status = FeeStatus.refunded
    review.decided_at = utcnow()
    _release_payment(job, db)

    db.commit()
    db.refresh(review)
    db.refresh(job)
    return _out(job, review)


@router.post("/jobs/{job_id}/photo-review/recheck/reject", response_model=PhotoReviewOut)
def recheck_reject(
    job_id: int,
    body: ReasonRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = _renter_job(job_id, db, current_user)
    review = _require_status(
        job,
        _get_review(job, db),
        PhotoReviewStatus.awaiting_renter_recheck,
        "There are no re-uploaded photos waiting for your review on this job",
    )

    reason = "Renter rejected the re-uploaded photos"
    if body and body.reason:
        reason = f"{reason}: {body.reason}"

    # Money and fee stay held until a human decides.
    review.status = PhotoReviewStatus.awaiting_human
    review.escalation_reason = reason

    db.commit()
    db.refresh(review)
    return _out(job, review)
