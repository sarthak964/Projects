from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.job import Job
from app.models.ledger import LedgerEntry
from app.models.payment import Payment, PaymentStatus
from app.models.photo_review import FeeStatus, PhotoReview
from app.models.user import User, UserRole
from app.schemas.ledger import (
    JobLedgerOut,
    LedgerEntryOut,
    MyLedgerEntry,
    MyLedgerOut,
    PlatformSummary,
)
from app.services.ledger import ESCROW, PLATFORM, backfill_ledger
from app.services.money import to_paise

router = APIRouter(tags=["ledger"])


def _rupees(paise: int) -> float:
    return round(paise / 100, 2)


def _paise(rupees) -> int:
    return to_paise(rupees if rupees is not None else 0)


def _balances(entries) -> dict:
    """Balance per account: what it received minus what it paid out."""
    balances = defaultdict(int)
    for e in entries:
        balances[e.credit_account] += e.amount_paise
        balances[e.debit_account] -= e.amount_paise
    return balances


@router.get("/ledger/me", response_model=MyLedgerOut)
def my_ledger(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter, UserRole.reviewer)),
):
    account = f"{current_user.role.value}:{current_user.id}"
    rows = (
        db.query(LedgerEntry)
        .filter(or_(LedgerEntry.debit_account == account, LedgerEntry.credit_account == account))
        .order_by(LedgerEntry.id)
        .all()
    )

    entries = []
    net = 0
    for e in rows:
        signed = e.amount_paise if e.credit_account == account else -e.amount_paise
        net += signed
        entries.append(
            MyLedgerEntry(
                id=e.id,
                job_id=e.job_id,
                kind=e.kind,
                description=e.description,
                amount=_rupees(signed),
                created_at=e.created_at,
            )
        )
    return MyLedgerOut(account=account, net=_rupees(net), entries=entries)


@router.get("/admin/ledger/jobs/{job_id}", response_model=JobLedgerOut)
def job_ledger(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    if not db.query(Job).filter(Job.id == job_id).first():
        raise HTTPException(status_code=404, detail="Job not found")

    rows = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.job_id == job_id)
        .order_by(LedgerEntry.id)
        .all()
    )
    escrow = _balances(rows).get(ESCROW, 0)
    return JobLedgerOut(
        job_id=job_id,
        entries=[
            LedgerEntryOut(
                id=e.id,
                job_id=e.job_id,
                kind=e.kind,
                description=e.description,
                debit_account=e.debit_account,
                credit_account=e.credit_account,
                amount=_rupees(e.amount_paise),
                created_at=e.created_at,
            )
            for e in rows
        ],
        escrow_balance=_rupees(escrow),
        settled=(escrow == 0),
    )


@router.get("/admin/ledger/summary", response_model=PlatformSummary)
def platform_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    rows = db.query(LedgerEntry).all()
    balances = _balances(rows)

    earned = defaultdict(int)
    for e in rows:
        if e.credit_account == PLATFORM:
            earned[e.kind] += e.amount_paise
        elif e.debit_account == PLATFORM:
            earned[e.kind] -= e.amount_paise

    # What escrow SHOULD hold according to the payment and fee statuses.
    expected_escrow = sum(
        _paise(p.amount)
        for p in db.query(Payment).filter(Payment.status == PaymentStatus.held).all()
    )
    for review in db.query(PhotoReview).all():
        if review.fee_status == FeeStatus.held:
            expected_escrow += _paise(review.fee_amount)
        if (review.human_fee_status or FeeStatus.none) == FeeStatus.held:
            expected_escrow += _paise(review.human_fee_amount)

    escrow = balances.get(ESCROW, 0)
    balanced = sum(balances.values()) == 0 and escrow == expected_escrow

    return PlatformSummary(
        platform_balance=_rupees(balances.get(PLATFORM, 0)),
        earned_by_kind={k: _rupees(v) for k, v in earned.items() if v != 0},
        escrow_balance=_rupees(escrow),
        renters_net=_rupees(sum(v for k, v in balances.items() if k.startswith("renter:"))),
        reviewers_net=_rupees(sum(v for k, v in balances.items() if k.startswith("reviewer:"))),
        entry_count=len(rows),
        balanced=balanced,
    )


@router.post("/admin/ledger/backfill")
def run_backfill(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    """Writes ledger entries for jobs that had payments before the ledger existed. Safe to repeat."""
    return {"entries_added": backfill_ledger(db)}
