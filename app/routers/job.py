from app.core.time import utcnow
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.config import ACCEPT_WINDOW_HOURS, SUBMIT_WINDOW_HOURS, MAX_SERVICE_DISTANCE_KM
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.models.payment import Payment, PaymentStatus
from app.models.reviewer_profile import ReviewerProfile
from app.schemas.job import JobCreate, JobOut, OpenJobOut
from app.services.geocoding import geocode_address
from app.services.pricing import haversine_distance_km, calculate_price, valid_coordinates
from app.services.job_lifecycle import check_and_expire_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobOut)
def create_job(
    job_in: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    coords = geocode_address(job_in.address)
    if coords is None:
        raise HTTPException(
            status_code=400, detail="Could not find coordinates for that address"
        )

    job = Job(
        renter_id=current_user.id,
        address=job_in.address,
        geocoded_lat=coords["lat"],
        geocoded_lng=coords["lng"],
        checklist_json=job_in.checklist,
        accept_deadline=utcnow() + timedelta(hours=ACCEPT_WINDOW_HOURS),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# NOTE: this must stay above "/{job_id}", otherwise "open" is parsed as a job id.
@router.get("/open", response_model=list[OpenJobOut])
def list_open_jobs(
    max_distance_km: float | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    """Jobs still waiting for a reviewer, nearest to the reviewer's home first."""
    profile = (
        db.query(ReviewerProfile).filter(ReviewerProfile.user_id == current_user.id).first()
    )
    if profile and profile.suspended:
        raise HTTPException(
            status_code=403,
            detail="Your reviewer account is suspended. Please contact support.",
        )
    if not profile or not valid_coordinates(profile.home_lat, profile.home_lng):
        raise HTTPException(
            status_code=400,
            detail="Set your location first with POST /reviewers/{user_id}/location",
        )

    now = utcnow()
    jobs = (
        db.query(Job)
        .filter(
            Job.status == JobStatus.requested,
            Job.accept_deadline > now,
            Job.geocoded_lat.isnot(None),
            Job.geocoded_lng.isnot(None),
        )
        .all()
    )

    results = []
    for job in jobs:
        if not valid_coordinates(job.geocoded_lat, job.geocoded_lng):
            continue
        distance_km = haversine_distance_km(
            job.geocoded_lat, job.geocoded_lng, profile.home_lat, profile.home_lng
        )
        if distance_km > MAX_SERVICE_DISTANCE_KM:
            continue
        if max_distance_km is not None and distance_km > max_distance_km:
            continue
        results.append(
            OpenJobOut(
                id=job.id,
                address=job.address,
                checklist_json=job.checklist_json,
                distance_km=round(distance_km, 2),
                estimated_price=calculate_price(distance_km),
                accept_deadline=job.accept_deadline,
            )
        )

    results.sort(key=lambda r: r.distance_km)
    return results[:limit]


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    is_participant = current_user.id in (job.renter_id, job.reviewer_id)
    is_open_for_reviewers = (
        current_user.role == UserRole.reviewer and job.status == JobStatus.requested
    )
    if not (is_participant or is_open_for_reviewers or current_user.role == UserRole.admin):
        raise HTTPException(status_code=403, detail="You do not have access to this job")

    return check_and_expire_job(job, db)


@router.post("/{job_id}/accept", response_model=JobOut)
def accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job = check_and_expire_job(job, db)

    if job.status != JobStatus.requested:
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be accepted from status '{job.status.value}'",
        )

    if not valid_coordinates(job.geocoded_lat, job.geocoded_lng):
        raise HTTPException(
            status_code=409,
            detail="This job has no valid property location. Contact support before accepting it.",
        )

    reviewer_profile = (
        db.query(ReviewerProfile)
        .filter(ReviewerProfile.user_id == current_user.id)
        .first()
    )
    if reviewer_profile and reviewer_profile.suspended:
        raise HTTPException(
            status_code=403,
            detail="Your reviewer account is suspended. Please contact support.",
        )
    if not reviewer_profile or not valid_coordinates(reviewer_profile.home_lat, reviewer_profile.home_lng):
        raise HTTPException(
            status_code=400,
            detail="Reviewer has not set their location yet. "
            "Call POST /reviewers/{user_id}/location first.",
        )

    distance_km = haversine_distance_km(
        job.geocoded_lat, job.geocoded_lng, reviewer_profile.home_lat, reviewer_profile.home_lng
    )
    if distance_km > MAX_SERVICE_DISTANCE_KM:
        raise HTTPException(
            status_code=400,
            detail=f"This job is outside the {MAX_SERVICE_DISTANCE_KM:g} km service radius from your saved location.",
        )
    price = calculate_price(distance_km)

    job.reviewer_id = current_user.id
    job.status = JobStatus.accepted
    job.price = price
    job.submit_deadline = utcnow() + timedelta(hours=SUBMIT_WINDOW_HOURS)

    payment = Payment(
        job_id=job.id,
        amount=price,
        status=PaymentStatus.held,
    )
    db.add(payment)

    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/visit", response_model=JobOut)
def mark_visited(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the reviewer for this job")

    job = check_and_expire_job(job, db)

    if job.status != JobStatus.accepted:
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be marked visited from status '{job.status.value}'",
        )

    job.status = JobStatus.visited
    db.commit()
    db.refresh(job)
    return job
