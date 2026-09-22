"""Runtime configuration and secret loading."""

from pathlib import Path, PureWindowsPath
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
    chrome_binary: Path | None = None
    browser_data_dir: Path | None = None
    selenium_cache_dir: Path | None = None
    browser_preflight: bool = False

    @staticmethod
    def _validate_runtime_path(path: Path, label: str, *, file: bool) -> None:
        raw = str(path)
        windows_path = PureWindowsPath(raw)
        if not path.is_absolute() and not windows_path.is_absolute():
            raise ValueError(f"{label} must be an absolute path")
        if windows_path.is_absolute() and any(
            part.casefold() == "users" for part in windows_path.parts[1:2]
        ):
            raise ValueError(f"{label} must not be located under C:\\Users")
        if not path.exists():
            raise ValueError(f"{label} does not exist: {path}")
        if file and not path.is_file():
            raise ValueError(f"{label} is not a regular file: {path}")
        if not file and not path.is_dir():
            raise ValueError(f"{label} is not a directory: {path}")

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

        if self.chrome_binary is not None:
            self._validate_runtime_path(self.chrome_binary, "Chrome binary", file=True)
        if self.browser_data_dir is not None:
            self._validate_runtime_path(self.browser_data_dir, "browser data directory", file=False)
        if self.selenium_cache_dir is not None:
            self._validate_runtime_path(
                self.selenium_cache_dir, "Selenium cache directory", file=False
            )
        if self.browser_preflight and (
            self.chrome_binary is None
            or self.browser_data_dir is None
            or self.selenium_cache_dir is None
        ):
            raise ValueError(
                "browser preflight requires Chrome binary, browser data directory, "
                "and Selenium cache directory"
            )
        return self

    def authentication_token(self) -> str:
        """Reveal the token only for constant-time authentication comparison."""

        assert self.api_token is not None
        return self.api_token.get_secret_value()
