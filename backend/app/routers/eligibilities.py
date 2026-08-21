"""Eligibility categories, and one child's determinations under them.

NOTHING HERE DELETES. `DELETE /api/eligibilities/students/{id}` archives --
same verb, same path, same 404 -- and returns the `archiveEventId` that puts
the row back. See `app/services/archive.py`; the routers either side of this
one made the same swap.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services import archive as archive_service

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
    include_archived: bool = Query(
        False, description="Include eligibilities that have been archived"
    ),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all eligibilities for a specific student.

    Archived determinations are hidden by default. `include_archived=true` is
    the archive view -- what was on the record and is not any more.
    """
    ensure_student_access(auth, student_id, action="get student eligibilities")
    repo = EligibilityRepository(db)
    return repo.get_student_eligibilities(student_id, include_archived=include_archived)


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
    reason: Optional[str] = Query(
        None, description="Why the eligibility is being archived"
    ),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive a student eligibility. NOTHING IS DELETED.

    Same verb, same path, and the same success message the React app already
    reads -- because this route used to destroy the row and the app was written
    against that. What changed is underneath: the determination is stamped with
    one archive event and hidden, and
    `POST /api/archive/events/{archiveEventId}/restore` puts it back.

    An eligibility determination is a legal finding about a child. Removing it
    outright made "this was taken off the record on the 4th" and "this never
    happened" the same fact, which is precisely the pair an IEP audit has to be
    able to tell apart.
    """
    ensure_eligibility_access(db, auth, eligibility_id)
    repo = EligibilityRepository(db)

    try:
        event = repo.archive_student_eligibility(
            eligibility_id, user_id=auth.effective_user.id, reason=reason
        )
    except archive_service.AlreadyArchivedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student eligibility not found"
        )

    return {
        "message": "Student eligibility deleted successfully",
        "archived": True,
        "archiveEventId": event.id,
    }
