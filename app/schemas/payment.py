from pydantic import ConfigDict, BaseModel
from app.models.payment import PaymentStatus


class PaymentOut(BaseModel):
    id: int
    job_id: int
    amount: float
    status: PaymentStatus
    escrow_provider_ref: str | None
    refund_amount: float | None

    model_config = ConfigDict(from_attributes=True)
