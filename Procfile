# Procfile — process declarations.
#
# Render's free tier doesn't support a release/pre-deploy phase, so
# the actual deploy folds migrations into the web start command (see
# render.yaml). This Procfile documents the process types for any
# host that *does* support a release phase (Heroku, paid Render):
#
#   release  — runs once per deploy before `web` gets traffic.
#   web      — the FastAPI server. $PORT is injected by the host.
#   worker   — arq background queue. Optional — only needed if you
#              use POST /ai/jobs (the synchronous /ai/messages path
#              works without it, and /connections/{id}/sync falls
#              back to inline sync when Redis is unavailable).
release: alembic upgrade head
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: arq worker.WorkerSettings
