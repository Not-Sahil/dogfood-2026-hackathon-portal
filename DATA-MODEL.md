# Data Model

## Core entities

`users` → authenticated actors with one of participant, judge, organizer, or admin roles.

`events` → event lifecycle and submission deadline.

`tracks`, `prizes` → event configuration.

`teams`, `team_members`, `team_invites` → team formation through one-time invites.

`projects`, `submissions` → project drafts and submitted snapshots.

`judges`, `judge_invites`, `judge_assignments` → judge lifecycle and assignment matrix.

`rubrics`, `criteria`, `scores` → configurable weighted judging system.

`audit_logs` → backend security and workflow trail.

## T3/T4 entities

`community_vote_configs` → configurable voting window and policy.

`community_votes` → one participant/project vote with duplicate protection and an address hash for rate limiting.

`community_comments` → public project discussion authored by authenticated participants.

`pairwise_comparisons` → judge/project-pair/winner records for Bradley-Terry recovery.

`webhook_endpoints` → event-scoped webhook registrations and shared secrets.

`judge_records` → signed participation record snapshots.

## Import/export paths

- `GET /api/export.csv?event_id=<id>` — judging results CSV.
- `GET /api/system/export/projects.csv?event_id=<id>` — bulk project CSV export.
- `POST /api/system/import/teams.csv?event_id=<id>` — team CSV import. Expected columns: `name,participant_email`.
- `GET /api/embed/gallery?event_id=<id>` — embeddable HTML gallery.
- `GET /api/judge-records/{judge_id}?event_id=<id>` — signed judge record.
- `GET /api/judge-records/{judge_id}/certificate?event_id=<id>` — printable certificate.
- `GET /api/public/judge-records/{record_id}` — publicly retrievable signed record.
