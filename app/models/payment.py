import enum

from sqlalchemy import Column, Integer, Float, String, Enum, ForeignKey

from app.core.database import Base


class PaymentStatus(str, enum.Enum):
    held = "held"
    released = "released"
    refunded = "refunded"
    partial_payout = "partial_payout"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)

    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.held)
    escrow_provider_ref = Column(String, nullable=True)
    refund_amount = Column(Float, nullable=True)
