# kk-pricewatch-collector

Standalone Python collection service for [`nirlog/kk.pricewatch`](https://github.com/nirlog/kk.pricewatch).
Its only integration boundary is HTTP collector protocol `1.0`; it imports no Bitrix
code and shares no database or filesystem with Bitrix.

Version **0.5.0** adds a deliberately small set of typed, pre-price browser actions to
the generic Selenium collector. It is not a browser-scenario engine and contains no
competitor-specific code.

## Local development

Requires Python 3.12+:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
export KK_PRICEWATCH_API_TOKEN='local-test-token'
python -m pytest
```

Exactly one token source is required. `KK_PRICEWATCH_API_TOKEN` remains convenient for
local/container use. `KK_PRICEWATCH_API_TOKEN_FILE` points to a UTF-8 file and is the
recommended production mechanism. The application does not load `.env` automatically.
Never put the token in a URL or protocol JSON.

## Manual foreground run

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

`GET /health` is public and returns exactly `{"status":"ok"}`.
`POST /api/collectors/browser` requires `Authorization: Bearer <token>` and invokes the
real `BrowserCollector`. Its strict options are documented in
[`docs/tasks/004-generic-browser-price-collector.md`](docs/tasks/004-generic-browser-price-collector.md).

## Windows production service

Production uses this fixed boundary:

```text
Bitrix -> HTTPS/Caddy -> FastAPI -> BrowserCollector
                               -> BrowserSessionFactory -> Selenium -> headless Chrome
```

WinSW runs the Collector automatically as low-privilege LocalService, restarts it after
failure, and rotates stdout/stderr. Uvicorn is never bound to `0.0.0.0`; do not expose
port 8000. Neither WinSW nor Caddy binaries are stored/downloaded by this repository.
The complete layout, prerequisites, commands, ACL model, and operational cautions are
in [`deploy/windows/README.md`](deploy/windows/README.md).

### Install

Clone an explicit release into `C:\Services\kk-pricewatch-collector`, open elevated
PowerShell, and provide the path to an operator-downloaded WinSW binary:

```powershell
.\deploy\windows\Install-CollectorService.ps1 `
  -WinSWPath 'C:\Installers\WinSW-x64.exe' `
  -ChromeBinary 'C:\Program Files\Google\Chrome\Application\chrome.exe'
```

The script creates the virtual environment and protected ProgramData directories,
securely prompts for a token when needed, installs and starts the automatic service,
and reports success only after checking `http://127.0.0.1:8000/health`.

### Status

```powershell
.\deploy\windows\Get-CollectorStatus.ps1
```

This displays installation/state/startup/health information, never token metadata.

### Update and rollback

Always provide an immutable release tag or commit explicitly:

```powershell
.\deploy\windows\Update-Collector.ps1 -Ref 'v0.5.0'
```

A dirty tree is rejected. The updater records the old SHA, installs and smoke-checks
the requested ref, starts it, and verifies health. Any failure triggers reinstall,
restart, and health verification of the recorded SHA. Persistent secrets and logs are
not touched. See the runbook for exact rollback failure behavior.

### Uninstall

```powershell
.\deploy\windows\Uninstall-CollectorService.ps1
```

Normal uninstall retains the repository, token, and logs and prints their location.
Destructive ProgramData removal requires `-PurgeData` plus explicit confirmation.

### Secret rotation

Securely replace
`C:\ProgramData\KKPriceWatchCollector\secrets\api-token.txt` without placing its value
on a command line, preserve/reapply its restricted ACL, then run
`Restart-Service KKPriceWatchCollector` and verify status. Coordinate the change so the
Bitrix module and Collector have the same token; these scripts never modify Bitrix.

### Caddy / HTTPS

Use an operator-owned Caddyfile and supplied binaries:

```powershell
.\deploy\windows\Install-CaddyService.ps1 `
  -CaddyPath 'C:\Tools\caddy.exe' `
  -CaddyfilePath 'C:\ProgramData\KKPriceWatchCaddy\Caddyfile' `
  -WinSWPath 'C:\Installers\WinSW-x64.exe'
```

The script validates the Caddyfile before installing automatic, restart-on-failure
`KKPriceWatchCaddy`. A reusable configuration shape is:

```caddyfile
collector.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Operators configure the actual hostname, DNS, certificates, inbound 80/443 firewall,
and separate Caddy access logs. No production hostname is hardcoded in templates.

## Browser collector example

Send JSON to `POST /api/collectors/browser` with a bearer header:

```json
{
  "schema_version": "1.0",
  "request_id": "e2e-1",
  "items": [{"id": "12", "url": "https://competitor.example/p/1?region=spb"}],
  "options": {
    "browser": {
      "allowed_hosts": ["competitor.example"],
      "actions": [
        {
          "type": "click",
          "by": "css",
          "selector": "#cookie-accept",
          "timeout_seconds": 5,
          "required": false
        },
        {
          "type": "wait_for",
          "by": "css",
          "selector": ".cookie-overlay",
          "state": "hidden",
          "timeout_seconds": 5,
          "required": false
        }
      ],
      "price": {
        "by": "css",
        "selector": ".product-price",
        "source": "text"
      },
      "currency": "RUB",
      "decimal_separator": "comma",
      "wait_timeout_seconds": 15,
      "page_load_timeout_seconds": 30
    }
  }
}
```

Before the existing price extraction, the collector may execute up to ten predefined
`click` and `wait_for` actions. Selectors are CSS or XPath; waits may target `present`,
`visible`, or `hidden`. Required actions fail the item, while optional action timeouts
are skipped. Each action timeout is 1--30 seconds and their total is at most 60 seconds.
Every click is followed by final-URL validation.

The collector supports one CSS or XPath price selector and extracts visible text or a
configured attribute. It applies an exact-host/public-DNS baseline SSRF policy before
navigation and checks the final redirect host. This is not complete DNS-rebinding
protection. No action can accept a URL, script, Selenium method, or arbitrary expected
condition. Full action semantics and exclusions are documented in
[`docs/tasks/005-constrained-browser-actions.md`](docs/tasks/005-constrained-browser-actions.md).
Protocol-level failures still use HTTP 200; protocol `1.0` is unchanged.

## Quality checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy app
docker build -t kk-pricewatch-collector:0.5.0 .
```

CI additionally parses every PowerShell deployment script on Windows. Docker remains an
optional portability check, not the primary production runtime. Supply its token only
at runtime; never bake it into an image.

## Browser runtime foundation

Task 003 uses official Selenium Manager and an operator-installed, explicitly configured
machine-wide Google Chrome. It creates an isolated temporary profile per session below
`C:\ProgramData\KKPriceWatchCollector\browser` and keeps the driver cache under
`selenium-cache`. Production performs one local-only browser preflight during startup;
Selenium Manager is strictly offline/cache-only in the WinSW service and `/health` stays
lightweight. Installation first provisions a matching ChromeDriver into ProgramData,
then proves it works in offline mode before registering the service. After an operator
updates Chrome, rerun driver provisioning before restarting the Collector. Run the same
production browser path manually with `deploy/windows/Test-BrowserRuntime.ps1 -Mode
ProvisionDriver`, followed by `-Mode Offline`. The endpoint now uses
`BrowserCollector`; the stub remains a deterministic test helper. See
[`docs/tasks/003-selenium-browser-runtime.md`](docs/tasks/003-selenium-browser-runtime.md).
