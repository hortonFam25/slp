from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserStudentAccess(Base):
    __tablename__ = "user_student_access"
    __table_args__ = (
        UniqueConstraint("user_id", "student_id", name="uq_user_student_access_user_student"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="1", index=True)
    created_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"))
    modified_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"))

    user = relationship("User", back_populates="student_access_links", foreign_keys=[user_id])
    student = relationship("Student")

