"""Command-line smoke test using the production browser factory."""

import argparse
from pathlib import Path

from app.browser.chrome import BrowserSessionFactory
from app.browser.errors import BrowserRuntimeError
from app.settings import Settings


def browser_runtime_settings(
    chrome_binary: Path,
    browser_data_dir: Path,
    selenium_cache_dir: Path,
) -> Settings:
    """Build smoke-only settings without reading production token variables."""
    return Settings(
        _env_prefix="KK_PRICEWATCH_BROWSER_SMOKE_INTERNAL_",
        api_token="browser-smoke-not-an-api-credential",
        chrome_binary=chrome_binary,
        browser_data_dir=browser_data_dir,
        selenium_cache_dir=selenium_cache_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local-only Chrome runtime smoke test")
    parser.add_argument("--chrome-binary", type=Path, required=True)
    parser.add_argument("--browser-data-dir", type=Path, required=True)
    parser.add_argument("--selenium-cache-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        settings = browser_runtime_settings(
            args.chrome_binary,
            args.browser_data_dir,
            args.selenium_cache_dir,
        )
        BrowserSessionFactory(settings).preflight()
    except (BrowserRuntimeError, ValueError) as exc:
        print(f"Browser runtime smoke failed: {exc}")
        return 1
    print("Browser runtime smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
