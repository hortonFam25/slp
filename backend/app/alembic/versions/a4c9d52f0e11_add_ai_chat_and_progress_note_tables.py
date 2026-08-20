"""Add AI chat and progress note tables

Revision ID: a4c9d52f0e11
Revises: 3b7c1a2f7d9e
Create Date: 2026-02-15 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4c9d52f0e11"
down_revision: Union[str, None] = "3b7c1a2f7d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("student_alias", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_date", sa.DateTime(), server_default=sa.text("GETDATE()"), nullable=False),
        sa.Column("modified_date", sa.DateTime(), server_default=sa.text("GETDATE()"), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_sessions_id"), "ai_chat_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_user_id"), "ai_chat_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_student_id"), "ai_chat_sessions", ["student_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_student_alias"), "ai_chat_sessions", ["student_alias"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_created_date"), "ai_chat_sessions", ["created_date"], unique=False)

    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("model_content", sa.Text(), nullable=False),
        sa.Column("ui_content", sa.Text(), nullable=False),
        sa.Column("created_date", sa.DateTime(), server_default=sa.text("GETDATE()"), nullable=False),
        sa.ForeignKeyConstraint(["chat_session_id"], ["ai_chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_messages_id"), "ai_chat_messages", ["id"], unique=False)
    op.create_index(op.f("ix_ai_chat_messages_chat_session_id"), "ai_chat_messages", ["chat_session_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_messages_role"), "ai_chat_messages", ["role"], unique=False)
    op.create_index(op.f("ix_ai_chat_messages_created_date"), "ai_chat_messages", ["created_date"], unique=False)

    op.create_table(
        "ai_saved_progress_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_session_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("student_alias", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("note_content", sa.Text(), nullable=False),
        sa.Column("template_version", sa.String(length=50), server_default="v1", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_date", sa.DateTime(), server_default=sa.text("GETDATE()"), nullable=False),
        sa.Column("modified_date", sa.DateTime(), server_default=sa.text("GETDATE()"), nullable=False),
        sa.ForeignKeyConstraint(["chat_session_id"], ["ai_chat_sessions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_saved_progress_notes_id"), "ai_saved_progress_notes", ["id"], unique=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_chat_session_id"), "ai_saved_progress_notes", ["chat_session_id"], unique=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_user_id"), "ai_saved_progress_notes", ["user_id"], unique=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_student_id"), "ai_saved_progress_notes", ["student_id"], unique=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_student_alias"), "ai_saved_progress_notes", ["student_alias"], unique=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_status"), "ai_saved_progress_notes", ["status"], unique=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_created_date"), "ai_saved_progress_notes", ["created_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_saved_progress_notes_created_date"), table_name="ai_saved_progress_notes")
    op.drop_index(op.f("ix_ai_saved_progress_notes_status"), table_name="ai_saved_progress_notes")
    op.drop_index(op.f("ix_ai_saved_progress_notes_student_alias"), table_name="ai_saved_progress_notes")
    op.drop_index(op.f("ix_ai_saved_progress_notes_student_id"), table_name="ai_saved_progress_notes")
    op.drop_index(op.f("ix_ai_saved_progress_notes_user_id"), table_name="ai_saved_progress_notes")
    op.drop_index(op.f("ix_ai_saved_progress_notes_chat_session_id"), table_name="ai_saved_progress_notes")
    op.drop_index(op.f("ix_ai_saved_progress_notes_id"), table_name="ai_saved_progress_notes")
    op.drop_table("ai_saved_progress_notes")

    op.drop_index(op.f("ix_ai_chat_messages_created_date"), table_name="ai_chat_messages")
    op.drop_index(op.f("ix_ai_chat_messages_role"), table_name="ai_chat_messages")
    op.drop_index(op.f("ix_ai_chat_messages_chat_session_id"), table_name="ai_chat_messages")
    op.drop_index(op.f("ix_ai_chat_messages_id"), table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")

    op.drop_index(op.f("ix_ai_chat_sessions_created_date"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_student_alias"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_student_id"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_user_id"), table_name="ai_chat_sessions")
    op.drop_index(op.f("ix_ai_chat_sessions_id"), table_name="ai_chat_sessions")
    op.drop_table("ai_chat_sessions")

