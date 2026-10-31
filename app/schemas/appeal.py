from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.admin_review import AdminReviewDetail


class AppealRequest(BaseModel):
    reason: str = Field(min_length=3)


class AppealDecisionRequest(BaseModel):
    decision: Literal["uphold", "overturn"]
    notes: str = Field(min_length=3)   # the admin must explain the decision


class AppealStatusOut(BaseModel):
    """What the renter or the reviewer sees about a case's human decision and appeal."""
    job_id: int
    review_status: str
    human_decision: str | None = None
    decision_notes: str | None = None
    decided_at: datetime | None = None
    appeal_deadline: datetime | None = None
    can_appeal: bool = False
    appeal_by: int | None = None
    appeal_reason: str | None = None
    appealed_at: datetime | None = None
    appeal_status: str | None = None
    appeal_notes: str | None = None
    appeal_decided_at: datetime | None = None


class AppealQueueItem(BaseModel):
    job_id: int
    appeal_by: int | None
    appeal_reason: str | None
    appealed_at: datetime | None
    human_decision: str | None
    decision_notes: str | None


class AppealDetail(AdminReviewDetail):
    """The full case view plus the appeal, for the admin."""
    appeal_by: int | None = None
    appeal_reason: str | None = None
    appealed_at: datetime | None = None
    appeal_status: str | None = None
    appeal_decided_by: int | None = None
    appeal_notes: str | None = None
    appeal_decided_at: datetime | None = None


class SuspendedReviewer(BaseModel):
    user_id: int
    name: str | None
    phone: str
    strikes: int
    suspended: bool


class UnsuspendRequest(BaseModel):
    notes: str = Field(min_length=3)
