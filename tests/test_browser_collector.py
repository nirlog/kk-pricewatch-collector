from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from app.collectors.browser import BrowserCollector
from app.contract.v1 import CollectorRequest


class Element:
    def __init__(self, text: str = "", attributes: dict[str, str] | None = None) -> None:
        self.text = text
        self.attributes = attributes or {}

    def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)


class Driver:
    title = ""

    def __init__(self, pages: dict[str, Element | Exception | str]) -> None:
        self.pages = pages
        self.current_url = ""
        self.timeouts: list[float] = []
        self.visited: list[str] = []
        self.quit_calls = 0

    def set_page_load_timeout(self, value: float) -> None:
        self.timeouts.append(value)

    def get(self, url: str) -> None:
        self.visited.append(url)
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        self.current_url = page if isinstance(page, str) else url

    def find_element(self, by: str, value: str) -> Element:
        del by, value
        page = self.pages[self.visited[-1]]
        if not isinstance(page, Element):
            raise NoSuchElementException()
        return page

    def execute_script(self, script: str) -> object:
        del script
        return None

    def quit(self) -> None:
        self.quit_calls += 1


class Factory:
    def __init__(self, driver: Driver, fail: bool = False) -> None:
        self.driver = driver
        self.fail = fail
        self.sessions = 0

    @contextmanager
    def session(self) -> Iterator[Driver]:
        self.sessions += 1
        if self.fail:
            raise RuntimeError("secret startup detail")
        try:
            yield self.driver
        finally:
            self.driver.quit()


class ImmediateWait:
    def __init__(self, driver: Driver, timeout: int) -> None:
        del timeout
        self.driver = driver

    def until(self, condition: Any) -> str:
        try:
            value = condition(self.driver)
        except NoSuchElementException as exc:
            raise TimeoutException() from exc
        if not value:
            raise TimeoutException()
        return str(value)


def request(urls: list[str], **browser_overrides: object) -> CollectorRequest:
    browser: dict[str, object] = {
        "allowed_hosts": ["example.com"],
        "price": {"by": "css", "selector": ".price", "source": "text"},
        "currency": "RUB",
        "decimal_separator": "comma",
        "wait_timeout_seconds": 1,
        "page_load_timeout_seconds": 30,
    }
    browser.update(browser_overrides)
    return CollectorRequest.model_validate(
        {
            "schema_version": "1.0",
            "request_id": "round-trip",
            "items": [{"id": str(index), "url": url} for index, url in enumerate(urls)],
            "options": {"browser": browser},
        }
    )


@pytest.fixture(autouse=True)
def immediate_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.collectors.browser.WebDriverWait", ImmediateWait)


def test_one_session_processes_multiple_items_in_order() -> None:
    urls = ["https://example.com/a", "https://example.com/b"]
    driver = Driver({url: Element("129 990,50 ₽") for url in urls})
    factory = Factory(driver)
    response = BrowserCollector(factory, lambda _: ["93.184.216.34"]).collect(request(urls))
    assert response.model_dump() == {
        "schema_version": "1.0",
        "request_id": "round-trip",
        "success": True,
        "items": [
            {"id": "0", "success": True, "price": "129990.50", "currency": "RUB"},
            {"id": "1", "success": True, "price": "129990.50", "currency": "RUB"},
        ],
    }
    assert factory.sessions == 1
    assert driver.quit_calls == 1
    assert driver.timeouts == [30]


def test_mixed_item_failures_do_not_stop_request() -> None:
    urls = [
        "https://example.com/missing",
        "https://example.com/load",
        "https://example.com/invalid",
        "https://example.com/good",
    ]
    driver = Driver(
        {
            urls[0]: Element(""),
            urls[1]: WebDriverException("sensitive stack"),
            urls[2]: Element("12,34,56"),
            urls[3]: Element("100,50"),
        }
    )
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(request(urls))
    assert response.success is True
    assert [item.id for item in response.items] == ["0", "1", "2", "3"]
    assert [item.success for item in response.items] == [False, False, False, True]
    assert [item.error.code for item in response.items[:3]] == [
        "PRICE_NOT_FOUND",
        "PAGE_LOAD_FAILED",
        "PRICE_INVALID",
    ]


def test_attribute_extraction_and_redirect_policy() -> None:
    source = "https://example.com/a"
    driver = Driver({source: Element(attributes={"content": "10.25"})})
    price = {"by": "css", "selector": "meta", "source": "attribute", "attribute": "content"}
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(
        request([source], price=price, decimal_separator="dot")
    )
    assert response.items[0].success is True

    redirect_driver = Driver({source: "https://attacker.example/value"})
    redirected = BrowserCollector(Factory(redirect_driver), lambda _: ["93.184.216.34"]).collect(
        request([source])
    )
    assert redirected.items[0].error.code == "INVALID_URL"


def test_invalid_configuration_is_sanitized_global_failure() -> None:
    driver = Driver({})
    raw = request(["https://example.com/a"]).model_copy(update={"options": {"browser": {}}})
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(raw)
    assert response.success is False
    assert response.error.code == "BROWSER_CONFIGURATION_ERROR"
    assert "validation" not in response.error.message.lower()
    assert driver.quit_calls == 0


def test_session_startup_failure_is_sanitized_global_failure() -> None:
    driver = Driver({})
    response = BrowserCollector(Factory(driver, fail=True), lambda _: ["93.184.216.34"]).collect(
        request(["https://example.com/a"])
    )
    assert response.success is False
    assert response.error.model_dump() == {
        "code": "COLLECTOR_ERROR",
        "message": "Collector failed.",
    }
    assert "secret" not in response.error.message
