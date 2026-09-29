# DOGFOOD 2026 — Integrated Hackathon Portal

A self-hostable submission, judging, community voting, pairwise judging, and event-operations portal built with **Next.js, FastAPI, SQLAlchemy, and SQLite**.

---

## 🚀 One-Command Start

Start the complete application with:

```powershell
docker compose up --build
```

Once the application is running, open:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
```

FastAPI exposes:

* OpenAPI document: `http://localhost:8000/openapi.json`
* Interactive API documentation: `http://localhost:8000/docs`

The Compose stack uses a **local SQLite volume** and seeds the database from the organizer-provided `fixtures.json`.

The application does **not** require a hosted database, cloud account, external API, or network connectivity after dependencies have been built locally.

---

# 👥 Roles

## Participant

Participants can:

* Form teams
* Create and use invite links
* Create and edit project drafts
* Submit projects
* Participate in community voting

## Judge

Judges can:

* Review assigned projects
* Use weighted rubric scoring
* Perform pairwise comparisons for the optional ranking mode

## Organizer

Organizers can manage:

* Events
* Tracks
* Prizes
* Judges
* Judge assignments
* Rubrics
* Results
* Score normalization
* Integrity
* Community-voting policy
* Pairwise ranking
* Webhooks
* Exports
* Certificates
* Signed judge records

## Admin

Admins provide platform-level administration with the **same backend enforcement boundary**.

---

# 🧪 DOGFOOD Acceptance Workflow

The official checker is committed at:

```text
run.py
```

The official fixture file is:

```text
fixtures.json
```

The DOGFOOD configuration is committed at the repository root:

```text
.dogfood.toml
```

The Compose seed uses **deterministic demo identities**, allowing the committed checker headers to work on a fresh local database with the default Compose secret.

### Run the acceptance checker

After the portal is running:

```powershell
python run.py .dogfood.toml > acceptance-report.txt
```

The checker is authoritative for the published **T1/T2 acceptance checks**.

> The checker does not inspect the frontend.

Keep the report generated from the running portal and commit that **exact output** as `acceptance-report.txt`.

---

# 📋 Implemented Tier Coverage

## T1 — Core

The core tier includes:

* Authentication and JWT sessions
* Participant, judge, organizer, and admin roles
* Event creation and date validation
* Tracks and prizes
* Team formation through invite links
* Draft, edit, and submit projects
* Backend deadline enforcement
* Public searchable gallery

---

## T2 — Judging

The judging tier includes:

* Judge invites
* Batch/algorithmic assignments
* Configurable weighted rubric
* Backend-enforced score isolation
* Judge progress
* Cross-judge normalization
* Integrity views
* Rank movement
* CSV export

---

## T3 — Public

The public tier includes:

* Configurable community voting window
* Comments
* Results hidden until voting closes
* Deterministic per-user randomized ballot ordering
* Authenticated voting
* One-vote-per-project protection
* Per-account vote allowance
* Short-window address rate limiting
* Duplicate submission fingerprints
* Audit records

---

## T4 — Stretch

The stretch tier includes:

* REST API / OpenAPI
* Event webhooks with HMAC signatures
* Printable judge certificates
* Signed Ed25519 judge participation records
* Public verification key
* Embeddable gallery HTML
* Bulk project export
* CSV team import

---

# 🏆 Bonus Implementations

## Normalization Proof

The backend exposes:

* Raw score
* Normalized score
* Raw rank
* Normalized rank
* Rank change
* Judge-level normalization details

An explicit normalization endpoint is available at:

```text
/api/normalization/proof
```

---

## Pairwise Mode

Judges can compare two assigned projects at:

```text
/api/pairwise/next
```

Judges submit their preferences at:

```text
/api/pairwise/vote
```

Organizers can recover a ranking using a **Bradley-Terry MM estimator** at:

```text
/api/pairwise/ranking
```

Pairwise judging is independent of the rubric normalization path, allowing organizers to compare the two methodologies rather than silently replacing one with the other.

---

# 🔐 Important Integrity Decisions

## Backend Authorization Boundary

The backend is the authorization boundary.

A hidden button is **never treated as access control**.

Frontend visibility does not determine whether an operation is authorized; authorization is enforced by the backend.

---

## Account-Based Community Voting

Community voting is intentionally **account-based rather than anonymous** so duplicate ballots can be rejected at the database constraint.

Additional controls include:

* Per-account vote allowance
* Short-window address rate limiting
* Duplicate submission fingerprints
* Audit records

These controls reduce common abuse patterns but do **not** claim to prove real-world identity.

---

## Score Normalization

Normalization is a documented **statistical calibration choice**.

It is not an assertion that every judge has been made objectively equal.

Judges with insufficient history or near-zero variance are handled conservatively.

---

## Independent Pairwise Rankings

Pairwise rankings are calculated independently of the rubric normalization path.

This allows an organizer to compare the two methodologies instead of silently replacing one with the other.

---

# 👤 Demo Accounts

## Organizer

```text
Email:    organizer@dogfood.local
Password: Organizer123!
```

## Participant

```text
Email:    participant@dogfood.local
Password: Participant123!
```

## Fixture Judges

The seed command prints the **first two judge identities and fresh local tokens**.

---

# 📁 Submission Files

The repository contains the following submission and supporting files:

```text
.dogfood.toml
acceptance-report.txt
run.py
fixtures.json
SPEC.md
LICENSE
ARCHITECTURE.md
DATA-MODEL.md
JUDGING.md
THREAT-MODEL.md
tests
DEMO-SCRIPT.md
```

`DEMO-SCRIPT.md` is included as the **run-of-show** for the project demonstration.

Before submission, paste the **final recording link** into `DEMO-SCRIPT.md`.

---

# 🛠️ Local Workflow

### 1. Start the portal

```powershell
docker compose up --build
```

### 2. Open the application

```text
http://localhost:3000
```

### 3. Access the backend

```text
http://localhost:8000
```

### 4. Access FastAPI documentation

```text
http://localhost:8000/docs
```

### 5. Run the DOGFOOD acceptance checker

```powershell
python run.py .dogfood.toml > acceptance-report.txt
```

The resulting `acceptance-report.txt` should be generated from the running portal and committed as the exact checker output.

---

# 📚 Project Documentation

Additional project documentation is included in the repository:

* `SPEC.md` — project specification
* `ARCHITECTURE.md` — system architecture
* `DATA-MODEL.md` — data model
* `JUDGING.md` — judging system
* `THREAT-MODEL.md` — threat model
* `DEMO-SCRIPT.md` — demonstration run-of-show

---

## 📄 License

See [`LICENSE`](LICENSE) for the project's licensing information.
