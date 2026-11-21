import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.coupon_routes import validate_coupon_rules
from app.customer_auth import require_customer
from app.database import SessionLocal
from app.models import (
    Booking,
    Coupon,
    CouponRedemption,
    Customer,
    FacilitySettings,
    SportPricing,
    SportPricingRule,
)

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


class BookingRequest(BaseModel):
    sport: Literal["Badminton", "Pickleball"]
    booking_date: date
    start_time: time
    duration_minutes: int = Field(gt=0, le=300)
    total_players: int = Field(gt=0, le=40)
    male_players: int = Field(ge=0, le=40)
    female_players: int = Field(ge=0, le=40)
    court_type: Literal["general", "girls_only"] = "general"
    payment_method: Literal["online"] | None = None
    coupon_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=40,
    )
    phone: str = Field(
        min_length=10,
        max_length=10,
        pattern=r"^[6-9][0-9]{9}$"
    )

    @model_validator(mode="after")
    def validate_players(self):
        if self.total_players != self.male_players + self.female_players:
            raise ValueError(
                "Total players must equal male players plus female players."
            )

        if self.duration_minutes % 60 != 0:
            raise ValueError(
                "Bookings must be in full-hour blocks (60, 120, 180 minutes, etc.)."
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


def calculate_booking_price(
    db,
    sport_id: int,
    duration_minutes: int,
    total_players: int,
) -> dict:
    """Calculate the booking price from the active hourly pricing rules."""

    if duration_minutes <= 0 or duration_minutes % 60 != 0:
        raise HTTPException(
            status_code=400,
            detail="Bookings must use full-hour durations.",
        )

    rules = db.scalars(
        select(SportPricingRule)
        .where(
            SportPricingRule.sport_id == sport_id,
            SportPricingRule.is_active.is_(True),
        )
        .order_by(SportPricingRule.hour_from)
    ).all()

    if not rules:
        raise HTTPException(
            status_code=503,
            detail="Pricing rules are not configured for this sport.",
        )

    total_hours = duration_minutes // 60
    per_player_total = Decimal("0.00")
    breakdown = []

    for hour_number in range(1, total_hours + 1):
        matching_rule = next(
            (
                rule for rule in rules
                if rule.hour_from <= hour_number
                and (
                    rule.hour_to is None
                    or hour_number <= rule.hour_to
                )
            ),
            None,
        )

        if matching_rule is None:
            raise HTTPException(
                status_code=503,
                detail=f"Pricing is not configured for hour {hour_number}.",
            )

        hourly_price = Decimal(matching_rule.price_per_player)
        per_player_total += hourly_price

        breakdown.append({
            "hour": hour_number,
            "price_per_player": float(hourly_price),
            "total_for_players": float(
                hourly_price * total_players
            ),
        })

    per_player_total = per_player_total.quantize(Decimal("0.01"))
    total_amount = (
        per_player_total * total_players
    ).quantize(Decimal("0.01"))

    return {
        "hours": total_hours,
        "per_player_amount": per_player_total,
        "total_amount": total_amount,
        "breakdown": breakdown,
    }

def calculate_capacity(
    bookings: list[Booking],
    requested_start: time,
    requested_end: time,
    requested_players: int,
    max_players: int,
) -> tuple[bool, int]:

    boundaries = {requested_start, requested_end}

    for booking in bookings:
        if (
            booking.start_time < requested_end
            and booking.end_time > requested_start
        ):
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
            for segment_start, segment_end in zip(
                ordered, ordered[1:]
            )
        ),
        default=0,
    )

    return True, max(0, max_players - current_max)


def load_overlapping_bookings(
    db,
    booking_date: date,
    start_time: time,
    end_time: time,
):
    return db.scalars(
        select(Booking).where(
            Booking.booking_date == booking_date,
            Booking.status.in_(["pending", "confirmed"]),
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        )
    ).all()


def get_booking_end_time(
    booking_date: date,
    start_time: time,
    duration_minutes: int,
):
    end_dt = datetime.combine(
        booking_date,
        start_time,
    ) + timedelta(minutes=duration_minutes)

    if end_dt.date() != booking_date:
        raise HTTPException(
            status_code=400,
            detail="Bookings cannot extend past midnight.",
        )

    return end_dt.time()


# --------------------------------------------------
# PUBLIC: CHECK AVAILABILITY
# --------------------------------------------------

@router.get("/availability")
def check_availability(
    sport: Literal["Badminton", "Pickleball"],
    booking_date: date,
    start_time: time,
    duration_minutes: int = 60,
    court_type: Literal["general", "girls_only"] = "general",
    total_players: int = 1,
):

    if (
        duration_minutes <= 0
        or duration_minutes > 300
        or duration_minutes % 60 != 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Duration must be 60, 120, 180, 240 or 300 minutes.",
        )

    if total_players <= 0 or total_players > 40:
        raise HTTPException(
            status_code=400,
            detail="Total players must be between 1 and 40.",
        )

    if court_type == "girls_only" and sport != "Badminton":
        raise HTTPException(
            status_code=400,
            detail="Girls-only courts are for badminton only.",
        )

    end_time = get_booking_end_time(
        booking_date,
        start_time,
        duration_minutes,
    )

    try:
        with SessionLocal() as db:

            facility = db.scalar(
                select(FacilitySettings).order_by(
                    FacilitySettings.id
                )
            )

            if facility is None:
                raise HTTPException(
                    status_code=503,
                    detail="Facility settings are not configured.",
                )

            if not facility.is_booking_enabled:
                raise HTTPException(
                    status_code=403,
                    detail="Bookings are currently disabled.",
                )

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
                raise HTTPException(
                    status_code=400,
                    detail="Requested time is outside operating hours.",
                )

            sport_record = db.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name == sport,
                    SportPricing.is_active.is_(True),
                )
            )

            if sport_record is None:
                raise HTTPException(
                    status_code=404,
                    detail="Sport is unavailable.",
                )

            overlapping = load_overlapping_bookings(
                db,
                booking_date,
                start_time,
                end_time,
            )

            available, remaining = calculate_capacity(
                overlapping,
                start_time,
                end_time,
                total_players,
                facility.max_players_per_hour,
            )

            pricing = calculate_booking_price(
                db=db,
                sport_id=sport_record.id,
                duration_minutes=duration_minutes,
                total_players=total_players,
            )

            estimated_amount = pricing["total_amount"]

            return {
                "available": available,
                "message": (
                    "This time slot is available."
                    if available
                    else "This time slot does not have enough player capacity."
                ),
                "sport": sport,
                "booking_date": booking_date.isoformat(),
                "start_time": start_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
                "duration_minutes": duration_minutes,
                "court_type": court_type,
                "total_players": total_players,
                "max_players_per_hour": facility.max_players_per_hour,
                "remaining_player_capacity": remaining,
                "hourly_rate": float(sport_record.hourly_rate),
                "per_player_amount": float(pricing["per_player_amount"]),
                "pricing_breakdown": pricing["breakdown"],
                "estimated_amount": float(estimated_amount),
            }

    except HTTPException:
        raise

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to check player availability.",
        )


# --------------------------------------------------
# PROTECTED: CREATE BOOKING
# --------------------------------------------------

@router.post("")
def create_booking(
    request: BookingRequest,
    customer: Customer = Depends(require_customer),
):

    now = datetime.now()

    if request.booking_date < now.date():
        raise HTTPException(
            status_code=400,
            detail="Booking date cannot be in the past.",
        )

    if (
        request.booking_date == now.date()
        and request.start_time <= now.time().replace(tzinfo=None)
    ):
        raise HTTPException(
            status_code=400,
            detail="Choose a future start time.",
        )

    end_time = get_booking_end_time(
        request.booking_date,
        request.start_time,
        request.duration_minutes,
    )

    try:
        with SessionLocal() as db:

            authenticated_customer = db.scalar(
                select(Customer).where(
                    Customer.id == customer.id,
                    Customer.is_active.is_(True),
                )
            )

            if authenticated_customer is None:
                raise HTTPException(
                    status_code=401,
                    detail="Customer account is unavailable.",
                )

            # Lock facility row to serialize booking capacity checks.
            facility = db.scalar(
                select(FacilitySettings)
                .order_by(FacilitySettings.id)
                .with_for_update()
            )

            if facility is None:
                raise HTTPException(
                    status_code=503,
                    detail="Facility settings are not configured.",
                )

            if not facility.is_booking_enabled:
                raise HTTPException(
                    status_code=403,
                    detail="Bookings are currently disabled.",
                )

            if (
                request.booking_date.strftime("%A")
                not in facility.operating_days
            ):
                raise HTTPException(
                    status_code=400,
                    detail="The facility is closed on this day.",
                )

            if (
                request.start_time < facility.opening_time
                or end_time > facility.closing_time
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Requested time is outside operating hours.",
                )

            sport_record = db.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name == request.sport,
                    SportPricing.is_active.is_(True),
                )
            )

            if sport_record is None:
                raise HTTPException(
                    status_code=404,
                    detail="Sport is unavailable.",
                )

            overlapping = load_overlapping_bookings(
                db,
                request.booking_date,
                request.start_time,
                end_time,
            )

            available, _remaining = calculate_capacity(
                overlapping,
                request.start_time,
                end_time,
                request.total_players,
                facility.max_players_per_hour,
            )

            if not available:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Sorry, this time slot is fully booked. "
                        "Please choose another time."
                    ),
                )

            # Calculate original booking amount on the backend.
            pricing = calculate_booking_price(
                db=db,
                sport_id=sport_record.id,
                duration_minutes=request.duration_minutes,
                total_players=request.total_players,
            )

            original_amount = pricing["total_amount"]

            discount_amount = Decimal("0.00")
            final_amount = original_amount
            coupon = None

            # Validate coupon and lock its row during this transaction.
            if request.coupon_code:

                coupon_code = request.coupon_code.strip().upper()

                coupon = db.scalar(
                    select(Coupon)
                    .where(Coupon.code == coupon_code)
                    .with_for_update()
                )

                if coupon is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Invalid coupon code.",
                    )

                discount_amount, final_amount = validate_coupon_rules(
                    db=db,
                    coupon=coupon,
                    customer_id=authenticated_customer.id,
                    applies_to="booking",
                    amount=original_amount,
                )

            is_fully_discounted = (
                final_amount == Decimal("0.00")
            )

            # Preserve the exact pricing applied when this booking was created.
            pricing_snapshot = {
                "sport_id": sport_record.id,
                "sport": sport_record.sport_name,
                "duration_minutes": request.duration_minutes,
                "total_hours": pricing["hours"],
                "total_players": request.total_players,
                "per_player_amount": float(pricing["per_player_amount"]),
                "pricing_breakdown": pricing["breakdown"],
                "original_amount": float(original_amount),
                "discount_amount": float(discount_amount),
                "final_amount": float(final_amount),
                "coupon_code": coupon.code if coupon else None,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }

            if not is_fully_discounted and request.payment_method != "online":
                raise HTTPException(
                    status_code=400,
                    detail="Please select online payment."
                )

            booking = Booking(
                booking_reference="KEA-" + secrets.token_hex(5).upper(),

                customer_id=authenticated_customer.id,
                customer_name=authenticated_customer.full_name,
                customer_phone=request.phone,

                sport_id=sport_record.id,
                booking_date=request.booking_date,
                start_time=request.start_time,
                end_time=end_time,
                duration_minutes=request.duration_minutes,

                total_players=request.total_players,
                male_players=request.male_players,
                female_players=request.female_players,
                court_type=request.court_type,

                total_amount=final_amount,
                pricing_snapshot=pricing_snapshot,
                payment_expires_at=(
                                None
                                if is_fully_discounted
                                else datetime.now(timezone.utc) + timedelta(minutes=10)
                            ),
                            
                status=(
                    "confirmed"
                    if is_fully_discounted
                    else "pending"
                ),

                

                payment_status=(
                    "waived"
                    if is_fully_discounted
                    else "unpaid"
                ),
            )

            db.add(booking)
            db.flush()

            # Save coupon redemption.
            if coupon is not None:

                redemption = CouponRedemption(
                    coupon_id=coupon.id,
                    customer_id=authenticated_customer.id,
                    booking_id=booking.id,
                    membership_id=None,
                    applies_to="booking",
                    original_amount=original_amount,
                    discount_amount=discount_amount,
                    final_amount=final_amount,
                    status=(
                        "redeemed"
                        if is_fully_discounted
                        else "reserved"
                    ),
                )

                db.add(redemption)

            db.commit()
            db.refresh(booking)

            return {
                "booking_id": booking.id,
                "message": (
                    "Booking confirmed with a 100% coupon discount. "
                    "No payment is required."
                    if is_fully_discounted
                    else "Booking created successfully. Payment is pending."
                ),

                "booking_reference": booking.booking_reference,
                "sport": request.sport,
                "booking_date": booking.booking_date.isoformat(),
                "start_time": booking.start_time.strftime("%H:%M"),
                "end_time": booking.end_time.strftime("%H:%M"),

                "court_type": booking.court_type,
                "total_players": booking.total_players,
                "male_players": booking.male_players,
                "female_players": booking.female_players,

                "original_amount": float(original_amount),
                "discount_amount": float(discount_amount),
                "total_amount": float(booking.total_amount),
                "per_player_amount": float(pricing["per_player_amount"]),
                "pricing_breakdown": pricing["breakdown"],


                "coupon_code": coupon.code if coupon else None,

                "status": booking.status,
                "payment_status": booking.payment_status,
                "payment_expires_at": (
                booking.payment_expires_at.isoformat()
                if booking.payment_expires_at
                else None
            ),
            }

    except HTTPException:
        raise

    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Booking could not be saved due to a data conflict.",
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to create booking.",
        )