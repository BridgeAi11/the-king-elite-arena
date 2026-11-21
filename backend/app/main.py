
from fastapi import Depends, FastAPI, HTTPException
from datetime import date, time
from app.auth import require_admin
from decimal import Decimal
from typing import Annotated
import logging
import os

logger = logging.getLogger(__name__)

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal, check_database_connection
from app.models import FacilitySettings, SportPricing, SportPricingRule
from app.booking_routes import router as booking_router
from app.admin_routes import router as admin_bookings_router
from app.membership_routes import (
    router as membership_router,
    public_router as public_membership_router,
)
from app.auth_routes import router as auth_router
from app.customer_auth_routes import router as customer_auth_router
from app.customer_booking_routes import router as customer_booking_router
from app.coupon_routes import (
    admin_router as admin_coupon_router,
    public_router as customer_coupon_router,
)
from app.payment_routes import router as payment_router
from app.refund_routes import router as admin_refund_router
from app.membership_payment_routes import (
    router as membership_payment_router,
)
import asyncio
from contextlib import asynccontextmanager

from app.booking_expiry import booking_expiry_loop
from app.admin_pricing_routes import router as admin_pricing_router
from app.access_routes import router as access_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.security import limiter
from starlette.middleware.base import BaseHTTPMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    expiry_task = asyncio.create_task(booking_expiry_loop())

    try:
        yield
    finally:
        expiry_task.cancel()

        try:
            await expiry_task
        except asyncio.CancelledError:
            pass

class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response

app = FastAPI(
    title="The King Elite Arena API",
    description="Backend API for The King Elite Arena sports facility.",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.include_router(booking_router)
app.include_router(customer_booking_router)
app.include_router(admin_bookings_router)
app.include_router(membership_router)
app.include_router(public_membership_router)
app.include_router(auth_router)
app.include_router(customer_auth_router)
app.include_router(admin_coupon_router)
app.include_router(customer_coupon_router)
app.include_router(payment_router)
app.include_router(membership_payment_router)
app.include_router(admin_refund_router)
app.include_router(admin_pricing_router)
app.include_router(access_router)



allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEEKDAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}



AdminAuth = Annotated[None, Depends(require_admin)]


class FacilityUpdate(BaseModel):
    facility_name: str = Field(min_length=1, max_length=150)
    max_players_per_hour: int = Field(ge=1, le=40)
    opening_time: time
    closing_time: time
    operating_days: list[str]
    is_booking_enabled: bool

    @model_validator(mode="after")
    def validate_facility(self):
        if self.opening_time >= self.closing_time:
            raise ValueError("Closing time must be later than opening time.")

        if not self.operating_days:
            raise ValueError("Select at least one operating day.")

        if len(self.operating_days) != len(set(self.operating_days)):
            raise ValueError("Operating days cannot contain duplicates.")

        invalid_days = set(self.operating_days) - WEEKDAYS
        if invalid_days:
            raise ValueError("Operating days contain an invalid weekday.")

        return self


class SportUpdate(BaseModel):
    hourly_rate: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    is_active: bool


@app.get("/", tags=["General"])
def root():
    return {
        "application": "The King Elite Arena API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    try:
        check_database_connection()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable",
        )

    return {"status": "healthy", "database": "connected"}


@app.get("/api/public/config", tags=["Public"])
def get_public_config():
    try:
        with SessionLocal() as db:
            facility = db.scalar(
                select(FacilitySettings).order_by(FacilitySettings.id)
            )
            sports = db.scalars(
                select(SportPricing)
                .where(SportPricing.is_active.is_(True))
                .order_by(SportPricing.sport_name)
            ).all()

            if facility is None:
                raise HTTPException(
                    status_code=503,
                    detail="Facility settings have not been configured.",
                )

            return {
                "facility": {
                    "facility_name": facility.facility_name,
                    "opening_time": facility.opening_time.strftime("%H:%M"),
                    "closing_time": facility.closing_time.strftime("%H:%M"),
                    "operating_days": facility.operating_days,
                    "is_booking_enabled": facility.is_booking_enabled,
                    "max_players_per_hour": facility.max_players_per_hour,
                },
                "sports": [
                    {
                        "name": sport.sport_name,
                        "hourly_rate": float(sport.hourly_rate),
                        "is_active": sport.is_active,
                    }
                    for sport in sports
                ],
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to load public facility settings.",
        )

@app.get("/api/public/pricing", tags=["Public"])
def get_public_pricing():
    try:
        with SessionLocal() as db:
            sports = db.scalars(
                select(SportPricing)
                .where(SportPricing.is_active.is_(True))
                .order_by(SportPricing.sport_name)
            ).all()

            result = []

            for sport in sports:
                rules = db.scalars(
                    select(SportPricingRule)
                    .where(
                        SportPricingRule.sport_id == sport.id,
                        SportPricingRule.is_active.is_(True),
                    )
                    .order_by(SportPricingRule.hour_from)
                ).all()

                result.append({
                    "sport_id": sport.id,
                    "sport_name": sport.sport_name,
                    "rules": [
                        {
                            "hour_from": rule.hour_from,
                            "hour_to": rule.hour_to,
                            "price_per_player": float(
                                rule.price_per_player
                            ),
                        }
                        for rule in rules
                    ],
                })

            return {"sports": result}

    except SQLAlchemyError:
        logger.exception("Unable to load public pricing.")
        raise HTTPException(
            status_code=503,
            detail="Unable to load public pricing.",
        )

@app.get(
    "/api/admin/config",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)
def get_admin_config():
    with SessionLocal() as db:
        facility = db.scalar(
            select(FacilitySettings).order_by(FacilitySettings.id)
        )
        sports = db.scalars(
            select(SportPricing).order_by(SportPricing.sport_name)
        ).all()

        if facility is None:
            raise HTTPException(
                status_code=503,
                detail="Facility settings have not been configured.",
            )

        return {
            "facility": {
                "facility_name": facility.facility_name,
                "opening_time": facility.opening_time.strftime("%H:%M"),
                "closing_time": facility.closing_time.strftime("%H:%M"),
                "operating_days": facility.operating_days,
                "is_booking_enabled": facility.is_booking_enabled,
                "max_players_per_hour": facility.max_players_per_hour,
            },
            "sports": [
                {
                    "name": sport.sport_name,
                    "hourly_rate": float(sport.hourly_rate),
                    "is_active": sport.is_active,
                }
                for sport in sports
            ],
        }


@app.put(
    "/api/admin/facility",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)
def update_facility(settings: FacilityUpdate):
    try:
        with SessionLocal() as db:
            facility = db.scalar(
                select(FacilitySettings).order_by(FacilitySettings.id)
            )

            if facility is None:
                raise HTTPException(
                    status_code=404,
                    detail="Facility settings not found.",
                )

            facility.facility_name = settings.facility_name
            facility.opening_time = settings.opening_time
            facility.closing_time = settings.closing_time
            facility.operating_days = settings.operating_days
            facility.is_booking_enabled = settings.is_booking_enabled
            facility.max_players_per_hour = settings.max_players_per_hour

            db.commit()
            db.refresh(facility)

            return {
                "message": "Facility settings updated successfully.",
                "facility": {
                    "facility_name": facility.facility_name,
                    "opening_time": facility.opening_time.strftime("%H:%M"),
                    "closing_time": facility.closing_time.strftime("%H:%M"),
                    "operating_days": facility.operating_days,
                    "is_booking_enabled": facility.is_booking_enabled,
                    "max_players_per_hour": facility.max_players_per_hour,
                },
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to update facility settings.",
        )


@app.patch(
    "/api/admin/sports/{sport_name}",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)
def update_sport(sport_name: str, update: SportUpdate):
    try:
        with SessionLocal() as db:
            sport = db.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name.ilike(sport_name)
                )
            )

            if sport is None:
                raise HTTPException(
                    status_code=404,
                    detail="Sport not found.",
                )

            sport.hourly_rate = update.hourly_rate
            sport.is_active = update.is_active

            db.commit()
            db.refresh(sport)

            return {
                "message": "Sport pricing updated successfully.",
                "sport": {
                    "name": sport.sport_name,
                    "hourly_rate": float(sport.hourly_rate),
                    "is_active": sport.is_active,
                },
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to update sport pricing.",
        )
