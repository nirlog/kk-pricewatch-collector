# kk-pricewatch-collector

Standalone Python collection service for [`nirlog/kk.pricewatch`](https://github.com/nirlog/kk.pricewatch).
Its only integration boundary is HTTP collector protocol `1.0`; it imports no Bitrix
code and shares no database or filesystem with Bitrix.

Version **0.2.0** adds a Windows production-service runtime around the unchanged,
deterministic protocol stub. It performs no real scraping, browser automation, or
competitor network requests.

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

`GET /health` is public and returns exactly `{"status":"ok"}`. The existing
`POST /api/collectors/browser` endpoint still requires `Authorization: Bearer <token>`.
The stub's request/response contract and options are documented in
[`docs/tasks/001-protocol-compatible-stub.md`](docs/tasks/001-protocol-compatible-stub.md).

## Windows production service

Production uses this fixed boundary:

```text
Bitrix -> public HTTPS -> Caddy -> http://127.0.0.1:8000 -> Uvicorn/FastAPI
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
.\deploy\windows\Install-CollectorService.ps1 -WinSWPath 'C:\Installers\WinSW-x64.exe'
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
.\deploy\windows\Update-Collector.ps1 -Ref 'v0.2.0'
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

## Protocol stub example

Send JSON to `POST /api/collectors/browser` with a bearer header:

```json
{
  "schema_version": "1.0",
  "request_id": "e2e-1",
  "items": [{"id": "12", "url": "https://competitor.example/p/1?region=spb"}],
  "options": {
    "stub": {
      "default": {"type": "success", "price": "12345.67", "currency": "RUB"}
    }
  }
}
```

Stub options also support deterministic per-item errors and global failures as defined
by Task 001. Protocol-level global failures still use HTTP 200. No endpoint or protocol
`1.0` shape changed in Task 002.

## Quality checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy app
docker build -t kk-pricewatch-collector:0.2.0 .
```

CI additionally parses every PowerShell deployment script on Windows. Docker remains an
optional portability check, not the primary production runtime. Supply its token only
at runtime; never bake it into an image.

## Future browser runtime

Task 002 installs no Selenium, Chrome/Chromium, ChromeDriver, Playwright, browser code,
or interactive desktop session. The Windows layout reserves
`C:\ProgramData\KKPriceWatchCollector\browser` for a future task without creating or
using it now.
