from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings


def clear_token_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KK_PRICEWATCH_API_TOKEN", raising=False)
    monkeypatch.delenv("KK_PRICEWATCH_API_TOKEN_FILE", raising=False)


def test_api_token_environment_works(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_token_environment(monkeypatch)
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN", "environment-secret")
    settings = Settings()
    assert settings.authentication_token() == "environment-secret"


def test_api_token_file_works_and_removes_trailing_newlines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_token_environment(monkeypatch)
    token_file = tmp_path / "api-token.txt"
    token_file.write_bytes(b"file-secret\r\n")
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN_FILE", str(token_file))
    settings = Settings()
    assert settings.authentication_token() == "file-secret"


@pytest.mark.parametrize("contents", ["", " \t\r\n"])
def test_empty_or_whitespace_token_file_is_rejected(
    contents: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_token_environment(monkeypatch)
    token_file = tmp_path / "api-token.txt"
    token_file.write_text(contents, encoding="utf-8")
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN_FILE", str(token_file))
    with pytest.raises(ValidationError, match="must not be blank") as error:
        Settings()
    assert "input_value" not in str(error.value)


def test_missing_token_file_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_token_environment(monkeypatch)
    path = tmp_path / "missing.txt"
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN_FILE", str(path))
    with pytest.raises(ValidationError, match="does not exist"):
        Settings()


def test_both_token_sources_are_rejected(tmp_path: Path) -> None:
    token_file = tmp_path / "api-token.txt"
    token_file.write_text("file-secret", encoding="utf-8")
    with pytest.raises(ValidationError, match="not both") as error:
        Settings(api_token="direct-secret", api_token_file=token_file)
    assert "direct-secret" not in str(error.value)
    assert "file-secret" not in str(error.value)
    assert "input_value" not in str(error.value)


def test_neither_token_source_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_token_environment(monkeypatch)
    with pytest.raises(ValidationError, match="exactly one"):
        Settings()


def test_token_is_absent_from_settings_repr() -> None:
    settings = Settings(api_token="representation-secret")
    assert "representation-secret" not in repr(settings)
    assert "api_token=" not in repr(settings)


def test_invalid_token_is_absent_from_validation_error() -> None:
    secret = "   "
    with pytest.raises(ValidationError) as error:
        Settings(api_token=secret)
    assert "input_value" not in str(error.value)


def test_browser_paths_validate_when_configured(tmp_path: Path) -> None:
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    browser = tmp_path / "browser"
    cache = tmp_path / "cache"
    browser.mkdir()
    cache.mkdir()
    settings = Settings(
        api_token="token",
        chrome_binary=chrome,
        browser_data_dir=browser,
        selenium_cache_dir=cache,
        browser_preflight=True,
    )
    assert settings.chrome_binary == chrome


def test_browser_preflight_requires_all_runtime_paths() -> None:
    with pytest.raises(ValidationError, match="preflight requires"):
        Settings(api_token="token", browser_preflight=True)


def test_relative_chrome_path_is_rejected() -> None:
    with pytest.raises(ValidationError, match="absolute path"):
        Settings(api_token="token", chrome_binary=Path("chrome.exe"))


def test_user_scoped_windows_chrome_path_is_rejected_before_existence_check() -> None:
    with pytest.raises(ValidationError, match=r"must not be located under C:\\Users"):
        Settings(
            api_token="token",
            chrome_binary=Path(r"C:\Users\Administrator\AppData\chrome.exe"),
        )


def test_chrome_binary_must_be_a_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="not a regular file"):
        Settings(api_token="token", chrome_binary=tmp_path)
