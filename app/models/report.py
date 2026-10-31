from app.core.time import utcnow
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)

    media_urls = Column(JSON, nullable=True)
    notes = Column(String, nullable=True)
    ai_verification_result = Column(JSON, nullable=True)
    ai_generated_summary = Column(String, nullable=True)
    check_score = Column(Float, nullable=True)

    submitted_at = Column(DateTime, default=utcnow)
