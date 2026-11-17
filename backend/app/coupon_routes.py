
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import require_admin
from app.customer_auth import require_customer
from app.database import SessionLocal
from app.models import Coupon, CouponRedemption, Customer


admin_router = APIRouter(
    prefix="/api/admin/coupons",
    tags=["Admin Coupons"],
)

public_router = APIRouter(
    prefix="/api/coupons",
    tags=["Customer Coupons"],
)


def normalize_code(value: str) -> str:
    return value.strip().upper()


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    description: str | None = Field(default=None, max_length=300)
    discount_type: Literal["percentage", "fixed"]
    discount_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    applies_to: Literal["booking", "membership", "both"] = "both"
    min_order_amount: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=10, decimal_places=2
    )
    max_discount_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    starts_at: datetime
    ends_at: datetime
    usage_limit: int | None = Field(default=None, gt=0)
    per_customer_limit: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def clean_code(cls, value):
        code = normalize_code(value)
        if not code or not code.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Coupon code can contain letters, numbers, - and _.")
        return code

    def validate_rules(self):
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100.")

        if self.ends_at <= self.starts_at:
            raise ValueError("End date must be later than start date.")

        return self

    model_config = ConfigDict(extra="forbid")


class CouponUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=3, max_length=40)
    description: str | None = Field(default=None, max_length=300)
    discount_type: Literal["percentage", "fixed"] | None = None
    discount_value: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    applies_to: Literal["booking", "membership", "both"] | None = None
    min_order_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    max_discount_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit: int | None = Field(default=None, gt=0)
    per_customer_limit: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def clean_code(cls, value):
        return normalize_code(value) if value is not None else value

    model_config = ConfigDict(extra="forbid")


class CouponValidationRequest(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    applies_to: Literal["booking", "membership"]
    order_amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value):
        return normalize_code(value)


def coupon_to_dict(coupon: Coupon, used_count: int = 0):
    return {
        "id": coupon.id,
        "code": coupon.code,
        "description": coupon.description,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "applies_to": coupon.applies_to,
        "min_order_amount": float(coupon.min_order_amount),
        "max_discount_amount": (
            float(coupon.max_discount_amount)
            if coupon.max_discount_amount is not None
            else None
        ),
        "starts_at": coupon.starts_at.isoformat(),
        "ends_at": coupon.ends_at.isoformat(),
        "usage_limit": coupon.usage_limit,
        "per_customer_limit": coupon.per_customer_limit,
        "is_active": coupon.is_active,
        "used_count": used_count,
        "remaining_uses": (
            max(0, coupon.usage_limit - used_count)
            if coupon.usage_limit is not None
            else None
        ),
        "created_at": coupon.created_at.isoformat(),
    }


def get_used_count(db, coupon_id: int) -> int:
    return db.scalar(
        select(func.count(CouponRedemption.id)).where(
            CouponRedemption.coupon_id == coupon_id,
            CouponRedemption.status.in_(["reserved", "redeemed"]),
        )
    ) or 0


def calculate_discount(coupon: Coupon, amount: Decimal) -> Decimal:
    if coupon.discount_type == "percentage":
        discount = amount * coupon.discount_value / Decimal("100")
    else:
        discount = coupon.discount_value

    if coupon.max_discount_amount is not None:
        discount = min(discount, coupon.max_discount_amount)

    discount = min(discount, amount)

    return discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_coupon_rules(
    db,
    coupon: Coupon,
    customer_id: int,
    applies_to: str,
    amount: Decimal,
):
    now = datetime.now(timezone.utc)

    if not coupon.is_active:
        raise HTTPException(400, "This coupon is currently inactive.")

    if now < coupon.starts_at or now > coupon.ends_at:
        raise HTTPException(400, "This coupon is not valid at this time.")

    if coupon.applies_to not in [applies_to, "both"]:
        raise HTTPException(400, "This coupon is not valid for this purchase.")

    if amount < coupon.min_order_amount:
        raise HTTPException(
            400,
            f"Minimum purchase amount is ₹{coupon.min_order_amount}.",
        )

    used_count = get_used_count(db, coupon.id)

    if coupon.usage_limit is not None and used_count >= coupon.usage_limit:
        raise HTTPException(400, "This coupon has reached its usage limit.")

    if coupon.per_customer_limit is not None:
        customer_uses = db.scalar(
            select(func.count(CouponRedemption.id)).where(
                CouponRedemption.coupon_id == coupon.id,
                CouponRedemption.customer_id == customer_id,
                CouponRedemption.status.in_(["reserved", "redeemed"]),
            )
        ) or 0

        if customer_uses >= coupon.per_customer_limit:
            raise HTTPException(
                400,
                "You have already used this coupon the maximum number of times.",
            )

    discount = calculate_discount(coupon, amount)
    final_amount = amount - discount

    return discount, final_amount


# --------------------------------------------------
# ADMIN: LIST COUPONS
# --------------------------------------------------

@admin_router.get("", dependencies=[Depends(require_admin)])
def list_coupons():
    try:
        with SessionLocal() as db:
            coupons = db.scalars(
                select(Coupon).order_by(Coupon.created_at.desc())
            ).all()

            return [
                coupon_to_dict(coupon, get_used_count(db, coupon.id))
                for coupon in coupons
            ]

    except SQLAlchemyError:
        raise HTTPException(503, "Unable to load coupons.")


# --------------------------------------------------
# ADMIN: CREATE COUPON
# --------------------------------------------------

@admin_router.post("", dependencies=[Depends(require_admin)])
def create_coupon(data: CouponCreate):
    data.validate_rules()

    try:
        with SessionLocal() as db:
            existing = db.scalar(
                select(Coupon).where(Coupon.code == data.code)
            )

            if existing:
                raise HTTPException(409, "This coupon code already exists.")

            coupon = Coupon(**data.model_dump())

            db.add(coupon)
            db.commit()
            db.refresh(coupon)

            return {
                "message": "Coupon created successfully.",
                "coupon": coupon_to_dict(coupon),
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Unable to create coupon.")


# --------------------------------------------------
# ADMIN: UPDATE COUPON
# --------------------------------------------------

@admin_router.patch(
    "/{coupon_id}",
    dependencies=[Depends(require_admin)],
)
def update_coupon(coupon_id: int, data: CouponUpdate):
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(400, "No update fields provided.")

    try:
        with SessionLocal() as db:
            coupon = db.scalar(
                select(Coupon)
                .where(Coupon.id == coupon_id)
                .with_for_update()
            )

            if coupon is None:
                raise HTTPException(404, "Coupon not found.")

            for key, value in updates.items():
                if key == "code" and value is not None:
                    duplicate = db.scalar(
                        select(Coupon).where(
                            Coupon.code == value,
                            Coupon.id != coupon_id,
                        )
                    )
                    if duplicate:
                        raise HTTPException(
                            409, "This coupon code already exists."
                        )

                setattr(coupon, key, value)

            if (
                coupon.discount_type == "percentage"
                and coupon.discount_value > 100
            ):
                raise HTTPException(
                    400, "Percentage discount cannot exceed 100."
                )

            if coupon.ends_at <= coupon.starts_at:
                raise HTTPException(
                    400, "End date must be later than start date."
                )

            db.commit()
            db.refresh(coupon)

            return {
                "message": "Coupon updated successfully.",
                "coupon": coupon_to_dict(
                    coupon, get_used_count(db, coupon.id)
                ),
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Unable to update coupon.")


# --------------------------------------------------
# ADMIN: DEACTIVATE COUPON
# --------------------------------------------------

@admin_router.delete(
    "/{coupon_id}",
    dependencies=[Depends(require_admin)],
)
def deactivate_coupon(coupon_id: int):
    try:
        with SessionLocal() as db:
            coupon = db.get(Coupon, coupon_id)

            if coupon is None:
                raise HTTPException(404, "Coupon not found.")

            coupon.is_active = False
            db.commit()

            return {"message": "Coupon deactivated successfully."}

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Unable to deactivate coupon.")


# --------------------------------------------------
# ADMIN: REDEMPTION HISTORY
# --------------------------------------------------

@admin_router.get(
    "/redemptions/history",
    dependencies=[Depends(require_admin)],
)
def coupon_redemption_history():
    try:
        with SessionLocal() as db:
            rows = db.execute(
                select(CouponRedemption, Coupon, Customer)
                .join(Coupon, Coupon.id == CouponRedemption.coupon_id)
                .join(Customer, Customer.id == CouponRedemption.customer_id)
                .order_by(CouponRedemption.created_at.desc())
            ).all()

            return [
                {
                    "id": redemption.id,
                    "coupon_code": coupon.code,
                    "customer_name": customer.full_name,
                    "customer_phone": customer.phone,
                    "applies_to": redemption.applies_to,
                    "booking_id": redemption.booking_id,
                    "membership_id": redemption.membership_id,
                    "original_amount": float(redemption.original_amount),
                    "discount_amount": float(redemption.discount_amount),
                    "final_amount": float(redemption.final_amount),
                    "status": redemption.status,
                    "created_at": redemption.created_at.isoformat(),
                }
                for redemption, coupon, customer in rows
            ]

    except SQLAlchemyError:
        raise HTTPException(503, "Unable to load coupon redemption history.")


# --------------------------------------------------
# CUSTOMER: VALIDATE COUPON
# --------------------------------------------------

@public_router.post("/validate")
def validate_coupon(
    data: CouponValidationRequest,
    customer: Customer = Depends(require_customer),
):
    try:
        with SessionLocal() as db:
            coupon = db.scalar(
                select(Coupon).where(
                    Coupon.code == data.code
                )
            )

            if coupon is None:
                raise HTTPException(404, "Invalid coupon code.")

            discount, final_amount = validate_coupon_rules(
                db=db,
                coupon=coupon,
                customer_id=customer.id,
                applies_to=data.applies_to,
                amount=data.order_amount,
            )

            return {
                "valid": True,
                "coupon_code": coupon.code,
                "original_amount": float(data.order_amount),
                "discount_amount": float(discount),
                "final_amount": float(final_amount),
                "is_fully_discounted": final_amount == Decimal("0.00"),
                "message": "Coupon applied successfully.",
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Unable to validate coupon.")
