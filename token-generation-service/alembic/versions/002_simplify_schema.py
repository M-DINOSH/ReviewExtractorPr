"""Simplify schema - keep only clients and tokens tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-16 15:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to clients table
    op.add_column('clients', sa.Column('branch_id', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('workspace_email', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('workspace_name', sa.String(255), nullable=True))
    
    # Create unique index on branch_id
    op.create_unique_constraint('uq_clients_branch_id', 'clients', ['branch_id'])
    
    # Drop branches and oauth_states tables
    op.drop_table('branches')
    op.drop_table('oauth_states')
    
    # Update column nullability after data migration
    op.alter_column('clients', 'branch_id', nullable=False)
    op.alter_column('clients', 'workspace_email', nullable=False)
    op.alter_column('clients', 'workspace_name', nullable=False)


def downgrade() -> None:
    # This is not reversible - remove the columns
    op.drop_constraint('uq_clients_branch_id', 'clients', type_='unique')
    op.drop_column('clients', 'branch_id')
    op.drop_column('clients', 'workspace_email')
    op.drop_column('clients', 'workspace_name')
