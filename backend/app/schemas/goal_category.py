from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class GoalCategoryBase(BaseModel):
    name: str = Field(..., max_length=50, description="Category name")
    description: Optional[str] = Field(None, max_length=200, description="Category description")
    is_active: bool = Field(True, description="Whether the category is active")


class GoalCategoryCreate(GoalCategoryBase):
    pass


class GoalCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50, description="Category name")
    description: Optional[str] = Field(None, max_length=200, description="Category description")
    is_active: Optional[bool] = Field(None, description="Whether the category is active")


class GoalCategoryRead(GoalCategoryBase):
    id: int
    created_date: datetime

    class Config:
        from_attributes = True