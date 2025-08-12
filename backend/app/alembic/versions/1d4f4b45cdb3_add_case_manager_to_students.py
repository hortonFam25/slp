"""add_case_manager_to_students

Revision ID: 1d4f4b45cdb3
Revises: eb62478a29e0
Create Date: 2025-08-08 21:48:44.528694

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d4f4b45cdb3'
down_revision: Union[str, None] = 'eb62478a29e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add case_manager field to students table
    op.add_column('students', sa.Column('case_manager', sa.String(100), nullable=True))
    
    # Create index for case_manager for performance
    op.create_index('ix_students_case_manager', 'students', ['case_manager'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_students_case_manager', 'students')
    op.drop_column('students', 'case_manager')
