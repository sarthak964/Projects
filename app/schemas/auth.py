import re

from pydantic import BaseModel, field_validator

from app.models.user import UserRole
from app.schemas.user import UserOut


def _normalize_phone(value: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", value)
    if not re.fullmatch(r"\+?\d{10,15}", cleaned):
        raise ValueError("Phone must be 10-15 digits, optionally starting with +")
    return cleaned


class OtpRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class OtpRequestOut(BaseModel):
    message: str
    dev_otp: str | None = None   # only filled in development mode


class OtpVerify(BaseModel):
    phone: str
    code: str
    name: str | None = None                # used only when creating a new account
    role: UserRole | None = None           # required for new accounts (renter or reviewer)

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
