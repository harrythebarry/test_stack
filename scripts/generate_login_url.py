"""
python ../scripts/generate_login_url.py <user_id>
"""

import sys

sys.path.append("../")
sys.path.append("../backend")

import argparse
from datetime import datetime, timedelta
from jose import jwt
from sqlalchemy import select

from backend.db.database import SessionLocal
from backend.db.models import User
from backend.config import JWT_SECRET_KEY, FRONTEND_URL


def generate_login_url(user_id: int):
    """Generate a login URL for a user."""
    db = SessionLocal()

    try:
        # Find user
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

        if not user:
            print(f"Error: User with ID '{user_id}' not found", file=sys.stderr)
            sys.exit(1)

        # Generate token
        token = jwt.encode(
            {
                "email": user.email,
                "exp": datetime.now() + timedelta(days=7),
            },
            JWT_SECRET_KEY,
            algorithm="HS256",
        )

        # Generate login URL
        login_url = f"{FRONTEND_URL}/email-login?token={token}"
        print(f"\nLogin URL for {user.username} {user.email} (ID: {user.id}):")
        print(login_url)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Generate a login URL for a user")
    parser.add_argument("user_id", type=int, help="ID of the user")
    args = parser.parse_args()

    generate_login_url(args.user_id)


if __name__ == "__main__":
    main()
