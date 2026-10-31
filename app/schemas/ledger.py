from datetime import datetime

from pydantic import BaseModel


class MyLedgerEntry(BaseModel):
    id: int
    job_id: int
    kind: str
    description: str | None
    amount: float            # positive = money received, negative = money paid out
    created_at: datetime


class MyLedgerOut(BaseModel):
    account: str
    net: float               # the total of all entries below (a renter's is negative: money spent)
    entries: list[MyLedgerEntry]


class LedgerEntryOut(BaseModel):
    id: int
    job_id: int
    kind: str
    description: str | None
    debit_account: str       # who paid
    credit_account: str      # who received
    amount: float
    created_at: datetime


class JobLedgerOut(BaseModel):
    job_id: int
    entries: list[LedgerEntryOut]
    escrow_balance: float    # money still held for this job
    settled: bool            # True when nothing is left in escrow for this job


class PlatformSummary(BaseModel):
    platform_balance: float          # everything the platform has earned so far
    earned_by_kind: dict[str, float] # e.g. commission, fee_kept, human_fee_kept (reversals netted off)
    escrow_balance: float            # money currently held across all jobs
    renters_net: float               # total renters have spent (negative)
    reviewers_net: float             # total paid to reviewers
    entry_count: int
    balanced: bool                   # every account balance adds up to zero
