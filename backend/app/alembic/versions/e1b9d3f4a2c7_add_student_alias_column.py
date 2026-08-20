"""Add persistent student alias column.

Revision ID: e1b9d3f4a2c7
Revises: c7a6f0d1b2e3
Create Date: 2026-02-17 10:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1b9d3f4a2c7"
down_revision: Union[str, None] = "c7a6f0d1b2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("student_alias", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE students
            SET student_alias = 'student_' + CAST(id AS VARCHAR(50))
            WHERE student_alias IS NULL OR student_alias = ''
            """
        )
    )

    op.alter_column("students", "student_alias", existing_type=sa.String(length=64), nullable=False)
    op.create_index(op.f("ix_students_student_alias"), "students", ["student_alias"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_students_student_alias"), table_name="students")
    op.drop_column("students", "student_alias")
