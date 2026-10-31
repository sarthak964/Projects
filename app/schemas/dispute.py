from datetime import datetime
from pydantic import ConfigDict, BaseModel, Field

from app.models.dispute import DisputeStatus, DisputeOutcome


class DisputeCreate(BaseModel):
    job_id: int
    reason: str
    evidence_urls: list[str] | None = None


class DisputeResolve(BaseModel):
    outcome: DisputeOutcome
    notes: str
    refund_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class DisputeOut(BaseModel):
    id: int
    job_id: int
    renter_id: int
    reason: str
    evidence_urls: list[str] | None
    status: DisputeStatus
    ai_recommendation: dict | list | None
    resolution_outcome: DisputeOutcome | None
    resolution_notes: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
