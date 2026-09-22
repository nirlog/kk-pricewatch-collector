"""Strict Selenium execution for the predefined browser action models."""

from collections.abc import Callable, Sequence
from typing import Any, cast

from selenium.common.exceptions import (
    InvalidSelectorException,
    InvalidSessionIdException,
    NoSuchDriverException,
    NoSuchElementException,
    NoSuchWindowException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from app.browser.chrome import WebDriver
from app.collectors.options import BrowserAction, ClickAction


class RequiredActionError(Exception):
    """A required, item-local action could not be completed."""


class ActionConfigurationError(Exception):
    """An action contains a selector rejected by Selenium."""


AfterClick = Callable[[], None]


class BrowserActionExecutor:
    """Execute only the closed set of validated action models, in order."""

    def execute(
        self,
        driver: WebDriver,
        actions: Sequence[BrowserAction],
        after_click: AfterClick,
    ) -> None:
        for action in actions:
            try:
                self._execute_one(driver, action)
            except InvalidSelectorException as exc:
                raise ActionConfigurationError from exc
            except (InvalidSessionIdException, NoSuchDriverException, NoSuchWindowException):
                raise
            except (TimeoutException, WebDriverException) as exc:
                if action.required:
                    raise RequiredActionError from exc
                # A click can navigate before WebDriver reports a local failure. Checking
                # even the optional-failure path keeps continuation inside the URL policy.
                if isinstance(action, ClickAction):
                    after_click()
                continue
            if isinstance(action, ClickAction):
                after_click()

    @staticmethod
    def _execute_one(driver: WebDriver, action: BrowserAction) -> None:
        locator = (By.CSS_SELECTOR if action.by == "css" else By.XPATH, action.selector)
        wait = WebDriverWait(
            cast(Any, driver),
            action.timeout_seconds,
            ignored_exceptions=(NoSuchElementException, StaleElementReferenceException),
        )
        if isinstance(action, ClickAction):
            clickable = expected_conditions.element_to_be_clickable(locator)

            def click_when_ready(candidate: Any) -> bool:
                element = clickable(candidate)
                if not element:
                    return False
                element.click()
                return True

            wait.until(click_when_ready)
            return

        conditions: dict[str, Callable[[Any], Any]] = {
            "present": expected_conditions.presence_of_element_located(locator),
            "visible": expected_conditions.visibility_of_element_located(locator),
            "hidden": expected_conditions.invisibility_of_element_located(locator),
        }
        wait.until(conditions[action.state])
