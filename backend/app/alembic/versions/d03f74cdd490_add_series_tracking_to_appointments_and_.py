"""Add series tracking to appointments and therapy sessions

Revision ID: d03f74cdd490
Revises: 7c26e869115f
Create Date: 2025-08-10 12:43:21.604123

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd03f74cdd490'
down_revision: Union[str, None] = '7c26e869115f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add series tracking fields to appointments table
    op.add_column('appointments', sa.Column('series_id', sa.String(36), nullable=True, index=True))
    op.add_column('appointments', sa.Column('series_metadata', sa.Text(), nullable=True))
    
    # Add series tracking fields to therapy_sessions table
    op.add_column('therapy_sessions', sa.Column('series_id', sa.String(36), nullable=True, index=True))
    op.add_column('therapy_sessions', sa.Column('series_metadata', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove series tracking fields from therapy_sessions table
    op.drop_column('therapy_sessions', 'series_metadata')
    op.drop_column('therapy_sessions', 'series_id')
    
    # Remove series tracking fields from appointments table
    op.drop_column('appointments', 'series_metadata')
    op.drop_column('appointments', 'series_id')
