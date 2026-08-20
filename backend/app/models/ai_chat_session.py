from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    student_alias = Column(String(100), nullable=True, index=True)
    title = Column(String(200), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    student = relationship("Student")
    user = relationship("User")
    messages = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")
    saved_progress_notes = relationship("AISavedProgressNote", back_populates="session")

