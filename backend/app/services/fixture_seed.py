import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import create_access_token, hash_password
from app.db.models import (
    Criterion,
    Event,
    Judge,
    JudgeAssignment,
    Prize,
    Project,
    ProjectStatus,
    Rubric,
    Score,
    Submission,
    Team,
    TeamMember,
    CommunityVoteConfig,
    Track,
    User,
    UserRole,
)


DEMO_PASSWORDS = {
    "organizer@dogfood.local": "Organizer123!",
    "judge_a@dogfood.local": "JudgeA123!",
    "judge_b@dogfood.local": "JudgeB123!",
    "participant@dogfood.local": "Participant123!",
}


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_or_create_user(db: Session, email: str, name: str, role: UserRole, password: str = "Demo123!") -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(name=name, email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


def _ensure_demo(db: Session) -> None:
    if db.scalar(select(Event).limit(1)):
        return

    now = datetime.now(timezone.utc)
    event = Event(
        name="DOGFOOD Demo 2026",
        description="Local seeded demonstration event.",
        start_date=now - timedelta(days=7),
        end_date=now + timedelta(days=7),
        submission_deadline=now + timedelta(days=2),
    )
    db.add(event)
    db.flush()

    track = Track(event_id=event.id, name="Developer Tools")
    db.add(track)
    db.add(Prize(event_id=event.id, title="Grand Prize", amount=80000, rank=1, description="Demo prize"))

    org = _get_or_create_user(db, "organizer@dogfood.local", "Organizer", UserRole.ORGANIZER, DEMO_PASSWORDS["organizer@dogfood.local"])
    judge_a_user = _get_or_create_user(db, "judge_a@dogfood.local", "Judge A", UserRole.JUDGE, DEMO_PASSWORDS["judge_a@dogfood.local"])
    judge_b_user = _get_or_create_user(db, "judge_b@dogfood.local", "Judge B", UserRole.JUDGE, DEMO_PASSWORDS["judge_b@dogfood.local"])
    participant = _get_or_create_user(db, "participant@dogfood.local", "Participant", UserRole.PARTICIPANT, DEMO_PASSWORDS["participant@dogfood.local"])

    judge_a = Judge(user_id=judge_a_user.id)
    judge_b = Judge(user_id=judge_b_user.id)
    db.add_all([judge_a, judge_b])
    db.flush()

    team = Team(event_id=event.id, name="Demo Team", created_by=participant.id)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=participant.id, is_captain=True))

    project = Project(
        event_id=event.id,
        team_id=team.id,
        track_id=track.id,
        title="SecureAI",
        summary="Demo project for the local platform.",
        repo_url="https://example.org/repo",
        demo_url="https://example.org/demo",
        status=ProjectStatus.SUBMITTED,
    )
    db.add(project)
    db.flush()
    db.add(Submission(project_id=project.id, submitted_at=now))
    db.add_all([
        JudgeAssignment(judge_id=judge_a.id, project_id=project.id),
        JudgeAssignment(judge_id=judge_b.id, project_id=project.id),
    ])

    rubric = Rubric(event_id=event.id, name="Default Rubric", active=True)
    db.add(rubric)
    db.flush()
    c1 = Criterion(rubric_id=rubric.id, name="Innovation", weight=50, max_score=5)
    c2 = Criterion(rubric_id=rubric.id, name="Technical Quality", weight=50, max_score=5)
    db.add_all([c1, c2])
    db.flush()
    db.add_all([
        Score(judge_id=judge_a.id, project_id=project.id, criterion_id=c1.id, score=5, comment="Strong idea."),
        Score(judge_id=judge_a.id, project_id=project.id, criterion_id=c2.id, score=4, comment="Good implementation."),
        Score(judge_id=judge_b.id, project_id=project.id, criterion_id=c1.id, score=4, comment="Clear value."),
        Score(judge_id=judge_b.id, project_id=project.id, criterion_id=c2.id, score=3, comment="Solid."),
    ])

    db.commit()


def _seed_fixture(db: Session, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False

    if not payload.get("event"):
        return False

    event_data = payload["event"]
    if db.scalar(select(Event).where(Event.name == event_data.get("name", "Sample Hack 2026"))):
        return True

    close = _parse_dt(event_data["submissions_close"])
    event = Event(
        name=event_data.get("name", "Sample Hack 2026"),
        description="Seeded from organizer fixtures.",
        start_date=close - timedelta(days=7),
        end_date=close,
        submission_deadline=close,
    )
    db.add(event)
    db.flush()

    track_map: dict[str, Track] = {}
    for item in payload.get("tracks", []):
        track = Track(event_id=event.id, name=item["name"])
        db.add(track)
        db.flush()
        track_map[item["id"]] = track

    for item in payload.get("prizes", []):
        db.add(Prize(
            event_id=event.id,
            title=item.get("title", "Prize"),
            description=item.get("description"),
            amount=item.get("amount"),
            rank=item.get("rank"),
        ))

    # Keep two dedicated checker accounts at deterministic user IDs on a fresh
    # database. This makes the committed .dogfood.toml usable immediately after
    # `docker compose up`, without depending on runtime token rewriting inside
    # the backend container.
    _get_or_create_user(
        db,
        "organizer@dogfood.local",
        "Organizer",
        UserRole.ORGANIZER,
        DEMO_PASSWORDS["organizer@dogfood.local"],
    )
    _get_or_create_user(
        db,
        "participant@dogfood.local",
        "Participant",
        UserRole.PARTICIPANT,
        DEMO_PASSWORDS["participant@dogfood.local"],
    )

    user_by_email: dict[str, User] = {}
    judge_map: dict[str, Judge] = {}
    for index, item in enumerate(payload.get("judges", []), start=1):
        email = item["email"]
        user = _get_or_create_user(db, email, item.get("name", f"Judge {index}"), UserRole.JUDGE, f"Judge{index}123!")
        user_by_email[email] = user
        judge = Judge(user_id=user.id)
        db.add(judge)
        db.flush()
        judge_map[item["id"]] = judge

    team_map: dict[str, Team] = {}
    for index, item in enumerate(payload.get("teams", []), start=1):
        members = item.get("members", [])
        captain_email = members[0] if members else f"participant{index}@fixture.local"
        participant = user_by_email.get(captain_email)
        if not participant:
            participant = _get_or_create_user(db, captain_email, captain_email.split("@")[0], UserRole.PARTICIPANT, "Participant123!")
            user_by_email[captain_email] = participant
        team = Team(event_id=event.id, name=item["name"], created_by=participant.id)
        db.add(team)
        db.flush()
        team_map[item["id"]] = team
        for pos, email in enumerate(members):
            user = user_by_email.get(email)
            if not user:
                user = _get_or_create_user(db, email, email.split("@")[0], UserRole.PARTICIPANT, "Participant123!")
                user_by_email[email] = user
            db.add(TeamMember(team_id=team.id, user_id=user.id, is_captain=(pos == 0)))

    project_map: dict[str, Project] = {}
    for item in payload.get("projects", []):
        team = team_map[item["team"]]
        track = track_map[item["track"]]
        submitted_at = _parse_dt(item["submitted_at"]) if item.get("submitted_at") else None
        project = Project(
            event_id=event.id,
            team_id=team.id,
            track_id=track.id,
            title=item["title"],
            summary=item.get("summary", ""),
            repo_url=item.get("repo_url"),
            demo_url=item.get("demo_url"),
            status=ProjectStatus.SUBMITTED if submitted_at else ProjectStatus.DRAFT,
        )
        db.add(project)
        db.flush()
        project_map[item["id"]] = project
        if submitted_at:
            db.add(Submission(project_id=project.id, submitted_at=submitted_at))

    # Build a rubric from score keys when fixtures do not explicitly provide a rubric.
    criterion_names: list[str] = []
    for score_item in payload.get("scores", []):
        for key in score_item.get("criteria", {}).keys():
            if key not in criterion_names:
                criterion_names.append(key)
    if not criterion_names:
        criterion_names = ["Functionality", "Quality"]

    rubric = Rubric(event_id=event.id, name="Fixture Rubric", active=True)
    db.add(rubric)
    db.flush()
    weight = round(100.0 / len(criterion_names), 4)
    for i, name in enumerate(criterion_names):
        db.add(Criterion(rubric_id=rubric.id, name=name, weight=(100 - weight * (len(criterion_names)-1)) if i == len(criterion_names)-1 else weight, max_score=5))
    db.flush()
    criterion_map = {c.name: c for c in db.scalars(select(Criterion).where(Criterion.rubric_id == rubric.id)).all()}

    for score_item in payload.get("scores", []):
        judge = judge_map.get(score_item["judge"])
        project = project_map.get(score_item["project"])
        if not judge or not project:
            continue
        db.merge(JudgeAssignment(judge_id=judge.id, project_id=project.id))
        for criterion_name, value in score_item.get("criteria", {}).items():
            criterion = criterion_map.get(criterion_name)
            if criterion:
                db.add(Score(
                    judge_id=judge.id,
                    project_id=project.id,
                    criterion_id=criterion.id,
                    score=float(value),
                    comment=score_item.get("comment"),
                ))

    db.commit()
    return True


def _ensure_community_config(db: Session, event: Event) -> None:
    from app.core.time import utcnow

    existing = db.scalar(select(CommunityVoteConfig).where(CommunityVoteConfig.event_id == event.id))
    if existing:
        return

    now = utcnow()
    db.add(CommunityVoteConfig(
        event_id=event.id,
        voting_start=now - timedelta(minutes=15),
        voting_end=now + timedelta(hours=24),
        results_hidden_until_close=True,
        max_votes_per_user=5,
        active=True,
    ))
    db.commit()


def _ensure_pairwise_assignments(db: Session, event: Event) -> None:
    judges = db.scalars(select(Judge).order_by(Judge.id)).all()[:2]
    projects = db.scalars(select(Project).where(Project.event_id == event.id, Project.status == ProjectStatus.SUBMITTED).order_by(Project.id)).all()[:6]
    if not judges or len(projects) < 2:
        return
    changed = False
    for judge in judges:
        # Give the first two fixture judges at least four projects, so the pairwise mode is demoable
        # even when the shared fixture has sparse assignments for a particular judge.
        for project in projects:
            existing = db.scalar(select(JudgeAssignment).where(JudgeAssignment.judge_id == judge.id, JudgeAssignment.project_id == project.id))
            if not existing:
                db.add(JudgeAssignment(judge_id=judge.id, project_id=project.id))
                changed = True
            if sum(1 for a in db.scalars(select(JudgeAssignment).where(JudgeAssignment.judge_id == judge.id)).all()) >= 4:
                break
    if changed:
        db.commit()



def seed_database(db: Session, fixture_path: str) -> None:
    fixture_env = os.getenv("FIXTURES_PATH", fixture_path)
    fixture = Path(fixture_env)
    seeded = _seed_fixture(db, fixture)
    if not seeded:
        _ensure_demo(db)
    event = db.scalar(select(Event).order_by(Event.id))
    if event:
        _ensure_community_config(db, event)
        _ensure_pairwise_assignments(db, event)


def print_seed_tokens(db: Session) -> None:
    print("seeded. test accounts:")
    demo_org = db.scalar(select(User).where(User.email == "organizer@dogfood.local"))
    demo_participant = db.scalar(select(User).where(User.email == "participant@dogfood.local"))
    if not demo_org:
        demo_org = _get_or_create_user(
            db, "organizer@dogfood.local", "Organizer", UserRole.ORGANIZER, DEMO_PASSWORDS["organizer@dogfood.local"]
        )
        db.commit()
    if not demo_participant:
        demo_participant = _get_or_create_user(
            db, "participant@dogfood.local", "Participant", UserRole.PARTICIPANT, DEMO_PASSWORDS["participant@dogfood.local"]
        )
        db.commit()

    print(f"  organizer: organizer@dogfood.local / {DEMO_PASSWORDS['organizer@dogfood.local']}")
    print(f"  participant: participant@dogfood.local / {DEMO_PASSWORDS['participant@dogfood.local']}")

    judges = db.scalars(
        select(Judge).options(joinedload(Judge.user)).order_by(Judge.id)
    ).all()
    for label, judge in zip(("judge_a", "judge_b"), judges[:2]):
        token = create_access_token(judge.user_id, judge.user.role.value, expires_minutes=60 * 24 * 3650)
        print(f"  {label}: judge_id={judge.id} user={judge.user.email} Authorization: Bearer {token}")

    org_token = create_access_token(demo_org.id, demo_org.role.value, expires_minutes=60 * 24 * 3650)
    participant_token = create_access_token(demo_participant.id, demo_participant.role.value, expires_minutes=60 * 24 * 3650)
    print(f"  organizer_token: Authorization: Bearer {org_token}")
    print(f"  participant_token: Authorization: Bearer {participant_token}")
