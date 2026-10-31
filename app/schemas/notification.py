from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    event_type: str
    title: str
    message: str
    deadline_at: datetime | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    total: int
    limit: int
    offset: int


class UnreadCount(BaseModel):
    unread_count: int


class MarkAllReadOut(BaseModel):
    marked_read: int
