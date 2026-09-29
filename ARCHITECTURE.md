# Architecture

## System shape

```text
Browser
  |
  v
Next.js frontend
  |
  | /api/* via Next.js rewrite
  v
FastAPI
  |
  +-- JWT auth + RBAC
  +-- T1 event/team/project services
  +-- T2 judge/rubric/scoring/results
  +-- T3 community voting/comments/integrity
  +-- T4 webhooks/records/exports/embed
  |
  v
SQLAlchemy
  |
  v
SQLite
```

The browser never owns authoritative judging state. Scores, assignments, deadlines, voting constraints, results, and signed records are generated or enforced in the backend.

## Seed path

`backend/app/services/fixture_seed.py` loads the organizer-provided `fixtures.json`, maps fixture IDs into the local relational schema, builds a rubric from the fixture criterion keys, creates assignments from score records, and provisions local login accounts. On startup the seed also ensures a configurable community-voting window and writes fresh checker credentials into the root `.dogfood.toml` for the local compose environment.

## T2 result path

1. Completed criterion scores are grouped into judge/project evaluations.
2. Criterion weights produce a 0–5 weighted score.
3. Per-judge mean/std values are computed from completed evaluations.
4. A judge score with sufficient history is converted to a z-score and mapped back to the panel distribution.
5. Raw and normalized project averages are calculated separately.
6. Raw rank, normalized rank, rank change, judge breakdown, anomalies, and incomplete-review counts are returned together.

## T3 voting path

Authenticated participant requests receive a deterministic HMAC-derived project ordering. Votes are constrained by a database uniqueness rule and a per-event account allowance. Results are withheld until the configured voting end when the hidden-results policy is active. Comments and votes produce audit records and can trigger webhooks.

## T4 records

Webhooks are local database registrations with HMAC-signed JSON delivery. Judge participation records are signed with a persisted Ed25519 private key; the corresponding public key is exposed through the API and the public record endpoint returns the signature and verification result. Certificates render the same signed record into a printable HTML page.

## API surface

FastAPI's `/openapi.json` is generated from the real route definitions. All UI flows use documented HTTP routes; no hidden browser-only mutation path exists.
