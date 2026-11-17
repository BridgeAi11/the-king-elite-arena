
import os
import uuid

import razorpay

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_db
from app.customer_auth import require_customer
from app.models import (
    Customer,
    CustomerMembership,
    MembershipPlan,
    MembershipPaymentOrder,
    MembershipTransaction,
)
from app.payment_routes import get_razorpay_client

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from app.models import MembershipTransaction


router = APIRouter(
    prefix="/api/membership-payments",
    tags=["Membership Payments"],
)

class VerifyMembershipPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=256)


@router.post("/verify")
def verify_membership_payment(
    data: VerifyMembershipPaymentRequest,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
):
    # Find the membership payment order.
    order_ref = (
        db.query(MembershipPaymentOrder)
        .filter(
            MembershipPaymentOrder.razorpay_order_id
            == data.razorpay_order_id,
            MembershipPaymentOrder.customer_id == customer.id,
        )
        .first()
    )

    if not order_ref:
        raise HTTPException(404, "Membership payment order not found.")

    client = get_razorpay_client()

    # Verify Razorpay signature and fetch payment details.
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
            "Unable to verify membership payment with Razorpay.",
        )

    if payment.get("order_id") != data.razorpay_order_id:
        raise HTTPException(400, "Payment order mismatch.")

    if int(payment.get("amount", 0)) != order_ref.amount_paise:
        raise HTTPException(400, "Payment amount mismatch.")

    if payment.get("currency") != order_ref.currency:
        raise HTTPException(400, "Payment currency mismatch.")

    if payment.get("status") != "captured":
        raise HTTPException(409, "Membership payment is not captured.")

    try:
        # Lock the customer first. This serializes purchases
        # when a customer verifies multiple membership payments.
        locked_customer = (
            db.query(Customer)
            .filter(Customer.id == customer.id)
            .with_for_update()
            .first()
        )

        if not locked_customer:
            raise HTTPException(404, "Customer not found.")

        # Lock the payment order.
        payment_order = (
            db.query(MembershipPaymentOrder)
            .filter(
                MembershipPaymentOrder.id == order_ref.id,
                MembershipPaymentOrder.customer_id == customer.id,
            )
            .with_for_update()
            .first()
        )

        if not payment_order:
            raise HTTPException(404, "Membership order not found.")

        # Idempotency: never create the same membership twice.
        if payment_order.status == "paid":
            existing_membership = (
                db.query(CustomerMembership)
                .filter(
                    CustomerMembership.id == payment_order.membership_id
                )
                .first()
            )

            if existing_membership:
                db.rollback()
                return {
                    "message": "Membership payment already processed.",
                    "membership_id": existing_membership.id,
                    "membership_status": existing_membership.status,
                    "start_date": existing_membership.start_date.isoformat(),
                    "expiry_date": existing_membership.expiry_date.isoformat(),
                }

            raise HTTPException(
                409,
                "Payment is marked paid but membership record is missing.",
            )

        if payment_order.status != "created":
            raise HTTPException(409, "Membership order is not payable.")

        # Check whether this payment ID was already used.
        duplicate_payment = (
            db.query(MembershipPaymentOrder)
            .filter(
                MembershipPaymentOrder.razorpay_payment_id
                == data.razorpay_payment_id
            )
            .first()
        )

        if duplicate_payment:
            raise HTTPException(
                409,
                "This Razorpay payment is already associated with an order.",
            )

        now = datetime.now(timezone.utc)

        # Find the latest unexpired active or scheduled membership.
        latest_membership = (
            db.query(CustomerMembership)
            .filter(
                CustomerMembership.customer_phone
                == locked_customer.phone,
                CustomerMembership.status.in_(["active", "scheduled"]),
                CustomerMembership.expiry_date > now,
            )
            .order_by(CustomerMembership.expiry_date.desc())
            .first()
        )

        if latest_membership:
            start_date = latest_membership.expiry_date
        else:
            start_date = now

        expiry_date = start_date + timedelta(
            days=payment_order.validity_days_snapshot
        )

        membership_status = (
            "active" if start_date <= now else "scheduled"
        )

        # Create the membership using purchased plan snapshots.
        membership = CustomerMembership(
            plan_id=payment_order.plan_id,
            customer_name=locked_customer.full_name,
            customer_phone=locked_customer.phone,
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

        # Record successful membership payment.
        transaction = MembershipTransaction(
            membership_id=membership.id,
            amount=payment_order.plan_price_snapshot,
            payment_method="razorpay",
            payment_status="paid",
            transaction_reference=data.razorpay_payment_id,
        )

        db.add(transaction)

        payment_order.razorpay_payment_id = data.razorpay_payment_id
        payment_order.membership_id = membership.id
        payment_order.status = "paid"

        db.commit()
        db.refresh(membership)

        return {
            "message": "Membership payment verified successfully.",
            "membership_id": membership.id,
            "membership_name": membership.plan_name,
            "membership_status": membership.status,
            "start_date": membership.start_date.isoformat(),
            "expiry_date": membership.expiry_date.isoformat(),
            "total_hours": float(membership.total_hours),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            500,
            "Unable to activate membership after payment.",
        )


@router.post("/create-order")
def create_membership_payment_order(
    plan_id: int,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
):
    try:
        # Only active membership plans can be purchased.
        plan = (
            db.query(MembershipPlan)
            .filter(
                MembershipPlan.id == plan_id,
                MembershipPlan.is_active.is_(True),
            )
            .first()
        )

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="Membership plan not found or inactive.",
            )

        # Razorpay checkout currently supports paid memberships only.
        if plan.price <= 0:
            raise HTTPException(
                status_code=400,
                detail="Free membership plans cannot use Razorpay checkout.",
            )

        amount_paise = int(plan.price * 100)

        # Reuse an existing order if its plan snapshot still matches.
        existing_order = (
            db.query(MembershipPaymentOrder)
            .filter(
                MembershipPaymentOrder.customer_id == customer.id,
                MembershipPaymentOrder.plan_id == plan.id,
                MembershipPaymentOrder.status == "created",
                MembershipPaymentOrder.amount_paise == amount_paise,
                MembershipPaymentOrder.plan_name_snapshot == plan.name,
                MembershipPaymentOrder.validity_days_snapshot
                == plan.validity_days,
                MembershipPaymentOrder.included_hours_snapshot
                == plan.included_hours,
            )
            .order_by(MembershipPaymentOrder.id.desc())
            .first()
        )

        if existing_order:
            return {
                "key_id": os.getenv("RAZORPAY_KEY_ID"),
                "order_id": existing_order.razorpay_order_id,
                "amount": existing_order.amount_paise,
                "currency": existing_order.currency,
                "plan_name": existing_order.plan_name_snapshot,
            }

        client = get_razorpay_client()

        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"kea-mem-{uuid.uuid4().hex[:20]}",
            "notes": {
                "customer_id": str(customer.id),
                "plan_id": str(plan.id),
                "order_type": "membership",
            },
        })

        payment_order = MembershipPaymentOrder(
            customer_id=customer.id,
            plan_id=plan.id,
            razorpay_order_id=order["id"],
            amount_paise=amount_paise,
            currency="INR",
            plan_name_snapshot=plan.name,
            plan_price_snapshot=plan.price,
            validity_days_snapshot=plan.validity_days,
            included_hours_snapshot=plan.included_hours,
            status="created",
        )

        db.add(payment_order)
        db.commit()
        db.refresh(payment_order)

        return {
            "key_id": os.getenv("RAZORPAY_KEY_ID"),
            "order_id": payment_order.razorpay_order_id,
            "amount": payment_order.amount_paise,
            "currency": payment_order.currency,
            "plan_name": payment_order.plan_name_snapshot,
        }

    except HTTPException:
        db.rollback()
        raise

    except razorpay.errors.RazorpayError:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Unable to create Razorpay membership order.",
        )

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create membership payment order.",
        )
