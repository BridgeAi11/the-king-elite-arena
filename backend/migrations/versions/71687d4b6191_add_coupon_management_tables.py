
"""add coupon management tables

Revision ID: 71687d4b6191
Revises: f5a0de596db5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "71687d4b6191"
down_revision: Union[str, Sequence[str], None] = "f5a0de596db5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "applies_to",
            sa.String(length=20),
            nullable=False,
            server_default="both",
        ),
        sa.Column(
            "min_order_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_discount_amount",
            sa.Numeric(10, 2),
            nullable=True,
        ),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ends_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("per_customer_limit", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="ck_coupons_discount_type",
        ),
        sa.CheckConstraint(
            "discount_value > 0",
            name="ck_coupons_discount_value_positive",
        ),
        sa.CheckConstraint(
            "discount_type != 'percentage' OR discount_value <= 100",
            name="ck_coupons_percentage_max_100",
        ),
        sa.CheckConstraint(
            "applies_to IN ('booking', 'membership', 'both')",
            name="ck_coupons_applies_to",
        ),
        sa.CheckConstraint(
            "min_order_amount >= 0",
            name="ck_coupons_min_order_nonnegative",
        ),
        sa.CheckConstraint(
            "max_discount_amount IS NULL OR max_discount_amount > 0",
            name="ck_coupons_max_discount_positive",
        ),
        sa.CheckConstraint(
            "usage_limit IS NULL OR usage_limit > 0",
            name="ck_coupons_usage_limit_positive",
        ),
        sa.CheckConstraint(
            "per_customer_limit IS NULL OR per_customer_limit > 0",
            name="ck_coupons_customer_limit_positive",
        ),
        sa.CheckConstraint(
            "ends_at > starts_at",
            name="ck_coupons_valid_dates",
        ),
    )

    op.create_index(
        "ix_coupons_code",
        "coupons",
        ["code"],
        unique=True,
    )

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "coupon_id",
            sa.Integer(),
            sa.ForeignKey("coupons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "booking_id",
            sa.Integer(),
            sa.ForeignKey("bookings.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "membership_id",
            sa.Integer(),
            sa.ForeignKey("customer_memberships.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("applies_to", sa.String(length=20), nullable=False),
        sa.Column("original_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="reserved",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "applies_to IN ('booking', 'membership')",
            name="ck_coupon_redemptions_applies_to",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'redeemed', 'released')",
            name="ck_coupon_redemptions_status",
        ),
        sa.CheckConstraint(
            "original_amount >= 0 AND discount_amount >= 0 "
            "AND final_amount >= 0",
            name="ck_coupon_redemptions_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "discount_amount <= original_amount",
            name="ck_coupon_redemptions_discount_limit",
        ),
        sa.CheckConstraint(
            "(booking_id IS NOT NULL AND membership_id IS NULL) OR "
            "(booking_id IS NULL AND membership_id IS NOT NULL)",
            name="ck_coupon_redemptions_single_target",
        ),
        sa.UniqueConstraint(
            "booking_id",
            name="uq_coupon_redemptions_booking_id",
        ),
        sa.UniqueConstraint(
            "membership_id",
            name="uq_coupon_redemptions_membership_id",
        ),
    )

    op.create_index(
        "ix_coupon_redemptions_coupon_id",
        "coupon_redemptions",
        ["coupon_id"],
    )
    op.create_index(
        "ix_coupon_redemptions_customer_id",
        "coupon_redemptions",
        ["customer_id"],
    )

    # Allow bookings fully covered by coupons to use "waived".
    op.drop_constraint(
        "ck_bookings_valid_payment_status",
        "bookings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_bookings_valid_payment_status",
        "bookings",
        "payment_status IN ('unpaid', 'paid', 'failed', 'refunded', 'waived')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_bookings_valid_payment_status",
        "bookings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_bookings_valid_payment_status",
        "bookings",
        "payment_status IN ('unpaid', 'paid', 'failed', 'refunded')",
    )

    op.drop_index(
        "ix_coupon_redemptions_customer_id",
        table_name="coupon_redemptions",
    )
    op.drop_index(
        "ix_coupon_redemptions_coupon_id",
        table_name="coupon_redemptions",
    )
    op.drop_table("coupon_redemptions")

    op.drop_index("ix_coupons_code", table_name="coupons")
    op.drop_table("coupons")
