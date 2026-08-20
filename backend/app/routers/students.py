from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context, grant_student_access
from app.repositories.student_repository import StudentRepository
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate, StudentSummary


router = APIRouter(prefix="/api/students", tags=["students"])


def _should_mask_student_names(auth: AuthContext) -> bool:
    return auth.is_admin or auth.user.id != auth.effective_user.id


def _student_alias(student) -> str:
    return getattr(student, "student_alias", None) or f"student_{student.id}"


def _masked_student_summary(student) -> StudentSummary:
    base = StudentSummary.model_validate(student)
    return base.model_copy(update={"first": _student_alias(student), "last": ""})


def _masked_student_read(student) -> StudentRead:
    base = StudentRead.model_validate(student)
    return base.model_copy(update={"first": _student_alias(student), "last": ""})


@router.get("/", response_model=List[StudentSummary])
@router.get("", response_model=List[StudentSummary])  # Handle both with and without trailing slash
def list_students(
    enrollment_status: Optional[str] = Query(None, description="Filter by enrollment status"),
    case_manager: Optional[str] = Query(None, description="Filter by case manager"),
    include_archived: bool = Query(False, description="Include archived students in results"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """List students with optional filtering"""
    repo = StudentRepository(db)
    
    allowed_student_ids = auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None
    if case_manager:
        students = repo.get_students_by_case_manager(
            case_manager,
            include_archived=include_archived,
            allowed_student_ids=allowed_student_ids,
        )
    else:
        students = repo.list_students(
            enrollment_status=enrollment_status,
            include_archived=include_archived,
            allowed_student_ids=allowed_student_ids,
        )
    if _should_mask_student_names(auth):
        return [_masked_student_summary(student) for student in students]
    return students


@router.get("/archived", response_model=List[StudentSummary])
def get_archived_students(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all archived students"""
    repo = StudentRepository(db)
    allowed_student_ids = auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None
    students = repo.get_archived_students(allowed_student_ids=allowed_student_ids)
    if _should_mask_student_names(auth):
        return [_masked_student_summary(student) for student in students]
    return students


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific student by ID"""
    repo = StudentRepository(db)
    student = repo.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    ensure_student_access(auth, student.id, action="read student")
    
    if _should_mask_student_names(auth):
        return _masked_student_read(student)
    return student


@router.post("/", response_model=StudentRead)
@router.post("", response_model=StudentRead)  # Handle both with and without trailing slash
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new student"""
    repo = StudentRepository(db)
    
    # Check if UIC already exists (if provided)
    if payload.uic:
        existing = repo.get_student_by_uic(payload.uic)
        if existing:
            raise HTTPException(status_code=400, detail="UIC already exists")
    
    student = repo.create_student(payload)
    # Ensure creator keeps access to newly created student.
    grant_student_access(db, auth.user.id, student.id, granted_by_user_id=auth.user.id)
    db.commit()
    if _should_mask_student_names(auth):
        return _masked_student_read(student)
    return student


@router.put("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an existing student"""
    repo = StudentRepository(db)
    
    # Check if UIC conflicts (if being updated)
    if payload.uic:
        existing = repo.get_student_by_uic(payload.uic)
        if existing and existing.id != student_id:
            raise HTTPException(status_code=400, detail="UIC already exists")
    
    ensure_student_access(auth, student_id, action="update student")
    allowed_student_ids = auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None
    student = repo.update_student(student_id, payload, allowed_student_ids=allowed_student_ids)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if _should_mask_student_names(auth):
        return _masked_student_read(student)
    return student


@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a student (permanent removal)"""
    repo = StudentRepository(db)
    ensure_student_access(auth, student_id, action="delete student")
    allowed_student_ids = auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None
    success = repo.delete_student(student_id, allowed_student_ids=allowed_student_ids)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}


@router.put("/{student_id}/archive", response_model=StudentRead)
def archive_student(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive a student (hide from active lists but preserve data)"""
    repo = StudentRepository(db)
    
    ensure_student_access(auth, student_id, action="archive student")
    allowed_student_ids = auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None
    student = repo.archive_student(student_id, allowed_student_ids=allowed_student_ids)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if _should_mask_student_names(auth):
        return _masked_student_read(student)
    return student


@router.put("/{student_id}/unarchive", response_model=StudentRead)
def unarchive_student(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Unarchive a student (restore to active lists)"""
    repo = StudentRepository(db)
    
    ensure_student_access(auth, student_id, action="unarchive student")
    allowed_student_ids = auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None
    student = repo.unarchive_student(student_id, allowed_student_ids=allowed_student_ids)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if _should_mask_student_names(auth):
        return _masked_student_read(student)
    return student


@router.get("/uic/{uic}", response_model=StudentRead)
def get_student_by_uic(
    uic: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a student by their UIC (for legacy system integration)"""
    repo = StudentRepository(db)
    student = repo.get_student_by_uic(uic)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    ensure_student_access(auth, student.id, action="read student by uic")
    if _should_mask_student_names(auth):
        return _masked_student_read(student)
    return student


