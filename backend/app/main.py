"""FastAPI application entry point.

Run with:
    uvicorn app.main:app --workers 1 --fd 3

Socket-activated by systemd (hexa-backend.socket on port 8001).
Idle-stops after 10 minutes of no activity (hexa-backend-idle.timer).
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.db.postgres.schema import ensure_schema

logger = logging.getLogger(__name__)


def _warm_embedding_model() -> None:
    """Preload the query-embedding model so the first user search isn't slow.

    The model files are already on disk (downloaded during ingestion), so
    this only pays the in-memory load cost — and it runs in a background
    thread, so it never blocks startup or drains the readiness of /health.
    If it fails (e.g. model missing), we just fall back to the existing
    lazy load on the first search; a failed warm-up is never fatal.
    """
    if not settings.embedding_enabled:
        return
    try:
        from app.search.pgvector_search import embed_query

        embed_query("warmup")
        logger.info("Embedding model warmed up")
    except Exception:
        logger.exception("Embedding model warm-up failed; falling back to lazy load")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Idempotent schema creation on startup; pool cleanup on shutdown."""
    if settings.auto_create_schema:
        ensure_schema()
    # Warm the embedding model in the background (non-blocking) so the
    # first real search doesn't pay the one-time model-load latency.
    if settings.embedding_enabled:
        threading.Thread(target=_warm_embedding_model, daemon=True).start()
    yield
    from app.db.postgres.session import _pool

    if _pool is not None:
        _pool.close()


app = FastAPI(
    title=settings.app_name,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)

# CORS — restricted in production, permissive in dev
if settings.cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = settings.cors_origins.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint — no DB dependency."""
    return {"status": "healthy", "timestamp": time.time()}


@app.get(f"{settings.api_prefix}/health")
async def api_health() -> dict:
    """API-level health check with DB connectivity."""
    from app.db.postgres.session import ping

    db_ok = ping()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "timestamp": time.time(),
    }


app.include_router(api_router, prefix=settings.api_prefix)
