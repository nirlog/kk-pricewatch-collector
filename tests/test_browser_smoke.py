from pathlib import Path

import pytest
from pydantic import ValidationError

from app.browser import smoke
from app.settings import Settings


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        (None, None),
        ("KK_PRICEWATCH_API_TOKEN", "production-environment-secret"),
        ("KK_PRICEWATCH_API_TOKEN_FILE", "C:/protected/production-token.txt"),
    ],
)
def test_smoke_settings_ignore_inherited_token_sources(
    variable: str | None,
    value: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KK_PRICEWATCH_API_TOKEN", raising=False)
    monkeypatch.delenv("KK_PRICEWATCH_API_TOKEN_FILE", raising=False)
    if variable is not None and value is not None:
        monkeypatch.setenv(variable, value)
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    browser = tmp_path / "browser"
    cache = tmp_path / "cache"
    browser.mkdir()
    cache.mkdir()

    settings = smoke.browser_runtime_settings(chrome, browser, cache)

    assert settings.chrome_binary == chrome
    assert settings.browser_data_dir == browser
    assert settings.selenium_cache_dir == cache


def test_smoke_output_does_not_print_inherited_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "production-secret-must-not-appear"
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN", secret)
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN_FILE", str(tmp_path / secret))
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    browser = tmp_path / "browser"
    cache = tmp_path / "cache"
    browser.mkdir()
    cache.mkdir()

    class PassingFactory:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        def preflight(self) -> None:
            return None

    monkeypatch.setattr(smoke, "BrowserSessionFactory", PassingFactory)
    monkeypatch.setattr(
        "sys.argv",
        [
            "app.browser.smoke",
            "--chrome-binary",
            str(chrome),
            "--browser-data-dir",
            str(browser),
            "--selenium-cache-dir",
            str(cache),
        ],
    )

    assert smoke.main() == 0
    assert secret not in capsys.readouterr().out


def test_production_settings_token_validation_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "api-token.txt"
    token_file.write_text("file-secret", encoding="utf-8")
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN", "environment-secret")
    monkeypatch.setenv("KK_PRICEWATCH_API_TOKEN_FILE", str(token_file))

    with pytest.raises(ValidationError, match="not both"):
        Settings()
