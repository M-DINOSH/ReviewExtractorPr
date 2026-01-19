"""initial_unified_token_management_tables

Revision ID: 001_tokens
Revises: 
Create Date: 2026-01-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_tokens'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create clients table (now shares the same database as tokens)
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('client_secret', sa.String(length=512), nullable=False),
        sa.Column('redirect_uri', sa.String(length=512), nullable=False),
        sa.Column('branch_id', sa.String(length=255), nullable=False),
        sa.Column('workspace_email', sa.String(length=255), nullable=False),
        sa.Column('workspace_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id'),
        sa.UniqueConstraint('branch_id'),
    )
    op.create_index(op.f('ix_clients_branch_id'), 'clients', ['branch_id'], unique=True)
    op.create_index(op.f('ix_clients_client_id'), 'clients', ['client_id'], unique=True)

    # Create tokens table
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=50), nullable=False, server_default='Bearer'),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_refreshed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tokens_client_valid', 'tokens', ['client_id', 'is_valid'], unique=False)
    op.create_index('ix_tokens_expires_at', 'tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tokens_expires_at', table_name='tokens')
    op.drop_index('ix_tokens_client_valid', table_name='tokens')
    op.drop_table('tokens')
    op.drop_index(op.f('ix_clients_client_id'), table_name='clients')
    op.drop_index(op.f('ix_clients_branch_id'), table_name='clients')
    op.drop_table('clients')

