from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.reviewer_profile import ReviewerProfile
from app.schemas.reviewer_profile import ReviewerLocationUpdate, ReviewerProfileOut
from app.services.geocoding import geocode_address

router = APIRouter(prefix="/reviewers", tags=["reviewers"])


@router.post("/{user_id}/location", response_model=ReviewerProfileOut)
def set_reviewer_location(
    user_id: int,
    location_in: ReviewerLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer, UserRole.admin)),
):
    if current_user.role != UserRole.admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You can only set your own location")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != UserRole.reviewer:
        raise HTTPException(status_code=400, detail="This user is not a reviewer")

    coords = geocode_address(location_in.address)
    if coords is None:
        raise HTTPException(
            status_code=400, detail="Could not find coordinates for that address"
        )

    profile = db.query(ReviewerProfile).filter(ReviewerProfile.user_id == user_id).first()
    if not profile:
        profile = ReviewerProfile(user_id=user_id)
        db.add(profile)

    profile.home_lat = coords["lat"]
    profile.home_lng = coords["lng"]

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{user_id}/profile", response_model=ReviewerProfileOut | None)
def read_reviewer_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer, UserRole.admin)),
):
    if current_user.role != UserRole.admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You can only read your own reviewer profile")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != UserRole.reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    return db.query(ReviewerProfile).filter(ReviewerProfile.user_id == user_id).first()
