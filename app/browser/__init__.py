"""Browser runtime infrastructure (not a collector implementation)."""

from app.browser.chrome import BrowserSessionFactory
from app.browser.errors import BrowserRuntimeError

__all__ = ["BrowserRuntimeError", "BrowserSessionFactory"]
