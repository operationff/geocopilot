"""phase3 ai engine fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add plan column to users (default 'free')
    op.add_column("users", sa.Column("plan", sa.String(50), nullable=False, server_default="free"))

    # Add cost/token tracking columns to prompt_results
    op.add_column("prompt_results", sa.Column("api_cost_usd", sa.Float(), nullable=True))
    op.add_column("prompt_results", sa.Column("tokens_used", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("prompt_results", "tokens_used")
    op.drop_column("prompt_results", "api_cost_usd")
    op.drop_column("users", "plan")
