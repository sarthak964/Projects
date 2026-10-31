from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.rating import Rating
from app.models.reviewer_profile import ReviewerProfile
from app.models.user import User, UserRole
from app.schemas.rating import RatingCreate, RatingOut

router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.post("/", response_model=RatingOut)
def submit_rating(
    rating_in: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    job = db.query(Job).filter(Job.id == rating_in.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="You did not create this job")

    if job.status != JobStatus.paid:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot rate a job at status '{job.status.value}' - "
            "only fully paid jobs can be rated",
        )

    if not job.reviewer_id:
        raise HTTPException(status_code=400, detail="Job has no reviewer to rate")

    existing = (
        db.query(Rating)
        .filter(Rating.job_id == rating_in.job_id, Rating.rater_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="A rating has already been submitted for this job"
        )

    rating = Rating(
        job_id=rating_in.job_id,
        rater_id=current_user.id,
        rated_id=job.reviewer_id,
        score=rating_in.score,
        comment=rating_in.comment,
    )
    db.add(rating)

    # Recompute the reviewer's running average across all ratings they've received.
    reviewer_profile = (
        db.query(ReviewerProfile).filter(ReviewerProfile.user_id == job.reviewer_id).first()
    )
    if reviewer_profile:
        all_scores = [
            r.score for r in db.query(Rating).filter(Rating.rated_id == job.reviewer_id).all()
        ]
        all_scores.append(rating.score)
        reviewer_profile.rating_avg = round(sum(all_scores) / len(all_scores), 2)

    db.commit()
    db.refresh(rating)
    return rating


@router.get("/{rating_id}", response_model=RatingOut)
def get_rating(
    rating_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rating = db.query(Rating).filter(Rating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    return rating


@router.get("/job/{job_id}", response_model=RatingOut | None)
def get_job_rating(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != UserRole.admin and current_user.id not in (job.renter_id, job.reviewer_id):
        raise HTTPException(status_code=403, detail="You do not have access to this job")
    return db.query(Rating).filter(Rating.job_id == job.id, Rating.rater_id == job.renter_id).first()
