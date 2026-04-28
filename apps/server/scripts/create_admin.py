#!/usr/bin/env python3
"""Create admin user in database."""
import os
import sys

# Load .env file
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL from env, fallback to SQLite for local dev
os.environ.setdefault("DATABASE_URL", "sqlite:///./zenstory.db")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from database import sync_engine  # noqa: E402
from models import User  # noqa: E402


def main():
    # Create tables
    print("Creating tables...")
    SQLModel.metadata.create_all(sync_engine)
    print("Tables created.")

    # Create password hash
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("admin123")

    # Create admin user
    with Session(sync_engine) as session:
        existing = session.query(User).filter(User.email == "admin@zenstory.com").first()
        if existing:
            print(f"Admin user already exists: {existing.email}")
        else:
            admin = User(
                email="admin@zenstory.com",
                username="admin",
                hashed_password=hashed_password,
                is_active=True,
            )
            session.add(admin)
            session.commit()
            print("Admin user created:")
            print("  Email: admin@zenstory.com")
            print("  Password: admin123")

if __name__ == "__main__":
    main()
