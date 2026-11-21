
import os
import hashlib
import hmac
import json
from datetime import datetime, timezone
from fastapi import Request

import razorpay
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.auth import get_db
from app.customer_auth import require_customer


from app.models import (
    Booking,
    Customer,
    CouponRedemption,
    PaymentTransaction,
    PaymentCapture,
    PaymentRefund,
    PaymentWebhookEvent,
    MembershipPaymentOrder,
)

from app.membership_payment_service import (
    process_membership_capture,
    process_membership_payment_failure,
)

router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"],
)


def get_razorpay_client():
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail="Razorpay credentials are not configured.",
        )

    return razorpay.Client(
        auth=(key_id, key_secret)
    )


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=256)



@router.post("/create-order")
def create_payment_order(
    booking_id: int,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.customer_id == customer.id,
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found.",
        )

    # Check booking status
    if booking.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="This booking is not awaiting payment.",
        )

    if booking.payment_status != "unpaid":
        raise HTTPException(
            status_code=400,
            detail="This booking does not require payment.",
        )

    # Check payment expiry
    if booking.payment_expires_at:
        expiry = booking.payment_expires_at

        # Handle timestamps without timezone information
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) >= expiry:
            raise HTTPException(
                status_code=409,
                detail="Payment time has expired. Please create a new booking.",
            )

    # Validate payment amount
    if booking.total_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid payment amount.",
        )

    amount_paise = int(booking.total_amount * 100)

    # Reuse an existing active Razorpay order
    existing = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.booking_id == booking.id,
            PaymentTransaction.status == "created",
        )
        .order_by(PaymentTransaction.id.desc())
        .first()
    )

    if existing:
        if existing.amount_paise != amount_paise:
            raise HTTPException(
                status_code=400,
                detail="Payment amount mismatch. Please contact support.",
            )

        return {
            "key_id": os.getenv("RAZORPAY_KEY_ID"),
            "order_id": existing.razorpay_order_id,
            "amount": existing.amount_paise,
            "currency": existing.currency,
            "booking_reference": booking.booking_reference,
            "payment_expires_at": booking.payment_expires_at,
        }

    client = get_razorpay_client()

    try:
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": booking.booking_reference,
            "notes": {
                "booking_id": str(booking.id),
                "customer_id": str(customer.id),
            },
        })

        transaction = PaymentTransaction(
            booking_id=booking.id,
            razorpay_order_id=order["id"],
            amount_paise=amount_paise,
            currency="INR",
            status="created",
        )

        db.add(transaction)
        db.commit()

        return {
            "key_id": os.getenv("RAZORPAY_KEY_ID"),
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "booking_reference": booking.booking_reference,
            "payment_expires_at": booking.payment_expires_at,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Unable to create Razorpay order.",
        )




@router.post("/verify")
def verify_payment(
    data: VerifyPaymentRequest,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
):
    # Read transaction reference without locking.
    transaction_ref = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.razorpay_order_id == data.razorpay_order_id
        )
        .first()
    )

    if not transaction_ref:
        raise HTTPException(404, "Payment order not found.")

    client = get_razorpay_client()

    # Verify signature and fetch payment before acquiring database locks.
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": data.razorpay_order_id,
            "razorpay_payment_id": data.razorpay_payment_id,
            "razorpay_signature": data.razorpay_signature,
        })

        payment = client.payment.fetch(data.razorpay_payment_id)

    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(400, "Invalid Razorpay payment signature.")

    except Exception:
        raise HTTPException(
            502,
            "Unable to verify payment with Razorpay.",
        )

    if payment.get("order_id") != data.razorpay_order_id:
        raise HTTPException(400, "Payment order mismatch.")

    if int(payment.get("amount", 0)) != transaction_ref.amount_paise:
        raise HTTPException(400, "Payment amount mismatch.")

    if payment.get("currency") != transaction_ref.currency:
        raise HTTPException(400, "Payment currency mismatch.")

    if payment.get("status") != "captured":
        raise HTTPException(409, "Payment is not captured yet.")

    try:
        # Lock 1: Booking.
        booking = (
            db.query(Booking)
            .filter(
                Booking.id == transaction_ref.booking_id,
                Booking.customer_id == customer.id,
            )
            .with_for_update()
            .first()
        )

        if not booking:
            raise HTTPException(404, "Booking not found.")

        # Lock 2: PaymentTransaction.
        transaction = (
            db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.id == transaction_ref.id,
                PaymentTransaction.booking_id == booking.id,
                PaymentTransaction.razorpay_order_id
                == data.razorpay_order_id,
            )
            .with_for_update()
            .first()
        )

        if not transaction:
            raise HTTPException(404, "Payment transaction not found.")

        # Check whether this exact payment was already recorded.
        existing_capture = (
            db.query(PaymentCapture)
            .filter(
                PaymentCapture.razorpay_payment_id
                == data.razorpay_payment_id
            )
            .first()
        )

        if existing_capture:
            if existing_capture.payment_transaction_id != transaction.id:
                raise HTTPException(
                    409,
                    "Payment ID is already associated with another transaction.",
                )

            db.rollback()

            return {
                "message": "Payment already recorded.",
                "booking_reference": booking.booking_reference,
                "status": booking.status,
                "payment_status": booking.payment_status,
                "capture_id": existing_capture.id,
            }

        # A new capture is allowed even if this order was paid before.
        if transaction.status not in ("created", "failed", "paid"):
            raise HTTPException(
                409,
                "Payment transaction is not eligible for capture recording.",
            )

        now = datetime.now(timezone.utc)

        # The first capture is the primary booking payment.
        is_first_capture = transaction.razorpay_payment_id is None

        capture = PaymentCapture(
            payment_transaction_id=transaction.id,
            razorpay_payment_id=data.razorpay_payment_id,
            amount_paise=int(payment["amount"]),
            currency=payment["currency"],
            status="captured",
            captured_at=now,
        )

        db.add(capture)
        db.flush()

        transaction.status = "paid"

        if is_first_capture:
            transaction.razorpay_payment_id = data.razorpay_payment_id

        expiry = booking.payment_expires_at

        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        booking_expired = expiry is not None and now >= expiry

        booking_eligible = (
            is_first_capture
            and booking.status == "pending"
            and booking.payment_status == "unpaid"
            and not booking_expired
        )

        if booking_eligible:
            booking.status = "confirmed"
            booking.payment_status = "paid"
            booking.payment_expires_at = None

            redemption = (
                db.query(CouponRedemption)
                .filter(
                    CouponRedemption.booking_id == booking.id,
                    CouponRedemption.status == "reserved",
                )
                .with_for_update()
                .first()
            )

            if redemption:
                redemption.status = "redeemed"

            db.commit()

            return {
                "message": "Payment verified successfully.",
                "booking_reference": booking.booking_reference,
                "booking_status": booking.status,
                "payment_status": booking.payment_status,
                "capture_id": capture.id,
                "capture_status": capture.status,
            }

        # Late first payment or an additional successful capture.
        # Do not reactivate a cancelled booking.
        if is_first_capture:
            if booking.status == "pending":
                booking.status = "cancelled"

            booking.payment_expires_at = None

            if booking.payment_status in ("unpaid", "failed"):
                booking.payment_status = "paid"

            redemption = (
                db.query(CouponRedemption)
                .filter(
                    CouponRedemption.booking_id == booking.id,
                    CouponRedemption.status == "reserved",
                )
                .with_for_update()
                .first()
            )

            if redemption:
                redemption.status = "released"

        # Create a separate pending refund for this capture.
        refund_record = PaymentRefund(
            payment_transaction_id=transaction.id,
            capture_id=capture.id,
            idempotency_key=f"kea-refund-capture-{capture.id}",
            amount_paise=capture.amount_paise,
            status="pending",
            reason=(
                "Payment captured after booking expiry or cancellation."
                if is_first_capture
                else "Additional payment captured for an already-paid order."
            ),
        )

        db.add(refund_record)
        db.commit()

        return {
            "message": (
                "Additional payment captured. Refund review is pending."
                if not is_first_capture
                else "Late payment captured. Refund review is pending."
            ),
            "booking_reference": booking.booking_reference,
            "booking_status": booking.status,
            "payment_status": booking.payment_status,
            "capture_id": capture.id,
            "capture_status": capture.status,
            "refund_id": refund_record.id,
            "refund_status": refund_record.status,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            500,
            "Unable to record payment capture.",
        )





@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    if not webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="Razorpay webhook secret is not configured.",
        )

    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("X-Razorpay-Event-Id")

    if not signature:
        raise HTTPException(400, "Missing webhook signature.")

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(400, "Invalid webhook signature.")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid webhook payload.")

    event_type = payload.get("event")

    if event_type not in ("payment.captured", "payment.failed"):
        return {"status": "ignored"}

    if not event_id:
        raise HTTPException(
            400,
            "Missing Razorpay webhook event ID.",
        )

    payment = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    order_id = payment.get("order_id")
    payment_id = payment.get("id")

    if not order_id or not payment_id:
        raise HTTPException(400, "Missing payment details.")

    try:
        # Step 1: Register the webhook event.
        # PostgreSQL unique constraint prevents duplicate event processing.
        event_statement = (
            pg_insert(PaymentWebhookEvent)
            .values(
                razorpay_event_id=event_id,
                event_type=event_type,
                payload_hash=hashlib.sha256(body).hexdigest(),
                status="received",
            )
            .on_conflict_do_nothing(
                index_elements=["razorpay_event_id"]
            )
            .returning(PaymentWebhookEvent.id)
        )

        event_record_id = db.execute(
            event_statement
        ).scalar_one_or_none()


        if event_record_id is None:
            db.rollback()
            return {"status": "already_processed"}

        # Step 2: Check whether this is a membership payment order.
        membership_order_ref = (
            db.query(MembershipPaymentOrder)
            .filter(
                MembershipPaymentOrder.razorpay_order_id == order_id
            )
            .first()
        )

        if membership_order_ref:
            expected_payment_status = (
                "captured"
                if event_type == "payment.captured"
                else "failed"
            )

            if payment.get("status") != expected_payment_status:
                raise HTTPException(
                    400,
                    "Payment status does not match webhook event.",
                )

            if int(payment.get("amount", 0)) != membership_order_ref.amount_paise:
                raise HTTPException(400, "Payment amount mismatch.")

            if payment.get("currency") != membership_order_ref.currency:
                raise HTTPException(400, "Payment currency mismatch.")

            # Process a failed membership payment.
            if event_type == "payment.failed":
                result_status = process_membership_payment_failure(
                    db=db,
                    payment_order_id=membership_order_ref.id,
                )

                webhook_event = (
                    db.query(PaymentWebhookEvent)
                    .filter(PaymentWebhookEvent.id == event_record_id)
                    .with_for_update()
                    .first()
                )

                webhook_event.status = "processed"
                webhook_event.processed_at = datetime.now(timezone.utc)

                db.commit()

                return {
                    "status": result_status,
                    "membership_order_id": membership_order_ref.id,
                }

            # Process a captured membership payment.
            result = process_membership_capture(
                db=db,
                payment_order_id=membership_order_ref.id,
                payment=payment,
            )

            webhook_event = (
                db.query(PaymentWebhookEvent)
                .filter(PaymentWebhookEvent.id == event_record_id)
                .with_for_update()
                .first()
            )

            webhook_event.status = "processed"
            webhook_event.processed_at = datetime.now(timezone.utc)

            db.commit()

            membership = result["membership"]
            capture = result["capture"]
            refund = result["refund"]

            if result["result"] == "activated":
                return {
                    "status": "membership_activated",
                    "membership_id": membership.id,
                    "capture_id": capture.id,
                }

            if result["result"] == "refund_pending":
                return {
                    "status": "refund_pending",
                    "capture_id": capture.id,
                    "refund_id": refund.id,
                    "refund_status": refund.status,
                }

            return {
                "status": "already_processed",
                "capture_id": capture.id,
                "membership_id": (
                    membership.id if membership else None
                ),
                "refund_id": refund.id if refund else None,
            }

        # Step 3: This is a booking payment. Keep the existing
        # booking payment processing logic unchanged.

        transaction_ref = (
            db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.razorpay_order_id == order_id
            )
            .first()
        )

        if not transaction_ref:
            raise HTTPException(
                404,
                "Payment transaction not found.",
            )

        # Step 3: Lock Booking first.
        booking = (
            db.query(Booking)
            .filter(Booking.id == transaction_ref.booking_id)
            .with_for_update()
            .first()
        )

        if not booking:
            raise HTTPException(404, "Booking not found.")

        # Step 4: Lock PaymentTransaction second.
        transaction = (
            db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.id == transaction_ref.id,
                PaymentTransaction.booking_id == booking.id,
                PaymentTransaction.razorpay_order_id == order_id,
            )
            .with_for_update()
            .first()
        )

        if not transaction:
            raise HTTPException(
                404,
                "Payment transaction not found.",
            )

       # Step 5: Validate payment details.
        expected_payment_status = (
            "captured"
            if event_type == "payment.captured"
            else "failed"
        )

        if payment.get("status") != expected_payment_status:
            raise HTTPException(
                400,
                "Payment status does not match webhook event."
            )

        if int(payment.get("amount", 0)) != transaction.amount_paise:
            raise HTTPException(400, "Payment amount mismatch.")

        if payment.get("currency") != transaction.currency:
            raise HTTPException(400, "Payment currency mismatch.")

        # Step 5A: Handle failed payment attempts.
        if event_type == "payment.failed":

            # Never downgrade a successfully paid transaction.
            if (
                transaction.status == "paid"
                or transaction.razorpay_payment_id is not None
            ):
                result_status = "ignored_already_paid"

            elif transaction.status in ("created", "failed"):
                transaction.status = "failed"
                result_status = "payment_failed"

            else:
                raise HTTPException(
                    409,
                    "Invalid transaction status for failed payment."
                )

            # Do not cancel the booking here.
            # The original 10-minute expiry remains unchanged.
            # The customer can retry payment while the booking is pending.

            webhook_event = (
                db.query(PaymentWebhookEvent)
                .filter(PaymentWebhookEvent.id == event_record_id)
                .with_for_update()
                .first()
            )

            webhook_event.status = "processed"
            webhook_event.processed_at = datetime.now(timezone.utc)

            db.commit()

            return {
                "status": result_status,
                "booking_reference": booking.booking_reference,
                "booking_status": booking.status,
                "payment_status": booking.payment_status,
                "transaction_status": transaction.status,
            }

        # Step 6: Check whether this exact payment was already recorded.
        existing_capture = (
            db.query(PaymentCapture)
            .filter(
                PaymentCapture.razorpay_payment_id == payment_id
            )
            .first()
        )

        if existing_capture:
            if existing_capture.payment_transaction_id != transaction.id:
                raise HTTPException(
                    409,
                    "Payment ID belongs to another transaction.",
                )

            webhook_event = (
                db.query(PaymentWebhookEvent)
                .filter(PaymentWebhookEvent.id == event_record_id)
                .with_for_update()
                .first()
            )

            webhook_event.status = "processed"
            webhook_event.processed_at = datetime.now(timezone.utc)

            db.commit()

            return {"status": "already_processed"}

        if transaction.status not in ("created", "failed", "paid"):
            raise HTTPException(
                409,
                "Invalid payment transaction status.",
            )

        now = datetime.now(timezone.utc)

        # Step 7: Determine whether this is the first capture.
        is_first_capture = transaction.razorpay_payment_id is None

        capture = PaymentCapture(
            payment_transaction_id=transaction.id,
            razorpay_payment_id=payment_id,
            amount_paise=int(payment["amount"]),
            currency=payment["currency"],
            status="captured",
            captured_at=now,
        )

        db.add(capture)
        db.flush()

        transaction.status = "paid"

        # Preserve the original payment ID as the primary payment.
        if is_first_capture:
            transaction.razorpay_payment_id = payment_id

        # Step 8: Determine booking eligibility.
        expiry = booking.payment_expires_at

        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        booking_expired = expiry is not None and now >= expiry

        booking_eligible = (
            is_first_capture
            and booking.status == "pending"
            and booking.payment_status == "unpaid"
            and not booking_expired
        )

        if booking_eligible:
            booking.status = "confirmed"
            booking.payment_status = "paid"
            booking.payment_expires_at = None

            redemption = (
                db.query(CouponRedemption)
                .filter(
                    CouponRedemption.booking_id == booking.id,
                    CouponRedemption.status == "reserved",
                )
                .with_for_update()
                .first()
            )

            if redemption:
                redemption.status = "redeemed"

            result_status = "processed"

        else:
            # Late first payment: do not reactivate cancelled bookings.
            if is_first_capture:
                if booking.status == "pending":
                    booking.status = "cancelled"

                booking.payment_expires_at = None

                if booking.payment_status in ("unpaid", "failed"):
                    booking.payment_status = "paid"

                redemption = (
                    db.query(CouponRedemption)
                    .filter(
                        CouponRedemption.booking_id == booking.id,
                        CouponRedemption.status == "reserved",
                    )
                    .with_for_update()
                    .first()
                )

                if redemption:
                    redemption.status = "released"

            # Every late or additional capture gets its own refund.
            refund_record = PaymentRefund(
                payment_transaction_id=transaction.id,
                capture_id=capture.id,
                idempotency_key=f"kea-refund-capture-{capture.id}",
                amount_paise=capture.amount_paise,
                status="pending",
                reason=(
                    "Late payment captured after booking expiry or cancellation."
                    if is_first_capture
                    else "Additional payment captured for an already-paid order."
                ),
            )

            db.add(refund_record)
            result_status = "refund_pending"

        # Step 9: Mark this webhook event processed.
        webhook_event = (
            db.query(PaymentWebhookEvent)
            .filter(PaymentWebhookEvent.id == event_record_id)
            .with_for_update()
            .first()
        )

        webhook_event.status = "processed"
        webhook_event.processed_at = now

        db.commit()

        return {
            "status": result_status,
            "booking_reference": booking.booking_reference,
            "booking_status": booking.status,
            "payment_status": booking.payment_status,
            "capture_id": capture.id,
            "capture_status": capture.status,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            500,
            "Unable to process payment webhook.",
        )
