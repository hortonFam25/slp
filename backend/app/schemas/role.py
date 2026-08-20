from datetime import datetime

from pydantic import BaseModel, Field


class RoleRead(BaseModel):
    id: int
    name: str = Field(..., description="Role display name")
    is_active: bool
    created_date: datetime
    modified_date: datetime

    class Config:
        from_attributes = True

