
"""add Google customer identity fields

Revision ID: 6b01e3df9c38
Revises: 7a21c4d9e610
"""

from alembic import op
import sqlalchemy as sa


revision = "6b01e3df9c38"
down_revision = "7a21c4d9e610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Allow customers to register with Google without providing a phone number.
    op.alter_column(
        "customers",
        "phone",
        existing_type=sa.String(length=20),
        nullable=True,
    )

    # Add Google identity fields. Existing customers remain unchanged.
    op.add_column(
        "customers",
        sa.Column("email", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "customers",
        sa.Column("google_sub", sa.String(length=255), nullable=True),
    )

    # Unique indexes allow multiple NULL values while preventing duplicates.
    op.create_index(
        "ix_customers_email",
        "customers",
        ["email"],
        unique=True,
    )

    op.create_index(
        "ix_customers_google_sub",
        "customers",
        ["google_sub"],
        unique=True,
    )


def downgrade() -> None:
    # Prevent downgrade if phone-less Google customers already exist.
    connection = op.get_bind()

    phone_less_customers = connection.execute(
        sa.text("SELECT COUNT(*) FROM customers WHERE phone IS NULL")
    ).scalar_one()

    if phone_less_customers:
        raise RuntimeError(
            "Cannot downgrade: customers without phone numbers exist. "
            "Restore phone numbers before downgrading."
        )

    op.drop_index("ix_customers_google_sub", table_name="customers")
    op.drop_index("ix_customers_email", table_name="customers")

    op.drop_column("customers", "google_sub")
    op.drop_column("customers", "email")

    op.alter_column(
        "customers",
        "phone",
        existing_type=sa.String(length=20),
        nullable=False,
    )
