from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import PLATFORM_COMMISSION_RATE
from app.services.money import to_paise, commission_paise
from app.models.job import Job
from app.models.ledger import LedgerEntry
from app.models.payment import Payment, PaymentStatus
from app.models.photo_review import FeeStatus, PhotoReview

ESCROW = "escrow"
PLATFORM = "platform"

DESCRIPTIONS = {
    "price_held": "Job price paid by the renter and held in escrow",
    "payout": "Reviewer payout, after commission",
    "commission": "Platform commission",
    "refund": "Job price refunded to the renter",
    "fee_held": "Photo check fee paid by the renter and held",
    "fee_kept": "Photo check fee kept by the platform",
    "fee_refund": "Photo check fee refunded to the renter",
    "human_fee_held": "Human review fee paid by the renter and held",
    "human_fee_kept": "Human review fee kept by the platform",
    "human_fee_refund": "Human review fee refunded to the renter",
}


def _paise(rupees) -> int:
    return to_paise(rupees if rupees is not None else 0)


def _targets(job, payment, review, rate: float) -> dict:
    """
    What the ledger should total for this job right now, from its current state.
    Returns {kind: (debit_account, credit_account, target_amount_in_paise)}.
    """
    renter = f"renter:{job.renter_id}"
    reviewer = f"reviewer:{job.reviewer_id}" if job.reviewer_id else None
    targets = {}

    if payment is not None and payment.amount:
        price = _paise(payment.amount)
        targets["price_held"] = (renter, ESCROW, price)

        if payment.status == PaymentStatus.released:
            paid_out, refund = price, 0
        elif payment.status == PaymentStatus.refunded:
            paid_out, refund = 0, price
        elif payment.status == PaymentStatus.partial_payout:
            if payment.refund_amount is None:
                raise ValueError("Partial payout requires a refund amount")
            refund = _paise(payment.refund_amount)
            if refund > price:
                raise ValueError("Refund cannot exceed the job price")
            paid_out = price - refund
        else:  # held
            paid_out, refund = 0, 0

        commission = commission_paise(paid_out, rate)
        if reviewer:
            targets["payout"] = (ESCROW, reviewer, paid_out - commission)
        targets["commission"] = (ESCROW, PLATFORM, commission)
        targets["refund"] = (ESCROW, renter, refund)

    if review is not None:
        for prefix, amount, status in (
            ("fee", review.fee_amount, review.fee_status),
            ("human_fee", review.human_fee_amount, review.human_fee_status),
        ):
            fee = _paise(amount)
            status = status or FeeStatus.none
            if fee > 0 and status != FeeStatus.none:
                targets[f"{prefix}_held"] = (renter, ESCROW, fee)
                targets[f"{prefix}_kept"] = (
                    ESCROW,
                    PLATFORM,
                    fee if status == FeeStatus.kept else 0,
                )
                targets[f"{prefix}_refund"] = (
                    ESCROW,
                    renter,
                    fee if status == FeeStatus.refunded else 0,
                )

    return targets


def _find_by_job(session: Session, model, job_id: int):
    # An object created in this flush is not in the database yet, so look there first.
    for obj in session.new:
        if isinstance(obj, model) and obj.job_id == job_id:
            return obj
    return session.query(model).filter(model.job_id == job_id).first()


def _net_for_kind(entries, kind: str, debit: str, credit: str) -> int:
    """Existing total for one kind: entries in the normal direction add, reversals subtract."""
    net = 0
    for e in entries:
        if e.kind != kind:
            continue
        if (e.debit_account, e.credit_account) == (debit, credit):
            net += e.amount_paise
        elif (e.debit_account, e.credit_account) == (credit, debit):
            net -= e.amount_paise
    return net


def sync_job_ledger(session: Session, job_id: int) -> int:
    """
    Brings the ledger in line with the job's current state by adding the missing
    entries. Safe to call any number of times. Returns how many entries it added.
    """
    job = session.get(Job, job_id)
    if job is None:
        return 0

    payment = _find_by_job(session, Payment, job_id)
    review = _find_by_job(session, PhotoReview, job_id)

    # Freeze the commission rate the first time money is paid out.
    if (
        payment is not None
        and payment.status in (PaymentStatus.released, PaymentStatus.partial_payout)
        and job.commission_rate is None
    ):
        job.commission_rate = PLATFORM_COMMISSION_RATE

    rate = job.commission_rate if job.commission_rate is not None else 0.0
    targets = _targets(job, payment, review, rate)

    entries = list(session.query(LedgerEntry).filter(LedgerEntry.job_id == job_id).all())
    entries += [e for e in session.new if isinstance(e, LedgerEntry) and e.job_id == job_id]

    added = 0
    for kind, (debit, credit, target) in targets.items():
        delta = target - _net_for_kind(entries, kind, debit, credit)
        if delta > 0:
            session.add(
                LedgerEntry(
                    job_id=job_id,
                    kind=kind,
                    debit_account=debit,
                    credit_account=credit,
                    amount_paise=delta,
                    description=DESCRIPTIONS[kind],
                )
            )
            added += 1
        elif delta < 0:
            session.add(
                LedgerEntry(
                    job_id=job_id,
                    kind=kind,
                    debit_account=credit,
                    credit_account=debit,
                    amount_paise=-delta,
                    description="Reversal: " + DESCRIPTIONS[kind],
                )
            )
            added += 1
    return added


def backfill_ledger(session: Session) -> int:
    """Writes ledger entries for jobs that already had payments before the ledger existed."""
    with session.no_autoflush:
        job_ids = [row[0] for row in session.query(Payment.job_id).all()]
        added = sum(sync_job_ledger(session, job_id) for job_id in job_ids)
    session.commit()
    return added


@event.listens_for(Session, "before_flush")
def _ledger_before_flush(session, flush_context, instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, LedgerEntry) and (obj in session.deleted or session.is_modified(obj)):
            raise ValueError("Ledger entries are append-only; add a reversal instead")
    job_ids = set()
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, Job) and obj.id is not None:
            job_ids.add(obj.id)
        elif isinstance(obj, (Payment, PhotoReview)) and obj.job_id is not None:
            job_ids.add(obj.job_id)

    for job_id in job_ids:
        sync_job_ledger(session, job_id)
