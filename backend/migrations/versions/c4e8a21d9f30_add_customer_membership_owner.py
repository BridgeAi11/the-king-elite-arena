
"""add customer ownership to memberships

Revision ID: c4e8a21d9f30
Revises: 6b01e3df9c38
"""

from alembic import op
import sqlalchemy as sa


revision = "c4e8a21d9f30"
down_revision = "6b01e3df9c38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep legacy memberships unlinked until ownership is verified.
    op.add_column(
        "customer_memberships",
        sa.Column("customer_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_customer_memberships_customer_id",
        "customer_memberships",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_customer_memberships_customer_id",
        "customer_memberships",
        ["customer_id"],
        unique=False,
    )

    # Google-only customers may not have a phone number.
    op.alter_column(
        "customer_memberships",
        "customer_phone",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    connection = op.get_bind()

    memberships_without_phone = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM customer_memberships "
            "WHERE customer_phone IS NULL"
        )
    ).scalar_one()

    if memberships_without_phone:
        raise RuntimeError(
            "Cannot downgrade: memberships without phone numbers exist."
        )

    op.alter_column(
        "customer_memberships",
        "customer_phone",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.drop_index(
        "ix_customer_memberships_customer_id",
        table_name="customer_memberships",
    )

    op.drop_constraint(
        "fk_customer_memberships_customer_id",
        "customer_memberships",
        type_="foreignkey",
    )

    op.drop_column("customer_memberships", "customer_id")
