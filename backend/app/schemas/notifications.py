from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    read: bool
    created_at: str


class NotificationList(BaseModel):
    items: list[NotificationOut] = Field(default_factory=list)
    unread: int = 0
