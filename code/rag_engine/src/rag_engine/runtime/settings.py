"""Runtime deployment settings (environment variables with the RAG_ prefix).

Defaults follow 06_runtime_api_and_deployment.md#src-22-2-已確認的初始預設.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore")

    # --- identity and mode
    mode: Literal["dev", "standalone"] = "dev"
    env: str = Field("builder", pattern=r"^[a-z][a-z0-9-]{0,31}$")
    runtime_ref: str = "dev-runtime"

    # --- DEV management API (HTTP Basic). Disabled in standalone mode.
    management_username: str | None = None
    management_password: SecretStr | None = None

    # --- resources and backends
    resources_file: str | None = None  # None uses the contract fixture resources (local demo only)
    index_backend: Literal["memory", "elasticsearch"] = "memory"
    embedding_backend: Literal["service", "hash"] = "service"
    es_url: str | None = None  # Builder test ES ("dev_test")
    es_username: str | None = None
    es_password: SecretStr | None = None
    es_ca_certs: str | None = None
    es_verify_certs: bool = True
    # Resolves PLED "es_number" to a cluster URL, for example "https://es{es_number}.pled.example:9200".
    pled_es_url_template: str | None = None
    es_number_of_shards: int = Field(1, gt=0)
    es_number_of_replicas: int = Field(1, ge=0)
    es_bulk_timeout_seconds: float = Field(60, gt=0)

    # --- standalone (FTEST/ENT) startup
    config_file: str | None = None  # {"system_id", "config_revision", "config"}
    pipeline: Literal["ingestion", "inference"] | None = None
    index_generation: str | None = None
    index_fingerprint: str | None = None

    # --- request limits
    max_body_bytes: int = Field(20_971_520, gt=0)
    ingestion_max_documents: int = Field(100, gt=0)

    # --- Ingestion queue and workers (per Pod)
    ingestion_queue_max_waiting_per_system: int = Field(100, gt=0)
    ingestion_queue_max_waiting_total: int = Field(500, gt=0)
    # Raised from 1 / 2 on 2026-11-24; revisit after measuring the bge-m3 service (roadmap R2).
    ingestion_max_concurrency_per_system: int = Field(2, gt=0)
    ingestion_max_concurrency_total: int = Field(4, gt=0)
    ingestion_document_timeout_seconds: float = Field(600, gt=0)

    # --- Inference
    inference_rate_limit_per_system_rps: float = Field(5, gt=0)
    inference_max_concurrency_per_system: int = Field(2, gt=0)
    inference_max_concurrency_total: int = Field(8, gt=0)
    inference_timeout_seconds: float = Field(60, gt=0)

    # --- terminal Run records
    status_retention_seconds: int = Field(259_200, gt=0)
    status_max_terminal_documents: int = Field(10_000, gt=0)
    status_cleanup_interval_seconds: int = Field(3_600, gt=0)

    # --- management operations
    idempotency_retention_seconds: int = Field(3_600, gt=0)
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.ingestion_queue_max_waiting_per_system > self.ingestion_queue_max_waiting_total:
            raise ValueError("per-System queue limit exceeds the Runtime total")
        if self.ingestion_max_concurrency_per_system > self.ingestion_max_concurrency_total:
            raise ValueError("per-System Ingestion concurrency exceeds the Runtime total")
        if self.inference_max_concurrency_per_system > self.inference_max_concurrency_total:
            raise ValueError("per-System Query concurrency exceeds the Runtime total")
        if self.mode == "dev" and (not self.management_username or not self.management_password):
            raise ValueError("DEV mode needs RAG_MANAGEMENT_USERNAME and RAG_MANAGEMENT_PASSWORD")
        if self.mode == "standalone" and not self.config_file:
            raise ValueError("standalone mode needs RAG_CONFIG_FILE")
        if self.mode == "standalone" and self.env == "builder":
            raise ValueError("standalone deployments must not use env 'builder'")
        return self
