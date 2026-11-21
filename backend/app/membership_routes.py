
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin, get_db
from app.customer_auth import require_customer
from app.models import MembershipPlan, Customer, CustomerMembership
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal



router = APIRouter(
    prefix="/api/admin/memberships",
    tags=["Membership Management"],
)


class MembershipPlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    validity_days: int = Field(gt=0)
    included_hours: Decimal = Field(
        gt=0, max_digits=8, decimal_places=2
    )
    is_active: bool = True
    display_order: int = 0


class MembershipPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    validity_days: int | None = Field(default=None, gt=0)
    included_hours: Decimal | None = Field(
        default=None, gt=0, max_digits=8, decimal_places=2
    )
    is_active: bool | None = None
    display_order: int | None = None

    model_config = ConfigDict(extra="forbid")


def plan_to_dict(plan: MembershipPlan):
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "price": float(plan.price),
        "validity_days": plan.validity_days,
        "included_hours": float(plan.included_hours),
        "is_active": plan.is_active,
        "display_order": plan.display_order,
        "created_at": plan.created_at.isoformat(),
    }


# ADMIN: Get all membership plans
@router.get("/plans", dependencies=[Depends(require_admin)])
def get_membership_plans():
    try:
        with SessionLocal() as db:
            plans = db.scalars(
                select(MembershipPlan).order_by(
                    MembershipPlan.display_order,
                    MembershipPlan.id,
                )
            ).all()

            return [plan_to_dict(plan) for plan in plans]

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to load membership plans.",
        )


# ADMIN: Create membership plan
@router.post("/plans", dependencies=[Depends(require_admin)])
def create_membership_plan(data: MembershipPlanCreate):
    try:
        with SessionLocal() as db:
            plan = MembershipPlan(**data.model_dump())

            db.add(plan)
            db.commit()
            db.refresh(plan)

            return {
                "message": "Membership plan created successfully.",
                "plan": plan_to_dict(plan),
            }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to create membership plan.",
        )


# ADMIN: Update membership plan
@router.patch("/plans/{plan_id}", dependencies=[Depends(require_admin)])
def update_membership_plan(
    plan_id: int,
    data: MembershipPlanUpdate,
):
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No update fields provided.",
        )

    if any(value is None for value in updates.values()
           if value is not None):
        raise HTTPException(
            status_code=400,
            detail="Invalid update.",
        )

    try:
        with SessionLocal() as db:
            plan = db.get(MembershipPlan, plan_id)

            if plan is None:
                raise HTTPException(
                    status_code=404,
                    detail="Membership plan not found.",
                )

            for key, value in updates.items():
                setattr(plan, key, value)

            db.commit()
            db.refresh(plan)

            return {
                "message": "Membership plan updated successfully.",
                "plan": plan_to_dict(plan),
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to update membership plan.",
        )


# ADMIN: Deactivate membership plan
@router.delete(
    "/plans/{plan_id}",
    dependencies=[Depends(require_admin)],
)
def deactivate_membership_plan(plan_id: int):
    try:
        with SessionLocal() as db:
            plan = db.get(MembershipPlan, plan_id)

            if plan is None:
                raise HTTPException(
                    status_code=404,
                    detail="Membership plan not found.",
                )

            plan.is_active = False

            db.commit()

            return {
                "message": "Membership plan deactivated successfully."
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to deactivate membership plan.",
        )


# PUBLIC: Display active membership plans on website
public_router = APIRouter(
    prefix="/api/public",
    tags=["Public Memberships"],
)


@public_router.get("/membership-plans")
def get_public_membership_plans():
    try:
        with SessionLocal() as db:
            plans = db.scalars(
                select(MembershipPlan)
                .where(MembershipPlan.is_active.is_(True))
                .order_by(
                    MembershipPlan.display_order,
                    MembershipPlan.id,
                )
            ).all()

            return [plan_to_dict(plan) for plan in plans]

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to load membership plans.",
        )

# CUSTOMER: Get logged-in customer's memberships
@public_router.get("/my-memberships")
def get_my_memberships(
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
):
    try:
        memberships = (
            db.query(CustomerMembership)
            .filter(
                CustomerMembership.customer_id == customer.id
            )
            .order_by(CustomerMembership.created_at.desc())
            .all()
        )

        return {
            "customer": {
                "id": customer.id,
                "full_name": customer.full_name,
                "phone": customer.phone,
            },
            "total_memberships": len(memberships),
            "memberships": [
                {
                    "membership_id": item.id,
                    "plan_name": item.plan_name,
                    "amount_paid": float(item.amount_paid),
                    "total_hours": float(item.total_hours),
                    "used_hours": float(item.used_hours),
                    "reserved_hours": float(item.reserved_hours),
                    "remaining_hours": float(
                        item.total_hours
                        - item.used_hours
                        - item.reserved_hours
                    ),
                    "start_date": item.start_date.isoformat(),
                    "expiry_date": item.expiry_date.isoformat(),
                    "status": item.status,
                }
                for item in memberships
            ],
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to load your memberships.",
        )