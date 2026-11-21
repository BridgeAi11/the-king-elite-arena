
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    CustomerMembership,
    MembershipPaymentOrder,
    MembershipPaymentCapture,
    MembershipPaymentRefund,
    MembershipTransaction,
    PaymentCapture,
    PaymentTransaction,
)


def _lock_membership_order(
    db: Session,
    payment_order_id: int,
):
    """
    Lock the customer first and membership order second.
    Both /verify and webhook must use this lock order.
    """
    order_ref = (
        db.query(MembershipPaymentOrder)
        .filter(MembershipPaymentOrder.id == payment_order_id)
        .first()
    )

    if not order_ref:
        raise HTTPException(404, "Membership payment order not found.")

    customer = (
        db.query(Customer)
        .filter(Customer.id == order_ref.customer_id)
        .with_for_update()
        .first()
    )

    if not customer:
        raise HTTPException(404, "Customer not found.")

    payment_order = (
        db.query(MembershipPaymentOrder)
        .filter(
            MembershipPaymentOrder.id == payment_order_id,
            MembershipPaymentOrder.customer_id == customer.id,
        )
        .with_for_update()
        .first()
    )

    if not payment_order:
        raise HTTPException(404, "Membership payment order not found.")

    return customer, payment_order


def process_membership_capture(
    db: Session,
    payment_order_id: int,
    payment: dict,
):
    """
    Shared capture processing for customer verification and webhook.

    This function does not commit. The caller commits the capture,
    membership, refund-review record, and webhook event together.
    """
    customer, payment_order = _lock_membership_order(
        db,
        payment_order_id,
    )

    payment_id = payment.get("id")

    if not payment_id:
        raise HTTPException(400, "Missing Razorpay payment ID.")

    if payment.get("order_id") != payment_order.razorpay_order_id:
        raise HTTPException(400, "Payment order mismatch.")

    if int(payment.get("amount", 0)) != payment_order.amount_paise:
        raise HTTPException(400, "Payment amount mismatch.")

    if payment.get("currency") != payment_order.currency:
        raise HTTPException(400, "Payment currency mismatch.")

    if payment.get("status") != "captured":
        raise HTTPException(409, "Membership payment is not captured.")

    # Idempotency: the same payment ID must never create another membership.
    existing_capture = (
        db.query(MembershipPaymentCapture)
        .filter(
            MembershipPaymentCapture.razorpay_payment_id == payment_id
        )
        .first()
    )

    if existing_capture:
        if (
            existing_capture.membership_payment_order_id
            != payment_order.id
        ):
            raise HTTPException(
                409,
                "Payment ID is already associated with another membership order.",
            )

        existing_membership = None

        if payment_order.membership_id:
            existing_membership = (
                db.query(CustomerMembership)
                .filter(
                    CustomerMembership.id == payment_order.membership_id
                )
                .first()
            )

        existing_refund = (
            db.query(MembershipPaymentRefund)
            .filter(
                MembershipPaymentRefund.capture_id == existing_capture.id
            )
            .first()
        )

        return {
            "result": "already_processed",
            "membership": existing_membership,
            "capture": existing_capture,
            "refund": existing_refund,
        }

    # Prevent reuse of a booking payment ID for a membership payment.
        # Protect successful membership payments created before the
    # membership capture table was introduced.
    if (
        payment_order.status == "paid"
        and payment_order.razorpay_payment_id == payment_id
    ):
        existing_membership = (
            db.query(CustomerMembership)
            .filter(
                CustomerMembership.id == payment_order.membership_id
            )
            .first()
        )

        if not existing_membership:
            raise HTTPException(
                409,
                "Previously paid membership order has no membership record.",
            )

        legacy_capture = MembershipPaymentCapture(
            membership_payment_order_id=payment_order.id,
            razorpay_payment_id=payment_id,
            amount_paise=int(payment["amount"]),
            currency=payment["currency"],
            status="captured",
            captured_at=datetime.now(timezone.utc),
        )

        db.add(legacy_capture)
        db.flush()

        return {
            "result": "already_processed",
            "membership": existing_membership,
            "capture": legacy_capture,
            "refund": None,
        }

    # Check the membership orders table for payment ID reuse.
    existing_membership_order = (
        db.query(MembershipPaymentOrder)
        .filter(
            MembershipPaymentOrder.razorpay_payment_id == payment_id,
            MembershipPaymentOrder.id != payment_order.id,
        )
        .first()
    )

    if existing_membership_order:
        raise HTTPException(
            409,
            "Payment ID is already associated with another membership order.",
        )

    # Also check the primary payment ID on historical booking transactions.
    booking_transaction = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.razorpay_payment_id == payment_id
        )
        .first()
    )

    if booking_transaction:
        raise HTTPException(
            409,
            "Payment ID is already associated with a booking transaction.",
        )

    booking_capture = (
        db.query(PaymentCapture)
        .filter(PaymentCapture.razorpay_payment_id == payment_id)
        .first()
    )

    if booking_capture:
        raise HTTPException(
            409,
            "This Razorpay payment ID is already associated with a booking.",
        )

    if payment_order.status not in ("created", "failed", "paid"):
        raise HTTPException(
            409,
            "Membership payment order is not eligible for capture processing.",
        )

    now = datetime.now(timezone.utc)

    capture = MembershipPaymentCapture(
        membership_payment_order_id=payment_order.id,
        razorpay_payment_id=payment_id,
        amount_paise=int(payment["amount"]),
        currency=payment["currency"],
        status="captured",
        captured_at=now,
    )

    db.add(capture)
    db.flush()

    # Only a previously created order can activate a membership.
    if payment_order.status == "created":
        latest_membership = (
            db.query(CustomerMembership)
            .filter(
                CustomerMembership.customer_id == customer.id,
                CustomerMembership.status.in_(["active", "scheduled"]),
                CustomerMembership.expiry_date > now,
            )
            .order_by(CustomerMembership.expiry_date.desc())
            .first()
        )

        start_date = (
            latest_membership.expiry_date
            if latest_membership
            else now
        )

        expiry_date = start_date + timedelta(
            days=payment_order.validity_days_snapshot
        )

        membership_status = (
            "active" if start_date <= now else "scheduled"
        )

        membership = CustomerMembership(
            plan_id=payment_order.plan_id,
            customer_id=customer.id,
            customer_name=customer.full_name,
            customer_phone=customer.phone,
            plan_name=payment_order.plan_name_snapshot,
            amount_paid=payment_order.plan_price_snapshot,
            total_hours=payment_order.included_hours_snapshot,
            used_hours=0,
            reserved_hours=0,
            start_date=start_date,
            expiry_date=expiry_date,
            status=membership_status,
        )

        db.add(membership)
        db.flush()

        transaction = MembershipTransaction(
            membership_id=membership.id,
            amount=payment_order.plan_price_snapshot,
            payment_method="razorpay",
            payment_status="paid",
            transaction_reference=payment_id,
        )

        db.add(transaction)

        payment_order.razorpay_payment_id = payment_id
        payment_order.membership_id = membership.id
        payment_order.status = "paid"

        db.flush()

        return {
            "result": "activated",
            "membership": membership,
            "capture": capture,
            "refund": None,
        }

    # Failed orders and already-paid orders must never activate another
    # membership from a subsequent capture.
    if payment_order.status == "failed":
        reason = (
            "Payment captured after membership order was marked failed. "
            "Manual refund review required."
        )
    else:
        reason = (
            "Additional payment captured for an already-paid membership order. "
            "Manual refund review required."
        )

    refund = MembershipPaymentRefund(
        membership_payment_order_id=payment_order.id,
        capture_id=capture.id,
        idempotency_key=f"kea-membership-refund-capture-{capture.id}",
        amount_paise=capture.amount_paise,
        status="pending",
        reason=reason,
    )

    db.add(refund)
    db.flush()

    return {
        "result": "refund_pending",
        "membership": None,
        "capture": capture,
        "refund": refund,
    }


def process_membership_payment_failure(
    db: Session,
    payment_order_id: int,
):
    """
    Mark an unpaid membership order as failed.

    Never downgrade a paid order.
    """
    _, payment_order = _lock_membership_order(
        db,
        payment_order_id,
    )

    if payment_order.status == "paid":
        return "ignored_already_paid"

    if payment_order.status == "failed":
        return "payment_failed"

    if payment_order.status != "created":
        raise HTTPException(
            409,
            "Membership order cannot be marked as failed.",
        )

    payment_order.status = "failed"
    db.flush()

    return "payment_failed"
