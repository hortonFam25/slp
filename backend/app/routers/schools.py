from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.dependencies.auth import get_auth_context
from app.repositories.school_repository import SchoolRepository
from app.schemas.school import (
    SchoolCreate,
    SchoolRead,
    SchoolUpdate,
    SchoolSummary,
    SchoolTeacherAssignmentCreate,
    SchoolTeacherAssignmentRead,
    SchoolTeacherAssignmentUpdate
)


router = APIRouter(prefix="/api", tags=["schools"], dependencies=[Depends(get_auth_context)])


@router.get("/schools", response_model=List[SchoolRead])
def list_schools(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    district: Optional[str] = Query(None, description="Filter by district"),
    search: Optional[str] = Query(None, description="Search in name, district, principal, or contact person"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """Get list of schools with optional filters"""
    repo = SchoolRepository(db)
    schools = repo.list_schools(
        is_active=is_active,
        district=district,
        search=search,
        skip=skip,
        limit=limit
    )
    return schools


@router.get("/schools/summary", response_model=List[SchoolSummary])
def get_schools_summary(
    active_only: bool = Query(True, description="Return only active schools"),
    db: Session = Depends(get_db)
):
    """Get lightweight school summary for dropdowns and lists"""
    repo = SchoolRepository(db)
    if active_only:
        return repo.get_active_schools_summary()
    else:
        return repo.list_schools(is_active=None, limit=1000)


@router.get("/schools/{school_id}", response_model=SchoolRead)
def get_school(school_id: int, db: Session = Depends(get_db)):
    """Get a specific school by ID"""
    repo = SchoolRepository(db)
    school = repo.get_school_by_id(school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.post("/schools", response_model=SchoolRead)
def create_school(school: SchoolCreate, db: Session = Depends(get_db)):
    """Create a new school"""
    repo = SchoolRepository(db)
    
    # Check if school with same name already exists
    existing_school = repo.get_school_by_name(school.name)
    if existing_school:
        raise HTTPException(
            status_code=400, 
            detail=f"School with name '{school.name}' already exists"
        )
    
    try:
        school_data = school.dict()
        return repo.create_school(school_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create school: {str(e)}")


@router.put("/schools/{school_id}", response_model=SchoolRead)
def update_school(
    school_id: int, 
    school_data: SchoolUpdate, 
    db: Session = Depends(get_db)
):
    """Update an existing school"""
    repo = SchoolRepository(db)
    
    # Check if school exists
    existing_school = repo.get_school_by_id(school_id)
    if not existing_school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Check for name conflicts (if name is being updated)
    if school_data.name and school_data.name != existing_school.name:
        name_conflict = repo.get_school_by_name(school_data.name)
        if name_conflict:
            raise HTTPException(
                status_code=400,
                detail=f"School with name '{school_data.name}' already exists"
            )
    
    try:
        update_dict = school_data.dict(exclude_unset=True)
        updated_school = repo.update_school(school_id, update_dict)
        if not updated_school:
            raise HTTPException(status_code=404, detail="School not found")
        return updated_school
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update school: {str(e)}")


@router.delete("/schools/{school_id}")
def delete_school(school_id: int, db: Session = Depends(get_db)):
    """Soft delete a school (mark as inactive)"""
    repo = SchoolRepository(db)
    success = repo.delete_school(school_id)
    if not success:
        raise HTTPException(status_code=404, detail="School not found")
    return {"message": "School deactivated successfully"}


@router.get("/schools/district/{district}", response_model=List[SchoolSummary])
def get_schools_by_district(district: str, db: Session = Depends(get_db)):
    """Get all active schools in a specific district"""
    repo = SchoolRepository(db)
    schools = repo.get_schools_by_district(district)
    return schools


@router.get("/schools/{school_id}/statistics")
def get_school_statistics(school_id: int, db: Session = Depends(get_db)):
    """Get detailed statistics for a school"""
    repo = SchoolRepository(db)
    
    # Verify school exists
    school = repo.get_school_by_id(school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    statistics = repo.get_school_statistics(school_id)
    return statistics


@router.get("/districts", response_model=List[str])
def get_districts(db: Session = Depends(get_db)):
    """Get list of all unique districts"""
    from app.models.school import School
    
    # Get distinct districts from active schools
    districts = db.query(School.district).distinct().filter(
        School.district.isnot(None),
        School.is_active == True
    ).all()
    return [district[0] for district in districts if district[0]]
