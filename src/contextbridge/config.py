from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contextbridge.schemas import Identifier


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTEXTBRIDGE_", env_file=".env", extra="ignore")

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
        mode="before",
    )
    @classmethod
    def empty_capture_binding(cls, value):
        # Compose uses an empty variable when optional ingestion is not configured.
        return None if value == "" else value

    @model_validator(mode="after")
    def coherent_provider_configuration(self):
        if self.integration_factory and self.worker_factory:
            raise ValueError("Choose one provider factory")
        if (self.embedding_model_id is None) != (self.embedding_dimensions is None):
            raise ValueError("Embedding model and dimensions must be configured together")
        return self
