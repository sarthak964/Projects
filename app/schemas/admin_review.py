from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HumanDecisionRequest(BaseModel):
    decision: Literal["genuine", "not_genuine"]
    notes: str = Field(min_length=3)   # the admin must explain the decision


class QueueItem(BaseModel):
    job_id: int
    renter_id: int
    reviewer_id: int | None
    rejected_items: list[str]
    escalation_reason: str | None
    fee_amount: float
    fee_status: str
    human_fee_amount: float = 0.0
    human_fee_status: str = "none"
    review_created_at: datetime | None


class ReviewPhoto(BaseModel):
    id: int
    checklist_item: str
    url: str
    created_at: datetime
    round: str                 # "original" or "reupload"
    is_rejected_item: bool


class AdminReviewDetail(BaseModel):
    job_id: int
    address: str
    checklist: list[str]
    renter_id: int
    reviewer_id: int | None
    job_status: str
    job_price: float | None
    payment_status: str | None

    report_notes: str | None
    review_status: str
    rejected_items: list[str]
    renter_reason: str | None
    escalation_reason: str | None
    fee_amount: float
    fee_status: str
    human_fee_amount: float = 0.0
    human_fee_status: str = "none"
    ai_verdict: dict | None
    photos: list[ReviewPhoto]

    human_decision: str | None = None
    decision_notes: str | None = None
    decided_by: int | None = None
    decided_at: datetime | None = None

    reviewer_strikes: int | None = None
    reviewer_suspended: bool | None = None
