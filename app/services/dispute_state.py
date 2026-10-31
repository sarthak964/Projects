from typing import Literal
from typing import TypedDict
from pydantic import BaseModel, Field


class DisputeAnalysisOutput(BaseModel):
    recommended_outcome: Literal["refund", "uphold"] = Field(
        description="Whether the renter's complaint should result in a refund, "
        "or the original verified report should be upheld and payment stand."
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1 in this recommendation. "
        "Use a LOW score whenever the complaint could plausibly be about something "
        "that was true at inspection time but changed afterward (normal wear, "
        "later damage), or whenever the renter's evidence doesn't clearly "
        "contradict the original reviewer's report."
    )
    reasoning: str = Field(description="Brief reasoning for this recommendation")


class DisputeState(TypedDict):
    job_id: int
    checklist: list[str]
    original_notes: str
    original_verification_result: list[dict]
    renter_reason: str
    renter_evidence_urls: list[str]
    recommended_outcome: str
    confidence: float
    reasoning: str
