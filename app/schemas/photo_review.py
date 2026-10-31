from datetime import datetime
from pydantic import BaseModel, Field


class RejectRequest(BaseModel):
    items: list[str] = Field(min_length=1)
    reason: str | None = None
    confirm_fee: float = Field(ge=0, allow_inf_nan=False)   # must equal the quoted fee, so the renter agrees to the exact amount


class ReasonRequest(BaseModel):
    reason: str | None = None


class DisputeAIResultRequest(BaseModel):
    reason: str | None = None
    confirm_fee: float = Field(ge=0, allow_inf_nan=False)   # must equal the human review fee, so the renter agrees to the exact amount


class FeeQuoteOut(BaseModel):
    items: list[str]
    photo_count: int
    fee: float


class PhotoReviewOut(BaseModel):
    job_id: int
    status: str
    review_deadline: datetime | None = None
    rejected_items: list[str] = Field(default_factory=list)
    renter_reason: str | None = None
    fee_amount: float = 0.0
    fee_status: str = "none"
    human_fee_amount: float = 0.0
    human_fee_status: str = "none"
    ai_verdict: dict | None = None
    ai_result_deadline: datetime | None = None
    reupload_deadline: datetime | None = None
    recheck_deadline: datetime | None = None
    escalation_reason: str | None = None
    decided_at: datetime | None = None
