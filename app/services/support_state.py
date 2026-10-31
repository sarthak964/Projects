from typing import Literal
from typing import TypedDict
from pydantic import BaseModel, Field


class SupportClassification(BaseModel):
    intent: Literal["faq", "status_check", "dispute", "escalate"] = Field(
        description="What the renter actually needs. 'faq' for a general question "
        "answerable from known policy facts. 'status_check' if they're asking what's "
        "happening with a specific job. 'dispute' if they are complaining that "
        "something on an already-verified/paid job is wrong and want a refund or "
        "similar remedy. 'escalate' for anything else - billing confusion, account "
        "issues, bugs, vague complaints with no clear job, or anything you are not "
        "confident fits the other three categories."
    )
    faq_answer: str | None = Field(
        default=None,
        description="If intent is faq: a direct, friendly answer using ONLY the known "
        "facts provided. Never invent policy details not given to you.",
    )
    dispute_reason: str | None = Field(
        default=None,
        description="If intent is dispute: a clean, one-paragraph restatement of the "
        "renter's complaint, suitable for filing as a formal dispute record.",
    )
    escalation_summary: str | None = Field(
        default=None,
        description="If intent is escalate: a short one-sentence summary of the issue "
        "for a human support agent skimming a queue of tickets.",
    )


class SupportState(TypedDict):
    renter_message: str
    job_id: int | None
    intent: str
    faq_answer: str | None
    dispute_reason: str | None
    escalation_summary: str | None
