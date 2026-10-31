from app.core.time import utcnow
import asyncio
import logging
from datetime import datetime

from app.core.config import SCHEDULER_INTERVAL_SECONDS
from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.photo_review import PhotoReview
from app.services import ledger as ledger_service  # noqa: F401  (keeps ledger recording on for sweeps)
from app.services.job_lifecycle import check_and_expire_job
from app.services import notifications as notification_service  # noqa: F401

# Shown in the uvicorn console.
logger = logging.getLogger("uvicorn.error")

# Jobs in these statuses can be waiting on a deadline.
SWEPT_STATUSES = (
    JobStatus.requested,
    JobStatus.accepted,
    JobStatus.visited,
    JobStatus.needs_reupload,
    JobStatus.verified,
)

# What the admin status endpoint shows.
state = {
    "last_run_at": None,
    "last_checked": 0,
    "last_changed": 0,
    "last_errors": 0,
    "total_sweeps": 0,
    "total_changed": 0,
}


def _snapshot(db, job: Job):
    review = db.query(PhotoReview).filter(PhotoReview.job_id == job.id).first()
    return (job.status, review.status if review else None)


def run_sweep() -> dict:
    """
    One pass over every job that could be waiting on a deadline. Applies whatever
    has expired, using the same logic as the endpoints. Returns counts.
    """
    db = SessionLocal()
    checked = 0
    changed = 0
    errors = 0
    try:
        job_ids = [
            row[0] for row in db.query(Job.id).filter(Job.status.in_(SWEPT_STATUSES)).all()
        ]
        for job_id in job_ids:
            try:
                job = db.get(Job, job_id)
                if job is None:
                    continue
                before = _snapshot(db, job)
                check_and_expire_job(job, db)
                after = _snapshot(db, job)
                checked += 1
                if before != after:
                    changed += 1
                    logger.info("Scheduler: job %s moved %s -> %s", job_id, before, after)
            except Exception:
                errors += 1
                db.rollback()
                logger.exception("Scheduler: failed to process job %s", job_id)
    finally:
        db.close()

    state["last_run_at"] = utcnow()
    state["last_checked"] = checked
    state["last_changed"] = changed
    state["last_errors"] = errors
    state["total_sweeps"] += 1
    state["total_changed"] += changed
    return {"checked": checked, "changed": changed, "errors": errors}


async def scheduler_loop():
    """Runs forever in the background, sweeping every SCHEDULER_INTERVAL_SECONDS."""
    logger.info("Scheduler started, sweeping every %s seconds", SCHEDULER_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.to_thread(run_sweep)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler sweep failed")
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)
