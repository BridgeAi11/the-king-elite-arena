
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
from app.membership_payment_service import process_membership_capture
from app.payment_routes import get_razorpay_client

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field



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
    # Find the order belonging to the authenticated customer.
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
        raise HTTPException(
            status_code=404,
            detail="Membership payment order not found.",
        )

    client = get_razorpay_client()

    # Verify Razorpay signature and fetch the payment.
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": data.razorpay_order_id,
            "razorpay_payment_id": data.razorpay_payment_id,
            "razorpay_signature": data.razorpay_signature,
        })

        payment = client.payment.fetch(data.razorpay_payment_id)

    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay payment signature.",
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Unable to verify membership payment with Razorpay.",
        )

    try:
        result = process_membership_capture(
            db=db,
            payment_order_id=order_ref.id,
            payment=payment,
        )

        db.commit()

        membership = result["membership"]
        capture = result["capture"]
        refund = result["refund"]

        if result["result"] == "already_processed":
            return {
                "message": "Membership payment already processed.",
                "membership_id": (
                    membership.id if membership else None
                ),
                "membership_status": (
                    membership.status if membership else None
                ),
                "capture_id": capture.id,
                "refund_id": refund.id if refund else None,
                "refund_status": refund.status if refund else None,
            }

        if result["result"] == "refund_pending":
            return {
                "message": (
                    "Payment captured, but the membership order "
                    "was not activated. Refund review is pending."
                ),
                "membership_id": None,
                "capture_id": capture.id,
                "capture_status": capture.status,
                "refund_id": refund.id,
                "refund_status": refund.status,
            }

        return {
            "message": "Membership payment verified successfully.",
            "membership_id": membership.id,
            "membership_name": membership.plan_name,
            "membership_status": membership.status,
            "start_date": membership.start_date.isoformat(),
            "expiry_date": membership.expiry_date.isoformat(),
            "total_hours": float(membership.total_hours),
            "capture_id": capture.id,
            "capture_status": capture.status,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to process membership payment.",
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
