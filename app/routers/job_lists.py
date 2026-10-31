from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.config import APPEAL_WINDOW_HOURS, PHOTO_REVIEW_WINDOW_HOURS
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.payment import Payment
from app.models.photo_review import PhotoReview
from app.models.report import Report
from app.models.user import User, UserRole
from app.schemas.job import JobOut
from app.schemas.job_list import JobListItem, JobListOut

router = APIRouter(tags=["job lists"])


def _page(query, limit, offset):
    total = query.count()
    rows = (
        query.outerjoin(Payment, Payment.job_id == Job.id)
        .outerjoin(PhotoReview, PhotoReview.job_id == Job.id)
        .outerjoin(Report, Report.job_id == Job.id)
        .add_entity(Payment).add_entity(PhotoReview).add_entity(Report)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset).limit(limit).all()
    )
    items = []
    for job, payment, review, report in rows:
        review_deadline = (
            job.verified_at + timedelta(hours=PHOTO_REVIEW_WINDOW_HOURS)
            if job.verified_at is not None else None
        )
        appeal_deadline = (
            review.decided_at + timedelta(hours=APPEAL_WINDOW_HOURS)
            if review is not None and review.decided_at is not None
            and review.human_decision is not None else None
        )
        review_status = (
            review.status.value if review is not None
            else "pending" if job.status == JobStatus.verified else None
        )
        items.append(JobListItem(
            **JobOut.model_validate(job).model_dump(),
            accept_deadline=job.accept_deadline,
            submit_deadline=job.submit_deadline,
            verified_at=job.verified_at,
            report_id=report.id if report is not None else None,
            check_score=report.check_score if report is not None else None,
            payment_status=payment.status if payment is not None else None,
            photo_review_status=review_status,
            appeal_status=review.appeal_status if review is not None else None,
            review_deadline=review_deadline,
            ai_result_deadline=review.ai_result_deadline if review is not None else None,
            reupload_deadline=review.reupload_deadline if review is not None else None,
            recheck_deadline=review.recheck_deadline if review is not None else None,
            appeal_deadline=appeal_deadline,
        ))
    return JobListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs/mine", response_model=JobListOut)
def my_jobs(
    status: JobStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter, UserRole.reviewer)),
):
    query = db.query(Job)
    owner = Job.renter_id if current_user.role == UserRole.renter else Job.reviewer_id
    query = query.filter(owner == current_user.id)
    if status is not None:
        query = query.filter(Job.status == status)
    return _page(query, limit, offset)


@router.get("/admin/jobs", response_model=JobListOut)
def admin_jobs(
    status: JobStatus | None = None,
    renter_id: int | None = Query(default=None, gt=0),
    reviewer_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    query = db.query(Job)
    if status is not None:
        query = query.filter(Job.status == status)
    if renter_id is not None:
        query = query.filter(Job.renter_id == renter_id)
    if reviewer_id is not None:
        query = query.filter(Job.reviewer_id == reviewer_id)
    return _page(query, limit, offset)
