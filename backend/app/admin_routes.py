
import os
import secrets
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import Booking, SportPricing
from sqlalchemy import case, func, select

router = APIRouter(
    prefix="/api/admin/bookings",
    tags=["Admin Bookings"],
)


def require_admin(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    configured_key = os.getenv("ADMIN_API_KEY")

    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Admin authentication is not configured.",
        )

    if not x_admin_key or not secrets.compare_digest(
        x_admin_key, configured_key
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin key.",
        )


@router.get("/summary", dependencies=[Depends(require_admin)])
def get_booking_summary():
    try:
        with SessionLocal() as db:
            result = db.execute(
                select(
                    func.count(Booking.id).label("total_bookings"),
                    func.sum(
                        case(
                            (Booking.status == "pending", 1),
                            else_=0,
                        )
                    ).label("pending_bookings"),
                    func.sum(
                        case(
                            (Booking.status == "confirmed", 1),
                            else_=0,
                        )
                    ).label("confirmed_bookings"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    Booking.payment_status == "paid",
                                    Booking.total_amount,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("verified_revenue"),
                )
            ).one()

            return {
                "total_bookings": result.total_bookings or 0,
                "pending_bookings": result.pending_bookings or 0,
                "confirmed_bookings": result.confirmed_bookings or 0,
                "verified_revenue": float(result.verified_revenue or 0),
            }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to load dashboard summary.",
        )

AdminAuth = Annotated[None, Depends(require_admin)]


def booking_to_dict(booking: Booking) -> dict:
    return {
        "id": booking.id,
        "booking_reference": booking.booking_reference,
        "customer_name": booking.customer_name,
        "customer_phone": booking.customer_phone,
        "sport_id": booking.sport_id,
        "booking_date": booking.booking_date.isoformat(),
        "start_time": booking.start_time.strftime("%H:%M"),
        "end_time": booking.end_time.strftime("%H:%M"),
        "duration_minutes": booking.duration_minutes,
        "total_players": booking.total_players,
        "male_players": booking.male_players,
        "female_players": booking.female_players,
        "court_type": booking.court_type,
        "total_amount": float(booking.total_amount),
        "status": booking.status,
        "payment_status": booking.payment_status,
        "created_at": (
            booking.created_at.isoformat()
            if booking.created_at
            else None
        ),
    }


@router.get("", dependencies=[Depends(require_admin)])
def list_bookings(
    search: str | None = Query(default=None, max_length=120),
    booking_date: date | None = None,
    status: Literal[
        "pending", "confirmed", "cancelled", "completed"
    ] | None = None,
    payment_status: Literal[
        "unpaid", "paid", "failed", "refunded"
    ] | None = None,
    sport: Literal["Badminton", "Pickleball"] | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    try:
        with SessionLocal() as db:
            query = (
                select(Booking, SportPricing.sport_name)
                .join(
                    SportPricing,
                    Booking.sport_id == SportPricing.id,
                )
            )

            if search:
                term = f"%{search.strip()}%"
                query = query.where(
                    or_(
                        Booking.booking_reference.ilike(term),
                        Booking.customer_name.ilike(term),
                        Booking.customer_phone.ilike(term),
                    )
                )

            if booking_date:
                query = query.where(
                    Booking.booking_date == booking_date
                )

            if status:
                query = query.where(Booking.status == status)

            if payment_status:
                query = query.where(
                    Booking.payment_status == payment_status
                )

            if sport:
                query = query.where(
                    SportPricing.sport_name == sport
                )

            total = len(
                db.execute(query.with_only_columns(Booking.id)).all()
            )

            rows = db.execute(
                query.order_by(
                    Booking.booking_date.desc(),
                    Booking.start_time.desc(),
                    Booking.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()

            items = []
            for booking, sport_name in rows:
                item = booking_to_dict(booking)
                item["sport"] = sport_name
                items.append(item)

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to load bookings.",
        )


@router.patch(
    "/{booking_reference}/status",
    dependencies=[Depends(require_admin)],
)
def update_booking_status(
    booking_reference: str,
    status: Literal[
        "pending", "confirmed", "cancelled", "completed"
    ],
):
    try:
        with SessionLocal() as db:
            booking = db.scalar(
                select(Booking)
                .where(
                    Booking.booking_reference == booking_reference
                )
                .with_for_update()
            )

            if booking is None:
                raise HTTPException(404, "Booking not found.")

            if booking.status == "cancelled":
                raise HTTPException(
                    409,
                    "A cancelled booking cannot be changed.",
                )

            if status == "confirmed" and booking.payment_status != "paid":
                raise HTTPException(
                    409,
                    "Only paid bookings can be confirmed.",
                )

            if status == "cancelled" and booking.payment_status == "paid":
                raise HTTPException(
                    409,
                    "Refund or verify payment before cancelling a paid booking.",
                )

            booking.status = status
            db.commit()
            db.refresh(booking)

            return {
                "message": "Booking status updated successfully.",
                "booking": booking_to_dict(booking),
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to update booking status.",
        )


@router.patch(
    "/{booking_reference}/payment",
    dependencies=[Depends(require_admin)],
)
def update_payment_status(
    booking_reference: str,
    payment_status: Literal[
        "unpaid", "paid", "failed", "refunded"
    ],
):
    try:
        with SessionLocal() as db:
            booking = db.scalar(
                select(Booking)
                .where(
                    Booking.booking_reference == booking_reference
                )
                .with_for_update()
            )

            if booking is None:
                raise HTTPException(404, "Booking not found.")

            if booking.payment_status == "refunded":
                raise HTTPException(
                    409,
                    "A refunded payment cannot be changed.",
                )

            if payment_status == "refunded" and booking.payment_status != "paid":
                raise HTTPException(
                    409,
                    "Only paid bookings can be marked as refunded.",
                )

            booking.payment_status = payment_status

            # Confirming a booking is a separate admin action.
            db.commit()
            db.refresh(booking)

            return {
                "message": "Payment status updated successfully.",
                "booking": booking_to_dict(booking),
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to update payment status.",
        )
