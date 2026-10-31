from pydantic import BaseModel


class SupportChatRequest(BaseModel):
    message: str
    job_id: int | None = None


class SupportChatResponse(BaseModel):
    intent: str
    reply: str
    dispute_id: int | None = None
    ticket_id: int | None = None
