
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

    customer_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
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
            "payment_status IN ('unpaid', 'paid', 'failed', 'refunded')",
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
