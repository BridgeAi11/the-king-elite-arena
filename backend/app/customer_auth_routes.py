
import os
import re
import hmac
import hashlib
import secrets
import logging
import requests

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_db
from app.models import Customer, CustomerOTP
from app.customer_auth import (
    create_customer_token,
    require_customer,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/customer-auth",
    tags=["Customer Authentication"],
)

OTP_HASH_SECRET = os.getenv("OTP_HASH_SECRET")
TWOFACTOR_API_KEY = os.getenv("TWOFACTOR_API_KEY")
TWOFACTOR_OTP_TEMPLATE = os.getenv("TWOFACTOR_OTP_TEMPLATE")

TWOFACTOR_SEND_URL = "https://2factor.in/API/V1/OTP/SEND"


class RequestOTP(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str


class VerifyOTP(BaseModel):
    phone: str
    otp: str = Field(pattern=r"^[0-9]{6}$")


def normalize_phone(phone: str) -> str:
    phone = re.sub(r"[\s\-()]", "", phone)

    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    if not re.fullmatch(r"[6-9][0-9]{9}", phone):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid 10-digit Indian mobile number",
        )

    return phone


def hash_otp(phone: str, otp: str) -> str:
    if not OTP_HASH_SECRET:
        raise HTTPException(
            status_code=500,
            detail="OTP security configuration is missing",
        )

    return hmac.new(
        OTP_HASH_SECRET.encode(),
        f"{phone}:{otp}".encode(),
        hashlib.sha256,
    ).hexdigest()



from urllib.parse import quote

def send_otp_sms(phone: str, otp: str) -> None:
    if not TWOFACTOR_API_KEY or not TWOFACTOR_OTP_TEMPLATE:
        raise HTTPException(
            status_code=503,
            detail="SMS service is not configured.",
        )

    international_phone = f"+91{phone}"

    url = (
        "https://2factor.in/API/V1/"
        f"{quote(TWOFACTOR_API_KEY, safe='')}/SMS/"
        f"{quote(international_phone, safe='')}/"
        f"{quote(otp, safe='')}/"
        f"{quote(TWOFACTOR_OTP_TEMPLATE, safe='')}"
    )

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        result = response.json()

        if (
            not isinstance(result, dict)
            or str(result.get("Status", "")).lower() != "success"
        ):
            logger.error(
                "2Factor rejected SMS request. Status=%s",
                result.get("Status") if isinstance(result, dict) else "Invalid",
            )
            raise HTTPException(
                status_code=502,
                detail="SMS delivery request was unsuccessful.",
            )

    except requests.Timeout:
        logger.exception("2Factor SMS request timed out.")
        raise HTTPException(
            status_code=504,
            detail="SMS provider timed out. Please try again.",
        )

    except requests.RequestException:
        logger.exception("2Factor SMS request failed.")
        raise HTTPException(
            status_code=502,
            detail="Unable to send OTP SMS. Please try again.",
        )

    except ValueError:
        logger.exception("Invalid JSON response from 2Factor.")
        raise HTTPException(
            status_code=502,
            detail="Invalid response from SMS provider.",
        )


@router.post("/request-otp")
def request_otp(
    data: RequestOTP,
    db: Session = Depends(get_db),
):
    phone = normalize_phone(data.phone)
    full_name = data.full_name.strip()

    if len(full_name) < 2:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid customer name",
        )

    now = datetime.now(timezone.utc)

    recent_otps = db.query(CustomerOTP).filter(
        CustomerOTP.phone == phone,
        CustomerOTP.created_at >= now - timedelta(minutes=15),
    ).order_by(CustomerOTP.created_at.desc()).all()

    if len(recent_otps) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many OTP requests. Try again later.",
        )

    if recent_otps:
        latest = recent_otps[0]

        if latest.created_at > now - timedelta(seconds=60):
            raise HTTPException(
                status_code=429,
                detail="Please wait 60 seconds before requesting another OTP.",
            )

    otp = f"{secrets.randbelow(1000000):06d}"

    # Send the SMS before saving the OTP as active.
    send_otp_sms(phone, otp)

    record = CustomerOTP(
        phone=phone,
        full_name=full_name,
        otp_hash=hash_otp(phone, otp),
        attempts=0,
        is_used=False,
        expires_at=now + timedelta(minutes=5),
    )

    db.add(record)
    db.commit()

    return {
        "message": "OTP sent successfully to your mobile number.",
        "expires_in": 300,
    }


@router.post("/verify-otp")
def verify_otp(
    data: VerifyOTP,
    db: Session = Depends(get_db),
):
    phone = normalize_phone(data.phone)
    now = datetime.now(timezone.utc)

    record = db.query(CustomerOTP).filter(
        CustomerOTP.phone == phone,
        CustomerOTP.is_used.is_(False),
    ).order_by(CustomerOTP.created_at.desc()).first()

    if not record:
        raise HTTPException(
            status_code=400,
            detail="Request a new OTP",
        )

    if record.expires_at <= now:
        raise HTTPException(
            status_code=400,
            detail="OTP expired. Request a new OTP.",
        )

    if record.attempts >= 5:
        raise HTTPException(
            status_code=429,
            detail="Maximum OTP attempts reached.",
        )

    record.attempts += 1

    submitted_hash = hash_otp(phone, data.otp)

    if not hmac.compare_digest(record.otp_hash, submitted_hash):
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Incorrect OTP",
        )

    record.is_used = True

    customer = db.query(Customer).filter(
        Customer.phone == phone
    ).first()

    if not customer:
        customer = Customer(
            full_name=record.full_name,
            phone=phone,
            is_active=True,
        )
        db.add(customer)
        db.flush()

    elif not customer.is_active:
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Customer account is inactive",
        )

    token = create_customer_token(customer.id)

    db.commit()

    return {
        "message": "Customer authenticated successfully",
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 604800,
        "customer": {
            "id": customer.id,
            "full_name": customer.full_name,
            "phone": customer.phone,
        },
    }


@router.get("/me")
def get_customer_profile(
    customer: Customer = Depends(require_customer),
):
    return {
        "id": customer.id,
        "full_name": customer.full_name,
        "phone": customer.phone,
        "is_active": customer.is_active,
    }
