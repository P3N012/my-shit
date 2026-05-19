# Procfile — process declarations.
#
# Render reads this; so does Heroku-style tooling. Documents the
# three process types this app supports:
#
#   release  — runs once per deploy *before* `web` gets traffic.
#              Perfect spot for migrations.
#   web      — the FastAPI server. $PORT is injected by the host.
#   worker   — arq background queue. Optional — only needed if you
#              use POST /ai/jobs (the synchronous /ai/messages path
#              works without it, and /connections/{id}/sync falls
#              back to inline sync when Redis is unavailable).
release: alembic upgrade head
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: arq worker.WorkerSettings
