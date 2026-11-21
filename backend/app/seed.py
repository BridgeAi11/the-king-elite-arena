
from datetime import time
from decimal import Decimal
import os

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.database import SessionLocal
from app.models import FacilitySettings, SportPricing, SportPricingRule


def seed_initial_data():
    url = make_url(os.environ["DATABASE_URL"])

    if (
        url.host != "dpg-dbu3kv9srm7s73eh2je0-a.oregon-postgres.render.com"
        or url.database != "king_elite_arena"
    ):
        raise RuntimeError("Unexpected database. Initialization cancelled.")

    schedules = {
        "Badminton": [
            (1, 1, Decimal("1.00")),
            (2, 2, Decimal("100.00")),
            (3, None, Decimal("80.00")),
        ],
        "Pickleball": [
            (1, 1, Decimal("200.00")),
            (2, None, Decimal("150.00")),
        ],
    }

    with SessionLocal.begin() as db:
        facility = db.scalar(
            select(FacilitySettings).order_by(FacilitySettings.id)
        )

        if facility is None:
            db.add(FacilitySettings(
                facility_name="The King Elite Arena",
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                operating_days=[
                    "Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday",
                ],
                is_booking_enabled=True,
                max_players_per_hour=40,
            ))
            print("Created facility settings.")
        else:
            print("Facility already exists. Skipped.")

        for sport_name, rules_data in schedules.items():
            sport = db.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name == sport_name
                )
            )

            if sport is None:
                sport = SportPricing(
                    sport_name=sport_name,
                    hourly_rate=rules_data[0][2],
                    is_active=True,
                )
                db.add(sport)
                db.flush()
                print(f"Created sport: {sport_name}")
            else:
                print(f"Sport already exists: {sport_name}")

            existing_rules = db.scalars(
                select(SportPricingRule).where(
                    SportPricingRule.sport_id == sport.id
                )
            ).all()

            if existing_rules:
                print(f"Existing rules found for {sport_name}. Skipped.")
                continue

            for hour_from, hour_to, price in rules_data:
                db.add(SportPricingRule(
                    sport_id=sport.id,
                    hour_from=hour_from,
                    hour_to=hour_to,
                    price_per_player=price,
                    is_active=True,
                ))

            print(f"Created pricing rules: {sport_name}")

    print("Production initialization completed.")


if __name__ == "__main__":
    seed_initial_data()
