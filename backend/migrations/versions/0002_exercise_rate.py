"""exercises start at 5 minutes per question

Revision ID: 0002
Revises: 0001
"""
from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only when still at the old default, so a value you set yourself stays.
    op.execute("UPDATE task_rates SET seconds_per_unit = 300 WHERE task_type = 'exercises' AND seconds_per_unit = 900")


def downgrade() -> None:
    op.execute("UPDATE task_rates SET seconds_per_unit = 900 WHERE task_type = 'exercises' AND seconds_per_unit = 300")
