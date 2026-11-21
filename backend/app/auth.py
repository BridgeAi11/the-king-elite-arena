
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AdminUser


password_hash = PasswordHash.recommended()

security = HTTPBearer(auto_error=False)

JWT_SECRET_KEY = os.getenv("ADMIN_JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"

if not JWT_SECRET_KEY:
    raise RuntimeError("ADMIN_JWT_SECRET_KEY is missing")

JWT_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(admin_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_EXPIRE_MINUTES
    )

    payload = {
    "sub": str(admin_id),
    "type": "admin",
    "exp": expires_at,
    "iat": datetime.now(timezone.utc),
}

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )



def require_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ] = None,
    db: Session = Depends(get_db),
) -> AdminUser:

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired admin token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials or credentials.scheme.lower() != "bearer":
        raise credentials_error

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        if payload.get("type") != "admin":
            raise credentials_error

        admin_id = int(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise credentials_error

    admin = db.query(AdminUser).filter(
        AdminUser.id == admin_id
    ).first()

    if not admin or not admin.is_active:
        raise credentials_error

    return admin
