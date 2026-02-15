from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.repositories.student_repository import StudentRepository
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate, StudentSummary


router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("/", response_model=List[StudentSummary])
@router.get("", response_model=List[StudentSummary])  # Handle both with and without trailing slash
def list_students(
    enrollment_status: Optional[str] = Query(None, description="Filter by enrollment status"),
    case_manager: Optional[str] = Query(None, description="Filter by case manager"),
    include_archived: bool = Query(False, description="Include archived students in results"),
    db: Session = Depends(get_db)
):
    """List students with optional filtering"""
    repo = StudentRepository(db)
    
    if case_manager:
        return repo.get_students_by_case_manager(case_manager, include_archived=include_archived)
    else:
        return repo.list_students(enrollment_status=enrollment_status, include_archived=include_archived)


@router.get("/archived", response_model=List[StudentSummary])
def get_archived_students(db: Session = Depends(get_db)):
    """Get all archived students"""
    repo = StudentRepository(db)
    return repo.get_archived_students()


@router.get("/{student_id}", response_model=StudentRead)
def get_student(student_id: int, db: Session = Depends(get_db)):
    """Get a specific student by ID"""
    repo = StudentRepository(db)
    student = repo.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return student


@router.post("/", response_model=StudentRead)
@router.post("", response_model=StudentRead)  # Handle both with and without trailing slash
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    """Create a new student"""
    repo = StudentRepository(db)
    
    # Check if UIC already exists (if provided)
    if payload.uic:
        existing = repo.get_student_by_uic(payload.uic)
        if existing:
            raise HTTPException(status_code=400, detail="UIC already exists")
    
    return repo.create_student(payload)


@router.put("/{student_id}", response_model=StudentRead)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    """Update an existing student"""
    repo = StudentRepository(db)
    
    # Check if UIC conflicts (if being updated)
    if payload.uic:
        existing = repo.get_student_by_uic(payload.uic)
        if existing and existing.id != student_id:
            raise HTTPException(status_code=400, detail="UIC already exists")
    
    student = repo.update_student(student_id, payload)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    """Delete a student (permanent removal)"""
    repo = StudentRepository(db)
    success = repo.delete_student(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}


@router.put("/{student_id}/archive", response_model=StudentRead)
def archive_student(student_id: int, db: Session = Depends(get_db)):
    """Archive a student (hide from active lists but preserve data)"""
    repo = StudentRepository(db)
    
    student = repo.archive_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return student


@router.put("/{student_id}/unarchive", response_model=StudentRead)
def unarchive_student(student_id: int, db: Session = Depends(get_db)):
    """Unarchive a student (restore to active lists)"""
    repo = StudentRepository(db)
    
    student = repo.unarchive_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return student


@router.get("/uic/{uic}", response_model=StudentRead)
def get_student_by_uic(uic: str, db: Session = Depends(get_db)):
    """Get a student by their UIC (for legacy system integration)"""
    repo = StudentRepository(db)
    student = repo.get_student_by_uic(uic)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


