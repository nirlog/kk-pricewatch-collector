"""Command-line smoke test using the production browser factory."""

import argparse
from pathlib import Path

from app.browser.chrome import BrowserSessionFactory
from app.browser.errors import BrowserRuntimeError
from app.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local-only Chrome runtime smoke test")
    parser.add_argument("--chrome-binary", type=Path, required=True)
    parser.add_argument("--browser-data-dir", type=Path, required=True)
    parser.add_argument("--selenium-cache-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        settings = Settings(
            api_token="browser-smoke-not-an-api-credential",
            chrome_binary=args.chrome_binary,
            browser_data_dir=args.browser_data_dir,
            selenium_cache_dir=args.selenium_cache_dir,
        )
        BrowserSessionFactory(settings).preflight()
    except (BrowserRuntimeError, ValueError) as exc:
        print(f"Browser runtime smoke failed: {exc}")
        return 1
    print("Browser runtime smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
