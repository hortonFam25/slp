"""add_actual_start_end_time_to_therapy_sessions

Revision ID: 3b7c1a2f7d9e
Revises: 9e22557e19e7
Create Date: 2026-01-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b7c1a2f7d9e"
down_revision: Union[str, None] = "9e22557e19e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("therapy_sessions", sa.Column("actual_start_time", sa.DateTime(), nullable=True))
    op.add_column("therapy_sessions", sa.Column("actual_end_time", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("therapy_sessions", "actual_end_time")
    op.drop_column("therapy_sessions", "actual_start_time")


