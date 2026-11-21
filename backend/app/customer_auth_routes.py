
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_db
from app.models import Customer
from app.customer_auth import (
    create_customer_token,
    require_customer,
)

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import Request
from app.security import limiter


router = APIRouter(
    prefix="/api/customer-auth",
    tags=["Customer Authentication"],
)


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=10000)


@router.post("/google")
@limiter.limit("5/minute")
def google_login(
    request: Request,
    data: GoogleLoginRequest,
    db: Session = Depends(get_db),
):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured on the server.",
        )

    # Verify Google ID token
    try:
        claims = id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Google sign-in token is invalid or expired.",
        )

    # Extract verified Google account details
    email = str(claims.get("email", "")).strip().lower()
    google_sub = str(claims.get("sub", "")).strip()
    full_name = str(claims.get("name", "")).strip()[:120]

    if (
        not email
        or not google_sub
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(
            status_code=401,
            detail="A verified Google email account is required.",
        )

    # Find customer using Google's unique account ID
    customer = (
        db.query(Customer)
        .filter(Customer.google_sub == google_sub)
        .first()
    )

    # Do not automatically link an existing account by email
    if not customer:
        existing_email = (
            db.query(Customer)
            .filter(Customer.email == email)
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=409,
                detail=(
                    "An account already exists with this email. "
                    "Please contact the arena administrator "
                    "to link your Google account."
                ),
            )

        # Create a new customer if no account exists
        customer = Customer(
            full_name=full_name or email.split("@")[0],
            phone=None,
            email=email,
            google_sub=google_sub,
            is_active=True,
        )

        db.add(customer)

        try:
            db.commit()
            db.refresh(customer)
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Unable to create customer account. Please try again.",
            )

    else:
        # Existing Google-linked customer
        if not customer.is_active:
            raise HTTPException(
                status_code=403,
                detail="Customer account is inactive.",
            )

        # Check whether this email belongs to another customer
        email_owner = (
            db.query(Customer)
            .filter(
                Customer.email == email,
                Customer.id != customer.id,
            )
            .first()
        )

        if email_owner:
            raise HTTPException(
                status_code=409,
                detail="This email is already associated with another customer account.",
            )

        customer.email = email

        if full_name and not customer.full_name:
            customer.full_name = full_name

        try:
            db.commit()
            db.refresh(customer)
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Unable to update customer account. Please try again.",
            )

    # Generate customer JWT
    return {
        "message": "Customer authenticated successfully",
        "access_token": create_customer_token(customer.id),
        "token_type": "bearer",
        "expires_in": 604800,
        "customer": {
            "id": customer.id,
            "full_name": customer.full_name,
            "phone": customer.phone,
            "email": customer.email,
            "is_active": customer.is_active,
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
