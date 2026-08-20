"""Allow general AI chat sessions without student selection.

Revision ID: 2d3b6ac8f4ce
Revises: 6f0d9ec5a2b1
Create Date: 2026-02-15 22:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2d3b6ac8f4ce"
down_revision: Union[str, None] = "6f0d9ec5a2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "ai_chat_sessions",
        "student_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "ai_chat_sessions",
        "student_alias",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "ai_chat_sessions",
        "student_alias",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        "ai_chat_sessions",
        "student_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
