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
│   │   ├── anthropic_client.py   # Anthropic SDK wrapper + cost estimator
│   │   └── security.py           # Password hashing, JWT, token hashing
│   ├── models/
│   │   ├── user.py               # User, RefreshToken
│   │   ├── organization.py       # Organization, Membership
│   │   ├── ai_job.py             # AIJob
│   │   ├── ai_usage.py           # AIUsage
│   │   └── platform_connection.py  # PlatformConnection, OAuthState
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── organization.py
│   │   ├── ai.py
│   │   └── platform_connection.py
│   ├── routes/
│   │   ├── auth.py               # /api/v1/auth/*
│   │   ├── organizations.py      # /api/v1/orgs/*
│   │   ├── ai.py                 # /api/v1/ai/*
│   │   └── connections.py        # /api/v1/connections/*
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── organization_service.py
│   │   ├── ai_service.py
│   │   ├── jobs_service.py
│   │   └── stripe_oauth_service.py
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
│   ├── test_rate_limit.py
│   ├── test_ai.py                # Anthropic SDK is mocked
│   └── test_connections.py       # Stripe SDK is mocked
├── worker.py                     # arq worker entry point
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
| `RATE_LIMIT_AI`                | no       | `30/minute`              | Per-IP, applied to `/ai/messages` and `/ai/jobs` |
| `ANTHROPIC_API_KEY`            | for AI   | —                        | Required to make real AI calls. Tests mock the SDK so this can be empty. |
| `ANTHROPIC_MODEL`              | no       | `claude-opus-4-7`        | Default model. Overridable per-call.           |
| `ANTHROPIC_MAX_TOKENS`         | no       | `4096`                   | Default `max_tokens` for completions.          |
| `AI_ENABLED`                   | no       | `true`                   | Master toggle for `/ai/*`.                     |
| `REDIS_URL`                    | for jobs | `redis://localhost:6379/0` | arq queue backend for async `/ai/jobs`.       |
| `STRIPE_SECRET_KEY`            | for Stripe | —                      | Platform secret key (`sk_test_...`). Required to exchange OAuth codes. |
| `STRIPE_CONNECT_CLIENT_ID`     | for Stripe | —                      | Connect client ID (`ca_...`) from Dashboard → Connect.                 |
| `STRIPE_OAUTH_REDIRECT_URI`    | no       | `…/connections/stripe/callback` | Must match a Redirect URI in Connect settings exactly.            |
| `STRIPE_OAUTH_SUCCESS_URL`     | no       | `localhost:3000/connections?stripe=ok` | Where the callback 302s on success.                        |
| `STRIPE_OAUTH_FAILURE_URL`     | no       | `localhost:3000/connections?stripe=error` | Where the callback 302s on failure.                     |

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

### Connections (`/connections`) — org-scoped (except the callback)

Stripe Connect OAuth and connected-data-source management.

| Method | Path                              | Description                                                                |
| ------ | --------------------------------- | -------------------------------------------------------------------------- |
| POST   | `/connections/stripe/connect`     | Returns a Stripe authorization URL; client navigates the user there.       |
| GET    | `/connections/stripe/callback`    | Stripe redirects here; **public**, bound to user by one-time state token.  |
| GET    | `/connections`                    | List the org's connected accounts (tokens never returned).                 |
| GET    | `/connections/{id}`               | Get one connection.                                                        |
| DELETE | `/connections/{id}`               | Disconnect: revoke at Stripe (best-effort) and remove the row.             |

### AI (`/ai`) — org-scoped, requires `X-Organization-Id` header

| Method | Path             | Description                                                                       |
| ------ | ---------------- | --------------------------------------------------------------------------------- |
| POST   | `/ai/messages`   | Synchronous Anthropic completion. Records one `ai_usage` row.                     |
| POST   | `/ai/jobs`       | Enqueue an async completion via arq + Redis. Returns a `job_id`.                  |
| GET    | `/ai/jobs/{id}`  | Job status (`queued`/`running`/`succeeded`/`failed`) and result if terminal.      |
| GET    | `/ai/usage`      | Cumulative token + cost totals for the active org.                                |

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

| Model          | Purpose                                                              |
| -------------- | -------------------------------------------------------------------- |
| `User`         | Account, password hash, status, subscription metadata                |
| `RefreshToken` | Hash + expiry of an issued refresh JWT, scoped to a `User`           |
| `Organization` | Tenant; everything user-data lives under an org                      |
| `Membership`   | `(user_id, organization_id, role)` — `owner` / `admin` / `member`    |
| `AIJob`        | Lifecycle for an enqueued AI call: `queued`/`running`/`succeeded`/`failed` |
| `AIUsage`      | One row per Anthropic call — token counts (incl. cache hits) + USD cost |
| `PlatformConnection` | A connected third-party account (Stripe today; Google Ads/GA4 later). Stores OAuth tokens scoped to one org. |
| `OAuthState`   | Short-lived CSRF token for the OAuth redirect leg. One-time use, 10-minute TTL. |

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

## AI integration

- **SDK.** Single wrapper at `app/core/anthropic_client.py`. Routes and
  the worker never import `anthropic` directly. Defaults applied here:
  model `claude-opus-4-7`, adaptive thinking enabled, top-level
  `cache_control: {"type": "ephemeral"}` on every request so the last
  cacheable block (usually the system prompt) is auto-cached.
- **Sync calls.** `POST /ai/messages` runs in the request thread and
  returns the completion. Records an `ai_usage` row with input/output
  tokens, cache_creation/cache_read tokens, and a USD cost derived
  from `MODEL_PRICING`. On upstream failure, still writes a usage row
  with the error message — the audit trail covers attempted spend.
- **Async calls.** `POST /ai/jobs` creates an `ai_jobs` row, enqueues
  the work onto Redis via arq, and returns the job id. The worker
  (`worker.py`) picks it up, runs `AIService.complete` with the same
  usage-recording contract, and writes the result back. Poll
  `GET /ai/jobs/{id}` for status.
- **Per-org accounting.** Every AI row is scoped to the active org
  (`X-Organization-Id`). `GET /ai/usage` aggregates calls/tokens/cost.
- **Run the worker locally:** `arq worker.WorkerSettings`. Compose
  brings up an `api` and a `worker` container that share the same
  image and env.

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
