from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import require_roles
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.event import Event, Prize, Track
from app.db.models.user import User, UserRole
from app.schemas.event import (
    EventCreate,
    EventOut,
    EventUpdate,
    PrizeCreate,
    PrizeOut,
    TrackCreate,
    TrackOut,
)
from app.services.audit import write_audit


router = APIRouter(
    prefix="/api/events",
    tags=["Events"],
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def get_event_or_404(db: Session, event_id: int) -> Event:
    event = db.scalar(
        select(Event)
        .options(
            joinedload(Event.tracks),
            joinedload(Event.prizes),
        )
        .where(Event.id == event_id)
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return event


def event_status(event: Event) -> str:
    now = utcnow()

    start = ensure_utc(event.start_date)
    deadline = ensure_utc(event.submission_deadline)

    if now < start:
        return "upcoming"

    if now > deadline:
        return "closed"

    return "open"


def build_event_response(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        name=event.name,
        description=event.description,
        start_date=event.start_date,
        end_date=event.end_date,
        submission_deadline=event.submission_deadline,
        status=event_status(event),
        tracks=event.tracks,
        prizes=event.prizes,
    )


# -------------------------------------------------------------------
# Events
# -------------------------------------------------------------------

@router.get(
    "",
    response_model=list[EventOut],
)
def list_events(
    db: Session = Depends(get_db),
):
    events = db.scalars(
        select(Event)
        .options(
            joinedload(Event.tracks),
            joinedload(Event.prizes),
        )
        .order_by(Event.id.desc())
    ).unique().all()

    return [
        build_event_response(event)
        for event in events
    ]


@router.get(
    "/{event_id}",
    response_model=EventOut,
)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = get_event_or_404(db, event_id)
    return build_event_response(event)


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    start_date = ensure_utc(payload.start_date)
    end_date = ensure_utc(payload.end_date)
    submission_deadline = ensure_utc(payload.submission_deadline)

    if not (
        start_date < submission_deadline <= end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Dates must satisfy: "
                "start_date < submission_deadline <= end_date"
            ),
        )

    event = Event(
        name=payload.name.strip(),
        description=payload.description.strip()
        if payload.description
        else None,
        start_date=start_date,
        end_date=end_date,
        submission_deadline=submission_deadline,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    write_audit(
        db,
        user.id,
        "event.create",
        "event",
        event.id,
    )

    db.commit()

    return build_event_response(event)


@router.put(
    "/{event_id}",
    response_model=EventOut,
)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    event = db.get(Event, event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():

        if field == "name":
            value = value.strip()

        elif field == "description" and value is not None:
            value = value.strip()

        elif field in {
            "start_date",
            "end_date",
            "submission_deadline",
        } and value is not None:
            value = ensure_utc(value)

        setattr(event, field, value)

    start_date = ensure_utc(event.start_date)
    end_date = ensure_utc(event.end_date)
    submission_deadline = ensure_utc(
        event.submission_deadline
    )

    if not (
        start_date < submission_deadline <= end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Dates must satisfy: "
                "start_date < submission_deadline <= end_date"
            ),
        )

    db.commit()

    write_audit(
        db,
        user.id,
        "event.update",
        "event",
        event.id,
    )

    db.commit()

    return build_event_response(
        get_event_or_404(db, event_id)
    )


# -------------------------------------------------------------------
# Tracks
# -------------------------------------------------------------------

@router.post(
    "/{event_id}/tracks",
    response_model=TrackOut,
    status_code=status.HTTP_201_CREATED,
)
def create_track(
    event_id: int,
    payload: TrackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    if not db.get(Event, event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    track = Track(
        event_id=event_id,
        name=payload.name.strip(),
    )

    db.add(track)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Track already exists in this event",
        ) from exc

    db.refresh(track)

    write_audit(
        db,
        user.id,
        "track.create",
        "track",
        track.id,
    )

    db.commit()

    return track


@router.put(
    "/tracks/{track_id}",
    response_model=TrackOut,
)
def update_track(
    track_id: int,
    payload: TrackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    track = db.get(Track, track_id)

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    track.name = payload.name.strip()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Track name already exists in this event",
        ) from exc

    db.refresh(track)

    write_audit(
        db,
        user.id,
        "track.update",
        "track",
        track.id,
    )

    db.commit()

    return track


@router.delete(
    "/tracks/{track_id}",
)
def delete_track(
    track_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    track = db.get(Track, track_id)

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    if track.projects:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a track that has projects",
        )

    db.delete(track)
    db.commit()

    write_audit(
        db,
        user.id,
        "track.delete",
        "track",
        track.id,
    )

    db.commit()

    return {
        "message": "Track deleted",
    }


# -------------------------------------------------------------------
# Prizes
# -------------------------------------------------------------------

@router.post(
    "/{event_id}/prizes",
    response_model=PrizeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prize(
    event_id: int,
    payload: PrizeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    if not db.get(Event, event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    prize = Prize(
        event_id=event_id,
        title=payload.title.strip(),
        description=payload.description.strip()
        if payload.description
        else None,
        amount=payload.amount,
        rank=payload.rank,
    )

    db.add(prize)
    db.commit()
    db.refresh(prize)

    write_audit(
        db,
        user.id,
        "prize.create",
        "prize",
        prize.id,
    )

    db.commit()

    return prize


@router.put(
    "/prizes/{prize_id}",
    response_model=PrizeOut,
)
def update_prize(
    prize_id: int,
    payload: PrizeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    prize = db.get(Prize, prize_id)

    if not prize:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prize not found",
        )

    prize.title = payload.title.strip()

    prize.description = (
        payload.description.strip()
        if payload.description
        else None
    )

    prize.amount = payload.amount
    prize.rank = payload.rank

    db.commit()
    db.refresh(prize)

    write_audit(
        db,
        user.id,
        "prize.update",
        "prize",
        prize.id,
    )

    db.commit()

    return prize


@router.delete(
    "/prizes/{prize_id}",
)
def delete_prize(
    prize_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    prize = db.get(Prize, prize_id)

    if not prize:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prize not found",
        )

    db.delete(prize)
    db.commit()

    write_audit(
        db,
        user.id,
        "prize.delete",
        "prize",
        prize.id,
    )

    db.commit()

    return {
        "message": "Prize deleted",
    }