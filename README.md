# InsightPlus Backend

FastAPI + PostgreSQL backend for the InsightPlus SaaS dashboard.

Provides user accounts and JWT-based authentication. Product features
(dashboard, analytics, integrations) are intentionally out of scope here
and will be added in dedicated modules as they're built.

---

## Stack

| Layer          | Choice                            |
| -------------- | --------------------------------- |
| Web framework  | FastAPI                           |
| ORM            | SQLAlchemy 2.x                    |
| Database       | PostgreSQL (SQLite for local dev) |
| Auth           | JWT (HS256), bcrypt for passwords |
| Config         | Pydantic Settings                 |
| Python         | 3.9+                              |

---

## Project layout

```
.
├── main.py                       # FastAPI app + entry point
├── requirements.txt
├── alembic.ini
├── alembic/                      # Migrations
│   ├── env.py
│   └── versions/
├── app/
│   ├── core/
│   │   ├── config.py             # Settings (env-driven)
│   │   ├── database.py           # Engine, session, Base
│   │   ├── limiter.py            # Shared slowapi limiter
│   │   ├── logging.py            # JSON / human formatters + request_id contextvar
│   │   ├── middleware.py         # RequestContextMiddleware
│   │   └── security.py           # Password hashing, JWT, token hashing
│   ├── models/
│   │   ├── user.py               # User, RefreshToken
│   │   └── organization.py       # Organization, Membership
│   ├── schemas/
│   │   ├── auth.py
│   │   └── organization.py
│   ├── routes/
│   │   ├── auth.py               # /api/v1/auth/*
│   │   └── organizations.py      # /api/v1/orgs/*
│   ├── services/
│   │   ├── auth_service.py
│   │   └── organization_service.py
│   └── utils/
│       └── dependencies.py       # get_current_user, get_current_membership, require_role
├── scripts/
│   └── seed_db.py                # Seed test users
├── tests/
│   ├── conftest.py               # Shared fixtures (per-test SQLite)
│   ├── test_auth.py
│   ├── test_cors.py
│   ├── test_meta.py
│   ├── test_organizations.py
│   └── test_rate_limit.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml      # pytest + Alembic-against-Postgres
```

---

## Quick start

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env                       # optional; compose has sensible defaults
docker compose up --build
```

Brings up Postgres + the API, runs migrations, exposes the API on
`http://localhost:8000`. Swagger UI at `/api/v1/docs`.

### Option B — Local Python

```bash
python -m venv venv && source venv/bin/activate     # (Windows: venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env                                # then edit (see Configuration)
alembic upgrade head                                # apply migrations
python scripts/seed_db.py                           # optional: test users
python main.py                                      # http://localhost:8000
```

---

## Configuration

All config is loaded from environment variables (or `.env`) via
`app/core/config.py`.

| Variable                       | Required | Default                  | Notes                                          |
| ------------------------------ | -------- | ------------------------ | ---------------------------------------------- |
| `DATABASE_URL`                 | yes      | —                        | e.g. `postgresql://user:pw@localhost/insight`  |
| `ACCESS_TOKEN_SECRET`          | yes      | —                        | High-entropy random string                     |
| `REFRESH_TOKEN_SECRET`         | yes      | —                        | Different from access secret                   |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | no       | `30`                     |                                                |
| `REFRESH_TOKEN_EXPIRE_DAYS`    | no       | `30`                     |                                                |
| `ALGORITHM`                    | no       | `HS256`                  |                                                |
| `ENVIRONMENT`                  | no       | `development`            | `development` \| `staging` \| `production`     |
| `API_V1_PREFIX`                | no       | `/api/v1`                |                                                |
| `PROJECT_NAME`                 | no       | `InsightPlus`            |                                                |
| `CORS_ORIGINS`                 | no       | `http://localhost:3000`  | Comma-separated. **Never `*` with cookies.**   |
| `HOST`                         | no       | `0.0.0.0`                |                                                |
| `PORT`                         | no       | `8000`                   |                                                |
| `LOG_LEVEL`                    | no       | `INFO`                   |                                                |
| `RATE_LIMIT_ENABLED`           | no       | `true`                   | Set `false` in test environments               |
| `RATE_LIMIT_LOGIN`             | no       | `5/minute`               | Per-IP                                         |
| `RATE_LIMIT_REGISTER`          | no       | `5/minute`               | Per-IP                                         |
| `RATE_LIMIT_REFRESH`           | no       | `20/minute`              | Per-IP                                         |

Generate strong secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## API

Base path: `/api/v1`

### Authentication (`/auth`)

| Method | Path             | Description                                                          |
| ------ | ---------------- | -------------------------------------------------------------------- |
| POST   | `/auth/register` | Create an account (auto-provisions a personal organization)          |
| POST   | `/auth/login`    | Exchange credentials for an access + refresh token pair              |
| POST   | `/auth/refresh`  | **Rotates** the refresh token; returns a new access + refresh pair   |
| POST   | `/auth/logout`   | Revoke a refresh token                                               |
| GET    | `/auth/me`       | Current user + memberships (requires `Authorization: Bearer <token>`) |

### Organizations (`/orgs`)

| Method | Path           | Description                                                       |
| ------ | -------------- | ----------------------------------------------------------------- |
| GET    | `/orgs`        | List orgs the current user belongs to                             |
| POST   | `/orgs`        | Create a new org (caller becomes `owner`)                         |
| GET    | `/orgs/{id}`   | Get a specific org (403 if the user has no membership)            |

### Meta

| Method | Path      | Description                                                              |
| ------ | --------- | ------------------------------------------------------------------------ |
| GET    | `/`       | Welcome payload                                                          |
| GET    | `/health` | **Liveness** — the process is up                                         |
| GET    | `/ready`  | **Readiness** — process is up *and* `SELECT 1` against the DB succeeded  |

Every response carries an `X-Request-Id` header (echoing the client's if
provided, otherwise a fresh UUID4) and every log line for that request
includes it.

---

## Authentication model

- **Access token** — short-lived JWT (default 30 min). Sent as
  `Authorization: Bearer <token>`. Stateless: not stored server-side.
- **Refresh token** — long-lived JWT (default 30 days). Stored as a
  **SHA-256 hash** in the `refresh_tokens` table, never as plaintext.
- **Rotation** — every call to `/auth/refresh` revokes the presented
  refresh token and issues a new one. Clients must replace **both**
  tokens on every refresh.
- **Logout** — deletes the corresponding refresh-token row. Outstanding
  access tokens remain valid until their natural expiry.

## Multi-tenancy

Every authenticated request that touches tenant data must declare which
organization it's acting against:

```
Authorization:       Bearer <access_token>
X-Organization-Id:   42
```

Org-scoped endpoints take a `Membership` via the
`get_current_membership` FastAPI dependency, which:

1. Resolves the user from the JWT (`get_current_user`).
2. Reads `X-Organization-Id` (400 if missing).
3. Looks up the `(user_id, organization_id)` membership row (403 if absent).
4. Returns the `Membership` — its `role` is then available for further
   authorization via the `require_role("owner", "admin", …)` factory.

Registering a user auto-creates a personal organization with that user
as `owner`. There is always at least one org per user.

---

## Database

Schema is managed by **Alembic**. Migrations live under `alembic/versions/`.

```bash
alembic upgrade head                        # apply all migrations
alembic revision --autogenerate -m "..."    # generate a new migration
alembic downgrade -1                        # roll back one
alembic current                             # show current revision
```

The app does **not** create tables at startup; running migrations is
explicit. CI verifies migrations apply cleanly against Postgres on every
PR.

### Models

| Model          | Purpose                                                       |
| -------------- | ------------------------------------------------------------- |
| `User`         | Account, password hash, status, subscription metadata         |
| `RefreshToken` | Hash + expiry of an issued refresh JWT, scoped to a `User`    |
| `Organization` | Tenant; everything user-data lives under an org               |
| `Membership`   | `(user_id, organization_id, role)` — `owner` / `admin` / `member` |

---

## Seeded test credentials

After running `python scripts/seed_db.py`:

| Role  | Email                      | Password       |
| ----- | -------------------------- | -------------- |
| User  | `test@insightplus.com`     | `password123`  |
| Admin | `admin@insightplus.com`    | `admin123`     |

These are obviously not for production.

---

## Development

```bash
python main.py                                # auto-reload in dev
uvicorn main:app --reload                     # equivalent
pytest                                        # run the test suite
pytest -k auth                                # filter
```

CI (GitHub Actions, `.github/workflows/ci.yml`) on every PR:

- applies Alembic migrations against a real Postgres service
- runs `pytest` (which uses SQLite per-test via `conftest.py`)

### Style

- PEP 8, type hints on public functions.
- Comments only where the *why* isn't obvious from the code.

---

## Troubleshooting

| Symptom                          | Fix                                                              |
| -------------------------------- | ---------------------------------------------------------------- |
| `ModuleNotFoundError`            | Virtualenv not activated, or `pip install -r requirements.txt`   |
| `database "insightplus_dev" does not exist` | `createdb insightplus_dev`                            |
| `password authentication failed` | Check `DATABASE_URL` in `.env`                                   |
| `connection refused`             | Postgres not running (`pg_isready`)                              |

---

## Operations

- **Logging.** Single root logger configured at startup. JSON output
  (one object per line) in non-development environments, compact
  human-readable output in `development`. Every record emitted while
  handling a request carries the request's `request_id`.
- **Request IDs.** `RequestContextMiddleware` assigns each request a
  UUID4 (or honours an upstream `X-Request-Id`), stashes it in a
  `ContextVar` for downstream logs, echoes it back on the response, and
  emits one access log per request.
- **Rate limiting.** `slowapi`, keyed by remote address. Defaults are
  `5/min` for register and login, `20/min` for refresh. Tune via env
  vars. Behind a reverse proxy, ensure the proxy sets the real client
  IP upstream (e.g. nginx `proxy_set_header X-Real-IP`).
- **Health probes.** `/health` for kubelet/load-balancer liveness;
  `/ready` for readiness (returns 503 when the database is unreachable).
- **Docker.** Multi-stage `Dockerfile` (builder installs deps system-wide
  with `--prefix=/install`, runtime image runs as a non-root user). The
  default `CMD` runs `alembic upgrade head` before launching uvicorn.

---

## Security notes

- `.env` is gitignored. Never commit secrets.
- Use strong random values for `ACCESS_TOKEN_SECRET` and
  `REFRESH_TOKEN_SECRET`. They must be distinct.
- `CORS_ORIGINS` is a strict allowlist; the wildcard `*` is rejected when
  `allow_credentials=True` (per CORS spec) and should not be used.
- Refresh tokens are hashed at rest. A leaked DB row cannot be replayed
  as a valid token.

---

## License

Proprietary — all rights reserved.
