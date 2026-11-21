
import base64
import hashlib
import hmac
import io
import os
import uuid

import qrcode

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_db
from app.customer_auth import require_customer

from app.models import (
    AccessCredential,
    Booking,
    Customer,
    CustomerMembership,
    MembershipTransaction,
)


router = APIRouter(
    prefix="/api/access",
    tags=["Access QR Codes"]
)


# --------------------------------------------------
# Generate a secure signature for the QR credential
# --------------------------------------------------

def _sign(credential_id: str) -> str:

    secret = os.getenv("ACCESS_QR_SECRET")

    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="QR security secret is not configured."
        )

    return hmac.new(
        secret.encode(),
        credential_id.encode(),
        hashlib.sha256
    ).hexdigest()


# --------------------------------------------------
# Convert QR payload into PNG data URL
# --------------------------------------------------

def _qr_response(credential, kind: str):

    signature = _sign(credential.id)

    token = f"{credential.id}.{signature}"

    api_base = os.getenv(
        "PUBLIC_API_URL",
        "http://127.0.0.1:8000"
    ).rstrip("/")

    payload = (
        f"{api_base}/api/access/validate?token={token}"
    )

    image = qrcode.make(payload)

    buffer = io.BytesIO()

    image.save(buffer, format="PNG")

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return {
        "credential_id": credential.id,
        "credential_type": kind,
        "qr_data_url": (
            f"data:image/png;base64,{encoded}"
        ),
        "qr_payload": payload,
        "created_at": (
            credential.created_at.isoformat()
            if credential.created_at else None
        )
    }


# --------------------------------------------------
# Get existing credential or create a new one
# --------------------------------------------------

def _get_or_create(
    db: Session,
    customer_id: int,
    entity_type: str,
    entity_id: int
):

    credential = (
        db.query(AccessCredential)
        .filter(
            AccessCredential.entity_type == entity_type,
            AccessCredential.entity_id == entity_id
        )
        .with_for_update()
        .first()
    )

    if credential and credential.customer_id != customer_id:
        raise HTTPException(
            status_code=404,
            detail="Access credential not found."
        )

    if credential and credential.revoked_at:
        raise HTTPException(
            status_code=410,
            detail="This QR credential has been revoked."
        )

    if not credential:

        credential = AccessCredential(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            entity_type=entity_type,
            entity_id=entity_id
        )

        db.add(credential)
        db.flush()

    return credential


# --------------------------------------------------
# BOOKING QR GENERATION
# --------------------------------------------------

@router.get("/booking/{booking_id}/qr")
def get_booking_qr(
    booking_id: int,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db)
):

    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.customer_id == customer.id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found."
        )

    # QR only after successful payment

    if (
        booking.status != "confirmed"
        or booking.payment_status != "paid"
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "QR is available only after "
                "successful booking payment."
            )
        )

    credential = _get_or_create(
        db,
        customer.id,
        "booking",
        booking.id
    )

    db.commit()
    db.refresh(credential)

    return {
        **_qr_response(credential, "booking"),
        "booking_reference": booking.booking_reference
    }


# --------------------------------------------------
# MEMBERSHIP QR GENERATION
# --------------------------------------------------

@router.get("/membership/{membership_id}/qr")
def get_membership_qr(
    membership_id: int,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db)
):

    membership = (
        db.query(CustomerMembership)
        .filter(
            CustomerMembership.id == membership_id,
            CustomerMembership.customer_id == customer.id        )
        .with_for_update()
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=404,
            detail="Membership not found."
        )

    # Confirm that membership payment succeeded

    paid_transaction = (
        db.query(MembershipTransaction.id)
        .filter(
            MembershipTransaction.membership_id == membership.id,
            MembershipTransaction.payment_status == "paid"
        )
        .first()
    )

    if not paid_transaction:
        raise HTTPException(
            status_code=409,
            detail=(
                "QR is available only after "
                "successful membership payment."
            )
        )

    if membership.status == "cancelled":
        raise HTTPException(
            status_code=410,
            detail="This membership is cancelled."
        )

    credential = _get_or_create(
        db,
        customer.id,
        "membership",
        membership.id
    )

    db.commit()
    db.refresh(credential)

    return {
        **_qr_response(credential, "membership"),
        "membership_name": membership.plan_name
    }


# --------------------------------------------------
# QR VALIDATION
# --------------------------------------------------

@router.get("/validate")
def validate_qr(
    token: str = Query(min_length=70, max_length=200),
    db: Session = Depends(get_db)
):

    try:
        credential_id, supplied_signature = token.split(".", 1)

        expected_signature = _sign(credential_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid QR token."
        )

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid QR signature."
        )

    credential = (
        db.query(AccessCredential)
        .filter(AccessCredential.id == credential_id)
        .first()
    )

    if not credential or credential.revoked_at:
        raise HTTPException(
            status_code=404,
            detail="QR credential is invalid or revoked."
        )

    # Booking validation

    if credential.entity_type == "booking":

        item = (
            db.query(Booking)
            .filter(Booking.id == credential.entity_id)
            .first()
        )

        if (
            not item
            or item.status != "confirmed"
            or item.payment_status != "paid"
        ):
            raise HTTPException(
                status_code=409,
                detail="Booking is not eligible for entry."
            )

        return {
            "valid": True,
            "type": "booking",
            "reference": item.booking_reference,
            "date": item.booking_date.isoformat(),
            "start_time": item.start_time.strftime("%H:%M"),
            "end_time": item.end_time.strftime("%H:%M"),
            "players": item.total_players
        }

    # Membership validation

    item = (
        db.query(CustomerMembership)
        .filter(
            CustomerMembership.id == credential.entity_id
        )
        .first()
    )

    if not item or item.status not in ("active", "scheduled"):
        raise HTTPException(
            status_code=409,
            detail="Membership is not eligible for entry."
        )

    return {
        "valid": True,
        "type": "membership",
        "membership": item.plan_name,
        "status": item.status,
        "start_date": item.start_date.isoformat(),
        "expiry_date": item.expiry_date.isoformat(),
        "remaining_hours": float(
            item.total_hours
            - item.used_hours
            - item.reserved_hours
        )
    }
