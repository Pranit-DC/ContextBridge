from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTEXTBRIDGE_", env_file=".env", extra="ignore")

    database_url: SecretStr
    api_token: SecretStr = Field(min_length=32)
    developer_id: str = Field(default="local-developer", min_length=1, max_length=128)
