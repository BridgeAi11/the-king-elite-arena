
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import require_admin
from app.database import SessionLocal
from app.models import SportPricing, SportPricingRule
import logging

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/admin/pricing",
    tags=["Admin Pricing"],
    dependencies=[Depends(require_admin)],
)


class PricingRuleInput(BaseModel):
    hour_from: int = Field(ge=1)
    hour_to: int | None = Field(default=None, ge=1)
    price_per_player: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )


class PricingScheduleInput(BaseModel):
    rules: list[PricingRuleInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_schedule(self):
        rules = self.rules

        if rules[0].hour_from != 1:
            raise ValueError("The first pricing rule must start at hour 1.")

        for index, rule in enumerate(rules):
            if rule.hour_to is not None and rule.hour_to < rule.hour_from:
                raise ValueError("hour_to cannot be less than hour_from.")

            if index < len(rules) - 1:
                next_rule = rules[index + 1]

                if rule.hour_to is None:
                    raise ValueError(
                        "Only the final pricing rule can have an unlimited end hour."
                    )

                if next_rule.hour_from != rule.hour_to + 1:
                    raise ValueError(
                        "Pricing rules must be continuous without gaps or overlaps."
                    )
            elif rule.hour_to is not None:
                raise ValueError(
                    "The final pricing rule must have hour_to set to null."
                )

        return self


def pricing_rule_to_dict(rule: SportPricingRule) -> dict:
    return {
        "id": rule.id,
        "hour_from": rule.hour_from,
        "hour_to": rule.hour_to,
        "price_per_player": float(rule.price_per_player),
        "is_active": rule.is_active,
    }


@router.get("")
def get_all_pricing():
    try:
        with SessionLocal() as db:
            sports = db.scalars(
                select(SportPricing).order_by(SportPricing.sport_name)
            ).all()

            result = []

            for sport in sports:
                rules = db.scalars(
                    select(SportPricingRule)
                    .where(SportPricingRule.sport_id == sport.id)
                    .order_by(SportPricingRule.hour_from)
                ).all()

                result.append({
                    "sport_id": sport.id,
                    "sport_name": sport.sport_name,
                    "is_active": sport.is_active,
                    "rules": [
                        pricing_rule_to_dict(rule)
                        for rule in rules
                    ],
                })

            return {"sports": result}

    except SQLAlchemyError:
        logger.exception("Failed to replace sport pricing rules")
        raise HTTPException(
            status_code=503,
            detail="Unable to update pricing rules.",
        )


@router.put("/{sport_id}/rules")
def replace_pricing_rules(
    sport_id: int,
    schedule: PricingScheduleInput,
):
    try:
        with SessionLocal() as db:
            sport = db.scalar(
                select(SportPricing)
                .where(SportPricing.id == sport_id)
                .with_for_update()
            )

            if sport is None:
                raise HTTPException(404, "Sport not found.")

            existing_rules = db.scalars(
                select(SportPricingRule)
                .where(SportPricingRule.sport_id == sport_id)
                .with_for_update()
            ).all()

            for rule in existing_rules:
                db.delete(rule)
            
            # Execute deletes before inserting replacement rules.
            db.flush()


            new_rules = []

            for item in schedule.rules:
                rule = SportPricingRule(
                    sport_id=sport_id,
                    hour_from=item.hour_from,
                    hour_to=item.hour_to,
                    price_per_player=item.price_per_player,
                    is_active=True,
                )
                db.add(rule)
                new_rules.append(rule)

            # Keep the legacy hourly rate synchronized with hour 1.
            sport.hourly_rate = schedule.rules[0].price_per_player

            db.flush()
            db.commit()

            for rule in new_rules:
                db.refresh(rule)

            return {
                "message": "Pricing rules updated successfully.",
                "sport_id": sport.id,
                "sport_name": sport.sport_name,
                "rules": [
                    pricing_rule_to_dict(rule)
                    for rule in new_rules
                ],
            }

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to update pricing rules.",
        )
