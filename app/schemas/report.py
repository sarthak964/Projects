from datetime import datetime
from pydantic import ConfigDict, BaseModel, Field, field_validator


class ReportCreate(BaseModel):
    # Photos are uploaded beforehand via POST /jobs/{job_id}/photos and are
    # attached to the report automatically.
    model_config = ConfigDict(str_strip_whitespace=True)

    job_id: int = Field(gt=0)
    notes: str = Field(min_length=10, max_length=10000)

    @field_validator("notes")
    @classmethod
    def meaningful_notes(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("Notes must describe the inspection findings, not only punctuation")
        return value


class ReportOut(BaseModel):
    id: int
    job_id: int
    media_urls: list[str] | None
    notes: str | None
    ai_verification_result: dict | list | None
    ai_generated_summary: str | None
    check_score: float | None
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)
