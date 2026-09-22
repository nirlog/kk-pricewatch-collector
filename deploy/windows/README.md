# Windows production deployment

These scripts install the Collector and optional Caddy reverse proxy with
[WinSW](https://github.com/winsw/winsw). They never download WinSW, Caddy, Python, or
browser software. Run install/update/uninstall from an elevated PowerShell session.
`Get-CollectorStatus.ps1` does not require elevation.

## Layout and identities

The default runtime checkout is `C:\Services\kk-pricewatch-collector`. Persistent data
is separate:

```text
C:\ProgramData\KKPriceWatchCollector\
  logs\                 WinSW-managed stdout/stderr, rotated by size
  secrets\api-token.txt
  service\              supplied WinSW copy and generated XML
  browser\              reserved for a future task; not created by Task 002
```

The Collector runs as `NT AUTHORITY\LocalService`, binds only
`127.0.0.1:8000`, automatically starts, and restarts after failures. The secret file
inherits no ACLs: Administrators and SYSTEM have Full Control and LocalService has Read.
The generated service XML contains only the secret *path*, never its contents. Do not
open a firewall rule for port 8000.

## Install and verify

Clone an explicit release/tag/commit into the runtime path first. Supply a downloaded,
operator-verified WinSW executable:

```powershell
.\deploy\windows\Install-CollectorService.ps1 `
  -WinSWPath 'C:\Installers\WinSW-x64.exe' `
  -RepositoryPath 'C:\Services\kk-pricewatch-collector'
.\deploy\windows\Get-CollectorStatus.ps1
```

When migrating from a foreground Uvicorn process, stop it before running the installer.
Installation refuses to continue if any process is already listening on local TCP port
8000; it never terminates that process automatically. This prevents the old process's
health response from being mistaken for a successfully started Windows service.

If no protected token file already exists, installation prompts with
`Read-Host -AsSecureString`; the value is not displayed or passed on a command line.
Alternatively use `-ProtectedTokenFile` with an operator-created file. Re-running the
installer against an installed service fails safely and directs the operator to update.
Success is reported only after exact local `/health` verification.

## Update and automatic rollback

A target ref is mandatory; use an immutable tag or commit SHA:

```powershell
.\deploy\windows\Update-Collector.ps1 -Ref 'v0.2.0'
```

The updater refuses a dirty checkout, records the current SHA, stops the service,
fetches and checks out the requested ref in detached mode, installs into the existing
virtual environment, compiles/imports the app, restarts, and checks health. Failure
checks out and reinstalls the recorded SHA, restarts it, verifies health, and returns a
non-zero result describing whether rollback succeeded. It never uses `git reset
--hard` and never removes persistent data.

## Secret rotation

1. Update the Bitrix `kk.pricewatch` token through its normal secure configuration.
2. As Administrator, securely replace
   `C:\ProgramData\KKPriceWatchCollector\secrets\api-token.txt` without putting the
   value in command arguments (for example, prompt with `Read-Host -AsSecureString`
   and use the same in-memory write/ACL procedure as the installer).
3. Reapply the documented restricted ACL if the file was replaced rather than edited.
4. Restart: `Restart-Service KKPriceWatchCollector`, then run the status script.

Both systems must switch to the identical token in a coordinated maintenance window.
The repository does not automate Bitrix configuration.

## Uninstall

```powershell
.\deploy\windows\Uninstall-CollectorService.ps1
```

The checkout, token, and logs remain. `-PurgeData` requests destructive deletion of all
ProgramData and triggers PowerShell confirmation; it still does not delete the repo.

## Caddy / public HTTPS

DNS and inbound TCP 80/443 firewall rules are operator responsibilities. Keep the
Caddyfile deployment-specific, for example:

```caddyfile
collector.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Validate and install using operator-provided binaries/files:

Before installation, stop any existing foreground Caddy process and verify that it no
longer listens on the production ports selected by your Caddyfile. The installer does
not parse reusable Caddyfiles for ports and never kills an existing or unrelated
process automatically.

```powershell
.\deploy\windows\Install-CaddyService.ps1 `
  -CaddyPath 'C:\Tools\caddy.exe' `
  -CaddyfilePath 'C:\ProgramData\KKPriceWatchCaddy\Caddyfile' `
  -WinSWPath 'C:\Installers\WinSW-x64.exe'
```

The script runs `caddy validate` first. `KKPriceWatchCaddy` then starts automatically as
LocalService and restarts on failure. After a short startup grace period, installation
fails unless Windows reports the service as Running. Wrapper logs rotate separately under
`C:\ProgramData\KKPriceWatchCaddy\logs`; configure Caddy access logs separately if
required. Remove only the service with `Uninstall-CaddyService.ps1`.

No Selenium, Chrome, driver, Playwright, interactive desktop, or scraping dependency is
installed. A future task may create the reserved `browser` directory and grant narrowly
scoped access to the same service identity.
