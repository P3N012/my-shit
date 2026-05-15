"""
Application logging.

- JSON output in non-development environments (one object per line) so
  logs are ingestible by Loki/Datadog/CloudWatch without extra parsing.
- A compact human-readable format in development.
- A request-scoped contextvar (`request_id_var`) carries the request ID
  into every log record emitted while handling a request.
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get()
        prefix = f"[{rid[:8]}] " if rid else ""
        return f"{record.levelname:<5} {prefix}{record.name}: {record.getMessage()}"


def configure_logging(level: str, environment: str) -> None:
    """Reset root logger handlers and install ours."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        HumanFormatter() if environment == "development" else JsonFormatter()
    )

    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn ships its own access logger; route it through ours so request_id
    # tagging is consistent and JSON output isn't broken up.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
