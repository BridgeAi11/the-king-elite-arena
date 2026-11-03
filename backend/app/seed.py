
from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import FacilitySettings, SportPricing


def seed_initial_data() -> None:
    with SessionLocal.begin() as session:
        # Create default facility settings if they do not exist.
        facility = session.scalar(
            select(FacilitySettings).limit(1)
        )

        if facility is None:
            session.add(
                FacilitySettings(
                    facility_name="The King Elite Arena",
                    opening_time="06:00",
                    closing_time="23:00",
                    operating_days=[
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ],
                    is_booking_enabled=True,
                )
            )

        # Create default sport prices without overwriting admin changes.
        initial_prices = {
            "Badminton": Decimal("150.00"),
            "Pickleball": Decimal("200.00"),
        }

        for sport_name, hourly_rate in initial_prices.items():
            existing_price = session.scalar(
                select(SportPricing).where(
                    SportPricing.sport_name == sport_name
                )
            )

            if existing_price is None:
                session.add(
                    SportPricing(
                        sport_name=sport_name,
                        hourly_rate=hourly_rate,
                        is_active=True,
                    )
                )

    print("Initial facility configuration is ready.")


if __name__ == "__main__":
    seed_initial_data()
