from datetime import datetime
from pydantic import ConfigDict, BaseModel
from app.models.user import UserRole


class UserCreate(BaseModel):
    phone: str
    name: str | None = None
    role: UserRole


class UserOut(BaseModel):
    id: int
    phone: str
    name: str | None
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)