from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import relationship

from app.db.base import Base


class TeacherRole(Base):
    __tablename__ = "teacher_roles"
    __table_args__ = (UniqueConstraint("teacher_id", "role_id", name="uq_teacher_roles_teacher_role"),)

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    created_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"))

    teacher = relationship("Teacher", back_populates="teacher_roles")
    role = relationship("Role", back_populates="teacher_roles")

