from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.services.fixture_seed import seed_database, print_seed_tokens
from app.routers import auth, events, teams, projects, judges, judging, results, community, pairwise, platform

app = FastAPI(
    title="JudgeForge API",
    description="Hackathon submission and judging platform",
    version="1.0.0",
)

allow_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(judges.router)
app.include_router(judging.router)
app.include_router(results.router)
app.include_router(community.router)
app.include_router(pairwise.router)
app.include_router(platform.router)


@app.on_event("startup")
def startup() -> None:
    if settings.auto_create_db:
        init_db()

    if settings.seed_on_start:
        db = SessionLocal()
        try:
            seed_database(db, settings.fixtures_path)
            print_seed_tokens(db)
        finally:
            db.close()


@app.get("/")
def root():
    return {
        "name": "JudgeForge API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }
