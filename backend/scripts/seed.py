from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.services.fixture_seed import print_seed_tokens, seed_database


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        seed_database(db, settings.fixtures_path)
        print_seed_tokens(db)
    finally:
        db.close()
