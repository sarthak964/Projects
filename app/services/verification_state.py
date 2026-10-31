from typing import Literal, TypedDict
from pydantic import BaseModel, Field, model_validator


class ChecklistItemResult(BaseModel):
    item: str = Field(description="The checklist item being evaluated, e.g. 'AC working'")
    addressed: bool = Field(
        description="Whether the reviewer's notes clearly speak to this item at all, "
        "regardless of the outcome. True even if the reviewer reports a problem "
        "(e.g. 'no fire extinguisher found' is addressed=true, passed=false)."
    )
    passed: bool = Field(
        description="Whether the submitted notes report that this item meets the requirement; not independent verification. Only meaningful "
        "when addressed=true; set to false if not addressed."
    )
    photo_observation: str = Field(
        default="",
        description="One sentence describing what is actually visible in the photos "
        "submitted for this item (objects, room, lighting), or 'no photos'. Write this "
        "BEFORE deciding photo_check, and only describe what you can really see.",
    )
    photo_check: Literal["supports", "contradicts", "unclear", "irrelevant", "no_photo"] = Field(
        default="no_photo",
        description="How the photos submitted for this item compare with the reviewer's "
        "claim, based on photo_observation. supports = you can point to something "
        "specific in the photos that shows the item (or the empty spot where a missing "
        "item would be) consistent with the notes. contradicts = photos clearly show "
        "something inconsistent with the notes. unclear = too dark, blurry or "
        "ambiguous to confirm or refute. irrelevant = photos do not show this item or "
        "the area where it would be, including blank, uniform-color, black or "
        "unrecognizable images. no_photo = zero photos were submitted for this item.",
    )
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False, description="Confidence score between 0 and 1")
    reasoning: str = Field(description="Brief reasoning for this judgment")


    @model_validator(mode="after")
    def consistent_pass(self):
        if self.passed and not self.addressed:
            raise ValueError("An unaddressed item cannot pass")
        return self


class VerificationOutput(BaseModel):
    results: list[ChecklistItemResult]


class VerificationState(TypedDict):
    job_id: int
    checklist: list[str]
    # Each photo: {"checklist_item": str, "path": str, "content_type": str}
    photos: list[dict]
    notes: str
    verification_result: list[dict]
    all_addressed: bool
    check_score: float
    summary: str
