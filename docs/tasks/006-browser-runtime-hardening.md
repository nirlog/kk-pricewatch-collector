# Task 006 — Browser Runtime Hardening

Target version: **0.5.1**

## Scope and invariants

This task hardens Windows maintenance around the existing Selenium/Chrome runtime.
Collector protocol 1.0, price extraction, constrained actions, and the public health
response are unchanged. Production WinSW continues to set `SE_OFFLINE=true`,
`SE_AVOID_STATS=true`, and `SE_AVOID_BROWSER_DOWNLOAD=true`. Application requests
therefore cannot ask Selenium Manager to download a driver.

`GET /health` remains browser-free and returns exactly `{"status":"ok"}`. Browser
compatibility is verified through the administrative runtime smoke because launching
Chrome from health would add latency, network-adjacent maintenance behavior, and a
public operational signal.

## Token-independent browser smoke

`app.browser.smoke` builds runtime settings with a smoke-specific environment prefix.
Inherited `KK_PRICEWATCH_API_TOKEN` and `KK_PRICEWATCH_API_TOKEN_FILE` values are
ignored without clearing or modifying them. The ordinary `Settings` construction path
still requires exactly one real application token source.

The smoke navigates only a deterministic `data:` document. PowerShell suppresses raw
Selenium Manager diagnostics and reports fixed maintenance results, preventing
machine-specific output or inherited authentication values from entering logs.

## Verification and explicit repair

`Repair-BrowserRuntime.ps1` accepts the repository, ProgramData, Chrome, and optional
virtual-environment Python paths. Its default verification mode runs `Offline` once
and never provisions. With `-Repair`, it still runs `Offline` first. Only an initial
failure permits `ProvisionDriver`, followed by a mandatory final `Offline` smoke.
Repair requires the installed Collector service to be stopped.

Every Selenium Manager process variable changed by the shared runtime module is
restored in a `finally` block. The production token variables are never changed.
Provisioning remains an elevated maintenance operation.

## Update behavior

`Update-Collector.ps1` requires the machine-wide Chrome path. Once the service is
stopped and target code installed, it cleans orphan profiles and runs offline browser
verification before service startup. Without `-RepairBrowserRuntime`, failure enters
the existing rollback path. With the switch, the updater may explicitly provision a
matching driver and must then pass offline verification.

Rollback reinstalls the recorded commit and package, repeats the narrowly scoped
profile cleanup, starts the previous service, and verifies `/health`. It deliberately
does not invoke browser verification from the previous checkout: a pre-existing
browser mismatch or legacy smoke implementation must not prevent restoration of
service availability. Profile-cleanup failure and possible browser degradation are
reported as warnings, while the original target update failure remains authoritative.
Rollback never provisions a driver, even when `-RepairBrowserRuntime` authorized
repair of the target.

## Orphan profile cleanup

Selenium sessions normally remove their temporary profiles. Crashes and reboots can
leave direct `chrome-*` directories below the configured browser data directory.
Cleanup runs during update while the service is stopped, or through the maintenance
command after confirming the installed service is stopped.

Only direct child directories matching `chrome-*` are candidates. Reparse points are
skipped. Cleanup does not recurse while discovering candidates, inspect profile
contents for paths, touch unrelated files or directories, touch `selenium-cache`, or
remove the browser data directory. `-CleanupWhatIf` reports candidates without
deleting them.

## CI coverage

Python tests cover inherited token sources, secret-free output, unchanged production
token validation, deployment assets, and version 0.5.1. Windows CI imports the shared
PowerShell module and exercises verification-only failure, successful repair, failed
final verification, environment restoration, dry-run cleanup, exact direct-child
cleanup, unrelated data preservation, reparse-point escape prevention, the rollback
documentation contract, and previous-service restoration independent of browser
cleanup or legacy smoke verification, without Chrome or network access.

Target version: **0.5.1**

## Scope and invariants

This task hardens Windows maintenance around the existing Selenium/Chrome runtime.
Collector protocol 1.0, price extraction, constrained actions, and the public health
response are unchanged. Production WinSW continues to set `SE_OFFLINE=true`,
`SE_AVOID_STATS=true`, and `SE_AVOID_BROWSER_DOWNLOAD=true`. Application requests
therefore cannot ask Selenium Manager to download a driver.

`GET /health` remains browser-free and returns exactly `{"status":"ok"}`. Browser
compatibility is verified through the administrative runtime smoke because launching
Chrome from health would add latency, network-adjacent maintenance behavior, and a
public operational signal.

## Token-independent browser smoke

`app.browser.smoke` builds runtime settings with a smoke-specific environment prefix.
Inherited `KK_PRICEWATCH_API_TOKEN` and `KK_PRICEWATCH_API_TOKEN_FILE` values are
ignored without clearing or modifying them. The ordinary `Settings` construction path
still requires exactly one real application token source.

The smoke navigates only a deterministic `data:` document. PowerShell suppresses raw
Selenium Manager diagnostics and reports fixed maintenance results, preventing
machine-specific output or inherited authentication values from entering logs.

## Verification and explicit repair

`Repair-BrowserRuntime.ps1` accepts the repository, ProgramData, Chrome, and optional
virtual-environment Python paths. Its default verification mode runs `Offline` once
and never provisions. With `-Repair`, it still runs `Offline` first. Only an initial
failure permits `ProvisionDriver`, followed by a mandatory final `Offline` smoke.
Repair requires the installed Collector service to be stopped.

Every Selenium Manager process variable changed by the shared runtime module is
restored in a `finally` block. The production token variables are never changed.
Provisioning remains an elevated maintenance operation.

## Update behavior

`Update-Collector.ps1` requires the machine-wide Chrome path. Once the service is
stopped and target code installed, it cleans orphan profiles and runs offline browser
verification before service startup. Without `-RepairBrowserRuntime`, failure enters
the existing rollback path. With the switch, the updater may explicitly provision a
matching driver and must then pass offline verification.

Rollback reinstalls the recorded commit and package, repeats the narrowly scoped
profile cleanup, starts the previous service, and verifies `/health`. It deliberately
does not invoke browser verification from the previous checkout: a pre-existing
browser mismatch or legacy smoke implementation must not prevent restoration of
service availability. Profile-cleanup failure and possible browser degradation are
reported as warnings, while the original target update failure remains authoritative.
Rollback never provisions a driver, even when `-RepairBrowserRuntime` authorized
repair of the target.

## Orphan profile cleanup

Selenium sessions normally remove their temporary profiles. Crashes and reboots can
leave direct `chrome-*` directories below the configured browser data directory.
Cleanup runs during update while the service is stopped, or through the maintenance
command after confirming the installed service is stopped.

Only direct child directories matching `chrome-*` are candidates. Reparse points are
skipped. Cleanup does not recurse while discovering candidates, inspect profile
contents for paths, touch unrelated files or directories, touch `selenium-cache`, or
remove the browser data directory. `-CleanupWhatIf` reports candidates without
deleting them.

## CI coverage

Python tests cover inherited token sources, secret-free output, unchanged production
token validation, deployment assets, and version 0.5.1. Windows CI imports the shared
PowerShell module and exercises verification-only failure, successful repair, failed
final verification, environment restoration, dry-run cleanup, exact direct-child
cleanup, unrelated data preservation, reparse-point escape prevention, and service-first
update rollback. Regression coverage also locks the rollback documentation contract so
previous-service restoration remains independent of browser cleanup failures and legacy
browser smoke verification, without requiring Chrome or network access.
