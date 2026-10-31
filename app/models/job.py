from app.core.time import utcnow
import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON

from app.core.database import Base


class JobStatus(str, enum.Enum):
    requested = "requested"
    accepted = "accepted"
    visited = "visited"
    report_submitted = "report_submitted"
    verified = "verified"
    needs_reupload = "needs_reupload"
    paid = "paid"
    expired = "expired"
    disputed = "disputed"
    refunded = "refunded"


class Job(Base):
    __tablename__ = "jobs"

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    id = Column(Integer, primary_key=True, index=True)
    renter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    address = Column(String, nullable=False)
    geocoded_lat = Column(Float, nullable=True)
    geocoded_lng = Column(Float, nullable=True)

    checklist_json = Column(JSON, nullable=True)
    price = Column(Float, nullable=True)

    # Platform commission rate, frozen the first time the job's money is paid out,
    # so changing the setting later never alters a job that has already been paid.
    commission_rate = Column(Float, nullable=True)

    status = Column(Enum(JobStatus), default=JobStatus.requested)

    created_at = Column(DateTime, default=utcnow)
    accept_deadline = Column(DateTime, nullable=True)
    submit_deadline = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
