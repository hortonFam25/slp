from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AIChatSessionCreate(BaseModel):
    student_id: int | None = None
    title: str | None = Field(default=None, max_length=200)


class AIChatSessionRead(BaseModel):
    id: int
    student_id: int | None = None
    student_alias: str | None = None
    title: str | None = None
    created_date: datetime
    modified_date: datetime

    class Config:
        from_attributes = True


class AIChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class AIChatMessageEditRequest(BaseModel):
    content: str = Field(..., min_length=1)


class AIChatMessageRead(BaseModel):
    id: int
    chat_session_id: int
    role: str
    content: str
    created_date: datetime


class AIChatMessagePairRead(BaseModel):
    user_message: AIChatMessageRead
    assistant_message: AIChatMessageRead


class AISaveProgressNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    note_content: str = Field(..., min_length=1)
    template_version: str = Field(default="v1", max_length=50)
    status: str = Field(default="draft", max_length=50)


class AIUpdateProgressNoteRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note_content: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, max_length=50)


class AISavedProgressNoteRead(BaseModel):
    id: int
    chat_session_id: int | None
    student_id: int
    student_alias: str
    title: str
    note_content: str
    template_version: str
    status: str
    created_date: datetime
    modified_date: datetime

    class Config:
        from_attributes = True

