from app.database import check_database_connection

if check_database_connection():
    print("Database connection successful!")