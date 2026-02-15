"""baseline

Revision ID: d702babff7fb
Revises: cf166ed4cb6a
Create Date: 2025-08-08 19:29:08.494484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd702babff7fb'
down_revision: Union[str, None] = 'cf166ed4cb6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
