from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, grant_student_access, require_admin
from app.models.student import Student
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class BootstrapUserRequest(BaseModel):
    external_auth_id: str
    email: str | None = None
    display_name: str | None = None
    role: str = "basic"
    grant_all_students: bool = True


@router.get("/me")
def get_me(auth: AuthContext = Depends(get_auth_context)):
    return {
        "user_id": auth.user.id,
        "external_auth_id": auth.user.external_auth_id,
        "email": auth.user.email,
        "display_name": auth.user.display_name,
        "role": auth.user.role,
        "is_authenticated": auth.is_authenticated,
        "access_mode": auth.access_mode,
        "enforce_access": auth.enforce_access,
        "allowed_student_count": len(auth.allowed_student_ids),
        "allowed_student_ids": auth.allowed_student_ids,
    }


@router.post("/users/bootstrap")
def bootstrap_user(
    payload: BootstrapUserRequest,
    db: Session = Depends(get_db),
    admin_auth: AuthContext = Depends(require_admin),
):
    user = db.query(User).filter(User.external_auth_id == payload.external_auth_id).first()
    if user is None:
        user = User(
            external_auth_id=payload.external_auth_id,
            email=payload.email.lower() if payload.email else None,
            display_name=payload.display_name or payload.email or payload.external_auth_id,
            role="admin" if payload.role == "admin" else "basic",
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.email = payload.email.lower() if payload.email else user.email
        user.display_name = payload.display_name or user.display_name
        user.role = "admin" if payload.role == "admin" else "basic"
        user.is_active = True
        db.add(user)
        db.flush()

    if payload.grant_all_students:
        student_ids = [row[0] for row in db.query(Student.id).all()]
        for student_id in student_ids:
            grant_student_access(db, user.id, student_id, granted_by_user_id=admin_auth.user.id)

    db.commit()
    db.refresh(user)
    return {
        "user_id": user.id,
        "external_auth_id": user.external_auth_id,
        "email": user.email,
        "role": user.role,
        "grant_all_students": payload.grant_all_students,
    }


@router.post("/users/{user_id}/grant-all-students")
def grant_all_students_to_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_auth: AuthContext = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    student_ids = [row[0] for row in db.query(Student.id).all()]
    for student_id in student_ids:
        grant_student_access(db, user.id, student_id, granted_by_user_id=admin_auth.user.id)
    db.commit()

    return {"user_id": user.id, "granted_students": len(student_ids)}

