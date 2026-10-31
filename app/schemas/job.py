from datetime import datetime
from typing import Annotated

from pydantic import ConfigDict, BaseModel, Field, field_validator

from app.models.job import JobStatus


class JobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    address: str = Field(min_length=1, max_length=500)
    checklist: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=1, max_length=30)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Address must not be blank")
        return value

    @field_validator("checklist")
    @classmethod
    def validate_checklist(cls, values: list[str]) -> list[str]:
        cleaned = []
        seen = set()

        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("Checklist items must not be blank")

            key = item.casefold()
            if key in seen:
                raise ValueError("Checklist items must not contain duplicates")

            seen.add(key)
            cleaned.append(item)

        return cleaned


class JobOut(BaseModel):
    id: int
    renter_id: int
    reviewer_id: int | None
    address: str
    geocoded_lat: float | None
    geocoded_lng: float | None
    checklist_json: list[str] | None
    price: float | None
    status: JobStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpenJobOut(BaseModel):
    id: int
    address: str
    checklist_json: list[str] | None
    distance_km: float
    estimated_price: float
    accept_deadline: datetime | None

    model_config = ConfigDict(from_attributes=True)
