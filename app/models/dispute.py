from app.core.time import utcnow
import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON

from app.core.database import Base


class DisputeStatus(str, enum.Enum):
    open = "open"
    ai_resolved = "ai_resolved"
    escalated = "escalated"
    resolved = "resolved"


class DisputeOutcome(str, enum.Enum):
    refund = "refund"
    uphold = "uphold"
    partial = "partial"


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    renter_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    reason = Column(String, nullable=False)
    evidence_urls = Column(JSON, nullable=True)

    status = Column(Enum(DisputeStatus), default=DisputeStatus.open)

    ai_recommendation = Column(JSON, nullable=True)
    resolution_outcome = Column(Enum(DisputeOutcome), nullable=True)
    resolution_notes = Column(String, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)
