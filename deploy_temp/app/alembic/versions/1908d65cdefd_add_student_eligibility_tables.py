"""add_student_eligibility_tables

Revision ID: 1908d65cdefd
Revises: 1d4f4b45cdb3
Create Date: 2025-08-08 22:08:09.537531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1908d65cdefd'
down_revision: Union[str, None] = '1d4f4b45cdb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create eligibility_categories lookup table
    op.create_table('eligibility_categories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('code', sa.String(20), nullable=True, unique=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('display_order', sa.Integer(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create student_eligibilities junction table (many-to-many)
    op.create_table('student_eligibilities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('eligibility_category_id', sa.Integer(), sa.ForeignKey('eligibility_categories.id'), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create indexes for performance
    op.create_index('ix_eligibility_categories_code', 'eligibility_categories', ['code'])
    op.create_index('ix_eligibility_categories_display_order', 'eligibility_categories', ['display_order'])
    op.create_index('ix_eligibility_categories_is_active', 'eligibility_categories', ['is_active'])
    
    op.create_index('ix_student_eligibilities_student_id', 'student_eligibilities', ['student_id'])
    op.create_index('ix_student_eligibilities_eligibility_category_id', 'student_eligibilities', ['eligibility_category_id'])
    op.create_index('ix_student_eligibilities_start_date', 'student_eligibilities', ['start_date'])
    op.create_index('ix_student_eligibilities_is_primary', 'student_eligibilities', ['is_primary'])
    
    # Create index for unique constraint (SQL Server compatible)
    op.create_index('ix_student_eligibilities_unique_active', 'student_eligibilities', 
                   ['student_id', 'eligibility_category_id'], unique=True)
    
    # Insert common eligibility categories
    op.execute("""
        INSERT INTO eligibility_categories (name, code, description, display_order) VALUES 
        ('Autism Spectrum Disorder', 'ASD', 'Students with autism spectrum disorder who require special education services', 1),
        ('Early Childhood Developmental Delay', 'ECDD', 'Children ages 3-5 with developmental delays in one or more areas', 2),
        ('Speech & Language Impairment', 'SLI', 'Students with communication disorders that adversely affect educational performance', 3),
        ('Specific Learning Disability', 'SLD', 'Students with specific learning disabilities in basic psychological processes', 4),
        ('Intellectual Disability', 'ID', 'Students with significantly sub-average intellectual functioning', 5),
        ('Multiple Disabilities', 'MD', 'Students with concomitant impairments requiring intensive services', 6),
        ('Hearing Impairment', 'HI', 'Students with hearing impairments that adversely affect educational performance', 7),
        ('Visual Impairment', 'VI', 'Students with visual impairments that adversely affect educational performance', 8),
        ('Emotional Disturbance', 'ED', 'Students with emotional disturbance that adversely affects educational performance', 9),
        ('Orthopedic Impairment', 'OI', 'Students with orthopedic impairments that adversely affect educational performance', 10),
        ('Other Health Impairment', 'OHI', 'Students with other health impairments that adversely affect educational performance', 11),
        ('Traumatic Brain Injury', 'TBI', 'Students with traumatic brain injury that adversely affects educational performance', 12),
        ('Deafness', 'DEAF', 'Students who are deaf and require special education services', 13),
        ('Deaf-Blindness', 'DB', 'Students with concomitant hearing and visual impairments', 14)
    """)


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('student_eligibilities')
    op.drop_table('eligibility_categories')
