from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contextbridge.retrieval.cloudflare import DIMENSIONS, MODEL_ID, valid_base_url
from contextbridge.schemas import Identifier


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXTBRIDGE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    api_token: SecretStr = Field(min_length=32)
    developer_id: str = Field(default="local-developer", min_length=1, max_length=128)
    capture_project_id: Identifier | None = None
    capture_allow_developer: bool = False
    capture_retention_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    capture_max_buffered_events: int = Field(default=1_000, ge=1, le=100_000)
    candidate_retention_seconds: int = Field(default=3_600, ge=60, le=2_592_000)
    broker_url: SecretStr = SecretStr("redis://redis:6379/0")
    worker_factory: str | None = Field(default=None, pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    integration_factory: str | None = Field(default=None, pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    formation_enabled: bool = False
    formation_tokens_per_minute: int = Field(default=8000, ge=128, le=8000)
    formation_tokens_per_day: int = Field(default=50000, ge=128, le=50000)
    retrieval_expand_graph: bool = False
    retrieval_check_decisions: bool = False
    retrieval_min_similarity: float = Field(default=0.4, ge=0, le=1, allow_inf_nan=False)
    consolidation_enabled: bool = False
    embedding_provider: Literal["cloudflare"] | None = None
    embedding_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    embedding_base_url: SecretStr | None = Field(default=None, repr=False, exclude=True)
    embedding_model_id: Identifier | None = None
    embedding_dimensions: int | None = Field(default=None, ge=1, le=4096)
    provider_timeout_seconds: float = Field(default=10, gt=0, le=120)
    worker_max_attempts: int = Field(default=3, ge=1, le=10)
    worker_timeout_seconds: int = Field(default=120, ge=5, le=600)
    worker_retry_seconds: int = Field(default=10, ge=1, le=300)
    worker_diagnostic_retention_seconds: int = Field(default=604_800, ge=60, le=2_592_000)

    @field_validator(
        "capture_project_id",
        "worker_factory",
        "integration_factory",
        "embedding_model_id",
        "embedding_dimensions",
        "embedding_provider",
        "embedding_api_key",
        "embedding_base_url",
        mode="before",
    )
    @classmethod
    def empty_capture_binding(cls, value):
        # Compose uses an empty variable when optional ingestion is not configured.
        return None if value == "" else value

    @model_validator(mode="after")
    def coherent_provider_configuration(self):
        if self.worker_factory and (self.integration_factory or self.formation_enabled):
            raise ValueError("Choose one provider factory")
        if self.embedding_provider == "cloudflare":
            if self.worker_factory:
                raise ValueError("Cloudflare embeddings require the shared integration runtime")
            if (
                self.embedding_api_key is None
                or not self.embedding_api_key.get_secret_value().strip()
                or self.embedding_base_url is None
                or not valid_base_url(self.embedding_base_url.get_secret_value())
                or self.embedding_model_id != MODEL_ID
                or self.embedding_dimensions not in (None, DIMENSIONS)
            ):
                raise ValueError("Invalid Cloudflare embedding configuration")
            self.embedding_dimensions = DIMENSIONS
        if (self.embedding_model_id is None) != (self.embedding_dimensions is None):
            raise ValueError("Embedding model and dimensions must be configured together")
        return self

    @property
    def embedding_only(self) -> bool:
        return (
            self.embedding_provider == "cloudflare"
            and self.integration_factory is None
            and not self.formation_enabled
        )
