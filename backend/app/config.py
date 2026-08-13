"""Application configuration.

Reads settings from environment variables with the HEXA_ prefix
(e.g. HEXA_DATABASE_URL), plus an optional .env file. All values are
plain configuration with documented defaults; ranking weights and
confidence thresholds deliberately live in their own modules
(ranking/weights_config.py, response/confidence_thresholds.py) so any
change to them has to pass the evaluation benchmark gate first
(CLAUDE.md rule 7).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must never be used outside development — anyone with the repo can forge
# JWTs with it. Production startup fails hard if it is still set.
_DEFAULT_JWT_SECRET = "dev-only-secret-change-me-in-production-32chars"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HEXA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "Hexta"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- Database ---
    # postgresql://user:password@host:port/dbname
    database_url: str = "postgresql://hexa_app:devpass@127.0.0.1:15432/hexa_assistant"
    database_pool_max: int = 4
    database_pool_timeout_s: int = 30

    # --- Auth ---
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    # Fixed 8h expiry, no sliding sessions (A6). This is a documented
    # decision for a single-host assistant: tokens are revoked on logout via
    # the jti blacklist (token_blacklist), and a deactivated user's token
    # stops verifying immediately because /auth/verify re-checks is_active.
    # Sliding sessions would keep idle-but-authenticated browser tabs alive
    # indefinitely; revisit only if user deactivation latency becomes a concern.
    jwt_expiry_minutes: int = 480

    # --- Auth lockout (brute-force defense) ---
    # Lock the account for `login_lockout_minutes` after `login_max_attempts`
    # failed logins within that window. Success resets the window.
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # --- CORS ---
    # Comma-separated list of allowed origins. "*" is permitted only in
    # development; non-development environments must enumerate origins.
    cors_origins: str = "*"

    # --- Embeddings (query-time, always-on process) ---
    embedding_enabled: bool = True
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = "nlp_models/embeddings"
    embedding_dim: int = 384

    # --- Storage ---
    storage_pending_dir: str = "storage/pending"
    storage_processed_dir: str = "storage/processed"
    # Permanent failures (unreadable/scanned-without-OCR files) land here so
    # they stop failing on every batch — see ingest_batch.main (I3).
    storage_quarantine_dir: str = "storage/quarantine"
    max_upload_bytes: int = 20 * 1024 * 1024

    # --- Ingestion chunking ---
    # Dedicated chunk-size knob for the batch pipeline. This used to piggyback
    # on max_excerpt_chars (a response-display setting) — the two are unrelated
    # concerns and must stay decoupled (I6).
    chunk_max_tokens: int = 300

    # --- Search ---
    bm25_limit: int = 25
    vector_limit: int = 25
    max_sub_queries: int = 4
    min_confidence_no_answer: float = 50.0

    # --- Response ---
    max_excerpt_chars: int = 600
    max_evidence_docs: int = 3

    # --- Behavioural ---
    auto_create_schema: bool = True
    audit_enabled: bool = True

    # --- Optional reranker (P2; OFF by default on the micro tier) ---
    rerank_enabled: bool = False
    rerank_model_dir: str = "nlp_models/reranker"
    # 6: benchmark-backed — the only top_k that meets the <200ms p95 budget
    # (rule 6) in the REAL serving env (linux container is ~2x slower than
    # the host venv: top_k=7 → 212ms p95, top_k=6 → 117ms). Retrieval
    # quality holds (MRR 0.528, recall@1 40% — reports
    # retrieval_benchmark_20260811_065700).
    rerank_top_k: int = 6
    # Cross-encoder latency budget (ms) — CLAUDE.md rule 6.
    rerank_budget_ms: float = 200.0

    @model_validator(mode="after")
    def _guard_secrets(self) -> "Settings":
        """Fail fast if the default JWT secret is used outside development."""
        if (
            self.environment != "development"
            and self.jwt_secret == _DEFAULT_JWT_SECRET
        ):
            raise ValueError(
                "HEXA_JWT_SECRET must be set to a strong, unique value in "
                "non-development environments (the bundled default is dev-only)."
            )
        return self

    @model_validator(mode="after")
    def _guard_cors(self) -> "Settings":
        """Fail fast if CORS is wide open outside development."""
        if (
            self.environment != "development"
            and self.cors_origins.strip() == "*"
        ):
            raise ValueError(
                "HEXA_CORS_ORIGINS must be an explicit comma-separated origin "
                "list in non-development environments (wildcard CORS plus "
                "credentials is a browser-level bypass of auth)."
            )
        return self

    @model_validator(mode="after")
    def _anchor_nlp_directories(self) -> "Settings":
        """Anchor relative ``nlp_models/*`` paths to the repo root so they
        resolve regardless of the process cwd — the benchmark runs from the
        repo root, the dev ``uvicorn`` server runs from ``backend/``. Storage
        paths stay backend-relative per the docs."""
        for attr in ("rerank_model_dir", "embedding_cache_dir"):
            value = getattr(self, attr)
            if value and not Path(value).is_absolute():
                setattr(
                    self,
                    attr,
                    str(Path(__file__).resolve().parents[2] / value),
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
