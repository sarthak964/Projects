from app.core.time import utcnow
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from app.core.database import Base


class LedgerEntry(Base):
    """
    One money movement between two accounts. Accounts are plain strings:
    "renter:<user id>", "reviewer:<user id>", "platform" and "escrow".
    An account's balance is the sum of what it received minus what it paid out.
    """

    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), index=True, nullable=False)

    kind = Column(String, index=True, nullable=False)          # e.g. price_held, payout, commission
    debit_account = Column(String, index=True, nullable=False)   # who paid
    credit_account = Column(String, index=True, nullable=False)  # who received
    amount_paise = Column(Integer, nullable=False)               # always positive

    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
