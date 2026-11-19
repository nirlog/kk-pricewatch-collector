from typing import Any

import pytest
from selenium.common.exceptions import (
    InvalidSelectorException,
    InvalidSessionIdException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from app.collectors.actions import (
    ActionConfigurationError,
    BrowserActionExecutor,
    RequiredActionError,
)
from app.collectors.options import BrowserCollectorOptions


class Element:
    def __init__(self, events: list[str], name: str) -> None:
        self.events = events
        self.name = name

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def click(self) -> None:
        self.events.append(self.name)


class Driver:
    current_url = "https://example.com/product"

    def __init__(self, outcomes: dict[str, list[object]]) -> None:
        self.outcomes = outcomes
        self.events: list[str] = []

    def find_element(self, by: str, value: str) -> object:
        del by
        outcomes = self.outcomes[value]
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        self.events.append(f"find:{value}")
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
        self.ignored = ignored_exceptions

    def until(self, condition: Any) -> Any:
        for _ in range(5):
            try:
                result = condition(self.driver)
            except self.ignored:
                continue
            if result:
                return result
        raise TimeoutException("private timeout detail")


def actions(*raw: dict[str, object]) -> list[Any]:
    options = BrowserCollectorOptions.model_validate(
        {
            "allowed_hosts": ["example.com"],
            "price": {"by": "css", "selector": ".price", "source": "text"},
            "currency": "RUB",
            "decimal_separator": "none",
            "actions": list(raw),
        }
    )
    return options.actions


@pytest.fixture(autouse=True)
def immediate_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.collectors.actions.WebDriverWait", ImmediateWait)


def test_click_retries_stale_and_actions_keep_declared_order() -> None:
    events: list[str] = []
    first = Element(events, "click:first")
    second = Element(events, "click:second")
    driver = Driver({"#first": [StaleElementReferenceException(), first], "#second": [second]})
    driver.events = events

    BrowserActionExecutor().execute(
        driver,
        actions(
            {"type": "click", "by": "css", "selector": "#first"},
            {"type": "click", "by": "css", "selector": "#second"},
        ),
        lambda: events.append("validated"),
    )

    assert events == [
        "find:#first",
        "click:first",
        "validated",
        "find:#second",
        "click:second",
        "validated",
    ]


@pytest.mark.parametrize("state", ["present", "visible", "hidden"])
def test_wait_states_succeed(state: str) -> None:
    element = Element([], "unused")
    outcomes: list[object] = [NoSuchElementException(), element]
    if state == "hidden":
        outcomes = [NoSuchElementException()]
    driver = Driver({".target": outcomes})
    BrowserActionExecutor().execute(
        driver,
        actions({"type": "wait_for", "by": "css", "selector": ".target", "state": state}),
        lambda: None,
    )


@pytest.mark.parametrize("action_type", ["click", "wait_for"])
def test_required_timeout_fails_and_optional_timeout_continues(action_type: str) -> None:
    base: dict[str, object] = {"type": action_type, "by": "css", "selector": ".missing"}
    if action_type == "wait_for":
        base["state"] = "present"
    driver = Driver({".missing": [NoSuchElementException()]})
    with pytest.raises(RequiredActionError):
        BrowserActionExecutor().execute(driver, actions(base), lambda: None)

    base["required"] = False
    BrowserActionExecutor().execute(driver, actions(base), lambda: None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (InvalidSelectorException("secret selector"), ActionConfigurationError),
        (InvalidSessionIdException("secret session"), InvalidSessionIdException),
    ],
)
def test_configuration_and_session_errors_are_classified(
    error: Exception, expected: type[Exception]
) -> None:
    driver = Driver({"x": [error]})
    with pytest.raises(expected):
        BrowserActionExecutor().execute(
            driver, actions({"type": "click", "by": "css", "selector": "x"}), lambda: None
        )
