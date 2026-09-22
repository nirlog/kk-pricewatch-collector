import tomllib
from pathlib import Path

WINDOWS_DEPLOYMENT = Path("deploy/windows")


def test_expected_windows_deployment_assets_exist() -> None:
    expected = {
        "Install-CollectorService.ps1",
        "Update-Collector.ps1",
        "Uninstall-CollectorService.ps1",
        "Get-CollectorStatus.ps1",
        "Install-CaddyService.ps1",
        "Uninstall-CaddyService.ps1",
        "CollectorRuntime.psm1",
        "Test-CollectorRuntime.ps1",
        "Test-BrowserRuntime.ps1",
        "templates/collector-service.xml",
        "templates/caddy-service.xml",
    }
    assert all((WINDOWS_DEPLOYMENT / relative).is_file() for relative in expected)


def test_scripts_have_strict_failure_settings() -> None:
    for script in WINDOWS_DEPLOYMENT.glob("*.ps1"):
        text = script.read_text(encoding="utf-8")
        assert "Set-StrictMode -Version Latest" in text
        assert "$ErrorActionPreference = 'Stop'" in text


def test_templates_contain_no_token_value_placeholder_or_public_uvicorn_bind() -> None:
    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WINDOWS_DEPLOYMENT / "templates").glob("*.xml")
    )
    assert "API_TOKEN_FILE" in templates
    assert "{{API_TOKEN}}" not in templates
    assert "0.0.0.0" not in templates
    assert "--host 127.0.0.1 --port 8000" in templates


def test_no_third_party_executables_are_committed() -> None:
    assert not list(WINDOWS_DEPLOYMENT.rglob("*.exe"))


def test_python_package_discovery_only_includes_application() -> None:
    configuration = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    discovery = configuration["tool"]["setuptools"]["packages"]["find"]
    assert discovery["include"] == ["app", "app.*"]
    assert discovery["exclude"] == [
        "deploy",
        "deploy.*",
        "docs",
        "docs.*",
        "tests",
        "tests.*",
    ]


def test_collector_installer_guards_port_and_cleans_up_failed_install() -> None:
    installer = (WINDOWS_DEPLOYMENT / "Install-CollectorService.ps1").read_text(encoding="utf-8")
    assert "Get-NetTCPConnection -LocalPort 8000 -State Listen" in installer
    assert "Port 8000 is already in use" in installer
    assert "$serviceRegistered = $true" in installer
    assert "& $serviceExe uninstall" in installer


def test_collector_installer_rejects_user_scoped_python_runtime() -> None:
    runtime = (WINDOWS_DEPLOYMENT / "CollectorRuntime.psm1").read_text(encoding="utf-8")
    assert "function Test-UserScopedPath" in runtime
    assert "Join-Path $env:SystemDrive 'Users'" in runtime
    assert "is user-scoped and cannot be used by LocalService" in runtime
    assert "provide its executable path with -Python" in runtime


def test_collector_installer_resolves_explicit_python_and_validates_existing_venv() -> None:
    installer = (WINDOWS_DEPLOYMENT / "Install-CollectorService.ps1").read_text(encoding="utf-8")
    runtime = (WINDOWS_DEPLOYMENT / "CollectorRuntime.psm1").read_text(encoding="utf-8")
    assert "[string] $Python = 'py'" in installer
    assert "Import-Module (Join-Path $PSScriptRoot 'CollectorRuntime.psm1')" in installer
    assert "sys.executable" in runtime
    assert "sys._base_executable" in runtime
    assert "json" not in runtime.lower()
    assert "function Get-VenvBaseExecutable" in runtime
    assert "Join-Path $VenvPath 'pyvenv.cfg'" in runtime
    assert "Existing virtual environment" in installer


def test_windows_ci_executes_shared_python_runtime_resolution() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    smoke = (WINDOWS_DEPLOYMENT / "Test-CollectorRuntime.ps1").read_text(encoding="utf-8")
    assert "Test-CollectorRuntime.ps1 -Python (Get-Command python).Source" in workflow
    assert "Import-Module (Join-Path $PSScriptRoot 'CollectorRuntime.psm1')" in smoke
    assert "Resolve-PythonRuntime -Command $Python" in smoke
    assert "missing-python.exe" in smoke


def test_collector_installer_recreates_only_venv_when_explicitly_requested() -> None:
    installer = (WINDOWS_DEPLOYMENT / "Install-CollectorService.ps1").read_text(encoding="utf-8")
    service_guard = installer.index("Get-Service -Name 'KKPriceWatchCollector'")
    removal = installer.index("Remove-Item -LiteralPath $venvPath -Recurse -Force")
    assert "[switch] $RecreateVenv" in installer
    assert "if ($RecreateVenv)" in installer
    assert service_guard < removal


def test_health_polling_sleeps_after_every_unsuccessful_attempt() -> None:
    for name in ("Install-CollectorService.ps1", "Update-Collector.ps1"):
        script = (WINDOWS_DEPLOYMENT / name).read_text(encoding="utf-8")
        catch_position = script.index("} catch {", script.index("Invoke-RestMethod"))
        sleep_position = script.index("Start-Sleep -Seconds 2", catch_position)
        loop_position = script.index("} while", catch_position)
        assert catch_position < sleep_position < loop_position


def test_caddy_install_verifies_running_service_state() -> None:
    installer = (WINDOWS_DEPLOYMENT / "Install-CaddyService.ps1").read_text(encoding="utf-8")
    assert "Get-Service -Name 'KKPriceWatchCaddy'" in installer
    assert "$runningService.Status -ne 'Running'" in installer


def test_browser_runtime_service_configuration_is_secure_and_explicit() -> None:
    installer = (WINDOWS_DEPLOYMENT / "Install-CollectorService.ps1").read_text(encoding="utf-8")
    template = (WINDOWS_DEPLOYMENT / "templates/collector-service.xml").read_text(encoding="utf-8")
    assert "[Parameter(Mandatory)] [string] $ChromeBinary" in installer
    assert "must not be installed under C:\\Users" in installer
    assert "'browser'" in installer
    assert "'selenium-cache'" in installer
    assert "*S-1-5-19:(OI)(CI)(M)" in installer
    assert "*S-1-5-19:(R)" in installer  # token remains read-only
    assert "NT AUTHORITY\\LocalService" in template
    assert "<startmode>Automatic</startmode>" in template
    assert 'name="KK_PRICEWATCH_BROWSER_PREFLIGHT" value="true"' in template
    assert 'name="SE_CACHE_PATH" value="{{SELENIUM_CACHE_DIR}}"' in template
    assert "{{API_TOKEN}}" not in template


def test_browser_smoke_delegates_to_production_python_runtime() -> None:
    smoke = (WINDOWS_DEPLOYMENT / "Test-BrowserRuntime.ps1").read_text(encoding="utf-8")
    assert "-m app.browser.smoke" in smoke
    assert "selenium.webdriver" not in smoke
