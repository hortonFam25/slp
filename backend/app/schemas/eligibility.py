from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


class EligibilityCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(True)
    display_order: Optional[int] = None


class EligibilityCategoryRead(EligibilityCategoryBase):
    id: int
    created_date: datetime
    modified_date: datetime

    class Config:
        from_attributes = True


class StudentEligibilityBase(BaseModel):
    student_id: int
    eligibility_category_id: int
    start_date: date
    end_date: Optional[date] = None
    is_primary: bool = Field(False)
    notes: Optional[str] = None


class StudentEligibilityRead(StudentEligibilityBase):
    id: int
    created_date: datetime
    modified_date: datetime
    eligibility_category: EligibilityCategoryRead

    @property
    def is_active(self) -> bool:
        """Check if this eligibility is currently active (no end date)"""
        return self.end_date is None

    class Config:
        from_attributes = True


class StudentEligibilityCreate(StudentEligibilityBase):
    pass


class StudentEligibilityUpdate(BaseModel):
    eligibility_category_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None
