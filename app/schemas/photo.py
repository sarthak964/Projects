from datetime import datetime
from pydantic import BaseModel


class PhotoOut(BaseModel):
    id: int
    job_id: int
    checklist_item: str
    content_type: str
    size_bytes: int
    created_at: datetime
    round: str = "original"
    url: str   # e.g. /photos/12 (requires login)
