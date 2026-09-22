import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_health_is_public_and_minimal(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert set(response.json()) == {"status"}


def test_collector_endpoint_still_requires_authentication(
    client: TestClient, minimal_payload: dict[str, object]
) -> None:
    response = client.post("/api/collectors/browser", json=minimal_payload)
    assert response.status_code == 401


def test_health_does_not_launch_browser() -> None:
    calls = 0

    class Factory:
        def preflight(self) -> None:
            nonlocal calls
            calls += 1

    with TestClient(
        create_app(Settings(api_token="token"), browser_factory_builder=lambda _: Factory())
    ) as test_client:
        assert test_client.get("/health").json() == {"status": "ok"}
        assert test_client.get("/health").json() == {"status": "ok"}
    assert calls == 0


def test_enabled_preflight_runs_once_at_startup(tmp_path) -> None:
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    browser = tmp_path / "browser"
    cache = tmp_path / "cache"
    browser.mkdir()
    cache.mkdir()
    calls = 0

    class Factory:
        def preflight(self) -> None:
            nonlocal calls
            calls += 1

    settings = Settings(
        api_token="token",
        chrome_binary=chrome,
        browser_data_dir=browser,
        selenium_cache_dir=cache,
        browser_preflight=True,
    )
    with TestClient(
        create_app(settings, browser_factory_builder=lambda _: Factory())
    ) as test_client:
        assert test_client.get("/health").status_code == 200
        assert test_client.get("/health").status_code == 200
    assert calls == 1


def test_failed_preflight_prevents_startup(tmp_path) -> None:
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    browser = tmp_path / "browser"
    cache = tmp_path / "cache"
    browser.mkdir()
    cache.mkdir()

    class Factory:
        def preflight(self) -> None:
            raise RuntimeError("Chrome unavailable")

    settings = Settings(
        api_token="token",
        chrome_binary=chrome,
        browser_data_dir=browser,
        selenium_cache_dir=cache,
        browser_preflight=True,
    )
    with (
        pytest.raises(RuntimeError, match="Chrome unavailable"),
        TestClient(create_app(settings, browser_factory_builder=lambda _: Factory())),
    ):
        pass
