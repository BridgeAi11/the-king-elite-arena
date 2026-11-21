
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    func,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FacilitySettings(Base):
    __tablename__ = "facility_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    facility_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="The King Elite Arena",
    )

    opening_time: Mapped[datetime.time] = mapped_column(
        Time,
        nullable=False,
        default=datetime.strptime("06:00", "%H:%M").time(),
    )

    closing_time: Mapped[datetime.time] = mapped_column(
        Time,
        nullable=False,
        default=datetime.strptime("23:00", "%H:%M").time(),
    )

    operating_days: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
    )

    is_booking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    max_players_per_hour: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=40,
        server_default="40",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SportPricing(Base):
    __tablename__ = "sport_pricing"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    sport_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "hourly_rate >= 0",
            name="ck_sport_pricing_hourly_rate_nonnegative",
        ),
    )


class SportPricingRule(Base):
    __tablename__ = "sport_pricing_rules"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    sport_id: Mapped[int] = mapped_column(
        ForeignKey("sport_pricing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # First hour covered by this pricing rule.
    hour_from: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Last hour covered. NULL means all remaining hours.
    hour_to: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    price_per_player: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "sport_id",
            "hour_from",
            name="uq_sport_pricing_rule_start_hour",
        ),
        CheckConstraint(
            "hour_from >= 1",
            name="ck_sport_pricing_rule_hour_from",
        ),
        CheckConstraint(
            "hour_to IS NULL OR hour_to >= hour_from",
            name="ck_sport_pricing_rule_hour_range",
        ),
        CheckConstraint(
            "price_per_player >= 0",
            name="ck_sport_pricing_rule_price",
        ),
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    google_sub: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

class CustomerOTP(Base):
    __tablename__ = "customer_otps"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
    String(120),
    nullable=False,
)

    otp_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_customer_otps_phone_created",
            "phone",
            "created_at",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_customer_otps_attempts_nonnegative",
        ),
    )

class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    booking_reference: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    sport_id: Mapped[int] = mapped_column(
        ForeignKey("sport_pricing.id", ondelete="RESTRICT"),
        nullable=False,
    )

    booking_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    start_time: Mapped[datetime.time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[datetime.time] = mapped_column(
        Time,
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_players: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    male_players: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    female_players: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    court_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="general",
        server_default="general",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    pricing_snapshot: Mapped[dict | None] = mapped_column(
    JSONB,
    nullable=True,
)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unpaid",
        server_default="unpaid",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    payment_expires_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    index=True,
)

    __table_args__ = (
        CheckConstraint(
            "duration_minutes > 0",
            name="ck_bookings_duration_positive",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_bookings_total_amount_nonnegative",
        ),
        CheckConstraint(
            "start_time < end_time",
            name="ck_bookings_valid_time_range",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'completed')",
            name="ck_bookings_valid_status",
        ),
        CheckConstraint(
            "payment_status IN ('unpaid', 'paid', 'failed', 'refunded', 'waived')",
            name="ck_bookings_valid_payment_status",
        ),
        CheckConstraint(
            "total_players > 0",
            name="ck_bookings_total_players_positive",
        ),
        CheckConstraint(
            "male_players >= 0 AND female_players >= 0",
            name="ck_bookings_player_counts_nonnegative",
        ),
        CheckConstraint(
            "total_players = male_players + female_players",
            name="ck_bookings_player_counts_match",
        ),
        CheckConstraint(
            "court_type IN ('general', 'girls_only')",
            name="ck_bookings_valid_court_type",
        ),
        CheckConstraint(
            "court_type != 'girls_only' OR "
            "(male_players = 0 AND female_players > 0)",
            name="ck_bookings_girls_court_players",
        ),
        Index(
            "ix_bookings_date_sport_status",
            "booking_date",
            "sport_id",
            "status",
        ),
    )


class MembershipPlan(Base):
    __tablename__ = "membership_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    validity_days: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    included_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("price >= 0"),
        CheckConstraint("validity_days > 0"),
        CheckConstraint("included_hours > 0"),
    )


class CustomerMembership(Base):
    __tablename__ = "customer_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("membership_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    customer_id: Mapped[int | None] = mapped_column(
    ForeignKey("customers.id", ondelete="RESTRICT"),
    nullable=True,
    index=True,
)

    customer_phone: Mapped[str | None] = mapped_column(
    String(20), nullable=True, index=True
)

    customer_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    customer_phone: Mapped[str | None] = mapped_column(
    String(20), nullable=True, index=True
)

    plan_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    total_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )

    used_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=0
    )

    reserved_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=0
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    expiry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("amount_paid >= 0"),
        CheckConstraint("total_hours > 0"),
        CheckConstraint("used_hours >= 0"),
        CheckConstraint("reserved_hours >= 0"),
        CheckConstraint(
            "used_hours + reserved_hours <= total_hours"
        ),
        CheckConstraint(
            "status IN ('active', 'scheduled', 'expired', 'cancelled')",
            name="customer_memberships_status_check",
        ),
        Index("ix_customer_memberships_status_expiry",
              "status", "expiry_date"),
    )


class MembershipUsage(Base):
    __tablename__ = "membership_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    membership_id: Mapped[int] = mapped_column(
        ForeignKey("customer_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )

    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=True,
    )

    sport_id: Mapped[int] = mapped_column(
        ForeignKey("sport_pricing.id", ondelete="RESTRICT"),
        nullable=False,
    )

    hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )

    usage_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("hours > 0"),
        CheckConstraint(
            "usage_status IN ('reserved', 'consumed', 'released')"
        ),
    )


class MembershipTransaction(Base):
    __tablename__ = "membership_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    membership_id: Mapped[int] = mapped_column(
        ForeignKey("customer_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    payment_method: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    transaction_reference: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("amount >= 0"),
        CheckConstraint(
            "payment_status IN ('pending', 'paid', 'failed', 'refunded')"
        ),
    )
class MembershipPaymentOrder(Base):
    __tablename__ = "membership_payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("membership_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_memberships.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )

    razorpay_order_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        server_default="INR",
    )

    plan_name_snapshot: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    plan_price_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    validity_days_snapshot: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    included_hours_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="created",
        server_default="created",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "amount_paise > 0",
            name="ck_membership_payment_amount_positive",
        ),
        CheckConstraint(
            "status IN ('created', 'paid', 'failed')",
            name="ck_membership_payment_valid_status",
        ),
        CheckConstraint(
            "plan_price_snapshot >= 0",
            name="ck_membership_payment_plan_price",
        ),
        CheckConstraint(
            "validity_days_snapshot > 0",
            name="ck_membership_payment_validity",
        ),
        CheckConstraint(
            "included_hours_snapshot > 0",
            name="ck_membership_payment_hours",
        ),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    username: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, index=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    code: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, index=True
    )

    description: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )

    discount_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    applies_to: Mapped[str] = mapped_column(
        String(20), nullable=False, default="both"
    )

    min_order_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    max_discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    usage_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    per_customer_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="ck_coupons_discount_type",
        ),
        CheckConstraint(
            "discount_value > 0",
            name="ck_coupons_discount_value_positive",
        ),
        CheckConstraint(
            "(discount_type != 'percentage' OR discount_value <= 100)",
            name="ck_coupons_percentage_max_100",
        ),
        CheckConstraint(
            "applies_to IN ('booking', 'membership', 'both')",
            name="ck_coupons_applies_to",
        ),
        CheckConstraint(
            "min_order_amount >= 0",
            name="ck_coupons_min_order_nonnegative",
        ),
        CheckConstraint(
            "max_discount_amount IS NULL OR max_discount_amount > 0",
            name="ck_coupons_max_discount_positive",
        ),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit > 0",
            name="ck_coupons_usage_limit_positive",
        ),
        CheckConstraint(
            "per_customer_limit IS NULL OR per_customer_limit > 0",
            name="ck_coupons_customer_limit_positive",
        ),
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_coupons_valid_dates",
        ),
    )


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    coupon_id: Mapped[int] = mapped_column(
        ForeignKey("coupons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )

    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_memberships.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )

    applies_to: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    final_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="reserved"
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "applies_to IN ('booking', 'membership')",
            name="ck_coupon_redemptions_applies_to",
        ),
        CheckConstraint(
            "status IN ('reserved', 'redeemed', 'released')",
            name="ck_coupon_redemptions_status",
        ),
        CheckConstraint(
            "original_amount >= 0 AND discount_amount >= 0 "
            "AND final_amount >= 0",
            name="ck_coupon_redemptions_amounts_nonnegative",
        ),
        CheckConstraint(
            "discount_amount <= original_amount",
            name="ck_coupon_redemptions_discount_limit",
        ),
        CheckConstraint(
            "(booking_id IS NOT NULL AND membership_id IS NULL) OR "
            "(booking_id IS NULL AND membership_id IS NOT NULL)",
            name="ck_coupon_redemptions_single_target",
        ),
    )


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    razorpay_order_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="created",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("amount_paise > 0"),
        CheckConstraint(
            "status IN ('created', 'paid', 'failed')"
        ),
    )


class PaymentCapture(Base):
    __tablename__ = "payment_captures"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    payment_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    razorpay_payment_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="captured",
        server_default="captured",
    )

    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "amount_paise > 0",
            name="ck_payment_captures_amount_positive",
        ),
        CheckConstraint(
            "status IN ('captured', 'partially_refunded', 'refunded')",
            name="ck_payment_captures_valid_status",
        ),
    )


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    razorpay_event_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="received",
        server_default="received",
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'processed', 'failed')",
            name="ck_payment_webhook_events_valid_status",
        ),
    )



class PaymentRefund(Base):
    __tablename__ = "payment_refunds"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    payment_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Nullable initially to support safely migrating old refund records.
    capture_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_captures.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    razorpay_refund_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    reason: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "amount_paise > 0",
            name="ck_payment_refunds_amount_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed')",
            name="ck_payment_refunds_valid_status",
        ),
    )
class MembershipPaymentCapture(Base):
    __tablename__ = "membership_payment_captures"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    membership_payment_order_id: Mapped[int] = mapped_column(
        ForeignKey("membership_payment_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    razorpay_payment_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        server_default="INR",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="captured",
        server_default="captured",
    )

    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "amount_paise > 0",
            name="ck_membership_payment_captures_amount_positive",
        ),
        CheckConstraint(
            "status IN ('captured', 'partially_refunded', 'refunded')",
            name="ck_membership_payment_captures_valid_status",
        ),
    )

class MembershipPaymentRefund(Base):
    __tablename__ = "membership_payment_refunds"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    membership_payment_order_id: Mapped[int] = mapped_column(
        ForeignKey("membership_payment_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    capture_id: Mapped[int] = mapped_column(
        ForeignKey("membership_payment_captures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    razorpay_refund_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    reason: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "amount_paise > 0",
            name="ck_membership_payment_refunds_amount_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed')",
            name="ck_membership_payment_refunds_valid_status",
        ),
    )

class AccessCredential(Base):
    __tablename__ = "access_credentials"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    entity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            name="uq_access_credential_entity"
        ),
        CheckConstraint(
            "entity_type IN ('booking', 'membership')",
            name="ck_access_credential_entity_type"
        ),
        Index(
            "ix_access_credentials_customer_entity",
            "customer_id",
            "entity_type"
        ),
    )