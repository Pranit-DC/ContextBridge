from ipaddress import ip_address
from uuid import uuid4

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contextbridge.schemas import Identifier


class MCPSettings(BaseSettings):
    # An agent may launch us from any repository. Only explicitly selected dotenv files are read.
    model_config = SettingsConfigDict(env_prefix="CONTEXTBRIDGE_", env_file=None, extra="ignore")

    api_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000")
    api_token: SecretStr = Field(min_length=32)
    project_id: Identifier
    agent_id: Identifier = "mcp-client"
    session_id: Identifier = Field(default_factory=lambda: str(uuid4()))
    request_timeout: float = Field(default=10, gt=0, le=60)

    @field_validator("api_url")
    @classmethod
    def require_local_service(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        host = (value.host or "").strip("[]")
        try:
            loopback = ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        if (
            not loopback
            or value.username is not None
            or value.password is not None
            or value.path not in (None, "/")
            or value.query is not None
            or value.fragment is not None
        ):
            raise ValueError("API URL must be a loopback origin without credentials or a path")
        return value
