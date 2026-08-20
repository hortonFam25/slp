from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import relationship

from app.db.base import Base


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("ai_chat_sessions.id"), nullable=False, index=True)
    parent_user_message_id = Column(
        Integer,
        ForeignKey("ai_chat_messages.id"),
        nullable=True,
        index=True,
    )
    role = Column(String(50), nullable=False, index=True)
    model_content = Column(Text, nullable=False)
    ui_content = Column(Text, nullable=False)
    created_date = Column(DateTime, nullable=False, server_default=text("GETDATE()"), index=True)

    session = relationship("AIChatSession", back_populates="messages")
    parent_user_message = relationship("AIChatMessage", remote_side=[id], uselist=False)

