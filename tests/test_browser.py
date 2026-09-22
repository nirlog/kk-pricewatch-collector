from pathlib import Path
from typing import Any

import pytest

from app.browser.chrome import BrowserSessionFactory
from app.browser.errors import BrowserRuntimeError
from app.settings import Settings


class FakeDriver:
    title = "kk-pricewatch-preflight"

    def __init__(self, *, fail_operation: bool = False) -> None:
        self.fail_operation = fail_operation
        self.quit_calls = 0
        self.urls: list[str] = []

    def get(self, url: str) -> None:
        self.urls.append(url)
        if self.fail_operation:
            raise RuntimeError("controlled fake failure")

    def execute_script(self, script: str) -> object:
        return self.title

    def quit(self) -> None:
        self.quit_calls += 1


def browser_settings(tmp_path: Path) -> Settings:
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    browser_data = tmp_path / "browser"
    cache = tmp_path / "cache"
    browser_data.mkdir()
    cache.mkdir()
    return Settings(
        api_token="test-token",
        chrome_binary=chrome,
        browser_data_dir=browser_data,
        selenium_cache_dir=cache,
    )


def test_factory_builds_expected_options_and_removes_isolated_profile(tmp_path: Path) -> None:
    settings = browser_settings(tmp_path)
    driver = FakeDriver()
    captured: dict[str, Any] = {}

    def build(**kwargs: Any) -> FakeDriver:
        captured.update(kwargs)
        return driver

    factory = BrowserSessionFactory(settings, driver_builder=build)
    with factory.session():
        options = captured["options"]
        arguments = options.arguments
        assert options.binary_location == str(settings.chrome_binary)
        assert "--headless=new" in arguments
        assert "--window-size=1280,720" in arguments
        profile = Path(
            next(arg.split("=", 1)[1] for arg in arguments if arg.startswith("--user-data"))
        )
        assert profile.parent == settings.browser_data_dir
        assert profile.is_dir()
    assert driver.quit_calls == 1
    assert not profile.exists()


def test_driver_is_quit_when_session_body_fails(tmp_path: Path) -> None:
    driver = FakeDriver()
    factory = BrowserSessionFactory(browser_settings(tmp_path), driver_builder=lambda **_: driver)
    with pytest.raises(BrowserRuntimeError, match="session failed"), factory.session():
        raise RuntimeError("consumer failure")
    assert driver.quit_calls == 1


def test_startup_failure_is_mapped_to_typed_error(tmp_path: Path) -> None:
    def fail(**_: Any) -> FakeDriver:
        raise RuntimeError("selenium detail")

    factory = BrowserSessionFactory(browser_settings(tmp_path), driver_builder=fail)
    with pytest.raises(BrowserRuntimeError, match="failed to start"), factory.session():
        pass


def test_preflight_uses_only_deterministic_data_page_and_quits(tmp_path: Path) -> None:
    driver = FakeDriver()
    factory = BrowserSessionFactory(browser_settings(tmp_path), driver_builder=lambda **_: driver)
    factory.preflight()
    assert driver.urls == ["data:text/html,<title>kk-pricewatch-preflight</title>"]
    assert driver.quit_calls == 1
