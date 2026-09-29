# DOGFOOD 2026 — Submission & Judging Portal

This frontend keeps the supplied Paper Ops visual design and connects its role-specific workspaces to the integrated FastAPI backend.

## Local

```bash
npm ci
npm run dev
```

Open `http://localhost:3000`. Browser requests use same-origin `/api`; `next.config.ts` forwards them to FastAPI at `API_INTERNAL_URL` (default `http://127.0.0.1:8000`). A direct browser API origin can instead be supplied through `NEXT_PUBLIC_API_BASE_URL`.

## Production

```bash
npm ci
npm run build
npm start
```

The app uses the normal Next.js server runtime so `/api` rewrites work without a separate browser-side API hostname.

## Real vs fixture data

`NEXT_PUBLIC_FIXTURE_DATA=0` is the default and uses the backend. Setting it to `1` deliberately enables the frontend's existing illustrative fixture paths after authentication; it is not required for the integrated portal.

## Workspaces

- Participant: authentication, team creation/join, project draft/edit/submit.
- Judge: assigned-project list, rubric loading, scoring, progress.
- Organizer: events, projects, teams, judges, assignments, rubric, results, integrity, CSV export.
- Admin: read-only overview screens where no backend mutation route is defined.

Backend authorization remains authoritative; frontend route guards are only presentation/navigation.
