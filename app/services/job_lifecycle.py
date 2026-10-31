from app.core.time import utcnow
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import (
    PHOTO_REVIEW_WINDOW_HOURS,
    RECHECK_WINDOW_HOURS,
    REUPLOAD_WINDOW_HOURS,
)
from app.services.payments import release_job_payment, require_payment
from app.models.job import Job, JobStatus
from app.models.payment import Payment, PaymentStatus
from app.models.photo_review import PhotoReview, PhotoReviewStatus, FeeStatus

# Statuses still waiting on a reviewer to submit their report, governed by
# job.submit_deadline (set when the job is accepted).
_AWAITING_SUBMIT_STATUSES = (JobStatus.accepted, JobStatus.visited, JobStatus.needs_reupload)


def _release_payment(job: Job, db: Session) -> None:
    release_job_payment(job, db)


def check_and_expire_job(job: Job, db: Session) -> Job:
    """
    Lazily applies any deadline that has passed for the job's current stage.
    The background scheduler and job endpoints share these deadline rules.

    - requested past accept_deadline            -> expired
    - accepted/visited/needs_reupload past
      submit_deadline                           -> expired, held payment refunded
    - verified, renter never reviewed the
      photos within the review window           -> photos auto-approved, reviewer paid
    - photo review awaiting a re-upload past
      its deadline                              -> sent to a human (no penalty)
    - photo review awaiting the renter's
      re-check past its deadline                -> auto-approved, reviewer paid, fee refunded
    - AI found the rejected photos genuine and
      the renter did not respond in time        -> treated as accepted, reviewer paid, fee kept
    """
    now = utcnow()

    if job.status == JobStatus.requested and job.accept_deadline and now > job.accept_deadline:
        job.status = JobStatus.expired
        db.commit()
        db.refresh(job)

    elif (
        job.status in _AWAITING_SUBMIT_STATUSES
        and job.submit_deadline
        and now > job.submit_deadline
    ):
        payment = require_payment(job, db, PaymentStatus.held)
        payment.status = PaymentStatus.refunded
        job.status = JobStatus.expired

        db.commit()
        db.refresh(job)

    elif job.status == JobStatus.verified:
        review = db.query(PhotoReview).filter(PhotoReview.job_id == job.id).first()

        if review is None:
            if (
                job.verified_at
                and now > job.verified_at + timedelta(hours=PHOTO_REVIEW_WINDOW_HOURS)
            ):
                _release_payment(job, db)
                db.add(
                    PhotoReview(
                        job_id=job.id,
                        status=PhotoReviewStatus.auto_approved,
                        rejected_items=[],
                        fee_amount=0.0,
                        fee_status=FeeStatus.none,
                        decided_at=now,
                    )
                )
                db.commit()
                db.refresh(job)

        elif review.status == PhotoReviewStatus.awaiting_reupload:
            deadline = review.reupload_deadline or (
                review.created_at + timedelta(hours=REUPLOAD_WINDOW_HOURS)
            )
            if now > deadline:
                review.status = PhotoReviewStatus.awaiting_human
                review.escalation_reason = "The reviewer did not re-upload the photos in time"
                db.commit()
                db.refresh(job)

        elif review.status == PhotoReviewStatus.awaiting_renter_recheck:
            if review.recheck_deadline and now > review.recheck_deadline:
                review.status = PhotoReviewStatus.auto_approved_after_reupload
                review.fee_status = FeeStatus.refunded
                review.decided_at = now
                _release_payment(job, db)
                db.commit()
                db.refresh(job)

        elif review.status == PhotoReviewStatus.ai_checked_genuine:
            deadline = review.ai_result_deadline or (
                review.created_at + timedelta(hours=RECHECK_WINDOW_HOURS)
            )
            if now > deadline:
                # The AI judged the photos genuine and the renter neither accepted
                # nor disputed: same outcome as accepting.
                review.status = PhotoReviewStatus.auto_accepted_ai_result
                review.fee_status = FeeStatus.kept
                review.decided_at = now
                _release_payment(job, db)
                db.commit()
                db.refresh(job)

    return job
