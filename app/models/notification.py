from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String

from app.core.database import Base
from app.core.time import utcnow


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_id", "user_id", "id"),
        Index("ix_notifications_user_unread_id", "user_id", "is_read", "id"),
        CheckConstraint("is_read IN (0, 1)", name="ck_notifications_is_read"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    event_key = Column(String(255), nullable=False, unique=True)
    event_type = Column(String(80), nullable=False)
    title = Column(String(160), nullable=False)
    message = Column(String, nullable=False)
    deadline_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
