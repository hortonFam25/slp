from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.access_control import ensure_eligibility_access
from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context
from app.repositories.eligibility_repository import EligibilityRepository
from app.schemas.eligibility import (
    EligibilityCategoryRead,
    StudentEligibilityRead,
    StudentEligibilityCreate,
    StudentEligibilityUpdate
)

router = APIRouter(prefix="/api", tags=["eligibilities"], dependencies=[Depends(get_auth_context)])


@router.get("/eligibilities/categories", response_model=List[EligibilityCategoryRead])
def get_eligibility_categories(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get all eligibility categories"""
    repo = EligibilityRepository(db)
    return repo.get_all_categories(active_only=active_only)


@router.get("/eligibilities/students/{student_id}", response_model=List[StudentEligibilityRead])
def get_student_eligibilities(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all eligibilities for a specific student"""
    ensure_student_access(auth, student_id, action="get student eligibilities")
    repo = EligibilityRepository(db)
    return repo.get_student_eligibilities(student_id)


@router.post("/eligibilities/students", response_model=StudentEligibilityRead)
def create_student_eligibility(
    payload: StudentEligibilityCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new student eligibility"""
    ensure_student_access(auth, payload.student_id, action="create student eligibility")
    repo = EligibilityRepository(db)
    
    # Verify the eligibility category exists
    category = repo.get_category_by_id(payload.eligibility_category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility category not found"
        )
    
    try:
        return repo.create_student_eligibility(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create eligibility: {str(e)}"
        )


@router.put("/eligibilities/students/{eligibility_id}", response_model=StudentEligibilityRead)
def update_student_eligibility(
    eligibility_id: int,
    payload: StudentEligibilityUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an existing student eligibility"""
    ensure_eligibility_access(db, auth, eligibility_id)
    repo = EligibilityRepository(db)
    
    eligibility = repo.update_student_eligibility(eligibility_id, payload)
    if not eligibility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student eligibility not found"
        )
    
    return eligibility


@router.delete("/eligibilities/students/{eligibility_id}")
def delete_student_eligibility(
    eligibility_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a student eligibility"""
    ensure_eligibility_access(db, auth, eligibility_id)
    repo = EligibilityRepository(db)
    
    if not repo.delete_student_eligibility(eligibility_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student eligibility not found"
        )
    
    return {"message": "Student eligibility deleted successfully"}
