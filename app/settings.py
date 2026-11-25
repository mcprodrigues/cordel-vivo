"""API configuration, read only from environment variables (AGENTS.md, principle 8)."""

from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Settings the application needs to build itself."""

    model_config = SettingsConfigDict(env_prefix="CORDEL_", extra="ignore", frozen=True)

    # Comma-separated so that keys can be rotated: add the new key, deploy, remove the old.
    api_keys: Annotated[tuple[SecretStr, ...], NoDecode, Field(min_length=1)]

    @field_validator("api_keys", mode="before")
    @classmethod
    def _split_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(key.strip() for key in value.split(",") if key.strip())
        return value

    @field_validator("api_keys")
    @classmethod
    def _reject_blank_keys(cls, keys: tuple[SecretStr, ...]) -> tuple[SecretStr, ...]:
        if any(not key.get_secret_value() for key in keys):
            raise ValueError("API keys must not be empty")
        return keys


class ServerSettings(BaseSettings):
    """Where `python -m app` listens. Not used by the application itself."""

    model_config = SettingsConfigDict(env_prefix="CORDEL_API_", extra="ignore", frozen=True)

    host: str
    port: Annotated[int, Field(gt=0, lt=65536)]
