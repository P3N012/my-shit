"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.routes import ai, auth, connections, organizations

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(level=settings.LOG_LEVEL, environment=settings.ENVIRONMENT)
    logger.info(
        f"Starting {settings.PROJECT_NAME} (env={settings.ENVIRONMENT}, "
        f"rate_limit_enabled={settings.RATE_LIMIT_ENABLED})"
    )
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="InsightPlus API",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# slowapi wiring
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


# Middleware order: outermost runs first. Add the request-context middleware
# last so it wraps everything below it (CORS, exception handlers, routes).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.get("/", tags=["meta"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": "1.0.0",
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health", tags=["meta"])
async def health_check():
    """Liveness: the process is up."""
    return {"status": "healthy"}


@app.get("/ready", tags=["meta"])
def readiness(db: Session = Depends(get_db)):
    """Readiness: the process is up *and* the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(f"readiness check failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        )
    return {"status": "ready"}


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(organizations.router, prefix=settings.API_V1_PREFIX)
app.include_router(connections.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai.router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
    )
