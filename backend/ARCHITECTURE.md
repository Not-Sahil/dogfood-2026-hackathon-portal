# Architecture

React frontend -> FastAPI backend -> SQLite for the local build.

The backend is a modular monolith with routers for auth, events, teams, projects, judges, judging, and results.

Sensitive access is enforced server-side through authentication, role checks, and resource ownership/assignment checks.

Judging pipeline:

assignment -> rubric -> criterion scores -> weighted raw score -> cross-judge normalization -> ranking -> CSV/export + explanation.

Audit logs capture important actions such as project submission, judge assignment, and score submission.
