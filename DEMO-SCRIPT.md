# DOGFOOD 2026 — Five-minute demo run-of-show

Use a fresh `docker compose up --build` stack. Keep the browser on `http://localhost:3000` and the FastAPI docs at `http://localhost:8000/docs` in a second tab if useful.

## 0:00–0:35 — Event + authentication
Show the public event overview and searchable gallery. Sign in as the seeded participant account and show the role-specific workspace.

## 0:35–1:20 — T1 submission flow
Open My Team, show the team, open My Projects, show a draft/submitted project, then open the public gallery. Mention that the backend enforces team membership and the submission deadline.

## 1:20–2:20 — T2 judging
Sign in as a judge. Open Assignments, open a submitted project, show the weighted rubric and save a review. Open Pairwise Mode and record one project comparison.

## 2:20–3:35 — Organizer judging integrity
Sign in as organizer. Show the progress dashboard, open Results, and point to raw score, normalized score, raw rank, normalized rank, rank change, judge breakdown, and integrity counts. Run the normalization proof and duplicate scan.

## 3:35–4:25 — T3 public layer
Open Community Voting as a participant. Show the randomized ballot, vote for a project, open comments, and explain that duplicate votes, account vote limits, address-rate limits, and hidden-results rules are enforced by the backend.

## 4:25–5:00 — T4 operations + export
Open Platform Operations as organizer. Show community policy controls, pairwise ranking, webhook registration, signed judge record, certificate, public verification key, project CSV export, and gallery embed endpoint. Finish with `python run.py .dogfood.toml` and the committed acceptance report showing the seven official T1/T2 checks.

## Suggested closing line

“JudgeForge keeps the portal self-hostable, keeps authorization in the backend, and makes the judging calculation inspectable instead of hiding it in the UI.”
