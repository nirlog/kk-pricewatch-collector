"""Isolated, dependency-injectable Chrome WebDriver sessions."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.browser.errors import BrowserRuntimeError
from app.settings import Settings


class WebDriver(Protocol):
    """Small portion of WebDriver used by the browser runtime."""

    @property
    def title(self) -> str: ...

    @property
    def current_url(self) -> str: ...

    def get(self, url: str) -> None: ...

    def set_page_load_timeout(self, time_to_wait: float) -> None: ...

    def find_element(self, by: str, value: str) -> object: ...

    def execute_script(self, script: str) -> object: ...

    def quit(self) -> None: ...


DriverBuilder = Callable[..., WebDriver]


class BrowserSessionFactory:
    """Create one headless Chrome instance with one temporary profile per call."""

    def __init__(
        self,
        settings: Settings,
        driver_builder: DriverBuilder = webdriver.Chrome,
    ) -> None:
        if (
            settings.chrome_binary is None
            or settings.browser_data_dir is None
            or settings.selenium_cache_dir is None
        ):
            raise BrowserRuntimeError("browser runtime paths are not fully configured")
        self._chrome_binary = settings.chrome_binary
        self._browser_data_dir = settings.browser_data_dir
        self._selenium_cache_dir = settings.selenium_cache_dir
        self._driver_builder = driver_builder

    def _options(self, profile: Path) -> Options:
        options = Options()
        options.binary_location = str(self._chrome_binary)
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,720")
        options.add_argument(f"--user-data-dir={profile}")
        return options

    @contextmanager
    def session(self) -> Iterator[WebDriver]:
        driver: WebDriver | None = None
        try:
            with TemporaryDirectory(prefix="chrome-", dir=self._browser_data_dir) as profile:
                # Selenium Manager reads this supported variable when resolving ChromeDriver.
                os.environ["SE_CACHE_PATH"] = str(self._selenium_cache_dir)
                try:
                    driver = self._driver_builder(options=self._options(Path(profile)))
                except Exception as exc:
                    raise BrowserRuntimeError(f"Chrome WebDriver failed to start: {exc}") from exc
                try:
                    yield driver
                finally:
                    try:
                        driver.quit()
                    except Exception as exc:
                        raise BrowserRuntimeError(
                            f"Chrome WebDriver failed to quit: {exc}"
                        ) from exc
        except BrowserRuntimeError:
            raise
        except Exception as exc:
            raise BrowserRuntimeError(f"browser session failed: {exc}") from exc

    def preflight(self) -> None:
        """Exercise Chrome against deterministic, non-network content."""

        try:
            with self.session() as driver:
                driver.get("data:text/html,<title>kk-pricewatch-preflight</title>")
                responsive = driver.execute_script("return document.title")
                if responsive != "kk-pricewatch-preflight" or driver.title != responsive:
                    raise BrowserRuntimeError(
                        "Chrome preflight returned an unexpected document title"
                    )
        except BrowserRuntimeError:
            raise
        except Exception as exc:
            raise BrowserRuntimeError(f"Chrome preflight failed: {exc}") from exc
