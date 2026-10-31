from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(Session, "before_flush")
def guard_job_changes(session, flush_context, instances):
    # Child-only changes must also compete on the parent job's version.
    # This covers photo review, appeals, reports, uploads and ledger effects.
    from app.models.job import Job, JobStatus
    from app.models.payment import Payment
    from app.models.photo import Photo
    from app.models.photo_review import PhotoReview
    from app.models.report import Report
    from app.models.dispute import Dispute
    from app.models.rating import Rating
    from app.models.ledger import LedgerEntry
    from app.models.reviewer_profile import ReviewerProfile

    job_ids = set()
    candidates = list(session.new) + list(session.dirty) + list(session.deleted)
    for obj in candidates:
        if obj in session.dirty and not session.is_modified(obj):
            continue
        if isinstance(obj, Job) and obj.id is not None and obj not in session.new:
            job_ids.add(obj.id)
        elif isinstance(obj, (Payment, Photo, PhotoReview, Report, Dispute, Rating, LedgerEntry)):
            if obj.job_id is not None:
                job_ids.add(obj.job_id)

    for job_id in sorted(job_ids):
        job = session.get(Job, job_id)
        if job is None or job in session.new or job in session.deleted:
            continue
        old = session.connection().execute(
            Job.__table__.select().where(Job.id == job_id)
        ).mappings().first()
        if old is not None:
            # Count fully paid jobs, undoing the count if a payout is reversed.
            previous = old["reviewer_id"] if old["status"] == JobStatus.paid else None
            current = job.reviewer_id if job.status == JobStatus.paid else None
            if previous != current:
                for reviewer_id, delta in ((previous, -1), (current, 1)):
                    if reviewer_id is not None:
                        profile = session.query(ReviewerProfile).filter_by(user_id=reviewer_id).first()
                        if profile is not None:
                            profile.jobs_completed = max(0, (profile.jobs_completed or 0) + delta)
        job.version_id = (job.version_id or 1) + 1


def get_db():
    db = SessionLocal()
    try:
        yield db
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This record changed during your request. Refresh it before trying again.",
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This request conflicts with an existing record. Refresh before trying again.",
        ) from None
    except OperationalError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
        if (code & 255) in (5, 6):
            raise HTTPException(
                status_code=503,
                detail="The database is busy. Please retry shortly.",
                headers={"Retry-After": "1"},
            ) from None
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
