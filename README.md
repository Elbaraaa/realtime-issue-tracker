# Realtime Issue Tracker

A full-stack issue tracker with a kanban board that updates live for everyone
on a project. Drag a card, and your teammates see it move.

**Stack:** FastAPI · SQLAlchemy 2 · PostgreSQL · Alembic · React 19 · TypeScript ·
TanStack Query · WebSockets · Docker · GitHub Actions

![Kanban board](docs/board.png)

![Issue panel with comments and history](docs/issue.png)

## Features

- Accounts with JWT authentication
- Projects with owners and members, invited by email
- Issues with per-project keys (`WEB-12`), status, priority, assignee
- Drag-and-drop kanban board, within and between columns
- Comments and a full change history on every issue
- Live updates over WebSockets, with automatic reconnect and resync

## Running it

```bash
docker compose up --build
```

Open <http://localhost:8080>, create an account, and create a project. Open a
second browser profile with another account and invite it to see live updates.
If port 8080 is taken, run `WEB_PORT=8090 docker compose up --build`.

For development with hot reload:

```bash
docker compose up db -d
cd backend && pip install -e ".[dev]" && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Architecture

```
browser ──HTTP /api──▶ nginx ──▶ FastAPI ──▶ PostgreSQL
   ▲                     │           │
   └────WebSocket /api/ws┘           └─ in-process hub fans activity out
```

Every write goes through the same path: validate, change rows, append an
`activity` row **in the same transaction**, commit, then publish that activity
to the project's WebSocket subscribers. The audit log and the live feed are the
same data, so they can't drift apart.

## Design decisions

**Issue numbers that never collide.** Each project keeps an `issue_seq`
counter. Creating an issue takes a `SELECT … FOR UPDATE` lock on the project
row, increments it, and inserts, so two people creating issues at the same
moment get `WEB-7` and `WEB-8`, never two `WEB-7`s. A unique constraint on
`(project_id, number)` backs this up.

**No silent overwrites.** Every issue has a `version`. Clients send the version
they read with each update; if someone else changed the issue in between, the
API returns `409 Conflict` instead of overwriting their work. The board rolls
back its optimistic move and refetches.

**Cheap reordering.** Cards have sparse float positions. Dropping a card between
two others takes the midpoint of their positions, so a move rewrites exactly
one row, no matter how long the column is.

**WebSocket auth without tokens in URLs.** The socket authenticates with its
first message (`{"token": "…"}`) rather than a query string, which keeps JWTs out
of proxy and access logs. Bad tokens close with `4401`, non-members with `4403`.
Clients reconnect with capped exponential backoff and refetch on every
reconnect, so nothing is lost while offline.

**Slowing down password guessing.** Failed sign-ins are counted in a sliding
15-minute window per account (5) and per client IP (20). Past either limit the
API answers `429` with `Retry-After`, before checking the password, so a
locked-out guesser can't confirm a correct one. A successful sign-in clears the
account's count. nginx passes the real client IP, and the API trusts it
because it is only reachable through nginx.

**Not leaking what exists.** Non-members get `404`, not `403`, for projects and
issues, so IDs can't be probed. Login checks a dummy bcrypt hash for unknown
emails, so response time doesn't reveal which accounts exist.

### Known limits

- The WebSocket hub is in-process, so it supports one API replica. Scaling out
  means putting Postgres `LISTEN/NOTIFY` or Redis pub/sub behind the same
  `publish`/`subscribe` interface in `backend/app/events.py`.
- Sign-in rate limits live in memory for the same reason, and there is no
  refresh-token rotation yet.

## Testing

```bash
cd backend && pytest                # SQLite by default
TEST_DATABASE_URL=postgresql+psycopg://tracker:tracker@localhost:5432/tracker_test pytest
cd frontend && npm run typecheck && npm test
```

CI runs on every push and pull request:

- **Backend:** ruff lint and format checks, then Alembic migrations. They are
  applied, checked against the models and rolled back. Then pytest against
  Postgres 16.
- **Frontend:** typecheck, Vitest and a production build.
- **Images:** a Docker Compose build of both images.

## API overview

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/auth/register`, `/api/auth/login` | Returns a JWT |
| `GET` | `/api/auth/me` | Current user |
| `GET` `POST` | `/api/projects` | Your projects / create one |
| `GET` `POST` | `/api/projects/{id}/members` | Owners add members by email |
| `GET` `POST` | `/api/projects/{id}/issues` | Filters: `status`, `assignee_id`, `q`, `limit`, `offset` |
| `GET` `PATCH` `DELETE` | `/api/issues/{id}` | `PATCH` requires `version` |
| `GET` `POST` | `/api/issues/{id}/comments` | |
| `GET` | `/api/issues/{id}/activity` | Change history |
| `WS` | `/api/ws/projects/{id}` | Live project activity |

Interactive docs are served at `/docs` when running the API directly.

## License

MIT
