# Task 002 — Windows production runtime and services

## Status and target

Implemented for version `0.2.0`. Protocol `1.0`, the authenticated
`POST /api/collectors/browser` route, and deterministic stub behavior remain unchanged.

## Decisions

- WinSW wraps both the Collector and optional Caddy; third-party binaries are supplied
  and verified by the operator and are never downloaded or committed by this project.
- Uvicorn runs from the checkout virtual environment as LocalService, with a fixed
  loopback-only `127.0.0.1:8000` listener. Only Caddy exposes production HTTPS.
- Generated wrapper state lives below ProgramData, independently of the Git checkout.
  WinSW rotates stdout/stderr by size and restarts crashed processes.
- Production authentication uses `KK_PRICEWATCH_API_TOKEN_FILE`; development and
  containers retain `KK_PRICEWATCH_API_TOKEN`. Exactly one source is required.
- `/health` is intentionally unauthenticated and returns only `{"status":"ok"}`.
- Updates require an explicit ref and a clean tree. The previous commit is restored,
  reinstalled, restarted, and health-checked whenever deployment fails.

## Security model

The token file is UTF-8 and is readable only by Administrators, SYSTEM, and the
LocalService Collector identity. Its value is absent from XML, arguments, log output,
model representations, and validation errors. The service configuration contains the
non-secret file path. Authorization continues to use constant-time comparison. No
firewall rule is made for port 8000, and DNS/TLS/public firewall management remains an
operator concern.

## Assets and verification

`deploy/windows/README.md` is the operator runbook. Templates contain paths only and are
materialized with XML escaping. Install, status, explicit-ref update with rollback,
uninstall/purge, Caddy validation/install, and Caddy uninstall have separate scripts.
Linux tests validate application behavior and static deployment invariants; CI parses
all PowerShell files on a Windows runner without installing services.

## Deferred work

Browser automation, browsers/drivers, profiles, scraping, queues, persistence, retries,
and Bitrix changes are outside this task. `C:\ProgramData\KKPriceWatchCollector\browser`
is reserved (but not created) for future persistent browser runtime data.
