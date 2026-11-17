
import os
import requests
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Booking,
    PaymentTransaction,
    PaymentCapture,
    PaymentRefund,
)


RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"


def get_razorpay_credentials():
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        return None, None

    return key_id, key_secret




def get_refund_records(refund_id: int, db: Session):
    """
    Lock records in this order:
    Booking -> PaymentTransaction -> PaymentCapture -> PaymentRefund.
    """

    # Read refund reference without locking.
    refund_ref = (
        db.query(PaymentRefund)
        .filter(PaymentRefund.id == refund_id)
        .first()
    )

    if not refund_ref:
        return None, None, None, None

    transaction_ref = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.id
            == refund_ref.payment_transaction_id
        )
        .first()
    )

    if not transaction_ref:
        return None, None, None, None

    # Lock 1: Booking.
    booking = (
        db.query(Booking)
        .filter(Booking.id == transaction_ref.booking_id)
        .with_for_update()
        .first()
    )

    if not booking:
        return None, None, None, None

    # Lock 2: PaymentTransaction.
    transaction = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.id == transaction_ref.id,
            PaymentTransaction.booking_id == booking.id,
        )
        .with_for_update()
        .first()
    )

    if not transaction:
        return None, None, None, None

    if refund_ref.capture_id is None:
        return None, transaction, booking, None

    # Lock 3: PaymentCapture.
    capture = (
        db.query(PaymentCapture)
        .filter(
            PaymentCapture.id == refund_ref.capture_id,
            PaymentCapture.payment_transaction_id == transaction.id,
        )
        .with_for_update()
        .first()
    )

    if not capture:
        return None, transaction, booking, None

    # Lock 4: PaymentRefund.
    refund = (
        db.query(PaymentRefund)
        .filter(
            PaymentRefund.id == refund_id,
            PaymentRefund.payment_transaction_id == transaction.id,
            PaymentRefund.capture_id == capture.id,
        )
        .with_for_update()
        .first()
    )

    if not refund:
        return None, transaction, booking, capture

    return refund, transaction, booking, capture


def mark_full_refund_processed(
    refund: PaymentRefund,
    transaction: PaymentTransaction,
    booking: Booking,
    capture: PaymentCapture,
):
    """
    Mark only the selected capture as refunded.
    Do not mark the booking refunded when an extra capture
    is refunded and the original payment remains successful.
    """

    if refund.amount_paise != capture.amount_paise:
        raise ValueError("Refund amount is not a full capture refund.")

    refund.status = "processed"
    capture.status = "refunded"

    # Only refund the booking if its primary payment was refunded.
    if capture.razorpay_payment_id == transaction.razorpay_payment_id:
        booking.payment_status = "refunded"



def process_refund(refund_id: int, db: Session):
    """
    Process a full capture refund through Razorpay.

    Uses the capture-specific payment ID, amount and
    persisted idempotency key.
    """

    try:
        # Phase 1: Lock records and claim the refund.
        refund, transaction, booking, capture = get_refund_records(
            refund_id, db
        )

        if not refund:
            db.rollback()
            return {"status": "not_found"}

        if not transaction or not booking:
            db.rollback()
            return {"status": "payment_not_confirmed"}

        if not capture:
            db.rollback()
            return {"status": "capture_not_found"}

        if refund.status == "processed":
            if refund.amount_paise != capture.amount_paise:
                db.rollback()
                return {"status": "invalid_refund_amount"}

            mark_full_refund_processed(
                refund, transaction, booking, capture
            )
            db.commit()
            return {"status": "already_processed"}

        if refund.status not in ("pending", "processing"):
            db.rollback()
            return {"status": refund.status}

        if capture.status == "refunded":
            db.rollback()
            return {"status": "already_refunded"}

        if transaction.status != "paid":
            db.rollback()
            return {"status": "payment_not_confirmed"}

        if not capture.razorpay_payment_id:
            db.rollback()
            return {"status": "missing_payment_id"}

        if (
            refund.amount_paise <= 0
            or refund.amount_paise != capture.amount_paise
        ):
            db.rollback()
            return {
                "status": "invalid_refund_amount",
                "message": "Only full capture refunds are supported.",
            }

        if not refund.idempotency_key:
            db.rollback()
            return {"status": "missing_idempotency_key"}

        now = datetime.now(timezone.utc)

        if refund.status == "processing":
            started_at = refund.processing_started_at

            if started_at is None:
                db.rollback()
                return {"status": "processing"}

            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            if now - started_at < timedelta(minutes=2):
                db.rollback()
                return {"status": "processing"}

        key_id, key_secret = get_razorpay_credentials()

        if not key_id or not key_secret:
            db.rollback()
            return {"status": "credentials_not_configured"}

        # Save capture-specific request details before releasing locks.
        payment_id = capture.razorpay_payment_id
        amount_paise = capture.amount_paise
        idempotency_key = refund.idempotency_key

        refund.status = "processing"
        refund.processing_started_at = now
        db.commit()

        # Phase 2: Call Razorpay outside database locks.
        url = (
            f"{RAZORPAY_BASE_URL}/payments/"
            f"{payment_id}/refund"
        )

        payload = {
            "amount": amount_paise,
            "speed": "normal",
            "receipt": f"KEA-REFUND-{refund_id}",
        }

        headers = {
            "Content-Type": "application/json",
            "X-Refund-Idempotency": idempotency_key,
        }

        try:
            response = requests.post(
                url,
                auth=(key_id, key_secret),
                headers=headers,
                json=payload,
                timeout=20,
            )
        except requests.RequestException:
            return {
                "status": "processing",
                "message": "Razorpay response not received. Reconciliation required.",
            }

        if (
            response.status_code in (408, 409, 425, 429)
            or response.status_code >= 500
        ):
            return {
                "status": "processing",
                "message": "Temporary or ambiguous Razorpay response. Reconciliation required.",
            }

        if not response.ok:
            final_status = "failed"
            razorpay_refund_id = None
        else:
            try:
                result = response.json()
            except ValueError:
                return {
                    "status": "processing",
                    "message": "Invalid Razorpay response. Reconciliation required.",
                }

            razorpay_refund_id = result.get("id")
            razorpay_status = result.get("status")

            if (
                not razorpay_refund_id
                or razorpay_status not in (
                    "created", "pending", "processed", "failed"
                )
                or int(result.get("amount", 0)) != amount_paise
                or result.get("payment_id") != payment_id
            ):
                return {
                    "status": "processing",
                    "message": "Unexpected Razorpay response. Reconciliation required.",
                }

            if razorpay_status == "processed":
                final_status = "processed"
            elif razorpay_status == "failed":
                final_status = "failed"
            else:
                final_status = "pending"

        # Phase 3: Re-lock and save the result.
        refund, transaction, booking, capture = get_refund_records(
            refund_id, db
        )

        if not refund or not transaction or not booking or not capture:
            db.rollback()
            return {
                "status": "processing",
                "message": "Unable to save refund result. Reconciliation required.",
            }

        if refund.status == "processed":
            db.rollback()
            return {"status": "already_processed"}

        if refund.status != "processing":
            db.rollback()
            return {"status": refund.status}

        if (
            capture.razorpay_payment_id != payment_id
            or capture.amount_paise != amount_paise
            or refund.amount_paise != amount_paise
        ):
            db.rollback()
            return {
                "status": "processing",
                "message": "Capture details changed. Manual reconciliation required.",
            }

        if razorpay_refund_id:
            refund.razorpay_refund_id = razorpay_refund_id

        refund.processing_started_at = None

        if final_status == "processed":
            mark_full_refund_processed(
                refund, transaction, booking, capture
            )
        else:
            refund.status = final_status

        db.commit()

        return {
            "status": refund.status,
            "razorpay_refund_id": refund.razorpay_refund_id,
        }

    except Exception:
        db.rollback()
        raise




def check_refund_status(refund_id: int, db: Session):
    """
    Reconcile a capture-specific refund with Razorpay.

    Never downgrade a locally processing refund based on
    a stale pending/created response.
    """

    try:
        # Phase 1: Read and validate local records.
        refund, transaction, booking, capture = get_refund_records(
            refund_id, db
        )

        if not refund:
            db.rollback()
            return {"status": "not_found"}

        if not transaction or not booking:
            db.rollback()
            return {"status": "payment_not_confirmed"}

        if not capture:
            db.rollback()
            return {"status": "capture_not_found"}

        if refund.status == "processed":
            if refund.amount_paise != capture.amount_paise:
                db.rollback()
                return {"status": "invalid_refund_amount"}

            mark_full_refund_processed(
                refund, transaction, booking, capture
            )
            db.commit()

            return {
                "status": "processed",
                "razorpay_refund_id": refund.razorpay_refund_id,
            }

        if not refund.razorpay_refund_id:
            current_status = refund.status
            db.rollback()
            return {
                "status": current_status,
                "message": "Razorpay refund has not been created yet.",
            }

        if refund.amount_paise != capture.amount_paise:
            db.rollback()
            return {"status": "invalid_refund_amount"}

        # Save values before releasing database locks.
        razorpay_refund_id = refund.razorpay_refund_id
        payment_id = capture.razorpay_payment_id
        amount_paise = capture.amount_paise
        currency = capture.currency

        db.rollback()

        key_id, key_secret = get_razorpay_credentials()

        if not key_id or not key_secret:
            return {"status": "credentials_not_configured"}

        # Phase 2: Fetch status outside database locks.
        url = (
            f"{RAZORPAY_BASE_URL}/refunds/"
            f"{razorpay_refund_id}"
        )

        response = requests.get(
            url,
            auth=(key_id, key_secret),
            timeout=20,
        )

        if not response.ok:
            return {
                "status": "pending",
                "message": "Unable to fetch refund status. Try again later.",
            }

        try:
            result = response.json()
        except ValueError:
            return {
                "status": "pending",
                "message": "Invalid Razorpay response.",
            }

        razorpay_status = result.get("status")

        # Verify that Razorpay returned the expected refund.
        if (
            result.get("id") != razorpay_refund_id
            or result.get("payment_id") != payment_id
            or int(result.get("amount", 0)) != amount_paise
            or (
                result.get("currency")
                and result.get("currency") != currency
            )
            or razorpay_status not in (
                "created", "pending", "processed", "failed"
            )
        ):
            return {
                "status": "pending",
                "message": "Razorpay refund details could not be verified.",
            }

        # Phase 3: Re-lock and reconcile.
        refund, transaction, booking, capture = get_refund_records(
            refund_id, db
        )

        if not refund or not transaction or not booking or not capture:
            db.rollback()
            return {
                "status": "pending",
                "message": "Unable to reconcile local refund records.",
            }

        # Do not overwrite a completed refund.
        if refund.status == "processed":
            db.rollback()
            return {
                "status": "processed",
                "razorpay_refund_id": razorpay_refund_id,
            }

        # Ensure the refund still refers to the same capture.
        if (
            refund.razorpay_refund_id != razorpay_refund_id
            or capture.razorpay_payment_id != payment_id
            or capture.amount_paise != amount_paise
            or refund.amount_paise != amount_paise
        ):
            db.rollback()
            return {
                "status": "pending",
                "message": "Refund details changed. Manual reconciliation required.",
            }

        if razorpay_status == "processed":
            mark_full_refund_processed(
                refund, transaction, booking, capture
            )

        elif razorpay_status == "failed":
            refund.status = "failed"
            refund.processing_started_at = None

        elif razorpay_status in ("created", "pending"):
            # Preserve an active processing claim.
            if refund.status != "processing":
                refund.status = "pending"

        db.commit()

        return {
            "status": refund.status,
            "razorpay_refund_id": refund.razorpay_refund_id,
        }

    except requests.RequestException:
        db.rollback()
        return {
            "status": "pending",
            "message": "Unable to contact Razorpay. Try again later.",
        }

    except Exception:
        db.rollback()
        raise
