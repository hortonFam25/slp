from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    external_auth_id = Column(String(100), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    display_name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, server_default="basic", index=True)
    is_active = Column(Boolean, nullable=False, server_default="1", index=True)
    created_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"))
    modified_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"))

    student_access_links = relationship(
        "UserStudentAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserStudentAccess.user_id",
    )

