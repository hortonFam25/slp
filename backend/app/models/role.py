from sqlalchemy import Boolean, Column, DateTime, func, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, server_default="1", index=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    teacher_roles = relationship("TeacherRole", back_populates="role", cascade="all, delete-orphan")

