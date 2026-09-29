# DOGFOOD 2026 — Integrated Hackathon Portal

Self-hostable submission, judging, community voting, pairwise judging, and event-operations portal built with Next.js, FastAPI, SQLAlchemy, and SQLite.

## One-command start

```powershell
docker compose up --build
```

Open `http://localhost:3000`.

The backend is available at `http://localhost:8000` and FastAPI exposes its OpenAPI document at `/openapi.json` and interactive docs at `/docs`.

The compose stack uses a local SQLite volume, seeds from the organizer-provided `fixtures.json`, and does not require a hosted database, cloud account, external API, or network connectivity after dependencies have been built locally.

## Roles

Participant: team formation, invite links, project drafts/editing, submissions, and community voting.

Judge: assigned project reviews, weighted rubric scoring, and pairwise comparisons for the optional ranking mode.

Organizer: events, tracks, prizes, judges, assignments, rubric, results, normalization, integrity, community-voting policy, pairwise ranking, webhooks, exports, certificates, and signed judge records.

Admin: platform-level administration with the same backend enforcement boundary.

## DOGFOOD acceptance workflow

The official checker is committed at `run.py`, the official fixture file is at `fixtures.json`, and `.dogfood.toml` is committed at the repository root. The compose seed uses deterministic demo identities so the committed checker headers work on a fresh local database with the default compose secret.

After the portal is running:

```powershell
python run.py .dogfood.toml > acceptance-report.txt
```

The checker is authoritative for the published T1/T2 acceptance checks; it does not inspect the frontend. Keep the report generated from the running portal and commit that exact output.

## Implemented tier coverage

### T1 — Core

Authentication and JWT sessions, participant/judge/organizer/admin roles, event creation and date validation, tracks and prizes, team formation through invite links, draft/edit/submit projects, backend deadline enforcement, and public searchable gallery.

### T2 — Judging

Judge invites, batch/algorithmic assignments, configurable weighted rubric, backend-enforced score isolation, judge progress, cross-judge normalization, integrity views, rank movement, and CSV export.

### T3 — Public

Configurable community voting window, comments, results hidden until voting closes, deterministic per-user randomized ballot ordering, authenticated voting, one-vote-per-project protection, per-account vote allowance, short-window address rate limiting, duplicate submission fingerprints, and audit records.

### T4 — Stretch

REST API/OpenAPI, event webhooks with HMAC signatures, printable judge certificates, signed Ed25519 judge participation records with a public verification key, embeddable gallery HTML, bulk project export, and CSV team import.

## Bonus implementations

Normalization Proof: the backend exposes raw score, normalized score, raw rank, normalized rank, rank change, judge-level normalization details, and an explicit normalization endpoint at `/api/normalization/proof`.

Pairwise Mode: judges can compare two assigned projects at `/api/pairwise/next` and submit preferences at `/api/pairwise/vote`; organizers recover a ranking with a Bradley-Terry MM estimator at `/api/pairwise/ranking`.

## Important integrity decisions

The backend is the authorization boundary. A hidden button is never treated as access control.

Community voting is intentionally account-based rather than anonymous so duplicate ballots can be rejected at the database constraint. A per-account allowance and short-window address rate limit provide additional anti-abuse controls. These controls reduce common abuse patterns but do not claim to prove real-world identity.

Normalization is a documented statistical calibration choice, not an assertion that every judge has been made objectively equal. Judges with insufficient history or near-zero variance are handled conservatively.

Pairwise rankings are calculated independently of the rubric normalization path, so an organizer can compare the two methodologies instead of silently replacing one with the other.

## Demo accounts

- Organizer: `organizer@dogfood.local` / `Organizer123!`
- Participant: `participant@dogfood.local` / `Participant123!`
- Fixture judges: the seed command prints the first two judge identities and fresh local tokens.

## Submission files

- `.dogfood.toml`
- `acceptance-report.txt`
- `run.py`
- `fixtures.json`
- `SPEC.md`
- `LICENSE`
- `ARCHITECTURE.md`
- `DATA-MODEL.md`
- `JUDGING.md`
- `THREAT-MODEL.md`
- tests
- `DEMO-SCRIPT.md` is included as the run-of-show; paste the final recording link here before submission
