"""FastAPI application entry point.

Run with:
    uvicorn app.main:app --workers 1 --fd 3

Socket-activated by systemd (hexa-backend.socket on port 18001).
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


def _warm_reranker() -> None:
    """Pre-load and pre-warm the cross-encoder reranker at startup.

    Pays the one-time ONNX session construction + first-Run graph-optimization
    cost HERE, before uvicorn starts accepting requests, so a cold first rerank
    call cannot breach the <200ms p95 latency budget (CLAUD.md rule 6). Unlike
    the embedding warm-up this is synchronous on purpose: a cold first rerank
    call (~330ms) would otherwise violate the hard budget on the very first
    user request. The warm itself is ~100-150ms so it does not materially delay
    readiness. Non-fatal if the model is absent or fails — reranking then stays
    lazy on first use.
    """
    if not settings.rerank_enabled:
        return
    try:
        from app.ranking.reranker import _get_reranker, _model_available

        if not _model_available(settings.rerank_model_dir):
            logger.warning("Reranker enabled but no model found in %s; skipping warm-up", settings.rerank_model_dir)
            return
        _get_reranker().score("warmup query", ["warmup passage"])
        logger.info("Reranker model warmed up")
    except Exception:
        logger.exception("Reranker warm-up failed; falling back to lazy load on first rerank")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Idempotent schema creation on startup; pool cleanup on shutdown."""
    if settings.auto_create_schema:
        ensure_schema()
    # Warm the embedding model in the background (non-blocking) so the
    # first real search doesn't pay the one-time model-load latency.
    if settings.embedding_enabled:
        threading.Thread(target=_warm_embedding_model, daemon=True).start()
    # Eagerly warm the reranker before serving so a cold first rerank call
    # can't breach the <200ms p95 gate (CLAUDE.md rule 6).
    if settings.rerank_enabled:
        _warm_reranker()
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

# CORS — restricted in production, permissive in dev.
# allow_origins must be an explicit list in non-development environments
# (enforced by Settings._guard_cors). Credentials are only sent when origins
# are explicit: the fetch spec forbids credentialed requests to "*".
if settings.cors_origins == "*":
    allow_origins = ["*"]
    allow_credentials = False
else:
    allow_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
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
