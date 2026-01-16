"""Initial migration - Create clients, branches, tokens, and oauth_states tables

Revision ID: 001
Revises: 
Create Date: 2026-01-16 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('client_secret', sa.String(length=512), nullable=False),
        sa.Column('redirect_uri', sa.String(length=512), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clients_id', 'clients', ['id'])
    op.create_index('ix_clients_client_id', 'clients', ['client_id'], unique=True)
    
    # Create branches table
    op.create_table(
        'branches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.String(length=255), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=True),
        sa.Column('account_id', sa.String(length=255), nullable=True),
        sa.Column('location_id', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_branches_id', 'branches', ['id'])
    op.create_index('ix_branches_branch_id', 'branches', ['branch_id'], unique=True)
    op.create_index('ix_branches_account_id', 'branches', ['account_id'])
    op.create_index('ix_branches_location_id', 'branches', ['location_id'])
    op.create_index('ix_branches_client_account', 'branches', ['client_id', 'account_id'])
    op.create_index('ix_branches_client_location', 'branches', ['client_id', 'location_id'])
    
    # Create tokens table
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=50), nullable=False, server_default='Bearer'),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_refreshed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tokens_id', 'tokens', ['id'])
    op.create_index('ix_tokens_client_valid', 'tokens', ['client_id', 'is_valid'])
    op.create_index('ix_tokens_expires_at', 'tokens', ['expires_at'])
    
    # Create oauth_states table
    op.create_table(
        'oauth_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=255), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_oauth_states_id', 'oauth_states', ['id'])
    op.create_index('ix_oauth_states_state', 'oauth_states', ['state'], unique=True)
    op.create_index('ix_oauth_states_expires_used', 'oauth_states', ['expires_at', 'is_used'])


def downgrade() -> None:
    op.drop_table('oauth_states')
    op.drop_table('tokens')
    op.drop_table('branches')
    op.drop_table('clients')
