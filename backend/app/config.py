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
    database_url: str = "postgresql://hexa_app:devpass@127.0.0.1:5432/hexa_assistant"
    database_pool_max: int = 4
    database_pool_timeout_s: int = 30

    # --- Auth ---
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480

    # --- CORS ---
    # Comma-separated list of allowed origins; "*" in non-production only.
    cors_origins: str = "*"

    # --- Embeddings (query-time, always-on process) ---
    embedding_enabled: bool = True
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = "nlp_models/embeddings"
    embedding_dim: int = 384

    # --- Storage ---
    storage_pending_dir: str = "storage/pending"
    storage_processed_dir: str = "storage/processed"
    max_upload_bytes: int = 20 * 1024 * 1024

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
    rerank_top_k: int = 10
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
    def _anchor_nlp_directories(self) -> "Settings":
        """Anchor relative ``nlp_models/*`` paths to the repo root so they
        resolve regardless of the process cwd — the benchmark runs from the
        repo root, the dev ``uvicorn`` server runs from ``backend/``. Storage
        paths stay backend-relative per the docs."""
        if self.rerank_model_dir and not Path(self.rerank_model_dir).is_absolute():
            self.rerank_model_dir = str(
                Path(__file__).resolve().parents[2] / self.rerank_model_dir
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
