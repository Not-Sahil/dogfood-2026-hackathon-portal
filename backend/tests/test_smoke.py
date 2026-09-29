import os

os.environ["DATABASE_URL"] = "sqlite:///./test_dogfood.db"
os.environ["AUTO_CREATE_DB"] = "true"
os.environ["SEED_ON_START"] = "true"

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import engine
from app.db.database import Base


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_gallery():
    response = client.get("/api/projects")
    assert response.status_code == 200


def teardown_module():
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_dogfood.db"):
        os.remove("test_dogfood.db")
