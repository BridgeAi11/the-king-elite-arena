import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_db
from app.models import Customer


JWT_SECRET_KEY = os.getenv("CUSTOMER_JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError("CUSTOMER_JWT_SECRET_KEY is missing")




def create_customer_token(customer_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(customer_id),
        "type": "customer",
        "iat": now,
        "exp": now + timedelta(days=7),
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm="HS256",
    )


def require_customer(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Customer:

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Customer authentication required",
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=["HS256"],
        )

        if payload.get("type") != "customer":
            raise HTTPException(
                status_code=401,
                detail="Invalid customer token",
            )

        customer_id = int(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_active.is_(True),
    ).first()

    if not customer:
        raise HTTPException(
            status_code=401,
            detail="Customer account not found or inactive",
        )

    return customer