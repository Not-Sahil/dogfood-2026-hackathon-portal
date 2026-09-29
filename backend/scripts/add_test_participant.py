from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.models.user import User, UserRole


db = SessionLocal()

try:
    email = "participant2@dogfood.local"

    existing = db.scalar(
        select(User).where(User.email == email)
    )

    if existing:
        print("participant2 already exists")
    else:
        user = User(
            name="Participant 2",
            email=email,
            password_hash=hash_password("Participant2@123"),
            role=UserRole.PARTICIPANT,
        )

        db.add(user)
        db.commit()

        print("Created:")
        print("  email: participant2@dogfood.local")
        print("  password: Participant2@123")

finally:
    db.close()