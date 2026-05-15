"""Shared slowapi limiter.

Defined in its own module so route modules can decorate handlers
without circular-importing `main`. Limits are keyed by the client's
remote address — appropriate for unauthenticated endpoints (login,
register). Behind a reverse proxy you'll want `X-Forwarded-For` parsing
upstream (in nginx/Traefik) so the original IP makes it through.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
)
