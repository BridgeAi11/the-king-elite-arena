
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Booking, CouponRedemption, PaymentTransaction

logger = logging.getLogger(__name__)


def expire_pending_bookings():
    expired_count = 0

    with SessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)

            bookings = db.scalars(
                select(Booking)
                .where(
                    Booking.status == "pending",
                    Booking.payment_status == "unpaid",
                    Booking.payment_expires_at.is_not(None),
                    Booking.payment_expires_at <= now,
                )
                .order_by(Booking.id)
                .with_for_update(skip_locked=True)
                .limit(100)
            ).all()

            for booking in bookings:
                transactions = db.scalars(
                    select(PaymentTransaction)
                    .where(PaymentTransaction.booking_id == booking.id)
                    .with_for_update()
                ).all()

                # Never expire a booking if a captured payment
                # has already been recorded in our database.
                if any(tx.status == "paid" for tx in transactions):
                    continue

                booking.status = "cancelled"
                booking.payment_expires_at = None

                # Mark unpaid transactions failed.
                for transaction in transactions:
                    if transaction.status == "created":
                        transaction.status = "failed"

                # Release reserved coupon usage.
                redemptions = db.scalars(
                    select(CouponRedemption)
                    .where(
                        CouponRedemption.booking_id == booking.id,
                        CouponRedemption.status == "reserved",
                    )
                    .with_for_update()
                ).all()

                for redemption in redemptions:
                    redemption.status = "released"

                expired_count += 1

            db.commit()

            if expired_count:
                logger.info(
                    "Expired %s unpaid bookings",
                    expired_count,
                )

            return expired_count

        except Exception:
            db.rollback()
            logger.exception("Booking expiry process failed")
            return 0


async def booking_expiry_loop():
    while True:
        try:
            await asyncio.to_thread(expire_pending_bookings)
        except Exception:
            logger.exception("Booking expiry scheduler error")

        await asyncio.sleep(60)
