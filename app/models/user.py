from app.core.time import utcnow
import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    renter = "renter"
    reviewer = "reviewer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime, default=utcnow)