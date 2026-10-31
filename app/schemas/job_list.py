from datetime import datetime

from pydantic import BaseModel

from app.models.payment import PaymentStatus
from app.schemas.job import JobOut


class JobListItem(JobOut):
    accept_deadline: datetime | None
    submit_deadline: datetime | None
    verified_at: datetime | None
    report_id: int | None
    check_score: float | None
    payment_status: PaymentStatus | None
    photo_review_status: str | None
    appeal_status: str | None
    review_deadline: datetime | None
    ai_result_deadline: datetime | None
    reupload_deadline: datetime | None
    recheck_deadline: datetime | None
    appeal_deadline: datetime | None


class JobListOut(BaseModel):
    items: list[JobListItem]
    total: int
    limit: int
    offset: int
