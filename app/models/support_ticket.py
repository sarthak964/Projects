from app.core.time import utcnow
import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum

from app.core.database import Base


class SupportTicketStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    renter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)

    message = Column(String, nullable=False)
    ai_summary = Column(String, nullable=True)
    status = Column(Enum(SupportTicketStatus), default=SupportTicketStatus.open)

    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)
