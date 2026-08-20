from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import relationship

from app.db.base import Base


class AISavedProgressNote(Base):
    __tablename__ = "ai_saved_progress_notes"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("ai_chat_sessions.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    student_alias = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    note_content = Column(Text, nullable=False)
    template_version = Column(String(50), nullable=False, server_default="v1")
    status = Column(String(50), nullable=False, server_default="draft", index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"), index=True)
    modified_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"))

    student = relationship("Student")
    user = relationship("User", foreign_keys=[user_id])
    created_by_user = relationship("User", foreign_keys=[created_by])
    session = relationship("AIChatSession", back_populates="saved_progress_notes")

