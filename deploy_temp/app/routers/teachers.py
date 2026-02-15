from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.repositories.teacher_repository import TeacherRepository
from app.schemas.teacher import (
    TeacherCreate,
    TeacherRead,
    TeacherUpdate,
    TeacherSummary,
    StudentTeacherAssignmentCreate,
    StudentTeacherAssignmentRead,
    StudentTeacherAssignmentUpdate
)
from app.schemas.school import (
    SchoolTeacherAssignmentCreate,
    SchoolTeacherAssignmentRead,
    SchoolTeacherAssignmentUpdate
)


router = APIRouter(prefix="/api", tags=["teachers"])


@router.get("/teachers", response_model=List[TeacherRead])
def list_teachers(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    school_id: Optional[int] = Query(None, description="Filter by current school assignment"),
    department: Optional[str] = Query(None, description="Filter by department"),
    search: Optional[str] = Query(None, description="Search in name, email, title, or department"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """Get list of teachers with optional filters"""
    repo = TeacherRepository(db)
    teachers = repo.list_teachers(
        is_active=is_active,
        school_id=school_id,
        department=department,
        search=search,
        skip=skip,
        limit=limit
    )
    return teachers


@router.get("/teachers/summary", response_model=List[TeacherSummary])
def get_teachers_summary(
    active_only: bool = Query(True, description="Return only active teachers"),
    school_id: Optional[int] = Query(None, description="Filter by school"),
    db: Session = Depends(get_db)
):
    """Get lightweight teacher summary for dropdowns and lists"""
    repo = TeacherRepository(db)
    if school_id:
        return repo.get_teachers_by_school(school_id, current_only=True)
    elif active_only:
        return repo.get_active_teachers_summary()
    else:
        return repo.list_teachers(is_active=None, limit=1000)


@router.get("/teachers/{teacher_id}", response_model=TeacherRead)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    """Get a specific teacher by ID"""
    repo = TeacherRepository(db)
    teacher = repo.get_teacher_by_id(teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher


@router.post("/teachers", response_model=TeacherRead)
def create_teacher(teacher: TeacherCreate, db: Session = Depends(get_db)):
    """Create a new teacher"""
    repo = TeacherRepository(db)
    
    # Check if teacher with same email already exists
    if teacher.email:
        existing_teacher = repo.get_teacher_by_email(teacher.email)
        if existing_teacher:
            raise HTTPException(
                status_code=400, 
                detail=f"Teacher with email '{teacher.email}' already exists"
            )
    
    try:
        teacher_data = teacher.dict()
        return repo.create_teacher(teacher_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create teacher: {str(e)}")


@router.put("/teachers/{teacher_id}", response_model=TeacherRead)
def update_teacher(
    teacher_id: int, 
    teacher_data: TeacherUpdate, 
    db: Session = Depends(get_db)
):
    """Update an existing teacher"""
    repo = TeacherRepository(db)
    
    # Check if teacher exists
    existing_teacher = repo.get_teacher_by_id(teacher_id)
    if not existing_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Check for email conflicts (if email is being updated)
    if teacher_data.email and teacher_data.email != existing_teacher.email:
        email_conflict = repo.get_teacher_by_email(teacher_data.email)
        if email_conflict:
            raise HTTPException(
                status_code=400,
                detail=f"Teacher with email '{teacher_data.email}' already exists"
            )
    
    try:
        update_dict = teacher_data.dict(exclude_unset=True)
        updated_teacher = repo.update_teacher(teacher_id, update_dict)
        if not updated_teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        return updated_teacher
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update teacher: {str(e)}")


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    """Soft delete a teacher (mark as inactive)"""
    repo = TeacherRepository(db)
    success = repo.delete_teacher(teacher_id)
    if not success:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return {"message": "Teacher deactivated successfully"}


@router.get("/schools/{school_id}/teachers", response_model=List[TeacherSummary])
def get_teachers_by_school(
    school_id: int, 
    current_only: bool = Query(True, description="Return only current assignments"),
    db: Session = Depends(get_db)
):
    """Get all teachers assigned to a specific school"""
    repo = TeacherRepository(db)
    teachers = repo.get_teachers_by_school(school_id, current_only=current_only)
    return teachers


@router.get("/teachers/{teacher_id}/statistics")
def get_teacher_statistics(teacher_id: int, db: Session = Depends(get_db)):
    """Get detailed statistics for a teacher"""
    repo = TeacherRepository(db)
    
    # Verify teacher exists
    teacher = repo.get_teacher_by_id(teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    statistics = repo.get_teacher_statistics(teacher_id)
    return statistics


# Teacher-School Assignment Endpoints
@router.get("/teachers/{teacher_id}/school-assignments", response_model=List[SchoolTeacherAssignmentRead])
def get_teacher_school_assignments(
    teacher_id: int,
    db: Session = Depends(get_db)
):
    """Get all school assignments for a teacher"""
    repo = TeacherRepository(db)
    
    # Verify teacher exists
    teacher = repo.get_teacher_by_id(teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    try:
        assignments = repo.get_teacher_school_assignments(teacher_id)
        return assignments
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get assignments: {str(e)}")


@router.post("/teacher-school-assignments", response_model=SchoolTeacherAssignmentRead)
def create_teacher_school_assignment(
    assignment: SchoolTeacherAssignmentCreate, 
    db: Session = Depends(get_db)
):
    """Assign a teacher to a school"""
    repo = TeacherRepository(db)
    
    try:
        assignment_data = assignment.dict()
        return repo.assign_teacher_to_school(assignment_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create assignment: {str(e)}")


@router.put("/teacher-school-assignments/{assignment_id}", response_model=SchoolTeacherAssignmentRead)
def update_teacher_school_assignment(
    assignment_id: int,
    assignment: SchoolTeacherAssignmentUpdate,
    db: Session = Depends(get_db)
):
    """Update a teacher-school assignment"""
    repo = TeacherRepository(db)
    
    try:
        assignment_data = assignment.dict(exclude_unset=True)
        updated_assignment = repo.update_teacher_school_assignment(assignment_id, assignment_data)
        if not updated_assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return updated_assignment
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update assignment: {str(e)}")


@router.delete("/teacher-school-assignments/{assignment_id}")
def delete_teacher_school_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """Delete a teacher-school assignment"""
    repo = TeacherRepository(db)
    
    success = repo.delete_teacher_school_assignment(assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"message": "Teacher-school assignment deleted successfully"}


@router.put("/teacher-school-assignments/{assignment_id}/end")
def end_teacher_school_assignment(
    assignment_id: int,
    end_date: date = Query(..., description="Assignment end date"),
    db: Session = Depends(get_db)
):
    """End a teacher-school assignment"""
    repo = TeacherRepository(db)
    success = repo.end_teacher_school_assignment(assignment_id, end_date)
    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"message": "Teacher-school assignment ended successfully"}


# Student-Teacher Assignment Endpoints
@router.post("/student-teacher-assignments", response_model=StudentTeacherAssignmentRead)
def create_student_teacher_assignment(
    assignment: StudentTeacherAssignmentCreate, 
    db: Session = Depends(get_db)
):
    """Assign a student to a teacher"""
    repo = TeacherRepository(db)
    
    try:
        assignment_data = assignment.dict()
        return repo.assign_student_to_teacher(assignment_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create assignment: {str(e)}")


@router.put("/student-teacher-assignments/{assignment_id}/end")
def end_student_teacher_assignment(
    assignment_id: int,
    end_date: date = Query(..., description="Assignment end date"),
    db: Session = Depends(get_db)
):
    """End a student-teacher assignment"""
    repo = TeacherRepository(db)
    success = repo.end_student_teacher_assignment(assignment_id, end_date)
    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"message": "Student-teacher assignment ended successfully"}


@router.get("/departments", response_model=List[str])
def get_departments(db: Session = Depends(get_db)):
    """Get list of all unique departments"""
    from app.models.teacher import Teacher
    
    # Get distinct departments from active teachers
    departments = db.query(Teacher.department).distinct().filter(
        Teacher.department.isnot(None),
        Teacher.is_active == True
    ).all()
    return [dept[0] for dept in departments if dept[0]]
