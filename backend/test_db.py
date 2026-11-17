
from sqlalchemy import text
from app.database import engine

try:
    with engine.connect() as conn:

        print("\n========== PAYMENT TRANSACTIONS ==========")

        payments = conn.execute(text("""
            SELECT
                id,
                booking_id,
                razorpay_order_id,
                razorpay_payment_id,
                amount_paise,
                status,
                created_at
            FROM payment_transactions
            ORDER BY id DESC
            LIMIT 10
        """)).mappings().all()

        for payment in payments:
            print(dict(payment))

        print("\n========== BOOKINGS ==========")

        bookings = conn.execute(text("""
            SELECT
                id,
                booking_reference,
                status,
                payment_status,
                total_amount,
                created_at,
                payment_expires_at
            FROM bookings
            ORDER BY id DESC
            LIMIT 10
        """)).mappings().all()

        for booking in bookings:
            print(dict(booking))

        print("\n========== EXPIRY STATUS ==========")

        expiry_records = conn.execute(text("""
            SELECT
                id,
                booking_reference,
                status,
                payment_status,
                payment_expires_at,
                CASE
                    WHEN payment_expires_at IS NULL
                        THEN 'NO EXPIRY'
                    WHEN payment_expires_at <= NOW()
                        THEN 'EXPIRED'
                    ELSE 'ACTIVE'
                END AS expiry_status
            FROM bookings
            WHERE status = 'pending'
              AND payment_status = 'unpaid'
            ORDER BY id DESC
        """)).mappings().all()

        for record in expiry_records:
            print(dict(record))

except Exception as e:
    print("Database check failed:", str(e))
