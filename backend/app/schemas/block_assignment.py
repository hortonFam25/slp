from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BlockAssignmentBase(BaseModel):
    time_block_id: int = Field(..., description="Time block being assigned to")
    student_id: int = Field(..., description="Student being assigned")
    status: str = Field("assigned", description="Assignment status (assigned, removed, completed)")
    assignment_date: datetime = Field(..., description="When assignment was made")
    removed_date: Optional[datetime] = Field(None, description="When assignment was removed")


class BlockAssignmentCreate(BaseModel):
    time_block_id: int
    student_id: int
    status: str = "assigned"


class BlockAssignmentUpdate(BaseModel):
    status: Optional[str] = None
    removed_date: Optional[datetime] = None


class BlockAssignmentRead(BlockAssignmentBase):
    id: int
    created_date: datetime
    modified_date: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class BlockAssignmentSummary(BaseModel):
    id: int
    time_block_id: int
    student_id: int
    student_name: str
    status: str
    assignment_date: datetime
    removed_date: Optional[datetime] = None
    duration_display: str

    class Config:
        from_attributes = True


class BlockAssignmentWithDetails(BlockAssignmentRead):
    student_name: str
    time_block_title: str
    time_block_start: datetime
    time_block_end: datetime
    is_active: bool
    duration_display: str

    class Config:
        from_attributes = True
