from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.student import Student
from app.models.user import User
from app.models.user_student_access import UserStudentAccess
# TokenClaims is the shape; WHICH validator produces it (the unverified
# development decoder or the real Entra/JWKS one) is decided in
# app.security.validator, from settings, in that one place. Importing
# validate_jwt from app.security.jwt directly would pin this door to the
# signature-less decoder in production, which is what it used to do.
from app.security.jwt import TokenClaims
from app.security.validator import validate_jwt
from app.settings import settings

logger = logging.getLogger(__name__)
http_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    claims: TokenClaims
    is_authenticated: bool
    is_admin: bool
    access_mode: str
    enforce_access: bool
    allowed_student_ids: list[int]
    effective_user: User

    @property
    def external_auth_id(self) -> str:
        return self.effective_user.external_auth_id


def normalize_access_mode(mode: str | None) -> str:
    normalized = (mode or "monitor").strip().lower()
    if normalized not in {"off", "monitor", "enforce"}:
        return "monitor"
    return normalized


def _safe_email(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    return v or None


def _resolve_email_from_claims(claims: TokenClaims) -> str | None:
    direct_candidates = [
        claims.preferred_username,
        getattr(claims, "email", None),
        getattr(claims, "upn", None),
    ]
    for value in direct_candidates:
        email = _safe_email(value)
        if email:
            return email

    unique_name = _safe_email(getattr(claims, "unique_name", None))
    if not unique_name:
        return None
    # Common Azure format: "provider#user@domain.com"
    if "#" in unique_name:
        possible_email = unique_name.split("#", 1)[1]
        return _safe_email(possible_email)
    return unique_name if "@" in unique_name else None


def _build_fallback_claims() -> TokenClaims:
    return TokenClaims(
        sub=settings.auth_fallback_user_external_id,
        name=settings.auth_fallback_user_name or None,
        preferred_username=settings.auth_fallback_user_email or None,
    )


def _parse_claims(creds: HTTPAuthorizationCredentials | None) -> tuple[TokenClaims, bool]:
    if not creds or creds.scheme.lower() != "bearer":
        if settings.auth_require_bearer:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
        return _build_fallback_claims(), False
    try:
        return validate_jwt(creds.credentials), True
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def _upsert_user(db: Session, claims: TokenClaims) -> User:
    email = _resolve_email_from_claims(claims)
    role = "admin" if email and email in set(settings.access_admin_emails) else "basic"
    display_name = claims.name or email or claims.sub

    user = db.query(User).filter(User.external_auth_id == claims.sub).first()
    if user is None:
        user = User(
            external_auth_id=claims.sub,
            email=email,
            display_name=display_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        changed = False
        if email and user.email != email:
            user.email = email
            changed = True
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if user.role != role:
            user.role = role
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            db.add(user)
            db.flush()
    return user


def grant_full_student_access(db: Session, user: User) -> None:
    student_ids = [row[0] for row in db.query(Student.id).all()]
    if not student_ids:
        return

    existing_links = {
        row.student_id: row
        for row in db.query(UserStudentAccess).filter(UserStudentAccess.user_id == user.id).all()
    }
    for student_id in student_ids:
        found_link = existing_links.get(student_id)
        if found_link is None:
            db.add(
                UserStudentAccess(
                    user_id=user.id,
                    student_id=student_id,
                    granted_by_user_id=user.id,
                    is_active=True,
                )
            )
        elif not found_link.is_active:
            found_link.is_active = True
            db.add(found_link)
    db.flush()


def grant_student_access(db: Session, user_id: int, student_id: int, granted_by_user_id: int | None = None) -> None:
    link = (
        db.query(UserStudentAccess)
        .filter(UserStudentAccess.user_id == user_id, UserStudentAccess.student_id == student_id)
        .first()
    )
    if link is None:
        db.add(
            UserStudentAccess(
                user_id=user_id,
                student_id=student_id,
                granted_by_user_id=granted_by_user_id or user_id,
                is_active=True,
            )
        )
    elif not link.is_active:
        link.is_active = True
        if granted_by_user_id:
            link.granted_by_user_id = granted_by_user_id
        db.add(link)
    db.flush()


def resolve_allowed_student_ids(db: Session, user: User, is_admin: bool) -> list[int]:
    if is_admin:
        return [row[0] for row in db.query(Student.id).all()]

    rows = (
        db.query(UserStudentAccess.student_id)
        .filter(
            UserStudentAccess.user_id == user.id,
            UserStudentAccess.is_active == True,  # noqa: E712
        )
        .all()
    )
    return [row[0] for row in rows]


# Back-compat aliases for the previous private names. Nothing in the tree
# imported them, but keeping them costs one line each and makes this rename
# invisible to anything that did.
_normalize_mode = normalize_access_mode
_grant_full_student_access = grant_full_student_access
_resolve_allowed_student_ids = resolve_allowed_student_ids


def get_auth_context(
    db: Session = Depends(get_db),
    request: Request = None,
    creds: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> AuthContext:
    claims, is_authenticated = _parse_claims(creds)
    mode = normalize_access_mode(settings.access_control_mode)

    user = _upsert_user(db, claims)

    user_email = _safe_email(user.email)
    full_access_users = set(settings.access_full_student_access_emails)
    if user.role == "admin" or (user_email and user_email in full_access_users):
        grant_full_student_access(db, user)

    db.commit()
    db.refresh(user)

    effective_user = user
    acting_as = request.headers.get("x-act-as-user", "").strip() if request is not None else ""
    if acting_as:
        if user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can act as another user")
        target_user = None
        if acting_as.isdigit():
            target_user = db.query(User).filter(User.id == int(acting_as)).first()
        if target_user is None:
            target_user = db.query(User).filter(User.external_auth_id == acting_as).first()
        if target_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
        effective_user = target_user

    allowed_student_ids = resolve_allowed_student_ids(
        db,
        effective_user,
        is_admin=effective_user.role == "admin",
    )

    return AuthContext(
        user=user,
        claims=claims,
        is_authenticated=is_authenticated,
        is_admin=user.role == "admin",
        access_mode=mode,
        enforce_access=mode == "enforce",
        allowed_student_ids=allowed_student_ids,
        effective_user=effective_user,
    )


def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> TokenClaims:
    return auth.claims


def require_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not auth.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return auth


def ensure_student_access(auth: AuthContext, student_id: int, *, action: str = "student access") -> None:
    if auth.access_mode == "off" or auth.is_admin:
        return
    if student_id in auth.allowed_student_ids:
        return
    if auth.access_mode == "monitor":
        logger.warning(
            "Access monitor: user %s would be denied for student %s during %s",
            auth.user.id,
            student_id,
            action,
        )
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient access for this student")


