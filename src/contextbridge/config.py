from pydantic import Field, SecretStr, field_validator
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

    @field_validator("capture_project_id", mode="before")
    @classmethod
    def empty_capture_binding(cls, value):
        # Compose uses an empty variable when optional ingestion is not configured.
        return None if value == "" else value
