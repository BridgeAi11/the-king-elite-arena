
from datetime import timedelta
import time
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Request
from app.security import limiter

from app.auth import (
    create_access_token,
    require_admin,
    verify_password,
    get_db,
)
from app.models import AdminUser


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1)



@router.post("/login")
@limiter.limit("5/minute")
def admin_login(
    request: Request,
    credentials: AdminLoginRequest,
    db: Session = Depends(get_db),
):
    total_start = time.perf_counter()

    # 1. Database query
    query_start = time.perf_counter()

    admin = db.query(AdminUser).filter(
        AdminUser.username == credentials.username
    ).first()

    query_time = time.perf_counter() - query_start

    # 2. Password verification
    password_start = time.perf_counter()

    password_valid = (
        admin is not None
        and admin.is_active
        and verify_password(
            credentials.password,
            admin.password_hash,
        )
    )

    password_time = time.perf_counter() - password_start

    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # 3. JWT generation
    token_start = time.perf_counter()

    access_token = create_access_token(admin.id)

    token_time = time.perf_counter() - token_start
    total_time = time.perf_counter() - total_start

    print(
        f"ADMIN LOGIN PERFORMANCE | "
        f"DB: {query_time:.3f}s | "
        f"Password: {password_time:.3f}s | "
        f"JWT: {token_time:.3f}s | "
        f"Total: {total_time:.3f}s"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 30 * 60,
        "admin": {
            "id": admin.id,
            "username": admin.username,
        },
    }


@router.get("/me")
def get_current_admin(
    admin: AdminUser = Depends(require_admin),
):
    return {
        "id": admin.id,
        "username": admin.username,
        "is_active": admin.is_active,
    }
