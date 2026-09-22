"""Runtime configuration and secret loading."""

from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings.

    The token remains a ``SecretStr`` until the authentication boundary needs its
    value, which keeps it out of model representations and validation diagnostics.
    """

    model_config = SettingsConfigDict(
        env_prefix="KK_PRICEWATCH_", extra="ignore", hide_input_in_errors=True
    )

    api_token: SecretStr | None = Field(default=None, repr=False)
    api_token_file: Path | None = None

    @model_validator(mode="after")
    def load_and_validate_token(self) -> Self:
        if self.api_token is not None and self.api_token_file is not None:
            raise ValueError("configure exactly one API token source, not both")
        if self.api_token is None and self.api_token_file is None:
            raise ValueError("configure exactly one API token source")

        if self.api_token_file is not None:
            path = self.api_token_file
            if not path.exists():
                raise ValueError(f"API token file does not exist: {path}")
            if not path.is_file():
                raise ValueError(f"API token path is not a regular file: {path}")
            try:
                token = path.read_text(encoding="utf-8").rstrip("\r\n")
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"API token file cannot be read as UTF-8: {path}") from exc
            self.api_token = SecretStr(token)

        assert self.api_token is not None
        if not self.api_token.get_secret_value().strip():
            raise ValueError("API token must not be blank")
        return self

    def authentication_token(self) -> str:
        """Reveal the token only for constant-time authentication comparison."""

        assert self.api_token is not None
        return self.api_token.get_secret_value()
