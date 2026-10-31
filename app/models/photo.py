from app.core.time import utcnow
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index

from app.core.database import Base


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (Index("ix_photos_job_review_item", "job_id", "photo_review_id", "checklist_item"),)

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), index=True, nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # NULL for originals; explicit case membership for replacement evidence.
    photo_review_id = Column(Integer, ForeignKey("photo_reviews.id"), nullable=True)

    checklist_item = Column(String, nullable=False)   # which checklist item this photo is for
    stored_name = Column(String, nullable=False)      # random file name on disk, never the client's
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=utcnow)
