from app.core.time import utcnow
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.config import DISPUTE_WINDOW_DAYS, DISPUTE_AUTO_RESOLVE_CONFIDENCE
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.dispute import Dispute, DisputeStatus, DisputeOutcome
from app.models.photo_review import PhotoReview
from app.models.report import Report
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.dispute import DisputeCreate, DisputeResolve, DisputeOut
from app.services.dispute_graph import dispute_graph
from app.services.money import to_paise
from app.services.payments import require_payment

router = APIRouter(prefix="/disputes", tags=["disputes"])


def _require_no_photo_review(job: Job, db: Session) -> None:
    review = (
        db.query(PhotoReview)
        .filter(PhotoReview.job_id == job.id)
        .first()
    )
    if review is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This job uses the photo-review workflow. "
                "Legacy disputes cannot change its outcome. "
                f"Use GET /jobs/{job.id}/photo-review to check the current "
                "stage, then use the appropriate photo-review or appeal action."
            ),
        )


def _require_legacy_case_active(job: Job, db: Session) -> None:
    _require_no_photo_review(job, db)
    if job.status != JobStatus.disputed:
        raise HTTPException(
            status_code=409,
            detail=(
                "This legacy dispute cannot change the job because its "
                f"current status is '{job.status.value}', not 'disputed'. "
                "An admin must inspect the case before further action."
            ),
        )


@router.get("/", response_model=list[DisputeOut])
def list_disputes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    job_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter, UserRole.admin)),
):
    query = db.query(Dispute)
    if current_user.role != UserRole.admin:
        query = query.filter(Dispute.renter_id == current_user.id)
    if job_id is not None:
        query = query.filter(Dispute.job_id == job_id)
    return query.order_by(Dispute.id.desc()).offset(offset).limit(limit).all()


@router.post("/", response_model=DisputeOut)
def file_dispute(
    dispute_in: DisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = db.query(Job).filter(Job.id == dispute_in.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="You did not create this job")

    existing = db.query(Dispute).filter(Dispute.job_id == dispute_in.job_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="A dispute already exists for this job")

    if job.verified_at is None:
        raise HTTPException(
            status_code=400,
            detail="This job was never verified, so there is nothing to dispute",
        )

    _require_no_photo_review(job, db)

    if job.status == JobStatus.verified:
        raise HTTPException(
            status_code=409,
            detail=(
                "This job is awaiting photo review. "
                "Use the photo-review workflow instead of a legacy dispute. "
                f"Start with GET /jobs/{job.id}/photo-review."
            ),
        )

    if job.status != JobStatus.paid:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot file a dispute while job is at status '{job.status.value}'",
        )

    if utcnow() > job.verified_at + timedelta(days=DISPUTE_WINDOW_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"The {DISPUTE_WINDOW_DAYS}-day dispute window for this job has passed",
        )

    dispute = Dispute(
        job_id=dispute_in.job_id,
        renter_id=current_user.id,
        reason=dispute_in.reason,
        evidence_urls=dispute_in.evidence_urls,
    )
    db.add(dispute)

    job.status = JobStatus.disputed

    db.commit()
    db.refresh(dispute)
    return dispute


@router.get("/{dispute_id}", response_model=DisputeOut)
def get_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if current_user.role != UserRole.admin and dispute.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this dispute")

    return dispute


@router.post("/{dispute_id}/triage", response_model=DisputeOut)
def triage_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if current_user.role != UserRole.admin and dispute.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this dispute")

    if dispute.status != DisputeStatus.open:
        raise HTTPException(
            status_code=400,
            detail=f"Dispute cannot be triaged from status '{dispute.status.value}'",
        )

    job = db.query(Job).filter(Job.id == dispute.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    _require_legacy_case_active(job, db)

    report = db.query(Report).filter(Report.job_id == dispute.job_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Associated report not found")

    payment = db.query(Payment).filter(Payment.job_id == dispute.job_id).first()

    graph_input = {
        "job_id": job.id,
        "checklist": job.checklist_json or [],
        "original_notes": report.notes or "",
        "original_verification_result": report.ai_verification_result or [],
        "renter_reason": dispute.reason,
        "renter_evidence_urls": dispute.evidence_urls or [],
        "recommended_outcome": "",
        "confidence": 0.0,
        "reasoning": "",
    }

    try:
        final_state = dispute_graph.invoke(graph_input)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Dispute analysis failed. The case is still open; please retry.",
        ) from None

    dispute.ai_recommendation = {
        "recommended_outcome": final_state["recommended_outcome"],
        "confidence": final_state["confidence"],
        "reasoning": final_state["reasoning"],
    }

    # Legacy cases also require a human before any money changes.
    dispute.status = DisputeStatus.escalated
    db.commit()
    db.refresh(dispute)
    return dispute


@router.post("/{dispute_id}/resolve", response_model=DisputeOut)
def resolve_dispute(
    dispute_id: int,
    resolve_in: DisputeResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if dispute.status != DisputeStatus.escalated:
        raise HTTPException(
            status_code=400,
            detail=f"Dispute cannot be manually resolved from status '{dispute.status.value}'",
        )

    job = db.query(Job).filter(Job.id == dispute.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Associated job not found")

    _require_legacy_case_active(job, db)

    payment = require_payment(job, db, PaymentStatus.released)
    if resolve_in.outcome == DisputeOutcome.partial:
        if resolve_in.refund_amount is None or not 0 <= resolve_in.refund_amount <= payment.amount:
            raise HTTPException(
                status_code=400,
                detail="refund_amount must be between zero and the job payment amount",
            )

    if resolve_in.outcome == DisputeOutcome.refund:
        if payment:
            payment.status = PaymentStatus.refunded
        job.status = JobStatus.refunded

    elif resolve_in.outcome == DisputeOutcome.uphold:
        if payment and payment.status == PaymentStatus.held:
            payment.status = PaymentStatus.released
        job.status = JobStatus.paid

    elif resolve_in.outcome == DisputeOutcome.partial:
        if resolve_in.refund_amount is None:
            raise HTTPException(
                status_code=400,
                detail="refund_amount is required when the outcome is 'partial'",
            )
        if payment:
            payment.status = PaymentStatus.partial_payout
            payment.refund_amount = resolve_in.refund_amount
        job.status = JobStatus.refunded

    dispute.resolution_outcome = resolve_in.outcome
    dispute.resolution_notes = resolve_in.notes
    dispute.status = DisputeStatus.resolved
    dispute.resolved_at = utcnow()

    db.commit()
    db.refresh(dispute)
    return dispute
