import json

from sqlalchemy.orm import Session

from app.db.models.audit import AuditLog


def write_audit(
    db: Session,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=json.dumps(details or {}),
        )
    )
