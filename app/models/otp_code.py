from app.core.time import utcnow
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean

from app.core.database import Base


class OtpCode(Base):
    __tablename__ = "otp_codes"

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, index=True, nullable=False)
    code_hash = Column(String, nullable=False)   # never store the raw code
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
