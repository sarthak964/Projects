"""Create notifications in the transaction that records each lifecycle change."""
from datetime import timedelta

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import APPEAL_WINDOW_HOURS, PHOTO_REVIEW_WINDOW_HOURS
from app.models.job import Job
from app.models.notification import Notification
from app.models.photo_review import PhotoReview
from app.models.user import User, UserRole

_PENDING = "trustay_notification_events"

# Each pair contains the renter's and the assigned reviewer's messages.
_JOBS = {
    "requested": ("Inspection requested", "Your inspection request is waiting for a reviewer.", None),
    "accepted": ("Reviewer assigned", "A reviewer accepted your inspection.", "You accepted this inspection. Visit and submit your report before the deadline."),
    "visited": ("Visit recorded", "The reviewer recorded the property visit.", "Upload photos for each checklist item and submit your notes."),
    "report_submitted": ("Report submitted", "The inspection report is awaiting notes verification.", "Your report was submitted and is awaiting notes verification."),
    "verified": ("Photos ready for review", "Review the inspection photos before the deadline. Silence can release payment automatically.", "The notes check is complete. The renter can now review your photos."),
    "needs_reupload": ("Report needs more detail", "The reviewer needs to complete the inspection report.", "Add the missing checklist details and resubmit your report before the deadline."),
    "paid": ("Payment released", "The inspection payment has been released to the reviewer.", "Your inspection payment has been released, after commission."),
    "expired": ("Inspection expired", "This inspection expired. Any held job payment has been refunded.", "This inspection expired. Check the job for its final status."),
    "disputed": ("Dispute opened", "A dispute is open for this inspection.", "A dispute is open for this inspection. Check the case details."),
    "refunded": ("Inspection refunded", "The inspection payment has been refunded.", "The inspection payment was refunded to the renter. Check the decision details."),
}

_REVIEWS = {
    "approved": ("Photos approved", "You approved the photos and payment was released.", "The renter approved your photos and payment was released."),
    "auto_approved": ("Photos automatically approved", "The photo-review deadline passed and payment was released.", "The photo-review deadline passed and your payment was released."),
    "ai_checked_genuine": ("Photo check result ready", "The AI check supports the photos. Accept the result or request human review before the deadline.", "The AI check supports your photos. The renter has a response window."),
    "awaiting_reupload": ("New photos requested", "The reviewer has been asked to upload new photos for the rejected items.", "Upload new photos for the rejected checklist items and mark the re-upload complete before the deadline."),
    "accepted_ai_result": ("Photo check result accepted", "You accepted the AI result. The check fee was kept and payment was released.", "The renter accepted the AI result and your payment was released."),
    "auto_accepted_ai_result": ("Photo check result automatically accepted", "The response deadline passed. The check fee was kept and payment was released.", "The renter's response deadline passed and your payment was released."),
    "awaiting_renter_recheck": ("New photos ready for review", "Review the replacement photos before the deadline.", "Your replacement photos are ready for the renter to review."),
    "approved_after_reupload": ("Replacement photos approved", "You approved the replacement photos. The check fee was refunded and payment was released.", "The renter approved your replacement photos and payment was released."),
    "auto_approved_after_reupload": ("Replacement photos automatically approved", "The recheck deadline passed. The check fee was refunded and payment was released.", "The recheck deadline passed and your payment was released."),
    "awaiting_human": ("Human review requested", "Your photo-review case is waiting for a human decision. Money remains held.", "This photo-review case is waiting for a human decision. No strike is applied before that decision."),
    "resolved_genuine": ("Photos accepted by human review", "A human accepted the photos. Open the case for the payment outcome and appeal options.", "A human accepted your photos. Open the case for the payment outcome."),
    "resolved_not_genuine": ("Photos rejected by human review", "A human rejected the photos. Open the case for the refund outcome.", "A human rejected your photos. Open the case for the outcome and appeal options."),
}

_APPEALS = {
    "pending": ("Appeal submitted", "An appeal is waiting for an admin decision."),
    "upheld": ("Appeal decision: upheld", "The original decision was upheld. Open the case for the outcome."),
    "overturned": ("Appeal decision: overturned", "The original decision was overturned. Open the case for the updated outcome."),
}


def _value(value):
    return value.value if hasattr(value, "value") else value


def _stored(session, obj):
    if obj in session.new or obj.id is None:
        return None
    table = obj.__table__
    return session.connection().execute(table.select().where(table.c.id == obj.id)).mappings().first()


def _job_for(session, job_id):
    for obj in session.new:
        if isinstance(obj, Job) and obj.id == job_id:
            return obj
    return session.get(Job, job_id)


@event.listens_for(Session, "before_flush")
def _collect_notifications(session, flush_context, instances):
    jobs = []
    reviews = []
    appeals = []
    candidates = list(session.new) + list(session.dirty)
    for obj in candidates:
        if not isinstance(obj, (Job, PhotoReview)):
            continue
        old = _stored(session, obj)
        if isinstance(obj, Job):
            # SQLAlchemy assigns the default status during the flush.
            status = _value(obj.status) or "requested"
            if old is None or _value(old["status"]) != status:
                jobs.append((obj, "job", status, None))
        else:
            job = _job_for(session, obj.job_id)
            if job is None:
                continue
            appeal = obj.appeal_status
            appeal_changed = appeal is not None and (old is None or old["appeal_status"] != appeal)
            if appeal_changed:
                appeals.append((job, "appeal", appeal, obj))
            status = _value(obj.status)
            if not appeal_changed and (old is None or _value(old["status"]) != status):
                reviews.append((job, "photo_review", status, obj))

    # A single approval/decision should not also generate a generic paid/refund alert.
    specific = {id(job) for job, kind, status, review in reviews + appeals}
    jobs = [row for row in jobs if id(row[0]) not in specific]
    if jobs or reviews or appeals:
        session.info.setdefault(_PENDING, []).extend(jobs + reviews + appeals)


def _deadline(job, kind, status, review):
    if kind == "job":
        if status in ("accepted", "visited", "needs_reupload"):
            return job.submit_deadline
        if status == "verified" and job.verified_at is not None:
            return job.verified_at + timedelta(hours=PHOTO_REVIEW_WINDOW_HOURS)
    elif kind == "photo_review":
        field = {
            "ai_checked_genuine": "ai_result_deadline",
            "awaiting_reupload": "reupload_deadline",
            "awaiting_renter_recheck": "recheck_deadline",
        }.get(status)
        if field:
            return getattr(review, field)
        if status in ("resolved_genuine", "resolved_not_genuine") and review.decided_at:
            return review.decided_at + timedelta(hours=APPEAL_WINDOW_HOURS)
    return None


@event.listens_for(Session, "after_flush_postexec")
def _write_notifications(session, flush_context):
    pending = session.info.pop(_PENDING, [])
    for job, kind, status, review in pending:
        mapping = _JOBS if kind == "job" else _REVIEWS if kind == "photo_review" else _APPEALS
        content = mapping.get(status)
        if content is None:
            continue
        title, renter_message = content[:2]
        reviewer_message = content[2] if len(content) > 2 else renter_message
        recipients = {job.renter_id: (title, renter_message)}
        if job.reviewer_id is not None and reviewer_message is not None:
            recipients[job.reviewer_id] = (title, reviewer_message)
        needs_admin = (kind == "photo_review" and status == "awaiting_human") or (kind == "appeal" and status == "pending")
        if needs_admin:
            admin_title = "Photo review needs a decision" if kind == "photo_review" else "Appeal needs a decision"
            for admin in session.query(User).filter(User.role == UserRole.admin).all():
                recipients[admin.id] = (admin_title, "A case is waiting in your admin queue.")
        for user_id, (recipient_title, message) in recipients.items():
            if user_id is None:
                continue
            key = f"job:{job.id}:v{job.version_id}:{kind}:{status}:user:{user_id}"
            session.add(Notification(
                user_id=user_id,
                job_id=job.id,
                event_key=key,
                event_type=f"{kind}.{status}",
                title=recipient_title,
                message=message,
                deadline_at=_deadline(job, kind, status, review),
            ))


@event.listens_for(Session, "after_soft_rollback")
def _clear_pending_notifications(session, previous_transaction):
    session.info.pop(_PENDING, None)
