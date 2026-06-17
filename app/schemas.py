from datetime import datetime

from pydantic import BaseModel


class FollowTaskRead(BaseModel):
    id: int
    task_type: str
    priority: str
    reason: str
    suggested_action: str
    status: str
    ai_message: str | None = None
    result: str | None = None

    model_config = {"from_attributes": True}


class CustomerRead(BaseModel):
    id: int
    name: str
    phone: str | None = None
    last_visit_time: datetime | None = None

    model_config = {"from_attributes": True}
