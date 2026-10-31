from pydantic import ConfigDict, BaseModel, Field


class RatingCreate(BaseModel):
    job_id: int
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class RatingOut(BaseModel):
    id: int
    job_id: int
    rater_id: int
    rated_id: int
    score: int
    comment: str | None

    model_config = ConfigDict(from_attributes=True)
