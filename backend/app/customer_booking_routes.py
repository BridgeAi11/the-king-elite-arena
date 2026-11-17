
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import Booking, Customer, SportPricing
from app.customer_auth import require_customer

router = APIRouter(
    prefix="/api/customer",
    tags=["Customer Bookings"],
)


@router.get("/bookings")
def get_customer_bookings(
    customer: Customer = Depends(require_customer),
):
    """
    Return bookings belonging only to the authenticated customer.
    """

    try:
        with SessionLocal() as db:

            bookings = db.execute(
                select(Booking, SportPricing.sport_name)
                .join(
                    SportPricing,
                    Booking.sport_id == SportPricing.id,
                )
                .where(
                    Booking.customer_id == customer.id
                )
                .order_by(
                    Booking.booking_date.desc(),
                    Booking.start_time.desc(),
                )
            ).all()

            return {
                "customer": {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "phone": customer.phone,
                },
                "total_bookings": len(bookings),
                "bookings": [
                    {
                        "booking_id": booking.id,
                        "booking_reference": booking.booking_reference,
                        "sport": sport_name,
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
                    }
                    for booking, sport_name in bookings
                ],
            }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve customer bookings.",
        )
