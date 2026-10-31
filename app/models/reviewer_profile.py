from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey

from app.core.database import Base


class ReviewerProfile(Base):
    __tablename__ = "reviewer_profiles"

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    kyc_status = Column(String, default="pending")        # pending / verified / rejected
    kyc_provider_ref = Column(String, nullable=True)       # reference id from KYC provider

    home_lat = Column(Float, nullable=True)
    home_lng = Column(Float, nullable=True)

    rating_avg = Column(Float, default=0.0)
    jobs_completed = Column(Integer, default=0)
    deposit_status = Column(String, default="not_paid")    # not_paid / paid / refunded

    strikes = Column(Integer, default=0)                   # given only after a human decision
    suspended = Column(Boolean, default=False)             # reached the strike limit
