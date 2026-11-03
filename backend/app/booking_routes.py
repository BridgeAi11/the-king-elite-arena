
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import SessionLocal
from app.models import Booking, FacilitySettings, SportPricing

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


class BookingRequest(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=8, max_length=20)
    sport: Literal["Badminton", "Pickleball"]
    booking_date: date
    start_time: time
    duration_minutes: int = Field(gt=0, le=300)
    total_players: int = Field(gt=0, le=40)
    male_players: int = Field(ge=0, le=40)
    female_players: int = Field(ge=0, le=40)
    court_type: Literal["general", "girls_only"] = "general"

    @model_validator(mode="after")
    def validate_players(self):
        if self.total_players != self.male_players + self.female_players:
            raise ValueError(
                "Total players must equal male players plus female players."
            )

        if self.court_type == "girls_only":
            if self.sport != "Badminton":
                raise ValueError(
                    "The girls-only court is available for badminton only."
                )
            if self.male_players > 0 or self.female_players == 0:
                raise ValueError(
                    "Only women players are permitted on the girls-only court."
                )

        return self


def get_end_time(start_time: time, duration_minutes: int) -> time:
    end_dt = datetime.combine(date.today(), start_time) + timedelta(
        minutes=duration_minutes
    )
    if end_dt.date() != date.today():
        raise HTTPException(400, "Bookings cannot extend past midnight.")
    return end_dt.time()


def calculate_capacity(
    bookings: list[Booking],
    requested_start: time,
    requested_end: time,
    requested_players: int,
    max_players: int,
) -> tuple[bool, int]:
    """Check player capacity in every segment of the requested interval."""
    boundaries = {requested_start, requested_end}

    for booking in bookings:
        if booking.start_time < requested_end and booking.end_time > requested_start:
            boundaries.add(max(booking.start_time, requested_start))
            boundaries.add(min(booking.end_time, requested_end))

    ordered = sorted(boundaries)

    for segment_start, segment_end in zip(ordered, ordered[1:]):
        if segment_start >= segment_end:
            continue

        existing_players = sum(
            booking.total_players
            for booking in bookings
            if booking.start_time < segment_end
            and booking.end_time > segment_start
        )

        if existing_players + requested_players > max_players:
            return False, max(0, max_players - existing_players)

    current_max = max(
        (
            sum(
                booking.total_players
                for booking in bookings
                if booking.start_time < segment_end
                and booking.end_time > segment_start
            )
            for segment_start, segment_end in zip(ordered, ordered[1:])
        ),
        default=0,
    )

    return True, max(0, max_players - current_max)


def load_overlapping_bookings(db, booking_date, start_time, end_time):
    return db.scalars(
        select(Booking).where(
            Booking.booking_date == booking_date,
            Booking.status.in_(["pending", "confirmed"]),
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        )
    ).all()


@router.get("/availability")
def check_availability(
    sport: Literal["Badminton", "Pickleball"],
    booking_date: date,
    start_time: time,
    duration_minutes: int = 60,
    court_type: Literal["general", "girls_only"] = "general",
    total_players: int = 1,
):
    if duration_minutes <= 0 or duration_minutes > 300:
        raise HTTPException(400, "Duration must be between 1 and 300 minutes.")

    if total_players <= 0:
        raise HTTPException(400, "At least one player is required.")

    if court_type == "girls_only" and sport != "Badminton":
        raise HTTPException(400, "Girls-only courts are for badminton only.")

    end_dt = datetime.combine(booking_date, start_time) + timedelta(
        minutes=duration_minutes
    )
    if end_dt.date() != booking_date:
        raise HTTPException(400, "Bookings cannot extend past midnight.")

    end_time = end_dt.time()

    try:
        with SessionLocal() as db:
            facility = db.scalar(
                select(FacilitySettings).order_by(FacilitySettings.id)
            )
            if facility is None:
                raise HTTPException(503, "Facility settings are not configured.")

            if not facility.is_booking_enabled:
                raise HTTPException(403, "Bookings are currently disabled.")

            if booking_date.strftime("%A") not in facility.operating_days:
                return {
                    "available": False,
                    "message": "The facility is closed on this day.",
                    "max_players_per_hour": facility.max_players_per_hour,
                }

            if (
                start_time < facility.opening_time
                or end_time > facility.closing_time
            ):
                raise HTTPException(400, "Requested time is outside operating hours.")

            sport_record = db.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name == sport,
                    SportPricing.is_active.is_(True),
                )
            )
            if sport_record is None:
                raise HTTPException(404, "Sport is unavailable.")

            overlapping = load_overlapping_bookings(
                db, booking_date, start_time, end_time
            )

            available, remaining = calculate_capacity(
                overlapping,
                start_time,
                end_time,
                total_players,
                facility.max_players_per_hour,
            )

            amount = (
                sport_record.hourly_rate
                * Decimal(duration_minutes)
                / Decimal(60)
            ).quantize(Decimal("0.01"))

            return {
                "sport": sport,
                "booking_date": booking_date.isoformat(),
                "start_time": start_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
                "court_type": court_type,
                "requested_players": total_players,
                "max_players_per_hour": facility.max_players_per_hour,
                "remaining_capacity_for_requested_time": remaining,
                "available": available,
                "hourly_rate": float(sport_record.hourly_rate),
                "estimated_amount": float(amount),
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Unable to check player availability.")


@router.post("")
def create_booking(request: BookingRequest):
    now = datetime.now()

    if request.booking_date < now.date():
        raise HTTPException(400, "Booking date cannot be in the past.")

    if (
        request.booking_date == now.date()
        and request.start_time <= now.time().replace(tzinfo=None)
    ):
        raise HTTPException(400, "Choose a future start time.")

    end_dt = datetime.combine(request.booking_date, request.start_time) + timedelta(
        minutes=request.duration_minutes
    )
    if end_dt.date() != request.booking_date:
        raise HTTPException(400, "Bookings cannot extend past midnight.")

    end_time = end_dt.time()

    try:
        with SessionLocal() as db:
            # Lock the facility row so concurrent booking attempts are serialized.
            facility = db.scalar(
                select(FacilitySettings)
                .order_by(FacilitySettings.id)
                .with_for_update()
            )
            if facility is None:
                raise HTTPException(503, "Facility settings are not configured.")

            if not facility.is_booking_enabled:
                raise HTTPException(403, "Bookings are currently disabled.")

            if request.booking_date.strftime("%A") not in facility.operating_days:
                raise HTTPException(400, "The facility is closed on this day.")

            if (
                request.start_time < facility.opening_time
                or end_time > facility.closing_time
            ):
                raise HTTPException(400, "Requested time is outside operating hours.")

            sport_record = db.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name == request.sport,
                    SportPricing.is_active.is_(True),
                )
            )
            if sport_record is None:
                raise HTTPException(404, "Sport is unavailable.")

            overlapping = load_overlapping_bookings(
                db, request.booking_date, request.start_time, end_time
            )

            available, remaining = calculate_capacity(
                overlapping,
                request.start_time,
                end_time,
                request.total_players,
                facility.max_players_per_hour,
            )

            if not available:
                raise HTTPException(
                    status_code=409,
                    detail="Sorry, this time slot is fully booked. Please choose another time.",
                )

            amount = (
                sport_record.hourly_rate
                * Decimal(request.duration_minutes)
                / Decimal(60)
            ).quantize(Decimal("0.01"))

            booking = Booking(
                booking_reference="KEA-" + secrets.token_hex(5).upper(),
                customer_name=request.customer_name.strip(),
                customer_phone=request.customer_phone.strip(),
                sport_id=sport_record.id,
                booking_date=request.booking_date,
                start_time=request.start_time,
                end_time=end_time,
                duration_minutes=request.duration_minutes,
                total_players=request.total_players,
                male_players=request.male_players,
                female_players=request.female_players,
                court_type=request.court_type,
                total_amount=amount,
                status="pending",
                payment_status="unpaid",
            )

            db.add(booking)
            db.commit()
            db.refresh(booking)

            return {
                "message": "Booking created successfully. Payment is pending.",
                "booking_reference": booking.booking_reference,
                "sport": request.sport,
                "booking_date": booking.booking_date.isoformat(),
                "start_time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),
                "court_type": booking.court_type,
                "total_players": booking.total_players,
                "male_players": booking.male_players,
                "female_players": booking.female_players,
                "total_amount": float(booking.total_amount),
                "status": booking.status,
                "payment_status": booking.payment_status,
            }

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(409, "Booking could not be saved due to a data conflict.")
    except SQLAlchemyError:
        raise HTTPException(503, "Unable to create booking.")
