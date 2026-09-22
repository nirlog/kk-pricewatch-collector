from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from selenium.common.exceptions import (
    InvalidSelectorException,
    InvalidSessionIdException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from app.collectors.browser import BrowserCollector
from app.contract.v1 import CollectorRequest


class Element:
    def __init__(
        self,
        text: str = "",
        attributes: dict[str, str] | None = None,
        on_click: Any | None = None,
    ) -> None:
        self.text = text
        self.attributes = attributes or {}
        self.on_click = on_click

    def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def click(self) -> None:
        if self.on_click is not None:
            self.on_click()


class Driver:
    title = ""

    def __init__(
        self, pages: dict[str, Element | Exception | str | list[Element | Exception]]
    ) -> None:
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
        if isinstance(page, list):
            if not page:
                raise NoSuchElementException()
            outcome = page.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
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


class ActionDriver(Driver):
    def __init__(
        self,
        pages: dict[str, Element | Exception | str | list[Element | Exception]],
        actions: dict[str, list[Element | Exception]],
    ) -> None:
        super().__init__(pages)
        self.actions = actions
        self.price_lookups = 0

    def find_element(self, by: str, value: str) -> Element:
        if value == ".price":
            self.price_lookups += 1
            return super().find_element(by, value)
        outcomes = self.actions[self.visited[-1]]
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ImmediateWait:
    def __init__(
        self,
        driver: Driver,
        timeout: int,
        ignored_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        del timeout
        self.driver = driver
        self.ignored_exceptions = ignored_exceptions

    def until(self, condition: Any) -> str:
        for _ in range(5):
            try:
                value = condition(self.driver)
            except self.ignored_exceptions:
                continue
            if value:
                return str(value)
        raise TimeoutException()


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
    monkeypatch.setattr("app.collectors.actions.WebDriverWait", ImmediateWait)


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


def test_transient_lookup_failures_timeout_without_aborting_later_items() -> None:
    urls = [
        "https://example.com/first",
        "https://example.com/transient",
        "https://example.com/last",
    ]
    driver = Driver(
        {
            urls[0]: Element("10,00"),
            urls[1]: [
                NoSuchElementException("not rendered"),
                StaleElementReferenceException("re-rendered"),
                Element(""),
            ],
            urls[2]: Element("30,00"),
        }
    )

    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(request(urls))

    assert response.success is True
    assert [item.id for item in response.items] == ["0", "1", "2"]
    assert response.items[0].success is True
    assert response.items[1].success is False
    assert response.items[1].error.code == "PRICE_NOT_FOUND"
    assert response.items[2].success is True
    assert driver.visited == urls
    assert driver.quit_calls == 1


def test_invalid_selector_is_sanitized_global_configuration_failure() -> None:
    url = "https://example.com/product"
    driver = Driver({url: [InvalidSelectorException("selector and local path details")]})

    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(
        request([url])
    )

    assert response.success is False
    assert response.error.model_dump() == {
        "code": "BROWSER_CONFIGURATION_ERROR",
        "message": "Browser collector selector is invalid.",
    }
    assert "details" not in response.error.message
    assert driver.quit_calls == 1


def test_lost_browser_session_remains_global_collector_failure() -> None:
    urls = ["https://example.com/first", "https://example.com/lost"]
    driver = Driver(
        {
            urls[0]: Element("10,00"),
            urls[1]: [InvalidSessionIdException("session and local path details")],
        }
    )

    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(request(urls))

    assert response.success is False
    assert response.error.model_dump() == {
        "code": "COLLECTOR_ERROR",
        "message": "Collector failed.",
    }
    assert driver.quit_calls == 1


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


def test_required_action_failure_is_isolated_between_items() -> None:
    urls = [f"https://example.com/{name}" for name in ("first", "second", "third")]
    driver = ActionDriver(
        {url: Element("10,00") for url in urls},
        {
            urls[0]: [Element()],
            urls[1]: [NoSuchElementException("private DOM detail")],
            urls[2]: [Element()],
        },
    )
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(
        request(
            urls,
            actions=[{"type": "click", "by": "css", "selector": "#accept"}],
        )
    )

    assert response.success is True
    assert [item.id for item in response.items] == ["0", "1", "2"]
    assert [item.success for item in response.items] == [True, False, True]
    assert response.items[1].error.model_dump() == {
        "code": "ACTION_FAILED",
        "message": "Required browser action could not be completed.",
    }
    assert driver.quit_calls == 1


def test_optional_action_timeout_continues_to_price() -> None:
    url = "https://example.com/product"
    driver = ActionDriver(
        {url: Element("25,00")}, {url: [NoSuchElementException("private DOM detail")]}
    )
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(
        request(
            [url],
            actions=[
                {
                    "type": "click",
                    "by": "css",
                    "selector": "#optional",
                    "required": False,
                }
            ],
        )
    )
    assert response.items[0].success is True
    assert driver.price_lookups == 1


@pytest.mark.parametrize(
    ("action_error", "code"),
    [
        (InvalidSelectorException("private selector detail"), "BROWSER_CONFIGURATION_ERROR"),
        (InvalidSessionIdException("private session detail"), "COLLECTOR_ERROR"),
    ],
)
def test_action_configuration_and_session_errors_are_sanitized_global_failures(
    action_error: Exception, code: str
) -> None:
    url = "https://example.com/product"
    driver = ActionDriver({url: Element("25,00")}, {url: [action_error]})
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(
        request([url], actions=[{"type": "click", "by": "css", "selector": "#accept"}])
    )
    assert response.success is False
    assert response.error.code == code
    assert "private" not in response.error.message


@pytest.mark.parametrize(
    ("destination", "success"),
    [
        ("https://example.com/product", True),
        ("https://shop.example.com/next", True),
        ("https://attacker.example/next", False),
    ],
)
def test_click_redirect_is_validated_before_price_extraction(
    destination: str, success: bool
) -> None:
    url = "https://example.com/product"
    driver = ActionDriver({url: Element("25,00")}, {url: []})
    driver.actions[url] = [Element(on_click=lambda: setattr(driver, "current_url", destination))]
    response = BrowserCollector(Factory(driver), lambda _: ["93.184.216.34"]).collect(
        request(
            [url],
            allowed_hosts=["example.com", "shop.example.com"],
            actions=[{"type": "click", "by": "css", "selector": "#continue"}],
        )
    )
    assert response.items[0].success is success
    if success:
        assert driver.price_lookups == 1
    else:
        assert response.items[0].error.code == "INVALID_URL"
        assert driver.price_lookups == 0
