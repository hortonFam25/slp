"""update_objective_number_limit_to_10

Revision ID: 8d2fc1498eae
Revises: 4df20edbb686
Create Date: 2025-08-08 23:38:35.724683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d2fc1498eae'
down_revision: Union[str, None] = '4df20edbb686'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing check constraint
    op.drop_constraint('ck_objective_number_range', 'goal_objectives', type_='check')
    
    # Create new check constraint with updated range (1-10)
    op.create_check_constraint(
        'ck_objective_number_range',
        'goal_objectives',
        'objective_number >= 1 AND objective_number <= 10'
    )


def downgrade() -> None:
    # Revert back to the original constraint (1-4)
    op.drop_constraint('ck_objective_number_range', 'goal_objectives', type_='check')
    
    op.create_check_constraint(
        'ck_objective_number_range',
        'goal_objectives',
        'objective_number >= 1 AND objective_number <= 4'
    )
