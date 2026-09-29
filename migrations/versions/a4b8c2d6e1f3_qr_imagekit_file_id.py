"""Store ImageKit file ID for payment QR cleanup.

Revision ID: a4b8c2d6e1f3
Revises: 9c7e4a2b1d6f
"""
from alembic import op
import sqlalchemy as sa


revision = "a4b8c2d6e1f3"
down_revision = "9c7e4a2b1d6f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "seller_profiles",
        sa.Column("qr_image_file_id", sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column("seller_profiles", "qr_image_file_id")
