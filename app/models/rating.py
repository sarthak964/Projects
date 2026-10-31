from sqlalchemy import Column, Integer, String, ForeignKey

from app.core.database import Base


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    rater_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # who gave the rating
    rated_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # who received it
    score = Column(Integer, nullable=False)      # e.g. 1-5
    comment = Column(String, nullable=True)