# Task 003 — Selenium / Chrome browser runtime foundation

Target version: **0.3.0**

## Goal and boundary

Provide a production-safe Selenium 4/headless Google Chrome runtime for the Windows
`LocalService` process. This task proves that a browser can start and respond, but does
not collect anything. `POST /api/collectors/browser` remains wired to the deterministic
`StubCollector`; real navigation, extraction, selectors, and a `BrowserCollector` are
reserved for Task 004.

```text
Bitrix -> HTTPS/Caddy -> FastAPI -> future BrowserCollector (inactive in Task 003)
                                    -> BrowserSessionFactory
                                    -> Selenium WebDriver -> headless Chrome
```

## Decisions and security constraints

- Selenium is bounded to major version 4 and uses official Selenium Manager. Chrome is
  never installed or downloaded by application code.
- `KK_PRICEWATCH_CHROME_BINARY` names an existing, absolute machine-wide executable;
  paths below `C:\Users` are rejected.
- `KK_PRICEWATCH_BROWSER_DATA_DIR` and `KK_PRICEWATCH_SELENIUM_CACHE_DIR` name existing,
  absolute directories. Production uses ProgramData, with only the runtime directories
  writable by LocalService. `SE_CACHE_PATH` directs Selenium Manager away from profiles.
- Every factory context creates a unique temporary `user-data-dir`, starts exactly one
  driver, always calls `quit`, and removes the profile. There is no shared driver/profile.
- Chrome receives only `--headless=new`, a deterministic window size, and the isolated
  profile. Certificate bypass, sandbox bypass, stealth, spoofing, proxies, CAPTCHA and
  anti-bot behavior are explicitly absent.
- `KK_PRICEWATCH_BROWSER_PREFLIGHT` defaults to false. When true, application startup
  loads a deterministic `data:` document, executes JavaScript, verifies its title, and
  quits. Failure aborts startup. `/health` never launches Chrome. The production WinSW
  process sets `SE_OFFLINE=true`, `SE_AVOID_STATS=true`, and
  `SE_AVOID_BROWSER_DOWNLOAD=true`, so Selenium Manager is cache-only and cannot make
  startup or preflight depend on the public internet.
- Installation has two explicit browser phases before service registration: an
  online-capable `ProvisionDriver` smoke may download a matching ChromeDriver into the
  ProgramData cache, but never Chrome and never telemetry; an `Offline` smoke then proves
  the prepared cache is sufficient. Either failure prevents service installation while
  retaining cache data for diagnostics.

## Acceptance criteria

1. Typed settings reject missing/non-file Chrome, relative paths, user-scoped Chrome,
   missing/non-directory runtime paths, and incomplete enabled preflight configuration.
2. The browser layer is independent of FastAPI, dependency-injectable, and maps runtime
   failures to `BrowserRuntimeError`.
3. Unit tests use fakes, make no network/browser calls, and cover options, profile
   isolation/cleanup, quit behavior, preflight lifecycle, lightweight health, and the
   unchanged stub endpoint/security behavior.
4. Windows installation requires a machine-wide Chrome path, creates browser/cache
   directories, applies LocalService Modify ACL only there, preserves the read-only token
   ACL, and generates secret-free WinSW browser environment settings.
5. `Test-BrowserRuntime.ps1` invokes the production Python factory and returns non-zero
   on failure. Its explicit `ProvisionDriver` and `Offline` modes control Selenium
   Manager without duplicating Selenium in PowerShell.

## Explicitly out of scope

Competitor requests, price parsing, CSS/XPath selectors, retries, queues, persistence,
CAPTCHA/Cloudflare bypass, webdriver hiding, fingerprint or user-agent spoofing, login
automation, cookies/profile farming, proxy support, Playwright, webdriver-manager,
undetected-chromedriver, and stealth plugins.
