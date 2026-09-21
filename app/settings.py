"""Runtime configuration."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(env_prefix="KK_PRICEWATCH_", extra="ignore")

    api_token: str = Field(min_length=1)

    @field_validator("api_token")
    @classmethod
    def reject_blank_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("API token must not be blank")
        return value
