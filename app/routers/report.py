from app.core.time import utcnow
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.photo import Photo
from app.models.report import Report
from app.models.user import User, UserRole
from app.schemas.report import ReportCreate, ReportOut
from app.services.verification_graph import verification_graph
from app.services.verification_nodes import (
    InvalidVerificationResult,
    _validate_checklist,
)
from app.services.job_lifecycle import check_and_expire_job

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ReportOut)
def submit_report(
    report_in: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    job = db.query(Job).filter(Job.id == report_in.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the reviewer for this job")

    job = check_and_expire_job(job, db)

    if job.status not in (JobStatus.visited, JobStatus.needs_reupload):
        raise HTTPException(
            status_code=400,
            detail=f"Report cannot be submitted from job status '{job.status.value}'",
        )

    try:
        _validate_checklist(job.checklist_json)
    except InvalidVerificationResult:
        raise HTTPException(status_code=409, detail="This job has an invalid saved checklist. Contact support.") from None

    # Every checklist item needs at least one photo as evidence.
    photos = db.query(Photo).filter(Photo.job_id == job.id).order_by(Photo.id).all()
    missing = [
        item
        for item in (job.checklist_json or [])
        if not any(p.checklist_item == item for p in photos)
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Every checklist item needs at least one photo. Missing photos for: {missing}",
        )
    media_urls = [f"/photos/{p.id}" for p in photos]

    existing = db.query(Report).filter(Report.job_id == report_in.job_id).first()

    if existing and job.status != JobStatus.needs_reupload:
        raise HTTPException(status_code=400, detail="A report already exists for this job")

    if existing:
        # Resubmission clears the previous verification results.
        existing.media_urls = media_urls
        existing.notes = report_in.notes
        existing.ai_verification_result = None
        existing.ai_generated_summary = None
        existing.check_score = None
        report = existing
    else:
        report = Report(
            job_id=report_in.job_id,
            media_urls=media_urls,
            notes=report_in.notes,
        )
        db.add(report)

    job.status = JobStatus.report_submitted
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/verify", response_model=ReportOut)
def verify_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    job = db.query(Job).filter(Job.id == report.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    if current_user.role != UserRole.admin and current_user.id not in (
        job.renter_id,
        job.reviewer_id,
    ):
        raise HTTPException(status_code=403, detail="You do not have access to this report")

    if job.status != JobStatus.report_submitted:
        raise HTTPException(
            status_code=400,
            detail=f"Report cannot be verified from job status '{job.status.value}'",
        )

    checklist = job.checklist_json
    try:
        _validate_checklist(checklist)
    except InvalidVerificationResult:
        raise HTTPException(
            status_code=409,
            detail=(
                "This job has an invalid saved checklist. "
                "Verification was not started. Please contact support."
            ),
        ) from None

    # Initial verification checks notes only.
    # The renter reviews photos; AI checks them only after rejection.
    graph_input = {
        "job_id": job.id,
        "checklist": checklist,
        "photos": [],
        "notes": report.notes or "",
        "verification_result": [],
        "all_addressed": False,
        "check_score": 0.0,
        "summary": "",
    }

    # Do not change report or job fields until the graph succeeds.
    try:
        final_state = verification_graph.invoke(graph_input)
    except InvalidVerificationResult:
        logger.warning(
            "Invalid AI checklist results for report %s", report.id
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI returned invalid checklist results. "
                "Nothing was saved. Please retry verification."
            ),
        ) from None
    except Exception:
        logger.exception("Verification failed for report %s", report.id)
        raise HTTPException(
            status_code=502,
            detail=(
                "The verification service failed. "
                "Nothing was saved. Please retry verification."
            ),
        ) from None

    report.ai_verification_result = final_state["verification_result"]
    report.ai_generated_summary = final_state["summary"]
    report.check_score = final_state["check_score"]

    if final_state["all_addressed"]:
        job.status = JobStatus.verified
        job.verified_at = utcnow()
    else:
        job.status = JobStatus.needs_reupload

    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    job = db.query(Job).filter(Job.id == report.job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Associated job not found")
    if current_user.role != UserRole.admin and current_user.id not in (job.renter_id, job.reviewer_id):
        raise HTTPException(status_code=403, detail="You do not have access to this report")
    return report
