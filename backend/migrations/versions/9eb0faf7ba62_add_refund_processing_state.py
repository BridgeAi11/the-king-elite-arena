
"""add refund processing state

Revision ID: 9eb0faf7ba62
Revises: f4dc19132575
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9eb0faf7ba62"
down_revision: Union[str, Sequence[str], None] = "f4dc19132575"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_refunds",
        sa.Column(
            "processing_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "ck_payment_refunds_valid_status",
        "payment_refunds",
        type_="check",
    )

    op.create_check_constraint(
        "ck_payment_refunds_valid_status",
        "payment_refunds",
        "status IN ('pending', 'processing', 'processed', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_payment_refunds_valid_status",
        "payment_refunds",
        type_="check",
    )

    op.create_check_constraint(
        "ck_payment_refunds_valid_status",
        "payment_refunds",
        "status IN ('pending', 'processed', 'failed')",
    )

    op.drop_column(
        "payment_refunds",
        "processing_started_at",
    )
