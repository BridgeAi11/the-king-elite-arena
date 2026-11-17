
from getpass import getpass

from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import AdminUser


def create_admin():
    username = input("Enter admin username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    password = getpass("Enter admin password: ")
    confirm_password = getpass("Confirm admin password: ")

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    with SessionLocal() as db:
        existing_admin = db.scalar(
            select(AdminUser).where(
                AdminUser.username == username
            )
        )

        if existing_admin:
            print("This admin username already exists.")
            return

        admin = AdminUser(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print(f"Admin account '{username}' created successfully.")


if __name__ == "__main__":
    create_admin()
