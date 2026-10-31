from pydantic import ConfigDict, BaseModel


class ReviewerLocationUpdate(BaseModel):
    address: str


class ReviewerProfileOut(BaseModel):
    id: int
    user_id: int
    kyc_status: str
    home_lat: float | None
    home_lng: float | None
    rating_avg: float
    jobs_completed: int
    strikes: int = 0
    suspended: bool = False
    deposit_status: str

    model_config = ConfigDict(from_attributes=True)
