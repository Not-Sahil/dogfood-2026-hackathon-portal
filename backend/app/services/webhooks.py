import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.platform import WebhookEndpoint


def dispatch_webhook(db: Session, event_id: int | None, action: str, payload: dict) -> None:
    endpoints = db.scalars(
        select(WebhookEndpoint).where(
            WebhookEndpoint.active.is_(True),
            (WebhookEndpoint.event_id == event_id) | (WebhookEndpoint.event_id.is_(None)),
        )
    ).all()
    if not endpoints:
        return

    body = {
        "action": action,
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    for endpoint in endpoints:
        signature = hmac.new(endpoint.secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
        request = urllib.request.Request(endpoint.url, data=encoded, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Dogfood-Event", action)
        request.add_header("X-Dogfood-Signature", f"sha256={signature}")
        try:
            with urllib.request.urlopen(request, timeout=2):
                pass
        except (urllib.error.URLError, TimeoutError, OSError):
            # Webhook delivery is best-effort and must not block the portal.
            continue
