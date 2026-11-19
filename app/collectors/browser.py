"""Framework-independent generic single-price Selenium collector."""

from contextlib import AbstractContextManager
from typing import Any, Protocol, cast

from pydantic import ValidationError
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
from selenium.webdriver.support.ui import WebDriverWait

from app.browser.chrome import WebDriver
from app.collectors.actions import (
    ActionConfigurationError,
    BrowserActionExecutor,
    RequiredActionError,
)
from app.collectors.options import BrowserCollectorOptions
from app.collectors.price import PriceParseError, parse_price
from app.collectors.url_policy import DnsResolver, UnsafeUrlError, UrlPolicy, system_dns_resolver
from app.contract.v1 import (
    CollectorError,
    CollectorRequest,
    CollectorResponse,
    FailedItem,
    FailedResponse,
    SuccessfulItem,
    SuccessfulResponse,
)


class SessionFactory(Protocol):
    def session(self) -> AbstractContextManager[WebDriver]: ...


class _InvalidSelector:
    """Internal marker preventing selector errors from crossing the session context."""


class BrowserCollector:
    """Collect every request item sequentially through one browser session."""

    def __init__(
        self,
        session_factory: SessionFactory,
        resolver: DnsResolver = system_dns_resolver,
        action_executor: BrowserActionExecutor | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._resolver = resolver
        self._action_executor = action_executor or BrowserActionExecutor()

    def collect(self, request: CollectorRequest) -> CollectorResponse:
        try:
            options = BrowserCollectorOptions.model_validate(request.options.get("browser"))
        except (ValidationError, TypeError):
            return FailedResponse(
                request_id=request.request_id,
                error=CollectorError(
                    code="BROWSER_CONFIGURATION_ERROR",
                    message="Browser collector configuration is missing or invalid.",
                ),
            )

        policy = UrlPolicy(options.allowed_hosts, self._resolver)
        invalid_selector = False
        try:
            with self._session_factory.session() as driver:
                driver.set_page_load_timeout(options.page_load_timeout_seconds)
                results: list[SuccessfulItem | FailedItem] = []
                for item in request.items:
                    result = self._collect_item(driver, item.id, item.url, options, policy)
                    if isinstance(result, _InvalidSelector):
                        invalid_selector = True
                        break
                    results.append(result)
        except Exception:
            return FailedResponse(
                request_id=request.request_id,
                error=CollectorError(code="COLLECTOR_ERROR", message="Collector failed."),
            )
        if invalid_selector:
            return FailedResponse(
                request_id=request.request_id,
                error=CollectorError(
                    code="BROWSER_CONFIGURATION_ERROR",
                    message="Browser collector selector is invalid.",
                ),
            )
        return SuccessfulResponse(request_id=request.request_id, items=results)

    def _collect_item(
        self,
        driver: WebDriver,
        item_id: str,
        url: str,
        options: BrowserCollectorOptions,
        policy: UrlPolicy,
    ) -> SuccessfulItem | FailedItem | _InvalidSelector:
        try:
            policy.validate_before_navigation(url)
        except UnsafeUrlError:
            return self._item_error(item_id, "INVALID_URL", "URL is not allowed.")

        try:
            driver.get(url)
        except (InvalidSessionIdException, NoSuchDriverException, NoSuchWindowException):
            raise
        except (TimeoutException, WebDriverException):
            return self._item_error(item_id, "PAGE_LOAD_FAILED", "Page could not be loaded.")

        try:
            policy.validate_after_navigation(driver.current_url)
        except (InvalidSessionIdException, NoSuchDriverException, NoSuchWindowException):
            raise
        except WebDriverException:
            return self._item_error(item_id, "PAGE_LOAD_FAILED", "Page could not be loaded.")
        except UnsafeUrlError:
            return self._item_error(item_id, "INVALID_URL", "Redirect URL is not allowed.")

        try:
            self._action_executor.execute(
                driver,
                options.actions,
                lambda: policy.validate_after_navigation(driver.current_url),
            )
        except ActionConfigurationError:
            return _InvalidSelector()
        except RequiredActionError:
            return self._item_error(
                item_id,
                "ACTION_FAILED",
                "Required browser action could not be completed.",
            )
        except UnsafeUrlError:
            return self._item_error(item_id, "INVALID_URL", "Redirect URL is not allowed.")

        by = By.CSS_SELECTOR if options.price.by == "css" else By.XPATH

        def extracted_value(candidate: Any) -> str | bool:
            element = candidate.find_element(by, options.price.selector)
            if options.price.source == "text":
                value = element.text
            else:
                assert options.price.attribute is not None
                value = element.get_attribute(options.price.attribute)
            return value if isinstance(value, str) and value.strip() else False

        try:
            raw = cast(
                str,
                WebDriverWait(
                    cast(Any, driver),
                    options.wait_timeout_seconds,
                    ignored_exceptions=(
                        NoSuchElementException,
                        StaleElementReferenceException,
                    ),
                ).until(extracted_value),
            )
        except InvalidSelectorException:
            return _InvalidSelector()
        except (InvalidSessionIdException, NoSuchDriverException, NoSuchWindowException):
            raise
        except TimeoutException:
            return self._item_error(item_id, "PRICE_NOT_FOUND", "Price was not found.")
        except WebDriverException:
            return self._item_error(item_id, "PRICE_NOT_FOUND", "Price was not found.")
        try:
            price = parse_price(raw, options.decimal_separator)
        except PriceParseError:
            return self._item_error(item_id, "PRICE_INVALID", "Price value is invalid.")
        return SuccessfulItem(id=item_id, price=price, currency=options.currency)

    @staticmethod
    def _item_error(item_id: str, code: str, message: str) -> FailedItem:
        return FailedItem(id=item_id, error=CollectorError(code=code, message=message))
