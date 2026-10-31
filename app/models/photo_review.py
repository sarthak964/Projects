from app.core.time import utcnow
import enum
from datetime import datetime

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Enum, JSON

from app.core.database import Base


class PhotoReviewStatus(str, enum.Enum):
    approved = "approved"                                  # renter approved the photos
    auto_approved = "auto_approved"                        # review window passed with no reply
    ai_checked_genuine = "ai_checked_genuine"              # AI found the rejected photos genuine; renter decides next
    awaiting_reupload = "awaiting_reupload"                # AI doubted the photos; reviewer may re-upload
    accepted_ai_result = "accepted_ai_result"              # renter accepted the AI's "genuine" verdict
    auto_accepted_ai_result = "auto_accepted_ai_result"    # renter did not reply to the AI's "genuine" verdict
    awaiting_renter_recheck = "awaiting_renter_recheck"    # reviewer re-uploaded; renter looks again
    approved_after_reupload = "approved_after_reupload"    # renter approved the new photos
    auto_approved_after_reupload = "auto_approved_after_reupload"  # renter did not reply to the new photos
    awaiting_human = "awaiting_human"                      # needs a human decision
    resolved_genuine = "resolved_genuine"                  # human: photos are genuine
    resolved_not_genuine = "resolved_not_genuine"          # human: photos are not genuine


class FeeStatus(str, enum.Enum):
    none = "none"
    held = "held"
    kept = "kept"
    refunded = "refunded"


class PhotoReview(Base):
    __tablename__ = "photo_reviews"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)

    status = Column(Enum(PhotoReviewStatus), nullable=False)
    rejected_items = Column(JSON, nullable=True)
    renter_reason = Column(String, nullable=True)

    fee_amount = Column(Float, default=0.0)
    fee_status = Column(Enum(FeeStatus), default=FeeStatus.none)

    # Second fee: paid when the renter disputes the AI's "genuine" verdict and asks for a human.
    human_fee_amount = Column(Float, default=0.0)
    human_fee_status = Column(Enum(FeeStatus), default=FeeStatus.none)

    ai_verdict = Column(JSON, nullable=True)

    ai_result_deadline = Column(DateTime, nullable=True)   # renter must respond to a "genuine" AI verdict by then
    reupload_deadline = Column(DateTime, nullable=True)
    recheck_deadline = Column(DateTime, nullable=True)
    reuploaded_at = Column(DateTime, nullable=True)
    escalation_reason = Column(String, nullable=True)

    human_decision = Column(String, nullable=True)         # "genuine" or "not_genuine"
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision_notes = Column(String, nullable=True)

    # One appeal per case, by whichever side lost the human decision.
    appeal_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    appeal_reason = Column(String, nullable=True)
    appealed_at = Column(DateTime, nullable=True)
    appeal_status = Column(String, nullable=True)          # "pending", "upheld" or "overturned"
    appeal_decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    appeal_notes = Column(String, nullable=True)
    appeal_decided_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    decided_at = Column(DateTime, nullable=True)
