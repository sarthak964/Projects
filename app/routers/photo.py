import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.core.config import UPLOAD_DIR, MAX_PHOTO_BYTES, MAX_PHOTOS_PER_ITEM
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.photo import Photo
from app.models.photo_review import PhotoReview, PhotoReviewStatus
from app.models.user import User, UserRole
from app.schemas.photo import PhotoOut
from app.services.images import inspect_image, InvalidImageError
from app.services.job_lifecycle import check_and_expire_job

router = APIRouter(tags=["photos"])
logger = logging.getLogger(__name__)

# Photos can be added after the visit is marked and until the report is submitted
# (or again if the report was sent back with needs_reupload). A second window
# opens when the renter rejects photos and the AI doubts them (re-upload round).
_UPLOADABLE_STATUSES = (JobStatus.visited, JobStatus.needs_reupload)


def _to_out(photo: Photo) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        job_id=photo.job_id,
        checklist_item=photo.checklist_item,
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        created_at=photo.created_at,
        url=f"/photos/{photo.id}",
        round="reupload" if photo.photo_review_id is not None else "original",
    )


def _can_view(user: User, job: Job) -> bool:
    return user.role == UserRole.admin or user.id in (job.renter_id, job.reviewer_id)


def _reupload_review(job: Job, db: Session) -> PhotoReview | None:
    """The photo review for this job if it is currently waiting for a re-upload."""
    if job.status != JobStatus.verified:
        return None
    review = db.query(PhotoReview).filter(PhotoReview.job_id == job.id).first()
    if review and review.status == PhotoReviewStatus.awaiting_reupload:
        return review
    return None


@router.post("/jobs/{job_id}/photos", response_model=PhotoOut)
def upload_photo(
    job_id: int,
    checklist_item: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the reviewer for this job")

    job = check_and_expire_job(job, db)

    reupload = _reupload_review(job, db)
    if reupload is None and job.status not in _UPLOADABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Photos can only be uploaded after you mark the visit and before the "
            "report is submitted, or when the renter has asked for a re-upload "
            f"(job is '{job.status.value}')",
        )

    if checklist_item not in (job.checklist_json or []):
        raise HTTPException(
            status_code=400,
            detail="checklist_item must exactly match one of this job's checklist items",
        )

    if reupload is not None and checklist_item not in (reupload.rejected_items or []):
        raise HTTPException(
            status_code=400,
            detail=f"Only photos for the rejected items can be re-uploaded: {reupload.rejected_items}",
        )

    count_query = db.query(Photo).filter(
        Photo.job_id == job.id, Photo.checklist_item == checklist_item
    )
    if reupload is not None:
        # In a re-upload round only the new photos count toward the cap.
        count_query = count_query.filter(Photo.photo_review_id == reupload.id)
    if count_query.count() >= MAX_PHOTOS_PER_ITEM:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_PHOTOS_PER_ITEM} photos per checklist item",
        )

    data = file.file.read(MAX_PHOTO_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Photo is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB",
        )

    try:
        content_type, extension = inspect_image(data)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / stored_name).write_bytes(data)

    photo = Photo(
        job_id=job.id,
        uploader_id=current_user.id,
        photo_review_id=reupload.id if reupload is not None else None,
        checklist_item=checklist_item,
        stored_name=stored_name,
        content_type=content_type,
        size_bytes=len(data),
    )
    db.add(photo)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not clean up uncommitted photo %s", stored_name)
        raise
    db.refresh(photo)
    return _to_out(photo)


@router.get("/jobs/{job_id}/photos", response_model=list[PhotoOut])
def list_job_photos(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not _can_view(current_user, job):
        raise HTTPException(status_code=403, detail="You do not have access to this job")

    photos = db.query(Photo).filter(Photo.job_id == job_id).order_by(Photo.id).all()
    return [_to_out(p) for p in photos]


@router.get("/photos/{photo_id}")
def get_photo_file(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    job = db.query(Job).filter(Job.id == photo.job_id).first()
    if not job or not _can_view(current_user, job):
        raise HTTPException(status_code=403, detail="You do not have access to this photo")

    path = UPLOAD_DIR / photo.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file is missing on the server")

    return FileResponse(path, media_type=photo.content_type)


@router.delete("/photos/{photo_id}")
def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.reviewer)),
):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    if photo.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own photos")

    job = db.query(Job).filter(Job.id == photo.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job = check_and_expire_job(job, db)

    reupload = _reupload_review(job, db)
    can_delete = job.status in _UPLOADABLE_STATUSES or (
        reupload is not None and photo.photo_review_id == reupload.id
    )
    if not can_delete:
        raise HTTPException(
            status_code=400,
            detail="Photos can no longer be deleted once the report has been submitted",
        )

    stored_name = photo.stored_name
    db.delete(photo)
    db.commit()
    # A failed/stale database transaction must never remove stored evidence.
    try:
        (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove deleted photo file %s", stored_name)
    return {"deleted": photo_id}
