
import os
import secrets
from datetime import time
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal, check_database_connection
from app.models import FacilitySettings, SportPricing
from app.booking_routes import router as booking_router
from app.admin_routes import router as admin_bookings_router

app = FastAPI(
    title="The King Elite Arena API",
    description="Backend API for The King Elite Arena sports facility.",
    version="0.3.0",
)

app.include_router(booking_router)
app.include_router(admin_bookings_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["*", "X-Admin-Key"],
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


def require_admin(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    configured_key = os.getenv("ADMIN_API_KEY")

    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Admin authentication is not configured.",
        )

    if not x_admin_key or not secrets.compare_digest(
        x_admin_key, configured_key
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin key.",
        )


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
